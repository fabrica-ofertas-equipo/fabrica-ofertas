"""Productor de alertas (B10 de ``docs/04`` §5): ``python -m scripts.alertas.producir`` (o ``python -m dashboard.alertas``).

Lee SOLO archivos locales (sin red, sin claves, sin ``.env``), calcula las alertas que no necesitan datos de ventas (``scripts.alertas.reglas``) y deja
``empresa/datos/alertas.jsonl`` conforme a ``contratos/alertas.schema.json``: una línea = el ESTADO VIGENTE de una alerta (``id`` único).

* **Por defecto no escribe nada** (``--simular``: solo muestra). Guardar exige ``--escribir`` (única escritura de todo este programa, atómica).
* **Idempotente:** repetir con el mismo estado del proyecto no agrega líneas ni cambia estados (salvo ``ts``, la hora de la última lectura).
  Lo que ya no se cumple pasa a ``cerrada``; una alerta ``reconocida`` que sigue viva sigue ``reconocida``; una cerrada que vuelve se reabre.
* **No pisa lo ajeno:** las líneas de otras reglas (las de F1 o las de ventas que escriba S-B) se conservan tal cual, byte a byte.
* **Fail-closed:** si el archivo existe pero no se puede leer entero o hay una línea propia que no cumple el esquema, NO escribe y lo dice (código 3).

Salida de la línea de comandos: 0 bien · 2 uso · 3 no se pudo leer/escribir con seguridad.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

from dashboard.api_base import Ctx
from dashboard.archivos import cargar_json_estricto, preparar_destino
from dashboard.seguridad import ErrorHttp
from scripts.alertas.ajenas import sanear_ajena
from scripts.alertas.hechos import REL_ALERTAS, leer_hechos, parsear_z
from scripts.alertas.reglas import REGLAS_PENDIENTES, REGLAS_PROPIAS, Alerta, calcular_alertas
from scripts.alertas.semaforo import calcular_semaforo

__all__ = ["COMANDO_ESCRIBIR", "ErrorArchivo", "ajenas_de", "es_nuestra", "estado_vigente", "fusionar", "leer_lineas", "main", "producir", "serializar"]

COMANDO_ESCRIBIR = ".venv/bin/python -m scripts.alertas.producir --escribir"
TOPE_ARCHIVO = 2 * 1024 * 1024
MAX_CERRADAS = 100              # retención: solo se guardan las últimas cerradas (el panel lee las últimas 200 líneas del archivo)
_ORDEN_GRAVEDAD = {"roja": 0, "naranja": 1, "amarilla": 2, "info": 3}
RAIZ_REPO = Path(__file__).resolve().parent.parent.parent


class ErrorArchivo(Exception):
    """El archivo de alertas existe pero no se puede tratar con seguridad (ilegible, demasiado grande, línea propia inválida)."""


# ----------------------------------------------------------------------------------------------
# Lectura del archivo actual
# ----------------------------------------------------------------------------------------------
def leer_lineas(ctx: Ctx) -> tuple[list[tuple[dict[str, Any] | None, str]], bool]:
    """``([(objeto|None, texto_crudo)], existe)``. Lanza ``ErrorArchivo`` si existe y no se puede leer entero con seguridad."""
    lec = ctx.raiz_confinada.texto(REL_ALERTAS, tope=TOPE_ARCHIVO)
    if lec.estado == "ausente":
        return [], False
    if not lec.ok:
        raise ErrorArchivo(lec.aviso or "No se pudo leer el archivo de alertas.")
    if lec.truncado:
        raise ErrorArchivo("El archivo de alertas es demasiado grande para tratarlo con seguridad.")
    salida: list[tuple[dict[str, Any] | None, str]] = []
    for cruda in str(lec.dato).split("\n"):
        if not cruda.strip():
            continue
        try:
            obj = cargar_json_estricto(cruda)
        except ValueError:
            obj = None
        salida.append((obj if isinstance(obj, dict) else None, cruda))
    return salida, True


def es_nuestra(obj: dict[str, Any] | None) -> bool:
    return bool(obj) and isinstance(obj.get("id"), str) and obj.get("regla_id") in REGLAS_PROPIAS and obj.get("origen") == "F2"


# ----------------------------------------------------------------------------------------------
# Fusión (estado vigente)
# ----------------------------------------------------------------------------------------------
def fusionar(previas: list[tuple[dict[str, Any] | None, str]], nuevas: list[Alerta], ahora: str) -> tuple[list[tuple[dict[str, Any], str | None]], list[str], list[str]]:
    """Estado vigente = alertas de hoy + las propias que se cerraron + lo ajeno intacto.

    Devuelve ``([(fila, texto_crudo|None)], ids_nuevas, ids_cerradas_ahora)``; ``texto_crudo`` solo para lo ajeno (se conserva byte a byte).
    """
    previas_propias = {o["id"]: o for o, _ in previas if es_nuestra(o)}
    vigentes: dict[str, dict[str, Any]] = {}
    for n in nuevas:
        fila = dict(n.fila)
        previa = previas_propias.get(fila["id"])
        if previa is not None and previa.get("estado") == "reconocida":
            fila["estado"] = "reconocida"                      # el dueño la reconoció y sigue viva
        vigentes[fila["id"]] = fila
    filas: list[tuple[dict[str, Any], str | None]] = []
    cerradas_ahora: list[str] = []
    vistos: set[str] = set()
    for obj, cruda in previas:
        if obj is None:
            filas.append(({"_basura": True}, cruda))           # línea ilegible: se conserva tal cual
            continue
        if isinstance(obj.get("id"), str):
            if obj["id"] in vistos:
                continue                                       # id repetido: una alerta = una línea; gana la primera
            vistos.add(obj["id"])
        if es_nuestra(obj):
            if obj["id"] in vigentes:
                continue                                       # la reemplaza la de hoy
            if obj.get("estado") != "cerrada":
                cerradas_ahora.append(obj["id"])
                obj = {**obj, "estado": "cerrada", "ts": ahora}
            filas.append((obj, None))
        else:
            filas.append((obj, cruda))                         # ajena (F1, ventas…): intacta
    ids_nuevas = [i for i in vigentes if i not in previas_propias or previas_propias[i].get("estado") == "cerrada"]
    for fila in vigentes.values():
        filas.append((fila, None))
    return filas, ids_nuevas, cerradas_ahora


def _ordenar(filas: list[tuple[dict[str, Any], str | None]]) -> list[tuple[dict[str, Any], str | None]]:
    """Orden estable: líneas ilegibles primero, después las cerradas (las más viejas antes; tope ``MAX_CERRADAS``) y al final las abiertas por regla e id."""
    basura = [f for f in filas if f[0].get("_basura")]
    sanas = [f for f in filas if not f[0].get("_basura")]
    cerradas = sorted((f for f in sanas if f[0].get("estado") == "cerrada"), key=lambda f: (str(f[0].get("ts") or ""), str(f[0].get("id"))))
    abiertas = sorted((f for f in sanas if f[0].get("estado") != "cerrada"), key=lambda f: (str(f[0].get("regla_id")), str(f[0].get("id"))))
    return basura + cerradas[-MAX_CERRADAS:] + abiertas


def serializar(filas: list[tuple[dict[str, Any], str | None]]) -> str:
    """JSONL: las líneas ajenas con su texto original; las propias en JSON compacto con el orden de claves del esquema, sin ``float``."""
    lineas: list[str] = []
    for fila, cruda in filas:
        if fila.get("_basura") or cruda is not None:
            lineas.append(cruda or "")
        else:
            lineas.append(json.dumps(fila, ensure_ascii=False, separators=(",", ":"), allow_nan=False))
    return "".join(f"{x}\n" for x in lineas)


# ----------------------------------------------------------------------------------------------
# Estado vigente (lo usa también el panel: GET /api/alertas) y producción
# ----------------------------------------------------------------------------------------------
def _problemas_esquema(filas: list[dict[str, Any]]) -> list[str]:
    try:
        from scripts.validar_esquemas import errores_de_esquema, problemas_alertas, problemas_artefacto  # import tardío: es un módulo grande
    except Exception:  # noqa: BLE001 - sin validador no se bloquea la lectura; las pruebas sí lo exigen
        return []
    malos: list[str] = []
    for f in filas:
        for e in errores_de_esquema("alertas", f):
            malos.append(f"{f.get('id')}: {str(e.message)[:120]}")
        for cod, msg in problemas_artefacto("alertas", f):
            malos.append(f"{f.get('id')}: {cod} {msg[:120]}")
    for cod, msg in problemas_alertas(filas):
        malos.append(f"{cod} {msg[:120]}")
    return malos


def ajenas_de(ev: dict[str, Any]) -> list[dict[str, Any]]:
    """Las líneas de otras reglas (F1, ventas y gasto de S-B) del estado vigente, SANEADAS (abiertas y cerradas). Las ilegibles o inválidas se omiten."""
    return [a for a in (sanear_ajena(fila) for fila, cruda in ev["filas"] if cruda is not None and not fila.get("_basura")) if a is not None]


def estado_vigente(ctx: Ctx, hechos: dict[str, Any] | None = None) -> dict[str, Any]:
    """Calcula (sin escribir) el estado vigente: ``{hechos, alertas (Alerta de hoy), filas, ids_nuevas, ids_cerradas, existe, archivo_ilegible, aviso}``."""
    h = hechos if hechos is not None else leer_hechos(ctx)
    nuevas = calcular_alertas(h)
    try:
        previas, existe = leer_lineas(ctx)
        ilegible = None
    except ErrorArchivo as exc:
        previas, existe, ilegible = [], True, str(exc)
    filas, ids_nuevas, ids_cerradas = fusionar(previas, nuevas, h["ahora"])
    return {"hechos": h, "alertas": nuevas, "filas": _ordenar(filas), "previas": previas, "ids_nuevas": ids_nuevas, "ids_cerradas": ids_cerradas,
            "existe": existe, "archivo_ilegible": ilegible}


def _escribir_atomico(ctx: Ctx, texto: str) -> None:
    destino = preparar_destino(ctx.raiz, REL_ALERTAS)
    fd, tmp = tempfile.mkstemp(prefix=".alertas.", suffix=".tmp", dir=str(destino.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(texto)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, destino)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def producir(ctx: Ctx, *, escribir: bool = False) -> dict[str, Any]:
    """Calcula y, solo con ``escribir=True``, guarda ``empresa/datos/alertas.jsonl``. Lanza ``ErrorArchivo`` si no se puede guardar con seguridad."""
    ev = estado_vigente(ctx)
    h = ev["hechos"]
    if ev["archivo_ilegible"]:
        if escribir:
            raise ErrorArchivo(ev["archivo_ilegible"])
    propias = [f for f, c in ev["filas"] if c is None and not f.get("_basura")]
    problemas = _problemas_esquema(propias)
    if problemas and escribir:
        raise ErrorArchivo("Una alerta propia no cumple el esquema; no se escribe nada: " + "; ".join(problemas[:3]))
    texto = serializar(ev["filas"])
    actual = ""
    if ev["existe"] and not ev["archivo_ilegible"]:
        lec = ctx.raiz_confinada.texto(REL_ALERTAS, tope=TOPE_ARCHIVO)
        actual = str(lec.dato) if lec.ok else ""
    sin_cambios = texto == actual
    if escribir and not sin_cambios:
        try:
            _escribir_atomico(ctx, texto)
        except (ErrorHttp, OSError) as exc:
            raise ErrorArchivo(f"No se pudo escribir {REL_ALERTAS}: {getattr(exc, 'mensaje', None) or type(exc).__name__}") from exc
    abiertas = [f for f, _ in ev["filas"] if f.get("estado") != "cerrada" and not f.get("_basura")]
    return {
        "ahora": h["ahora"], "modo": "escrito" if escribir else "simulado", "archivo": REL_ALERTAS, "sin_cambios": sin_cambios, "lineas": len(ev["filas"]),
        "abiertas": len(abiertas), "cerradas": len(ev["filas"]) - len(abiertas), "ids_nuevas": ev["ids_nuevas"], "ids_cerradas": ev["ids_cerradas"],
        "alertas": [{**a.fila, **a.extra} for a in ev["alertas"]], "reglas_pendientes": REGLAS_PENDIENTES, "problemas": problemas,
        "avisos": h["avisos"] + ([ev["archivo_ilegible"]] if ev["archivo_ilegible"] else []),
        "semaforo": calcular_semaforo(h, ajenas_de(ev)),
    }


# ----------------------------------------------------------------------------------------------
# Línea de comandos
# ----------------------------------------------------------------------------------------------
def _argumentos(argv: list[str] | None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(prog="python -m scripts.alertas.producir", description="Calcula las alertas desde los archivos del proyecto (solo lectura; --escribir guarda).")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--simular", action="store_true", help="solo muestra lo que pasaría; no escribe nada (es lo que hace por defecto)")
    g.add_argument("--escribir", action="store_true", help="guarda empresa/datos/alertas.jsonl (única escritura)")
    ap.add_argument("--raiz", default=None, help="raíz del proyecto (defecto: FABRICA_RAIZ o la carpeta de este código)")
    ap.add_argument("--ahora", default=None, help="instante fijo AAAA-MM-DDTHH:MM:SSZ (para pruebas y repetir un cálculo)")
    ap.add_argument("--json", action="store_true", help="salida en JSON")
    ap.add_argument("--semaforo", action="store_true", help="muestra también el semáforo «¿me puedo ausentar?»")
    return ap.parse_args(argv)


def _texto(res: dict[str, Any], con_semaforo: bool) -> str:
    rot = {"roja": "ROJA", "naranja": "NARANJA", "amarilla": "AMARILLA", "info": "INFO"}
    L = [f"Alertas de {res['ahora']} · {'GUARDADO en ' + res['archivo'] if res['modo'] == 'escrito' else 'SIMULACRO (no se escribió nada)'}",
         f"{res['abiertas']} abiertas · {res['cerradas']} cerradas · {'sin cambios' if res['sin_cambios'] else 'el archivo cambiaría' if res['modo'] == 'simulado' else 'archivo actualizado'}"]
    for a in sorted(res["alertas"], key=lambda a: (_ORDEN_GRAVEDAD.get(a["severidad"], 9), a["id"])):
        L.append(f"  [{rot.get(a['severidad'], a['severidad'])}] {a['id']} — {a['titulo']}\n      {a['accion_sugerida']}")
    if res["ids_cerradas"]:
        L.append("Se cerraron: " + ", ".join(res["ids_cerradas"]))
    L.append(f"Reglas que todavía no se calculan (faltan datos de ventas y gasto): {len(res['reglas_pendientes'])} (F2-A01…A15); ver REGLAS_PENDIENTES en scripts/alertas/reglas.py")
    for a in res["avisos"]:
        L.append(f"Aviso: {a}")
    if con_semaforo:
        s = res["semaforo"]
        L += ["", f"¿Me puedo ausentar? {s['nivel'].upper()} — {s['titulo']}", s["resumen"]]
        for p in s["pasos"]:
            L.append(f"  {p['paso']}. [{p['nivel'].upper()}] {p['titulo']} — {p['responsable_texto']}: {p['que_hacer']}")
    return "\n".join(L)


def main(argv: list[str] | None = None) -> int:
    args = _argumentos(argv)
    raiz = Path(args.raiz or os.environ.get("FABRICA_RAIZ") or RAIZ_REPO)
    if not raiz.is_dir():
        print("error: --raiz no es una carpeta", file=sys.stderr)
        return 2
    ahora = None
    if args.ahora:
        ahora = parsear_z(args.ahora)
        if ahora is None:
            print("error: --ahora debe verse así: 2026-11-07T08:30:00Z", file=sys.stderr)
            return 2
    ctx = Ctx(raiz, ahora=(lambda: ahora) if ahora else (lambda: _dt.datetime.now(_dt.timezone.utc)))
    try:
        res = producir(ctx, escribir=bool(args.escribir))
    except ErrorArchivo as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3
    print(json.dumps(res, ensure_ascii=False, indent=2) if args.json else _texto(res, args.semaforo))
    return 0


if __name__ == "__main__":
    sys.exit(main())
