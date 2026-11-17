"""Finales de las ranuras de imagen: 2048 px -> medida y peso de cada ranura (webp/jpg) + manifiesto final + propuesta para assets.json.

Qué hace
--------
Para cada ranura del plan toma el candidato elegido (``seleccion_maker``), lo reduce con Lanczos (``ffmpeg``; el texto queda nítido) a la medida
final y lo codifica en ``final/<slot>.webp`` (``cwebp``, calidad descendente hasta entrar en el peso máximo de la ranura) o ``final/<slot>.jpg``.
Escribe ``final/manifiesto-final.json`` con, por ranura: archivo, sha256, medida, peso, modelo, créditos (todas las rondas), intentos por ronda,
``ilustrativa``, ``reemplazar_con_real_cuando_exista_producto``, ``etiqueta_ia_visible``, candidato de origen y si lo aprobó la revisión
independiente de la ronda indicada; y una **propuesta** de cambios a ``assets.json`` (no lo edita).

Las medidas salen de ``assets.json`` (solo lectura) cuando la ranura existe allí; para ranuras nuevas (``portada-pack``, ``bump``) y para el ``og``
(1200x630, la medida de Open Graph que pidió el encargo, frente a 1200x675 de ``assets.json``; formato y peso sí salen de ``assets.json``) valen las del plan.

Uso::

    python3 scripts/imagenes/finales_ranuras.py PLAN --assets DIR [--assets-json assets.json] [--revision revision-ronda1.json --revision revision-ronda2.json] [--solo a,b]

Salidas: 0 ok · 2 uso o falta de candidato elegido · 6 falló una herramienta externa (ffmpeg/cwebp).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable

CALIDADES_WEBP = (90, 86, 82, 78, 74, 70, 66, 62, 58, 54, 50)
CALIDADES_JPG = (2, 3, 4, 5, 6, 8, 10, 12)               # -q:v de ffmpeg (menor = mejor)
HERRAMIENTA = "Kie (gpt-image-2, nano-banana-pro) + Chrome"


def sha256_archivo(ruta: Path) -> str:
    h = hashlib.sha256()
    with Path(ruta).open("rb") as fh:
        for trozo in iter(lambda: fh.read(1 << 20), b""):
            h.update(trozo)
    return h.hexdigest()


def medidas(plan_slot: dict, assets_json: dict | None) -> dict:
    """Ancho, alto, formato y peso máximo de la ranura: ``assets.json`` manda salvo en el og (medida del encargo) y en ranuras nuevas."""
    req = dict(plan_slot.get("dimensiones_requeridas") or {})
    base = {"ancho": req.get("ancho"), "alto": req.get("alto"), "formato": req.get("formato_final", "webp"), "peso_max_kb": req.get("peso_max_kb"), "origen_medida": "plan"}
    if assets_json and plan_slot.get("asset_slot"):
        for s in assets_json.get("slots", []):
            if s.get("slot_id") == plan_slot["asset_slot"] and s.get("ancho_px"):
                if plan_slot["slot_id"] == "og":          # el og conserva la medida del encargo (1200x630) pero respeta formato y peso de assets.json
                    base.update(formato=s["formato"], peso_max_kb=s["peso_max_kb"], origen_medida="plan (1200x630); formato y peso de assets.json")
                else:
                    base.update(ancho=s["ancho_px"], alto=s["alto_px"], formato=s["formato"], peso_max_kb=s["peso_max_kb"], origen_medida="assets.json")
    return base


def convertir(origen: Path, destino: Path, ancho: int, alto: int, formato: str, peso_max_kb: int | None) -> dict:
    """Reduce con Lanczos y codifica probando calidades de mayor a menor hasta entrar en el peso. Devuelve calidad y peso."""
    ff = shutil.which("ffmpeg")
    if not ff:
        raise RuntimeError("falta ffmpeg")
    destino.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td) / "x.png"
        r = subprocess.run([ff, "-v", "error", "-y", "-i", str(origen), "-vf", f"scale={ancho}:{alto}:flags=lanczos", str(tmp)], capture_output=True)
        if r.returncode != 0:
            raise RuntimeError(f"ffmpeg no pudo reducir {origen.name}: {r.stderr[-200:]!r}")
        if formato == "webp":
            cw = shutil.which("cwebp")
            if not cw:
                raise RuntimeError("falta cwebp")
            for q in CALIDADES_WEBP:
                r = subprocess.run([cw, "-quiet", "-q", str(q), "-m", "6", "-sharp_yuv", str(tmp), "-o", str(destino)], capture_output=True)
                if r.returncode != 0:
                    raise RuntimeError(f"cwebp falló en {origen.name}")
                kb = destino.stat().st_size / 1024
                if not peso_max_kb or kb <= peso_max_kb:
                    return {"calidad": q, "peso_kb": round(kb, 1), "peso_ok": True}
            return {"calidad": q, "peso_kb": round(kb, 1), "peso_ok": False}
        for q in CALIDADES_JPG:
            r = subprocess.run([ff, "-v", "error", "-y", "-i", str(tmp), "-q:v", str(q), str(destino)], capture_output=True)
            if r.returncode != 0:
                raise RuntimeError(f"ffmpeg no pudo escribir {destino.name}")
            kb = destino.stat().st_size / 1024
            if not peso_max_kb or kb <= peso_max_kb:
                return {"calidad": q, "peso_kb": round(kb, 1), "peso_ok": True}
        return {"calidad": q, "peso_kb": round(kb, 1), "peso_ok": False}


def medir(ruta: Path) -> tuple[int, int]:
    """Ancho y alto reales del archivo final (sips en macOS; dwebp/ffprobe no hacen falta)."""
    r = subprocess.run(["sips", "-g", "pixelWidth", "-g", "pixelHeight", str(ruta)], capture_output=True, text=True)
    w = h = 0
    for linea in r.stdout.splitlines():
        if "pixelWidth" in linea:
            w = int(linea.split(":")[1])
        if "pixelHeight" in linea:
            h = int(linea.split(":")[1])
    return w, h


def resumen_candidatos(assets: Path, slot_id: str) -> dict:
    cands = []
    for j in sorted((assets / "candidatos" / slot_id).glob("*.json")):
        try:
            cands.append(json.loads(j.read_text(encoding="utf-8")))
        except ValueError:
            continue
    creditos = 0.0
    intentos: dict[str, int] = {}
    for c in cands:
        real = c.get("creditos_reales")
        creditos += float(real) if isinstance(real, (int, float)) else float(c.get("creditos_cotizados") or 0)
        if c.get("tipo") != "compuesta" and not c.get("derivada_de"):
            k = f"ronda{c.get('ronda', 1)}"
            intentos[k] = intentos.get(k, 0) + 1
    return {"creditos": round(creditos, 1), "intentos_por_ronda": intentos, "candidatos": {c["candidato"]: c for c in cands}}


def propuesta_assets(entrada: dict, slot_plan: dict, assets_json: dict | None) -> dict:
    """Parche propuesto para el slot en assets.json (esquema 1.1.0-propuesta: estado aprobado, sha256 con prefijo, origen ia)."""
    existe = bool(assets_json and any(s.get("slot_id") == slot_plan.get("asset_slot") for s in assets_json.get("slots", [])))
    campos = {
        "ancho_px": entrada["ancho"], "alto_px": entrada["alto"], "formato": entrada["formato"], "peso_max_kb": entrada["peso_max_kb"],
        "estado": "aprobado" if entrada["aprobado_por_revision"] else "asignado", "archivo": entrada["archivo"], "sha256": f"sha256:{entrada['sha256']}",
        "origen": "ia", "ia_generado": True, "etiqueta_ia_visible": entrada["etiqueta_ia_visible"], "herramienta": HERRAMIENTA,
        "alt": slot_plan.get("alt_propuesto"),
    }
    if entrada.get("ilustrativa"):
        campos.update(ilustrativa=True, reemplazar_con_real_cuando_exista_producto=True)     # campos nuevos: el esquema aún no los admite
    return {"slot_id": entrada["slot"], "accion": "actualizar" if existe else "crear", "campos": campos}


def generar_finales(plan: dict, assets: Path, assets_json: dict | None, revision: dict | None, solo: set[str] | None = None,
                    convertir_fn: Callable[..., dict] = convertir, medir_fn: Callable[[Path], tuple[int, int]] = medir) -> dict:
    final = assets / "final"
    revisiones = revision if isinstance(revision, list) else ([revision] if revision else [])
    aprobados: dict[str, str] = {}
    for rev in revisiones:                               # las rondas posteriores pisan a las anteriores
        aprobados |= rev.get("estrictas", {}).get("PASA", {}) | rev.get("ilustrativas", {}).get("PASA", {})
    entradas, parches = [], []
    for s in plan["slots"]:
        if solo and s["slot_id"] not in solo:
            continue
        sel = (s.get("seleccion_maker") or {}).get("candidato")
        if not sel:
            raise SystemExit(f"2: el slot {s['slot_id']} no tiene candidato elegido")
        info = resumen_candidatos(assets, s["slot_id"])
        cand = info["candidatos"].get(sel)
        origen = assets / "candidatos" / s["slot_id"] / f"{sel}.png"
        if not cand or not origen.is_file():
            raise SystemExit(f"2: no existe el candidato {s['slot_id']}/{sel}")
        m = medidas(s, assets_json)
        destino = final / f"{s['slot_id']}.{m['formato']}"
        r = convertir_fn(origen, destino, m["ancho"], m["alto"], m["formato"], m["peso_max_kb"])
        w, h = medir_fn(destino)
        entrada = {
            "slot": s["slot_id"], "archivo": f"final/{destino.name}", "sha256": sha256_archivo(destino), "ancho": w, "alto": h, "formato": m["formato"],
            "peso_kb": r["peso_kb"], "peso_max_kb": m["peso_max_kb"], "peso_ok": r["peso_ok"], "calidad_codificacion": r["calidad"], "origen_medida": m["origen_medida"],
            "modelo": cand.get("modelo"), "candidato_origen": sel, "derivada_de": cand.get("derivada_de"), "task_id": cand.get("task_id"),
            "creditos_slot": info["creditos"], "intentos_por_ronda": info["intentos_por_ronda"],
            "ilustrativa": bool(s.get("ilustrativa")), "reemplazar_con_real_cuando_exista_producto": bool(s.get("reemplazar_con_real_cuando_exista_producto")),
            "etiqueta_ia_visible": bool(s.get("etiqueta_ia_visible", True)), "ia_generado": True,
            "aprobado_por_revision": aprobados.get(s["slot_id"]) == sel, "estado": s.get("estado_revision"), "alt_propuesto": s.get("alt_propuesto"),
            "medida_ok": (w, h) == (m["ancho"], m["alto"]),
        }
        entradas.append(entrada)
        parches.append(propuesta_assets(entrada, s, assets_json))
    manifiesto = {"schema_version": "0.1.0", "oferta_id": plan.get("oferta_id"), "ts": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                  "nota": "Finales a la medida y peso de cada ranura. `aprobado_por_revision` = el candidato elegido coincide con el que PASÓ la revisión independiente indicada; false = pendiente de revisión. No sustituyen las imágenes de producto reales de D4.",
                  "ranuras": entradas, "propuesta_assets_json": parches}
    final.mkdir(parents=True, exist_ok=True)
    (final / "manifiesto-final.json").write_text(json.dumps(manifiesto, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifiesto


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Finales de las ranuras de imagen.")
    ap.add_argument("plan", type=Path)
    ap.add_argument("--assets", type=Path, required=True)
    ap.add_argument("--assets-json", type=Path, default=None)
    ap.add_argument("--revision", type=Path, action="append", default=[], help="revisión independiente (repetible; las rondas posteriores pisan)")
    ap.add_argument("--solo", default="")
    a = ap.parse_args(argv)
    plan = json.loads(a.plan.read_text(encoding="utf-8"))
    aj = json.loads(a.assets_json.read_text(encoding="utf-8")) if a.assets_json and a.assets_json.is_file() else None
    rev = [json.loads(r.read_text(encoding="utf-8")) for r in a.revision if r.is_file()]
    try:
        man = generar_finales(plan, a.assets.resolve(), aj, rev, set(filter(None, a.solo.split(","))))
    except RuntimeError as e:
        print(f"HERRAMIENTA: {e}", file=sys.stderr)
        return 6
    malos = [e["slot"] for e in man["ranuras"] if not e["peso_ok"] or not e["medida_ok"]]
    print(json.dumps({"ranuras": len(man["ranuras"]), "con_problema": malos}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
