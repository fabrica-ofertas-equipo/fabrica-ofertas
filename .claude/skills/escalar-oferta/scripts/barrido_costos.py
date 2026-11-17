#!/usr/bin/env python3
"""Barrido de costos de producción: lee lo que de verdad se gastó en cada carpeta de trabajo y lo compara con el libro.

Por qué existe (17-nov): el libro carga ``produccion`` a mano (créditos de Kie sumados en la nota), las voces de Gemini
nunca tuvieron costo, las renovaciones se sumaban solo a veces y las ofertas que no salieron no aparecían en ningún lado.
Este script es la fuente: barre TODA la carpeta ``ofertas/`` y arma, por oferta del libro y por carpeta suelta:

* **Kie** (Nano Banana, Kling, Suno…): todos los ``gasto*.jsonl`` / ``gasto-*.jsonl`` / ``costos-borrador.jsonl``.
  Cuenta solo lo cobrado: líneas de resultado (``fase`` resultado, o sin ``fase``), nunca «enviado», «previo», «saldo»
  ni cotizaciones de ``costos-borrador`` (esas se informan aparte como «solo cotizado»). Si una tarea aparece varias
  veces (``task_id``/``task``), cuenta una. Se saltan las copias de la madre (``*copia*``): ya están en la madre.
* **Gemini imágenes** (gemini-3-pro-image): líneas con ``imagenes``.
* **Gemini voces (TTS)**: no hay registro de llamadas, así que se mide el audio: cada .wav de voz (``audio*/``,
  ``voces*/``, ``*-voz.wav``, tomas y descartes incluidos), sin repetir el mismo archivo copiado entre carpetas
  (huella sha1 del contenido; la copia la paga la primera carpeta que lo tuvo). Costo = segundos × precio por segundo.
* **Transcripción**: whisper-cli local (modelo large-v3-turbo en la Mac): costo 0, se informa para que conste.

Precios en el libro (``libro-de-tests.json``): ``precio_credito_kie_usd``, ``precio_imagen_gemini_usd`` y
``precio_tts_gemini_usd_por_min`` (si falta: 0,0192 = 32 tokens de audio por segundo a 10 USD el millón, tarifa de
Gemini Flash TTS; confirmar en AI Studio → Usage).

Uso:
  python3 .claude/skills/escalar-oferta/scripts/barrido_costos.py            # informe
  python3 .claude/skills/escalar-oferta/scripts/barrido_costos.py --json     # para el panel
  python3 .claude/skills/escalar-oferta/scripts/barrido_costos.py --aplicar  # escribe produccion.barrido en el libro

``--aplicar`` NO pisa la carga manual: guarda ``produccion.barrido`` (lo medido) y el panel usa, para cada rubro, el
mayor de los dos (lo manual trae cosas que el barrido no ve, como rondas cuyos registros se borraron; lo barrido trae
renovaciones y voces que nadie sumó). Las carpetas sin oferta en el libro van a ``produccion_sin_oferta`` (costo hundido
de la cartera: lo que se produjo y no salió).
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
import wave
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[4]
OFERTAS = RAIZ / "ofertas"
LIBRO = OFERTAS / "_funnels" / "libro-de-tests.json"
TTS_USD_MIN_DEFECTO = 0.0192
NO_COBRADO = {"enviado", "previo", "saldo", "cotizado", "error", "fallo", "falla", "pendiente"}
RX_GASTO = re.compile(r"^(gasto.*|costos-borrador)\.jsonl$")
RX_VOZ_DIR = re.compile(r"(^|/)(audio[^/]*|voces?[^/]*|voz[^/]*|tts[^/]*|locucion[^/]*)(/|$)", re.I)
# Registros que no sirven para sumar (se usa lo del libro): motivo al lado.
NO_CONFIABLES = {
    "_borrador-oferta-c/06-creativos/gasto-kie.jsonl":
        "midió la baja del saldo con varios avatares en paralelo: cada línea cuenta también los demás (suma 40 mil; el libro tiene 8.734)",
}
RX_NO_VOZ = re.compile(r"(musica|music|suno|sfx|efecto|referente|ref-|/ref/|clips?/|crudo|original|descarga)", re.I)


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _dia(linea: dict) -> str | None:
    for k in ("ts", "t", "fecha", "cuando"):
        v = linea.get(k)
        if isinstance(v, str) and len(v) >= 10:
            return v[:10]
    return None


def _creditos(linea: dict) -> float | None:
    for k in ("creditos", "cred", "credits", "creditos_reales", "costo_creditos"):
        n = _num(linea.get(k))
        if n is not None:
            return n
    return None


def leer_gasto(archivo: Path, firmas: set[str]) -> dict:
    """Devuelve {kie, kie_cotizado, gemini_img, por_dia{dia: kie}, lineas}."""
    lineas = []
    for crudo in archivo.read_text(encoding="utf-8", errors="replace").splitlines():
        crudo = crudo.strip()
        if not crudo:
            continue
        try:
            o = json.loads(crudo)
        except json.JSONDecodeError:
            continue
        if isinstance(o, dict):
            lineas.append(o)
    es_cotizacion = archivo.name == "costos-borrador.jsonl"
    hay_resultados = any(str(o.get("fase", "")).lower() == "resultado" for o in lineas)
    out = {"kie": 0.0, "kie_cotizado": 0.0, "gemini_img": 0.0, "por_dia": defaultdict(float), "lineas": 0, "duplicadas": 0}
    for o in lineas:
        imgs = _num(o.get("imagenes"))
        modelo = str(o.get("modelo", ""))
        if imgs is not None and "gemini" in modelo:
            out["gemini_img"] += imgs
            continue
        c = _creditos(o)
        if c is None:
            if es_cotizacion is False and _num(o.get("cotizado")) is not None and not hay_resultados and str(o.get("fase", "")).lower() not in NO_COBRADO:
                c = _num(o.get("cotizado"))
            else:
                continue
        if es_cotizacion:
            out["kie_cotizado"] += c
            continue
        fase = str(o.get("fase", o.get("estado", ""))).lower()
        if fase in NO_COBRADO and hay_resultados:
            continue
        if fase in ("enviado", "previo", "saldo"):
            continue
        # firma global: la misma tarea (o la misma línea copiada a otra carpeta de réplica) se cobra una sola vez
        tarea = o.get("task_id") or o.get("task") or o.get("taskId")
        firma = f"t:{tarea}" if tarea else "l:" + json.dumps(o, sort_keys=True, ensure_ascii=False)
        if firma in firmas:
            out["duplicadas"] += 1
            continue
        firmas.add(firma)
        out["kie"] += c
        out["lineas"] += 1
        d = _dia(o)
        if d:
            out["por_dia"][d] += c
    return out


def es_voz(p: Path, rel: str) -> bool:
    if p.suffix.lower() != ".wav":
        return False
    if RX_NO_VOZ.search(rel):
        return False
    return bool(RX_VOZ_DIR.search(rel)) or p.stem.endswith("-voz") or ".toma" in p.name


def segundos_wav(p: Path) -> float:
    try:
        with wave.open(str(p), "rb") as w:
            return w.getnframes() / float(w.getframerate() or 1)
    except Exception:  # noqa: BLE001 - wav raro: se ignora, no se inventa
        return 0.0


def barrer(carpetas: list[Path]) -> dict[str, dict]:
    res: dict[str, dict] = {}
    huellas: dict[str, str] = {}
    firmas: set[str] = set()
    voces, gastos = [], []
    for c in carpetas:
        res[c.name] = {"kie": 0.0, "kie_cotizado": 0.0, "gemini_img": 0.0, "tts_seg": 0.0, "tts_archivos": 0, "tts_copias": 0,
                       "archivos_gasto": 0, "duplicadas": 0, "ignorados": [], "por_dia": defaultdict(float), "por_etapa": defaultdict(float),
                       "desde": None, "hasta": None}
        for f in c.rglob("*.jsonl"):
            if RX_GASTO.match(f.name) and "copia" not in f.name:
                gastos.append((f.stat().st_mtime, len(c.name), c, f))
        for f in c.rglob("*.wav"):
            rel = str(f.relative_to(c))
            if es_voz(f, rel):
                voces.append((f.stat().st_mtime, c.name, f))
    for _, _, c, f in sorted(gastos, key=lambda x: (x[1], x[0])):   # la madre (nombre más corto: las réplicas le agregan -ie, -de…) paga; las copias no
            r = res[c.name]
            rel = f"{c.name}/{f.relative_to(c)}"
            if rel in NO_CONFIABLES:
                r["ignorados"].append({"archivo": rel, "motivo": NO_CONFIABLES[rel]})
                continue
            g = leer_gasto(f, firmas)
            r["duplicadas"] += g["duplicadas"]
            r["archivos_gasto"] += 1
            r["kie"] += g["kie"]
            r["kie_cotizado"] += g["kie_cotizado"]
            r["gemini_img"] += g["gemini_img"]
            etapa = f.relative_to(c).parts[0] if len(f.relative_to(c).parts) > 1 else "raíz"
            r["por_etapa"][etapa] += g["kie"]
            for d, v in g["por_dia"].items():
                r["por_dia"][d] += v
    for r in res.values():
        dias = sorted(r["por_dia"])
        r["desde"], r["hasta"] = (dias[0], dias[-1]) if dias else (None, None)
    for _, nombre, f in sorted(voces, key=lambda x: (len(x[1]), x[0])):   # la madre paga; las copias no
        h = hashlib.sha1(f.read_bytes()).hexdigest()
        if h in huellas:
            res[nombre]["tts_copias"] += 1
            continue
        huellas[h] = nombre
        res[nombre]["tts_seg"] += segundos_wav(f)
        res[nombre]["tts_archivos"] += 1
    return res


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--aplicar", action="store_true", help="escribe produccion.barrido en el libro")
    a = ap.parse_args()

    L = json.loads(LIBRO.read_text(encoding="utf-8"))
    pk = _num(L.get("precio_credito_kie_usd")) or 0.005
    pg = _num(L.get("precio_imagen_gemini_usd")) or 0.134
    ptts = _num(L.get("precio_tts_gemini_usd_por_min")) or TTS_USD_MIN_DEFECTO

    carpetas = sorted(p for p in OFERTAS.iterdir() if p.is_dir() and (p.name.startswith("_borrador-") or p.name.startswith("OF-")))
    medido = barrer(carpetas)

    por_carpeta_tests: dict[str, list[dict]] = defaultdict(list)
    for t in L.get("tests", []):
        ct = ((t.get("ficha") or {}).get("carpeta_trabajo") or "").strip().rstrip("/")
        if ct:
            por_carpeta_tests[Path(ct).name].append(t)

    filas, sin_oferta = [], []
    for nombre, r in medido.items():
        usd_kie, usd_img, usd_tts = r["kie"] * pk, r["gemini_img"] * pg, r["tts_seg"] / 60 * ptts
        base = {"carpeta": nombre, "kie_creditos": round(r["kie"]), "kie_usd": round(usd_kie, 2), "kie_solo_cotizado": round(r["kie_cotizado"]),
                "gemini_imagenes": round(r["gemini_img"]), "gemini_img_usd": round(usd_img, 2),
                "tts_minutos": round(r["tts_seg"] / 60, 1), "tts_archivos": r["tts_archivos"], "tts_copias_no_cobradas": r["tts_copias"],
                "tts_usd": round(usd_tts, 2), "transcripcion_usd": 0.0, "total_usd": round(usd_kie + usd_img + usd_tts, 2),
                "por_etapa_kie": {k: round(v) for k, v in sorted(r["por_etapa"].items())},
                "por_dia_kie": {k: round(v) for k, v in sorted(r["por_dia"].items())},
                "desde": r["desde"], "hasta": r["hasta"], "archivos_gasto": r["archivos_gasto"],
                "lineas_copiadas_no_cobradas": r["duplicadas"], "registros_ignorados": r["ignorados"]}
        tests = por_carpeta_tests.get(nombre)
        if not tests:
            if base["total_usd"] > 0:
                sin_oferta.append(base)
            continue
        t = tests[0]
        p = t.get("produccion") or {}
        man_kie, man_img = _num(p.get("kie_creditos")) or 0, _num(p.get("gemini_imagenes")) or 0
        base.update({"test": t["nombre"], "estado": t.get("estado"), "libro_kie_creditos": man_kie, "libro_gemini_imagenes": man_img,
                     "dif_kie_creditos": round(r["kie"] - man_kie), "libro_vacio": not t.get("produccion"),
                     "compartida_con": [x["nombre"] for x in tests[1:]]})
        filas.append(base)

    hoy = dt.date.today().isoformat()
    resumen = {
        "fecha": hoy, "precios": {"kie_credito_usd": pk, "gemini_imagen_usd": pg, "tts_usd_por_min": ptts},
        "ofertas": sorted(filas, key=lambda f: -f["total_usd"]), "sin_oferta": sorted(sin_oferta, key=lambda f: -f["total_usd"]),
        "totales": {
            "kie_creditos": sum(f["kie_creditos"] for f in filas + sin_oferta),
            "tts_minutos": round(sum(f["tts_minutos"] for f in filas + sin_oferta), 1),
            "total_usd": round(sum(f["total_usd"] for f in filas + sin_oferta), 2),
            "sin_oferta_usd": round(sum(f["total_usd"] for f in sin_oferta), 2),
            "libro_kie_creditos": sum(f["libro_kie_creditos"] for f in filas),
        },
        "transcripcion": "whisper-cli local (large-v3-turbo): sin costo por uso",
    }

    if a.aplicar:
        por_nombre = {f["test"]: f for f in filas}
        for t in L.get("tests", []):
            f = por_nombre.get(t["nombre"])
            if not f:
                continue
            p = t.get("produccion") or {"kie_creditos": 0, "gemini_imagenes": 0, "otros_usd": 0, "nota": "cargado por el barrido de costos"}
            ini = str(t.get("inicio") or "")[:10]
            despues = sum(v for d, v in f["por_dia_kie"].items() if ini and d >= ini)   # renovaciones y backend: lo producido desde el día de salida (la renovación sale en la mañana del mercado)
            p["barrido"] = {"fecha": hoy, "kie_creditos": f["kie_creditos"], "gemini_imagenes": f["gemini_imagenes"], "kie_despues_de_lanzar": round(despues),
                            "tts_minutos": f["tts_minutos"], "tts_usd": f["tts_usd"], "por_dia_kie": f["por_dia_kie"]}
            t["produccion"] = p
        L["produccion_sin_oferta"] = [{"carpeta": f["carpeta"], "kie_creditos": f["kie_creditos"], "gemini_imagenes": f["gemini_imagenes"],
                                       "tts_minutos": f["tts_minutos"], "total_usd": f["total_usd"], "fecha": hoy} for f in sin_oferta]
        L.setdefault("precio_tts_gemini_usd_por_min", ptts)
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import libro as _libro  # noqa: PLC0415 - mismo candado que libro.py (la vigilancia escribe el libro en paralelo)

        def _poner(L2: dict) -> None:
            por_n = {t["nombre"]: t for t in L.get("tests", [])}
            for t2 in L2.get("tests", []):
                if t2["nombre"] in por_n and por_n[t2["nombre"]].get("produccion"):
                    t2["produccion"] = por_n[t2["nombre"]]["produccion"]
            L2["produccion_sin_oferta"] = L["produccion_sin_oferta"]
            L2.setdefault("precio_tts_gemini_usd_por_min", ptts)
        _libro.modificar(_poner)

    if a.json:
        print(json.dumps(resumen, ensure_ascii=False, indent=1))
        return 0
    u = lambda x: f"US$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    print(f"Barrido de costos de producción · {hoy} · Kie {pk} USD/crédito · Gemini img {pg} · TTS {ptts} USD/min\n")
    print(f"{'Oferta':28} {'Kie barrido':>11} {'Kie libro':>10} {'dif':>7} {'img':>5} {'TTS min':>8} {'Total':>11}")
    for f in resumen["ofertas"]:
        marca = "  ← libro vacío" if f["libro_vacio"] else ("  ← falta en el libro" if f["dif_kie_creditos"] > 50 else "")
        print(f"{f['test'][:28]:28} {f['kie_creditos']:>11,} {f['libro_kie_creditos']:>10,.0f} {f['dif_kie_creditos']:>+7,} {f['gemini_imagenes']:>5} {f['tts_minutos']:>8} {u(f['total_usd']):>11}{marca}")
    if sin_oferta:
        print("\nProducido sin oferta en el libro (costo hundido):")
        for f in sin_oferta:
            print(f"  {f['carpeta']:40} Kie {f['kie_creditos']:>6,}  TTS {f['tts_minutos']:>5} min  {u(f['total_usd'])}")
    T = resumen["totales"]
    print(f"\nTotal barrido: {T['kie_creditos']:,} créditos Kie (libro: {T['libro_kie_creditos']:,.0f}), {T['tts_minutos']} min de voz · {u(T['total_usd'])}")
    print("Transcripción: " + resumen["transcripcion"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
