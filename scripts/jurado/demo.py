#!/usr/bin/env python3
"""Corrida de DEMOSTRACIÓN del Jurado de creativos, sin LLM: votos sintéticos sobre las piezas del piloto.

Solo existe para mostrar el flujo de punta a punta (avatares → paquetes ciegos → votos → jurado.json → calibración vacía).
Todo lo que produce lleva ``demostracion: true`` y los votos llevan ``origen: sintetico_demo``; ``agregar.py`` rechaza esos
votos fuera de una demostración y ``calibrar.py`` rechaza un jurado de demostración fuera de ``--fixture``. Los votos NO
son la opinión de nadie: salen de una función determinista de la semilla (calidad latente por pieza + sesgo por avatar +
ruido), nunca de un modelo. Nada de lo que sale de aquí sirve para decidir un anuncio.

Piezas: los 11 ganchos candidatos de la oferta piloto OF-202611-91 (``datos/ganchos.jsonl`` de la skill d6-creativos, en polaco),
tratados como piezas de texto; las dos anclas son textos de control escritos para la demostración (``control_sintetico``).

Uso (desde la raíz, con .venv)::

    .venv/bin/python -m scripts.jurado.demo corrida --salida .claude/skills/jurado-creativos/evals/demostracion
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

from scripts.jurado import _comun as c
from scripts.jurado import agregar, avatares, calibrar, paquetes

OFERTA_PILOTO = "OF-202611-91"
VOZ_PILOTO = c.RAIZ / "ofertas" / OFERTA_PILOTO / "02-validacion" / "voz_cliente.json"
GANCHOS = c.RAIZ / ".claude" / "skills" / "d6-creativos" / "datos" / "ganchos.jsonl"
AHORA_DEMO = "2026-11-08T07:00:00Z"
SEMILLA_DEMO = "demo-OF-202611-91-2026-11-08"

#: Controles escritos a mano para la demostración (NO son resultados de mercado). Texto en polaco como el resto de las piezas.
ANCLAS_DEMO = [
    {"ancla_id": "ctrl-demo-buena", "veredicto_conocido": "ganadora", "origen_resultado": "control_sintetico", "tipo": "texto",
     "texto_visible": "Mapa myśli z angielskim słownictwem na Twoim poziomie. Zobacz bezpłatną próbkę.",
     "evidencia": {"nota": "Control escrito para la demostración: pieza clara y sin promesas. No es un resultado de mercado."}},
    {"ancla_id": "ctrl-demo-mala", "veredicto_conocido": "perdedora", "origen_resultado": "control_sintetico", "tipo": "texto",
     "texto_visible": "KUP TERAZ!!! Najlepszy kurs na świecie. Zero wysiłku, 100% pewności.",
     "evidencia": {"nota": "Control escrito para la demostración: pieza deliberadamente defectuosa. No es un resultado de mercado."}},
]
CALIDAD_ANCLA = {"ganadora": 0.85, "perdedora": 0.12}


def piezas_del_piloto() -> list[dict]:
    """Los ganchos candidatos de la oferta piloto como piezas de texto (con un ad_name que SÍ delataría formato y versión)."""
    piezas = []
    for g in c.leer_jsonl(GANCHOS):
        if g.get("oferta_id") == OFERTA_PILOTO and g.get("rol") == "candidato" and g.get("locale") == "pl-PL":
            codigo = g["id"].lower().replace("-", "")
            piezas.append({"ad_name": f"{codigo}-{g['angulo']}_img_h1_v1", "tipo": "texto", "texto_visible": g["texto"], "id_origen": g["id"]})
    return piezas


def _unidad(*partes: Any) -> float:
    return int(c.hash_corto(*partes, largo=8), 16) / 0xFFFFFFFF


def votos_sinteticos(tanda_dir: Path, calidad: Mapping[str, float] | None = None, ruido: float = 0.2, sesgo: float = 0.15) -> int:
    """Escribe un voto sintético por llamada en ``votos/``. ``calidad`` fija la calidad latente por ad_name/ancla_id (0-1)."""
    man = c.leer_json(tanda_dir / "privado" / "manifiesto.json")
    llave = c.leer_json(tanda_dir / "privado" / "llave.json")
    c.exigir(man.get("demostracion"), "los votos sintéticos solo se generan para una tanda armada con --demo")
    destino = tanda_dir / "votos"
    if destino.exists():
        shutil.rmtree(destino)
    destino.mkdir(parents=True)
    n = 0
    for o in man["orden_llamadas"]:
        pid = o["pieza_id"]
        if pid in llave["piezas"]:
            nombre = llave["piezas"][pid]["ad_name"]
            q = (calidad or {}).get(nombre, _unidad(man["semilla_entero"], "calidad", nombre))
        else:
            info = llave["anclas"][pid]
            q = (calidad or {}).get(info["ancla_id"], CALIDAD_ANCLA[info["veredicto_conocido"]])
        es_base = o["avatar_id"] == man.get("avatar_baseline")
        b = 0.0 if es_base else (_unidad(man["semilla_entero"], "sesgo", o["avatar_id"]) - 0.5) * 2 * sesgo
        r = (_unidad(man["semilla_entero"], "ruido", o["paquete_id"]) - 0.5) * 2 * ruido
        s = min(1.0, max(0.0, q + b + r))
        general = round(10 * s)
        voto = {
            "paquete_id": o["paquete_id"], "avatar_id": o["avatar_id"], "pieza_id": pid, "voto": s > 0.5,
            "motivo": "Voto sintético de demostración: lo genera una función, no un modelo.",
            "puntaje_gancho": min(10, max(0, general + (1 if r > 0 else -1))), "puntaje_claridad": general, "puntaje_cta": None,
            "puntaje_general": general, "idea": None, "alerta_ceguera": None, "origen": "sintetico_demo",
        }
        c.escribir_json(destino / f"{Path(o['archivo']).stem}.json", voto)
        n += 1
    return n


def corrida(salida: Path, ahora: str = AHORA_DEMO) -> dict:
    """Flujo completo de demostración. Devuelve un resumen. Reescribe ``salida`` entera."""
    if salida.exists():
        shutil.rmtree(salida)
    tanda = salida / "tanda-2026-11-08_pl-PL"
    (tanda / "entrada").mkdir(parents=True)
    voz = c.leer_json(VOZ_PILOTO)
    panel = avatares.generar_panel(voz, c.sha256_archivo(VOZ_PILOTO), "ofertas/OF-202611-91/02-validacion/voz_cliente.json", 10, SEMILLA_DEMO,
                                   incluir_baseline=True, oferta_id=OFERTA_PILOTO, ahora=ahora)
    panel["demostracion"] = True
    c.exigir(not avatares.validar_panel(panel, voz), "panel de demostración inválido")
    c.escribir_json(salida / "avatares.json", panel)
    c.agregar_jsonl(salida / "registro_avatares.jsonl", {"evento": "generado", "ts": ahora, "demostracion": True, "avatares": [a["avatar_id"] for a in panel["avatares"]]})
    piezas = {"oferta_id": OFERTA_PILOTO, "locale": "pl-PL", "tanda_id": "tanda-2026-11-08_pl-PL", "demostracion": True, "piezas": piezas_del_piloto()}
    anclas = {"locale": "pl-PL", "demostracion": True, "anclas": ANCLAS_DEMO}
    c.escribir_json(tanda / "entrada" / "piezas.json", piezas)
    c.escribir_json(tanda / "entrada" / "anclas.json", anclas)
    man = paquetes.armar(panel, piezas, anclas, SEMILLA_DEMO, tanda, demo=True, tanda_id=piezas["tanda_id"], ahora=ahora,
                         entradas_sha={"avatares_sha256": c.sha256_archivo(salida / "avatares.json"), "piezas_sha256": c.sha256_archivo(tanda / "entrada" / "piezas.json"),
                                       "anclas_sha256": c.sha256_archivo(tanda / "entrada" / "anclas.json")})
    n_votos = votos_sinteticos(tanda)
    llave = c.leer_json(tanda / "privado" / "llave.json")
    votos = agregar.leer_votos_dir(tanda / "votos")
    doc = agregar.agregar(man, llave, panel, votos, ahora=ahora)
    c.escribir_json(tanda / "jurado.json", doc)
    l1 = agregar.verificar(doc, man, llave)
    c.escribir_json(tanda / "privado" / "l1.json", l1)
    # Calibración sin etiquetas: muestra que hoy el jurado está en «acumulando» y que no inventa precisión.
    cal = calibrar.calibrar([{**doc, "_archivo": "tanda-2026-11-08_pl-PL/jurado.json"}], [], fixture=True, ahora=ahora)
    c.escribir_json(salida / "calibracion-vacia.json", cal)
    calibrar.fusionar_precision(str(tanda / "jurado.json"), cal, str(salida / "calibracion-vacia.json"), "../calibracion-vacia.json")
    (salida / "LEEME-DEMOSTRACION.md").write_text(
        "# DEMOSTRACIÓN — no es una opinión de nadie\n\n"
        "Esta carpeta muestra el flujo del Jurado de creativos con **votos sintéticos** generados por una función determinista "
        "(`scripts/jurado/demo.py`), sin ningún LLM. Las piezas son los 11 ganchos candidatos de la oferta piloto OF-202611-91 y dos "
        "controles escritos a mano. **Nada de aquí sirve para decidir un anuncio**: todos los archivos llevan `demostracion: true` y los votos "
        "`origen: sintetico_demo`; `agregar.py` y `calibrar.py` los rechazan fuera de una demostración.\n\n"
        "Qué mirar: `avatares.json` (10 avatares con sus citas y su límite de N), `tanda-*/ciego/` (lo que vería un votante: una pieza por "
        "paquete, ids opacos), `tanda-*/privado/` (manifiesto con la semilla y el orden, llave, informes de ceguera y L1), `tanda-*/votos/` "
        "y `tanda-*/jurado.json` (ranking, bandas, acuerdo, anclas). `calibracion-vacia.json` muestra que hoy hay 0 de 150 etiquetas: "
        "no se mide ningún acierto.\n\nReproducir: `.venv/bin/python -m scripts.jurado.demo corrida --salida "
        ".claude/skills/jurado-creativos/evals/demostracion`.\n", encoding="utf-8")
    return {"avatares": len(panel["avatares"]), "piezas": len(piezas["piezas"]), "anclas": len(ANCLAS_DEMO), "llamadas": man["n_llamadas"], "votos": n_votos,
            "ordenadas": len(doc["orden"]), "l1_ok": l1["ok"], "estado_calibracion": cal["estado_global"], "salida": str(salida)}


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m scripts.jurado.demo", description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("corrida", help="corre la demostración completa")
    r.add_argument("--salida", required=True)
    args = p.parse_args(argv)
    try:
        res = corrida(Path(args.salida))
    except c.ErrorJurado as e:
        print(f"error: {e}", file=sys.stderr)
        return c.SALIDA_RECHAZO
    print("DEMOSTRACIÓN (votos sintéticos, sin LLM):", res)
    return c.SALIDA_OK if res["l1_ok"] else c.SALIDA_RECHAZO


if __name__ == "__main__":
    sys.exit(main())
