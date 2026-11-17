#!/usr/bin/env python3
"""Lanza «hijos» de Claude (`claude -p`) con candados TÉCNICOS, en paralelo y con tope de costo.

Por qué existe: las sesiones de construcción tienen conectores con escritura viva (Meta, Shopify, Higgsfield,
Drive). Un subagente normal los hereda; pedirle «no los uses» es una promesa, no una barrera. Un hijo lanzado por
este script NO TIENE esas herramientas: arranca con `--strict-mcp-config`, `--disallowedTools "mcp__*"`,
`--settings {"disableClaudeAiConnectors": true}` y una lista blanca de herramientas integradas. Además:
  - modo `dontAsk`: lo que no está permitido explícitamente se deniega (no hay a quién preguntar);
  - solo puede LEER dentro del proyecto y ESCRIBIR en las rutas `editar` de su trabajo;
  - Bash acotado (Python del .venv, node, mkdir, ls, chmod); sin curl ni comandos arbitrarios;
  - al arrancar se verifica el evento `system/init`: si aparece cualquier `mcp__*` o un servidor MCP, se mata al hijo;
  - tope de USD y de turnos por hijo, y tope total de la corrida (no se lanzan más hijos al alcanzarlo).
Límite honesto: `Bash(.venv/bin/python:*)` permite ejecutar código Python arbitrario; este script elimina el riesgo de
los conectores, NO es un sandbox total. Por eso los prompts siguen prohibiendo red, git y claves.

Uso (desde la raíz del repositorio):
    python3 -m scripts.lanzar_hijos CONFIG.json --salida CARPETA_NUEVA [--concurrentes 4] [--tope-total-usd 120]
CONFIG.json:
    {"preambulo": "texto común (opcional)",
     "trabajos": [{"id": "B2", "prompt": "...", "editar": ["tracking/workers/**"], "bash": ["node:*"],
                   "max_usd": 15, "max_turnos": 150, "max_minutos": 90, "depende_de": ["B1n"]}]}
Códigos de salida: 0 todo bien · 2 uso · 3 configuración inválida · 6 algún hijo falló o fue omitido.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Mapping, Sequence

HERRAMIENTAS = "Read,Write,Edit,Glob,Grep,Bash"
BASH_BASE = ("Bash(.venv/bin/python:*)", "Bash(node:*)", "Bash(mkdir:*)", "Bash(ls:*)", "Bash(chmod:*)")
CONFIG_SIN_CONECTORES = {"disableClaudeAiConnectors": True}


class ErrorConfig(Exception):
    """Configuración de trabajos inválida (código 3)."""


def raiz_repositorio() -> Path:
    return Path(__file__).resolve().parents[1]


def reglas_permitidas(raiz: Path, trabajo: Mapping[str, Any]) -> list[str]:
    """Reglas `--allowedTools` de un trabajo: lectura solo del proyecto, escritura solo en `editar`."""
    base = f"/{raiz}/**"
    reglas = [f"Read({base})", f"Glob({base})", f"Grep({base})"]
    reglas += [f"Edit({ruta})" for ruta in trabajo.get("editar", [])]
    reglas += list(BASH_BASE)
    reglas += [f"Bash({patron})" for patron in trabajo.get("bash", [])]
    return reglas


def construir_comando(raiz: Path, trabajo: Mapping[str, Any]) -> list[str]:
    """Línea de comando completa del hijo. El prompt va por stdin (sin límite de argumentos)."""
    return [
        "claude", "-p", "--output-format", "stream-json", "--verbose",
        "--tools", HERRAMIENTAS,
        "--strict-mcp-config", "--disallowedTools", "mcp__*",
        "--settings", json.dumps(CONFIG_SIN_CONECTORES),
        "--permission-mode", "dontAsk", "--no-session-persistence",
        "--max-budget-usd", str(trabajo.get("max_usd", 10)),
        "--max-turns", str(trabajo.get("max_turnos", 100)),
        "--allowedTools", *reglas_permitidas(raiz, trabajo),
    ]


def violacion_en_init(evento: Mapping[str, Any]) -> str | None:
    """Motivo si el evento `system/init` muestra conectores; None si el hijo está limpio."""
    herramientas = [str(t) for t in evento.get("tools", [])]
    malas = [t for t in herramientas if t.startswith("mcp__")]
    if malas:
        return f"el hijo tiene herramientas MCP: {malas[:5]}"
    if evento.get("mcp_servers"):
        return f"el hijo tiene servidores MCP: {evento.get('mcp_servers')}"
    return None


def extraer_json(texto: str) -> Any:
    """Primer objeto JSON razonable de un texto (el informe final del hijo), o None."""
    if not texto:
        return None
    ini, fin = texto.find("{"), texto.rfind("}")
    if ini < 0 or fin <= ini:
        return None
    try:
        return json.loads(texto[ini:fin + 1])
    except json.JSONDecodeError:
        return None


def validar_config(config: Any) -> list[dict[str, Any]]:
    """Valida la configuración y devuelve los trabajos con el preámbulo ya antepuesto."""
    if not isinstance(config, dict) or not isinstance(config.get("trabajos"), list) or not config["trabajos"]:
        raise ErrorConfig("la configuración necesita una lista no vacía «trabajos»")
    ids: set[str] = set()
    salida = []
    for i, t in enumerate(config["trabajos"]):
        if not isinstance(t, dict) or not t.get("id") or not (t.get("prompt") or t.get("prompt_archivo")):
            raise ErrorConfig(f"trabajos[{i}]: faltan «id» o «prompt»")
        if t["id"] in ids:
            raise ErrorConfig(f"trabajos[{i}]: id repetido {t['id']!r}")
        ids.add(t["id"])
        for ruta in t.get("editar", []):
            if ruta.startswith("/") or ".." in Path(ruta).parts or ruta in ("**", "*"):
                raise ErrorConfig(f"trabajos[{i}].editar: ruta no permitida {ruta!r} (relativa al proyecto, sin «..»)")
        texto = t.get("prompt") or Path(t["prompt_archivo"]).read_text(encoding="utf-8")
        salida.append({**t, "prompt_completo": (config.get("preambulo", "") + "\n\n" + texto).strip()})
    for t in salida:
        for d in t.get("depende_de", []):
            if d not in ids:
                raise ErrorConfig(f"{t['id']}: depende de un id inexistente {d!r}")
    return salida


class Corrida:
    """Estado compartido de una corrida: costos, resultados y bloqueo de lanzamiento."""

    def __init__(self, tope_total_usd: float) -> None:
        self.tope = tope_total_usd
        self.gastado = 0.0
        self.resultados: dict[str, dict[str, Any]] = {}
        self.cerrojo = threading.Lock()

    def agotada(self) -> bool:
        with self.cerrojo:
            return self.gastado >= self.tope

    def anotar(self, id_: str, resultado: dict[str, Any]) -> None:
        with self.cerrojo:
            self.gastado += float(resultado.get("costo_usd") or 0)
            self.resultados[id_] = resultado


def ejecutar_hijo(raiz: Path, trabajo: Mapping[str, Any], salida: Path) -> dict[str, Any]:
    """Corre un hijo, vigila su arranque y devuelve su resultado. Nunca lanza: todo error queda en el resultado."""
    t0 = time.time()
    id_ = trabajo["id"]
    registro = salida / f"{id_}.jsonl"
    resultado: dict[str, Any] = {"id": id_, "estado": "error", "costo_usd": 0.0, "turnos": 0, "informe": None, "texto": ""}
    try:
        proc = subprocess.Popen(construir_comando(raiz, trabajo), cwd=raiz, stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except OSError as exc:
        resultado["texto"] = f"no se pudo lanzar claude: {exc}"
        return resultado
    errores: list[str] = []
    hilo_err = threading.Thread(target=lambda: errores.append(proc.stderr.read()), daemon=True)
    hilo_err.start()
    limite = t0 + 60 * float(trabajo.get("max_minutos", 90))
    try:
        proc.stdin.write(trabajo["prompt_completo"])
        proc.stdin.close()
        with open(registro, "w", encoding="utf-8") as f:
            for linea in proc.stdout:
                f.write(linea)
                try:
                    ev = json.loads(linea)
                except json.JSONDecodeError:
                    continue
                if ev.get("type") == "system" and ev.get("subtype") == "init":
                    motivo = violacion_en_init(ev)
                    if motivo:
                        proc.kill()
                        resultado.update(estado="VIOLACION_MCP", texto=motivo)
                        return resultado
                if ev.get("type") == "result":
                    resultado.update(estado="error" if ev.get("is_error") else "ok", costo_usd=ev.get("total_cost_usd") or 0.0,
                                     turnos=ev.get("num_turns") or 0, texto=str(ev.get("result") or ""))
                if time.time() > limite:
                    proc.kill()
                    resultado.update(estado="TIEMPO_AGOTADO")
                    break
        proc.wait(timeout=30)
    except Exception as exc:  # el hijo no debe tumbar la corrida
        resultado["texto"] = f"{type(exc).__name__}: {exc}"
        proc.kill()
    resultado["informe"] = extraer_json(resultado["texto"])
    resultado["segundos"] = round(time.time() - t0)
    if errores and not resultado["texto"]:
        resultado["texto"] = errores[0][:500]
    return resultado


MARCAS_TRANSITORIAS = ("api error", "connection closed", "overloaded", "rate limit", "econnreset", "timed out",
                       "502", "503", "529", "internal server error",
                       "not logged in", "please run /login")   # la sesión compartida se cae si varios hijos renuevan el token a la vez
NOTA_REANUDACION = ("\n\nNOTA DE REANUDACIÓN: la ejecución anterior de este trabajo se cortó por un fallo transitorio "
                    "(red, API o sesión). Puede haber archivos tuyos a medio hacer en tus carpetas: léelos primero, "
                    "conserva lo que esté bien y continúa desde ahí; no empieces de cero.")


def es_transitorio(resultado: Mapping[str, Any]) -> bool:
    """¿Fue un fallo pasajero (red, API o sesión caída) que se puede reintentar? Una violación de MCP, un tope de
    turnos o un permiso denegado NUNCA lo son."""
    if resultado.get("estado") != "error":
        return False
    texto = str(resultado.get("texto") or "").lower()
    return any(marca in texto for marca in MARCAS_TRANSITORIAS)


def ejecutar_con_reintentos(raiz: Path, trabajo: Mapping[str, Any], salida: Path) -> dict[str, Any]:
    """Como `ejecutar_hijo`, pero reintenta fallos pasajeros con espera creciente (`reintentos`, 2 por defecto)."""
    maximo = int(trabajo.get("reintentos", 2))
    gastado = 0.0
    for intento in range(maximo + 1):
        resultado = ejecutar_hijo(raiz, trabajo, salida)
        gastado += float(resultado.get("costo_usd") or 0)
        resultado["intentos"] = intento + 1
        if resultado["estado"] == "ok" or not es_transitorio(resultado) or intento == maximo:
            break
        time.sleep(60 * (intento + 1))
        trabajo = {**trabajo, "prompt_completo": str(trabajo.get("prompt_completo", "")).split(NOTA_REANUDACION)[0] + NOTA_REANUDACION}
    resultado["costo_usd"] = gastado
    return resultado


def correr(raiz: Path, trabajos: Sequence[Mapping[str, Any]], salida: Path, concurrentes: int,
           tope_total_usd: float, escalonar_seg: float = 0.0) -> dict[str, Any]:
    """Ejecuta todos los trabajos respetando dependencias, concurrencia y tope total. Devuelve el resumen."""
    corrida = Corrida(tope_total_usd)
    pendientes = {t["id"]: t for t in trabajos}
    hechos: dict[str, str] = {}
    lanzados: dict[str, Any] = {}
    with ThreadPoolExecutor(max_workers=concurrentes) as pool:
        while pendientes or lanzados:
            for id_, fut in list(lanzados.items()):
                if fut.done():
                    r = fut.result()
                    corrida.anotar(id_, r)
                    (salida / f"{id_}.json").write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
                    with open(salida / "costos.jsonl", "a", encoding="utf-8") as f:
                        f.write(json.dumps({"id": id_, "estado": r["estado"], "costo_usd": r["costo_usd"],
                                            "acumulado_usd": round(corrida.gastado, 4)}, ensure_ascii=False) + "\n")
                    hechos[id_] = r["estado"]
                    del lanzados[id_]
            for id_, t in list(pendientes.items()):
                deps = t.get("depende_de", [])
                if any(d in hechos and hechos[d] != "ok" for d in deps):
                    corrida.resultados[id_] = {"id": id_, "estado": "OMITIDO_DEPENDENCIA", "costo_usd": 0.0}
                    hechos[id_] = "OMITIDO_DEPENDENCIA"
                    del pendientes[id_]
                elif corrida.agotada():
                    corrida.resultados[id_] = {"id": id_, "estado": "OMITIDO_TOPE_TOTAL", "costo_usd": 0.0}
                    hechos[id_] = "OMITIDO_TOPE_TOTAL"
                    del pendientes[id_]
                elif all(hechos.get(d) == "ok" for d in deps) and len(lanzados) < concurrentes:
                    if lanzados or hechos:
                        time.sleep(escalonar_seg)        # arranques escalonados: no renovar la sesión todos a la vez
                    lanzados[id_] = pool.submit(ejecutar_con_reintentos, raiz, t, salida)
                    del pendientes[id_]
            time.sleep(1)
    resumen = {"gastado_usd": round(corrida.gastado, 4), "tope_total_usd": tope_total_usd,
               "resultados": {k: {x: v[x] for x in ("estado", "costo_usd", "turnos") if x in v}
                              for k, v in corrida.resultados.items()}}
    (salida / "resumen.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8")
    return resumen


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python3 -m scripts.lanzar_hijos", description=__doc__.split("\n")[0])
    parser.add_argument("config", type=Path)
    parser.add_argument("--salida", type=Path, required=True, help="carpeta NUEVA para registros y resultados")
    parser.add_argument("--concurrentes", type=int, default=4)
    parser.add_argument("--tope-total-usd", type=float, default=100.0)
    parser.add_argument("--escalonar-seg", type=float, default=45.0, help="espera entre el arranque de un hijo y el siguiente")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)
    if args.salida.exists():
        print(f"ERROR: {args.salida} ya existe; use una carpeta nueva", file=sys.stderr)
        return 2
    try:
        trabajos = validar_config(json.loads(args.config.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError, ErrorConfig) as exc:
        print(f"ERROR de configuración: {exc}", file=sys.stderr)
        return 3
    args.salida.mkdir(parents=True)
    resumen = correr(raiz_repositorio(), trabajos, args.salida, max(1, args.concurrentes), args.tope_total_usd,
                     args.escalonar_seg)
    print(json.dumps(resumen, ensure_ascii=False, indent=2))
    return 0 if all(r["estado"] == "ok" for r in resumen["resultados"].values()) else 6


if __name__ == "__main__":
    raise SystemExit(main())
