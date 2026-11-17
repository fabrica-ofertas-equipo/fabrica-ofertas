"""Ranuras de imagen con Kie.ai: genera candidatos con tope de créditos, trazabilidad y reintento por corrección.

Qué hace
--------
Lee un **plan de ranuras** (``plan-slots.json``: por ranura el prompt exacto, las imágenes de referencia planas,
el ratio, los modelos a probar y cuántos intentos de cada uno) y, por cada candidato:

1. sube las referencias a Kie (``Kie.subir``; el archivo se borra a las 24 h) y arma el ``input`` del modelo
   (``nano-banana-pro`` / ``nano-banana-2``: ``image_input``; ``gpt-image-2-image-to-image``: ``input_urls``);
2. cotiza (``estimar_creditos``) y **se detiene** si el gasto acumulado de la ronda más lo cotizado superaría el
   tope (900 créditos por defecto ≈ 4,5 US$). El acumulado sale de los JSON de candidatos ya escritos (el real
   ``creditsConsumed`` si se conoce; si no, lo cotizado, por prudencia);
3. anota el gasto ANTES de enviar (``registrar_previo``, vía ``SKETCH_COSTOS_BORRADOR``) y guarda el ``task_id``
   en cuanto existe, para poder retomar la tarea si se corta la red;
4. descarga el PNG a ``candidatos/<slot>/<intento>.png`` y escribe al lado ``<intento>.json`` con el prompt
   exacto, el modelo, los parámetros, los créditos, el ``task_id``, el sha256, los textos que debe llevar y las
   **comprobaciones de código** (dimensiones y ratio, no vacía, tamaño, peso WebP a las medidas finales, OCR de
   los textos esperados con Vision de macOS si está disponible).

Es idempotente: un candidato cuyo PNG y JSON ya existen no se vuelve a generar (no se paga dos veces).

Comandos (el ciclo de revisión, desde ``manifiesto --ciego`` hasta ``finalizar``, está documentado en ``README.md`` y vive en ``ciclo_revision.py``)::

    python3 scripts/imagenes/ranuras_kie.py generar   PLAN --assets DIR [--solo a,b] [--tope 900] [--seco]
    python3 scripts/imagenes/ranuras_kie.py reintentar PLAN --assets DIR --slot S --modelo M --correccion "texto"
    python3 scripts/imagenes/ranuras_kie.py elegir    PLAN --assets DIR --slot S --candidato C --motivo "texto"
    python3 scripts/imagenes/ranuras_kie.py manifiesto PLAN --assets DIR [--salida paquete-revision.json] [--ciego [--solo-slots a,b] [--solo-re-revisar]]
    python3 scripts/imagenes/ranuras_kie.py revisar-prompt PLAN --assets DIR
    python3 scripts/imagenes/ranuras_kie.py aplicar-revision PLAN REVISION.json --assets DIR [--tope N] [--n 1]
    python3 scripts/imagenes/ranuras_kie.py finalizar PLAN --assets DIR [--assets-json assets.json] [--incluir-pendientes]
    python3 scripts/imagenes/ranuras_kie.py derivar   PLAN --assets DIR --slot S --desde PNG --base CAND --nombre N
    python3 scripts/imagenes/ranuras_kie.py recomprobar PLAN --assets DIR
    python3 scripts/imagenes/ranuras_kie.py saldo     --assets DIR --fase inicio|fin

La clave ``KIE_API_KEY`` se lee de ``.env`` SOLO dentro del proceso y se pone en ``os.environ``: nunca se imprime,
se copia ni se registra. Los comandos que no llaman a Kie (``elegir``, ``manifiesto``, ``--seco``) no la necesitan.
El cliente de Kie y la cotización son inyectables para probar sin red (``tests/imagenes/``).

Salidas: 0 ok · 2 uso/plan inválido · 3 revisión rechazada (aplicar-revision no escribió nada) · 4 finalizar sin slots aprobados · 5 tope de créditos (no se envió lo que lo superaba) · 6 falló Kie.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import difflib
import hashlib
import importlib.util
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path
from typing import Any, Callable

RAIZ_PROYECTO = Path(__file__).resolve().parents[2]
KIE_PY = RAIZ_PROYECTO / ".claude/skills/d6-sketch-animado/scripts/sketchlib/kie.py"
OCR_SWIFT = Path(__file__).resolve().parent / "ocr_vision.swift"
TOPE_DEFECTO = 900
VERSION = "1.0.0"
ABREV = {"nano-banana-pro": "nbp", "nano-banana-2": "nb2", "gpt-image-2-image-to-image": "gpt2"}
MAX_REFS = {"nano-banana-pro": 8, "nano-banana-2": 10, "gpt-image-2-image-to-image": 16}
MIN_BYTES = 20_000
# Créditos medidos (creditsConsumed, 2K, 2026-11-07): kie.py estima 6 (gpt-image-2) y 8 (nano-banana-2) pero se cobraron 10 y 12.
# La cotización de la ronda toma el mayor entre la de kie.py y la medida, para que el tope sea prudente.
CREDITOS_MEDIDOS = {"nano-banana-pro": 18, "nano-banana-2": 12, "gpt-image-2-image-to-image": 10}


class TopeExcedido(RuntimeError):
    """El siguiente envío superaría el tope de créditos de la ronda."""


class PlanInvalido(ValueError):
    pass


# ── utilidades ──────────────────────────────────────────────────────────────
def ahora() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_archivo(ruta: Path) -> str:
    h = hashlib.sha256()
    with Path(ruta).open("rb") as fh:
        for trozo in iter(lambda: fh.read(1 << 20), b""):
            h.update(trozo)
    return h.hexdigest()


def sha256_texto(t: str) -> str:
    return hashlib.sha256(t.encode("utf-8")).hexdigest()


def cargar_clave(env: Path | None = None) -> bool:
    """Pone KIE_API_KEY en os.environ leyendo SOLO esa variable de .env. No imprime nada. Devuelve si quedó definida."""
    if os.environ.get("KIE_API_KEY"):
        return True
    ruta = Path(env) if env else RAIZ_PROYECTO / ".env"
    if not ruta.is_file():
        return False
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if linea.startswith("KIE_API_KEY="):
            valor = linea.split("=", 1)[1].strip().strip('"').strip("'")
            if valor:
                os.environ["KIE_API_KEY"] = valor
                return True
    return False


def cargar_kie():
    """Importa kie.py del skill d6-sketch-animado (sin tocarlo) y devuelve el módulo."""
    if not KIE_PY.is_file():
        raise RuntimeError(f"no está {KIE_PY}")
    spec = importlib.util.spec_from_file_location("kie_d6", KIE_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def leer_png_dims(ruta: Path) -> tuple[int, int]:
    """Ancho y alto de un PNG leyendo el IHDR (sin librerías). ValueError si no es PNG."""
    with Path(ruta).open("rb") as fh:
        cab = fh.read(24)
    if cab[:8] != b"\x89PNG\r\n\x1a\n" or cab[12:16] != b"IHDR":
        raise ValueError("no es un PNG")
    return struct.unpack(">II", cab[16:24])


def asegurar_png(ruta: Path) -> None:
    """Si el archivo descargado es JPEG/WebP lo convierte a PNG con sips (macOS)."""
    with Path(ruta).open("rb") as fh:
        magia = fh.read(12)
    if magia[:8] == b"\x89PNG\r\n\x1a\n":
        return
    if not shutil.which("sips"):
        raise RuntimeError("el resultado no es PNG y no hay sips para convertirlo")
    tmp = Path(ruta).with_suffix(".conv.png")
    subprocess.run(["sips", "-s", "format", "png", str(ruta), "--out", str(tmp)], check=True, capture_output=True)
    tmp.replace(ruta)


def normalizar(t: str, plegar: bool) -> str:
    t = unicodedata.normalize("NFC", t).casefold().replace("ł", "l") if plegar else unicodedata.normalize("NFC", t).casefold()
    if plegar:
        t = "".join(ch for ch in unicodedata.normalize("NFD", t) if unicodedata.category(ch) != "Mn")
    return "".join(ch for ch in t if ch.isalnum())


# ── entrada de cada modelo ──────────────────────────────────────────────────
def construir_entrada(modelo: str, prompt: str, urls: list[str], ratio: str, resolution: str) -> dict:
    """``input`` de createTask según el modelo (formatos de .claude/skills/d6-sketch-animado/scripts/sketchlib/pipeline.py)."""
    n = MAX_REFS.get(modelo)
    if n is None:
        raise PlanInvalido(f"modelo de imagen no soportado: {modelo}")
    if modelo == "gpt-image-2-image-to-image":
        if not urls:
            raise PlanInvalido("gpt-image-2-image-to-image necesita al menos una referencia")
        return {"prompt": prompt, "input_urls": urls[:n], "aspect_ratio": ratio, "resolution": resolution}
    entrada = {"prompt": prompt, "aspect_ratio": ratio, "resolution": resolution, "output_format": "png"}
    if urls:                                        # sin referencias, nano-banana trabaja de texto a imagen
        entrada["image_input"] = urls[:n]
    return entrada


# ── gasto y tope ────────────────────────────────────────────────────────────
def leer_candidatos(dir_candidatos: Path) -> list[dict]:
    out = []
    for j in sorted(Path(dir_candidatos).glob("*/*.json")):
        try:
            out.append(json.loads(j.read_text(encoding="utf-8")))
        except ValueError:
            continue
    return out


def gasto_acumulado(dir_candidatos: Path, ronda: int | None = None) -> float:
    """Créditos de la ronda (``None`` = todas): el real si se conoce; si no, lo cotizado (prudente: una tarea fallida cuenta hasta conciliar).

    Los JSON sin ``ronda`` son de la ronda 1.
    """
    total = 0.0
    for c in leer_candidatos(dir_candidatos):
        if ronda is not None and int(c.get("ronda", 1)) != int(ronda):
            continue
        real = c.get("creditos_reales")
        total += float(real) if isinstance(real, (int, float)) else float(c.get("creditos_cotizados") or 0)
    return total


def comprobar_tope(acumulado: float, cotizado: float, tope: float) -> None:
    if acumulado + cotizado > tope:
        raise TopeExcedido(f"se superaría el tope: acumulado {acumulado:g} + cotizado {cotizado:g} > {tope:g} créditos")


# ── comprobaciones de código por candidato ──────────────────────────────────
def _stddev_gris(png: Path) -> float | None:
    """Desviación típica de una miniatura 64x64 en gris (ffmpeg). None si no hay ffmpeg."""
    ff = shutil.which("ffmpeg")
    if not ff:
        return None
    r = subprocess.run([ff, "-v", "error", "-i", str(png), "-vf", "scale=64:64,format=gray", "-f", "rawvideo", "-"],
                       capture_output=True, timeout=60)
    datos = r.stdout
    if len(datos) < 4096:
        return None
    media = sum(datos) / len(datos)
    return (sum((b - media) ** 2 for b in datos) / len(datos)) ** 0.5


def _peso_webp_kb(png: Path, ancho: int, alto: int) -> float | None:
    cw = shutil.which("cwebp")
    if not cw:
        return None
    with tempfile.TemporaryDirectory() as td:
        salida = Path(td) / "x.webp"
        r = subprocess.run([cw, "-quiet", "-q", "80", "-resize", str(ancho), str(alto), str(png), "-o", str(salida)],
                           capture_output=True, timeout=120)
        if r.returncode != 0 or not salida.exists():
            return None
        return round(salida.stat().st_size / 1024, 1)


def ocr_png(png: Path) -> list[str] | None:
    """Líneas de texto por Vision (macOS). Compila ocr_vision.swift en el directorio temporal la primera vez. None si no se puede."""
    swiftc = shutil.which("swiftc")
    if not swiftc or not OCR_SWIFT.is_file() or sys.platform != "darwin":
        return None
    binario = Path(tempfile.gettempdir()) / f"ocr_vision_{sha256_archivo(OCR_SWIFT)[:10]}"
    if not binario.exists():
        r = subprocess.run([swiftc, "-O", str(OCR_SWIFT), "-o", str(binario)], capture_output=True, timeout=300)
        if r.returncode != 0:
            return None
    r = subprocess.run([str(binario), str(png), "pl-PL,en-US"], capture_output=True, text=True, timeout=120)
    try:
        return json.loads(r.stdout)["lineas"]
    except (ValueError, KeyError):
        return None


def evaluar_ocr(lineas: list[str], esperados: list[str]) -> dict:
    """Compara los textos esperados con lo leído. ``exacto`` conserva los diacríticos; ``aproximado`` los pliega (Ł→L, Ś→S)."""
    junto_ex = normalizar(" ".join(lineas), plegar=False)
    junto_ap = normalizar(" ".join(lineas), plegar=True)
    ok, solo_aprox, faltan = [], [], []
    for t in esperados:
        ex, ap = normalizar(t, False), normalizar(t, True)
        if not ex:
            continue
        if ex in junto_ex:
            ok.append(t)
        elif ap in junto_ap:
            solo_aprox.append(t)
        else:
            mejor = max((difflib.SequenceMatcher(None, ap, normalizar(l, True)).ratio() for l in lineas), default=0.0)
            (solo_aprox if mejor >= 0.88 else faltan).append(t)
    n = len(ok) + len(solo_aprox) + len(faltan)
    return {"leidas": lineas, "encontrados_exactos": ok, "encontrados_sin_diacriticos_o_dudosos": solo_aprox,
            "no_encontrados": faltan, "tasa_exacta": round(len(ok) / n, 3) if n else None}


def comprobar_candidato(png: Path, slot: dict, ocr: Callable[[Path], list[str] | None] | None = ocr_png,
                        usar_externos: bool = True) -> dict:
    """Comprobaciones de código: dimensiones, ratio, no vacía, tamaño, hash, peso WebP final y OCR de textos."""
    dims = slot.get("dimensiones_requeridas") or {}
    res: dict[str, Any] = {"existe": Path(png).is_file()}
    if not res["existe"]:
        res["codigo_ok"] = False
        return res
    res["bytes"] = Path(png).stat().st_size
    res["sha256"] = sha256_archivo(png)
    try:
        w, h = leer_png_dims(png)
    except ValueError as e:
        res.update(codigo_ok=False, error=str(e))
        return res
    res["ancho"], res["alto"] = w, h
    rw, rh = (int(x) for x in str(slot.get("ratio", "1:1")).split(":"))
    esperado = rw / rh
    corte = (slot.get("post") or {}).get("recorte_centrado")
    if corte:                                      # og: el ratio que cuenta es el de la medida final recortada
        esperado = corte[0] / corte[1]
    res["ratio_ok"] = abs(w / h - esperado) / esperado <= 0.02
    ra, rl = dims.get("ancho"), dims.get("alto")
    res["tamano_suficiente"] = (w >= ra and h >= rl) if ra and rl else True
    res["no_pequeno"] = res["bytes"] >= MIN_BYTES
    desv = _stddev_gris(png) if usar_externos else None
    res["desviacion_gris"] = None if desv is None else round(desv, 2)
    res["no_vacia"] = (desv is None and res["no_pequeno"]) or (desv is not None and desv > 6.0 and res["no_pequeno"])
    if usar_externos and ra and rl:
        kb = _peso_webp_kb(png, ra, rl)
        res["peso_webp_kb_a_medida_final"] = kb
        mx = dims.get("peso_max_kb")
        res["peso_webp_ok"] = None if (kb is None or not mx) else kb <= mx
    esperados = slot.get("textos_esperados") or []
    if ocr and esperados:
        lineas = ocr(png)
        res["ocr"] = evaluar_ocr(lineas, esperados) if lineas is not None else {"estado": "no_disponible"}
    res["codigo_ok"] = bool(res["ratio_ok"] and res["tamano_suficiente"] and res["no_vacia"] and res["no_pequeno"])
    return res


# ── post-proceso (solo og: recorte centrado a medida final) ─────────────────
def recortar_centrado(png: Path, ancho: int, alto: int) -> None:
    """Escala por ancho y recorta al centro a ancho x alto (sips). Deja el original como <nombre>.raw.png."""
    raw = png.with_suffix(".raw.png")
    shutil.copy(png, raw)
    subprocess.run(["sips", "--resampleWidth", str(ancho), str(png)], check=True, capture_output=True)
    subprocess.run(["sips", "-c", str(alto), str(ancho), str(png)], check=True, capture_output=True)


# ── plan ────────────────────────────────────────────────────────────────────
def cargar_plan(ruta: Path) -> dict:
    plan = json.loads(Path(ruta).read_text(encoding="utf-8"))
    if not isinstance(plan.get("slots"), list) or not plan["slots"]:
        raise PlanInvalido("el plan no tiene slots")
    vistos = set()
    for s in plan["slots"]:
        for k in ("slot_id", "ratio", "prompt", "intentos"):
            if k not in s:
                raise PlanInvalido(f"slot sin '{k}': {s.get('slot_id')}")
        if s["slot_id"] in vistos:
            raise PlanInvalido(f"slot repetido: {s['slot_id']}")
        vistos.add(s["slot_id"])
        for it in s["intentos"]:
            if it["modelo"] not in MAX_REFS:
                raise PlanInvalido(f"{s['slot_id']}: modelo no soportado {it['modelo']}")
    return plan


def nombre_intento(dir_slot: Path, modelo: str, reintento: bool = False, prefijo: str = "") -> str:
    base = prefijo + ABREV.get(modelo, "mod") + ("-r" if reintento else "-")
    n = 1
    while (dir_slot / f"{base}{n:02d}.json").exists() or (dir_slot / f"{base}{n:02d}.png").exists():
        n += 1
    return f"{base}{n:02d}"


def _resolver_refs(slot: dict, assets: Path) -> list[Path]:
    refs = []
    for r in slot.get("referencias", []):
        p = Path(r)
        p = p if p.is_absolute() else assets / p
        if not p.is_file():
            raise PlanInvalido(f"{slot['slot_id']}: falta la referencia {r}")
        refs.append(p)
    return refs


# ── generación de un candidato ──────────────────────────────────────────────
def generar_candidato(cliente: Any, estimar: Callable[[str, dict], int], plan: dict, slot: dict, modelo: str, assets: Path,
                      tope: float, nombre: str | None = None, correccion: str | None = None,
                      comprobar: Callable[..., dict] = comprobar_candidato, max_seg: int = 900) -> dict:
    dir_slot = assets / "candidatos" / slot["slot_id"]
    dir_slot.mkdir(parents=True, exist_ok=True)
    nombre = nombre or nombre_intento(dir_slot, modelo, bool(correccion), plan.get("prefijo_candidatos", ""))
    png, js = dir_slot / f"{nombre}.png", dir_slot / f"{nombre}.json"
    refs = _resolver_refs(slot, assets)
    urls = [cliente.subir(r) for r in refs]
    prompt = slot["prompt"] + (f"\n\nCORRECCIÓN respecto del intento anterior: {correccion}" if correccion else "")
    resolution = slot.get("resolution") or plan.get("resolution", "2K")
    entrada = construir_entrada(modelo, prompt, urls, slot["ratio"], resolution)
    cotizado = int(estimar(modelo, entrada))
    comprobar_tope(gasto_acumulado(assets / "candidatos", plan.get("ronda")), cotizado, tope)
    etiqueta = f"{slot['slot_id']}/{nombre}"
    reg: dict[str, Any] = {
        "schema_version": "1.0.0", "ts": ahora(), "oferta_id": plan.get("oferta_id"), "slot_id": slot["slot_id"], "candidato": nombre,
        "ronda": plan.get("ronda", 1), "tipo": "escena_con_marcadores" if slot.get("escena") else "directo",
        "estado": "enviando", "modelo": modelo, "parametros": {k: v for k, v in entrada.items() if k not in ("prompt", "image_input", "input_urls")},
        "prompt": prompt, "prompt_sha256": sha256_texto(prompt), "correccion": correccion,
        "referencias": [{"archivo": str(r.relative_to(assets)) if r.is_relative_to(assets) else str(r), "sha256": sha256_archivo(r)} for r in refs],
        "textos_esperados": slot.get("textos_esperados", []), "creditos_cotizados": cotizado, "creditos_reales": None, "task_id": None,
        "ilustrativa": bool(slot.get("ilustrativa")), "ia_generado": True, "etiqueta_ia_visible": slot.get("etiqueta_ia_visible", True),
    }
    js.write_text(json.dumps(reg, ensure_ascii=False, indent=2), encoding="utf-8")
    tid = cliente.crear(modelo, entrada, etiqueta)        # anota registrar_previo ANTES de enviar (dentro de Kie.crear)
    reg.update(task_id=tid, estado="creada")
    js.write_text(json.dumps(reg, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        d = cliente.recuperar(tid, png, etiqueta=etiqueta, max_seg=max_seg)
    except Exception as e:  # noqa: BLE001 - se registra y se relanza
        reg.update(estado="fallo", error=str(e)[:500])
        js.write_text(json.dumps(reg, ensure_ascii=False, indent=2), encoding="utf-8")
        raise
    asegurar_png(png)
    post = slot.get("post") or {}
    if post.get("recorte_centrado"):
        recortar_centrado(png, *post["recorte_centrado"])
    real = d.get("creditsConsumed")
    reg.update(estado="ok", creditos_reales=real if isinstance(real, (int, float)) else None, task_id=d.get("taskId", tid))
    slot_chk = dict(slot)
    if slot.get("escena"):                          # la escena lleva marcadores de color y ningún texto: solo se comprueban dimensiones
        slot_chk["textos_esperados"] = []
    reg["comprobaciones"] = comprobar(png, slot_chk)
    reg["sha256"] = reg["comprobaciones"].get("sha256")
    reg["archivo"] = str(png.relative_to(assets))
    js.write_text(json.dumps(reg, ensure_ascii=False, indent=2), encoding="utf-8")
    return reg


def ejecutar_plan(cliente: Any, estimar: Callable[[str, dict], int], plan: dict, assets: Path, tope: float,
                  solo: set[str] | None = None, seco: bool = False, **kw) -> list[dict]:
    """Genera todos los candidatos que falten. Idempotente. Con ``seco`` solo cotiza."""
    hechos = []
    for slot in plan["slots"]:
        if solo and slot["slot_id"] not in solo:
            continue
        dir_slot = assets / "candidatos" / slot["slot_id"]
        for it in slot["intentos"]:
            for k in range(1, int(it.get("n", 1)) + 1):
                nombre = f"{plan.get('prefijo_candidatos', '')}{ABREV.get(it['modelo'], 'mod')}-{k:02d}"
                if (dir_slot / f"{nombre}.png").exists() and (dir_slot / f"{nombre}.json").exists():
                    continue                                  # ya generado: no se paga dos veces
                if seco:
                    ent = construir_entrada(it["modelo"], slot["prompt"], ["https://x"] * len(slot.get("referencias", [])), slot["ratio"], slot.get("resolution") or plan.get("resolution", "2K"))
                    cot = estimar(it["modelo"], ent)
                    comprobar_tope(gasto_acumulado(assets / "candidatos", plan.get("ronda")) + sum(h["cotizado"] for h in hechos), cot, tope)
                    hechos.append({"slot_id": slot["slot_id"], "candidato": nombre, "modelo": it["modelo"], "cotizado": cot, "seco": True})
                    continue
                hechos.append(generar_candidato(cliente, estimar, plan, slot, it["modelo"], assets, tope, nombre=nombre, **kw))
    return hechos


def recomprobar(plan: dict, assets: Path, comprobar: Callable[..., dict] = comprobar_candidato) -> int:
    """Vuelve a correr las comprobaciones de código sobre los candidatos ya escritos y actualiza sus JSON. Devuelve cuántos."""
    n = 0
    por_slot = {s["slot_id"]: s for s in plan["slots"]}
    for j in sorted((assets / "candidatos").glob("*/*.json")):
        reg = json.loads(j.read_text(encoding="utf-8"))
        slot, png = por_slot.get(reg.get("slot_id")), j.with_suffix(".png")
        if reg.get("estado") != "ok" or slot is None or not png.is_file():
            continue
        reg["comprobaciones"] = comprobar(png, dict(slot))
        reg["sha256"] = reg["comprobaciones"].get("sha256")
        j.write_text(json.dumps(reg, ensure_ascii=False, indent=2), encoding="utf-8")
        n += 1
    return n


# ── candidato derivado (p. ej. og = placa de Kie + texto HTML exacto) ───────
def registrar_derivado(plan: dict, slot: dict, assets: Path, desde: Path, nombre: str, base: str,
                       comprobar: Callable[..., dict] = comprobar_candidato, tipo: str = "compuesta") -> dict:
    """Copia ``desde`` a candidatos/<slot>/<nombre>.png y escribe su JSON (sin créditos propios; apunta a la placa de Kie ``base``)."""
    dir_slot = assets / "candidatos" / slot["slot_id"]
    dir_slot.mkdir(parents=True, exist_ok=True)
    png, js = dir_slot / f"{nombre}.png", dir_slot / f"{nombre}.json"
    shutil.copy(desde, png)
    base_json = dir_slot / f"{base}.json"
    base_reg = json.loads(base_json.read_text(encoding="utf-8")) if base_json.is_file() else {}
    reg = {"schema_version": "1.0.0", "ts": ahora(), "oferta_id": plan.get("oferta_id"), "slot_id": slot["slot_id"], "candidato": nombre,
           "ronda": plan.get("ronda", 1), "tipo": tipo,
           "estado": "ok", "modelo": "compuesta: base de Kie + portadas planas por código (HTML/CSS→PNG con Chrome)", "derivada_de": base,
           "task_id": base_reg.get("task_id"), "creditos_cotizados": 0, "creditos_reales": 0,
           "prompt": base_reg.get("prompt"), "prompt_sha256": base_reg.get("prompt_sha256"),
           "referencias": [{"archivo": str(desde), "sha256": sha256_archivo(desde)}],
           "textos_esperados": slot.get("textos_esperados", []), "ilustrativa": bool(slot.get("ilustrativa")), "ia_generado": True,
           "etiqueta_ia_visible": slot.get("etiqueta_ia_visible", True),
           "nota": "Los créditos de la base ya están en el candidato base; esta composición no gasta."}
    reg["comprobaciones"] = comprobar(png, dict(slot))
    reg["sha256"] = reg["comprobaciones"].get("sha256")
    reg["archivo"] = str(png.relative_to(assets))
    js.write_text(json.dumps(reg, ensure_ascii=False, indent=2), encoding="utf-8")
    return reg


# ── manifiesto de revisión ──────────────────────────────────────────────────
def construir_manifiesto(plan: dict, assets: Path, ledger: dict | None = None, estados: dict | None = None,
                         flags_fn: Callable[[dict], dict] | None = None) -> dict:
    """``estados`` (de ``ciclo_revision.estado_slots``) manda sobre ``estado_revision`` del plan; ``flags_fn`` calcula ``ilustrativa`` y ``reemplazar_…``."""
    por_slot: dict[str, list[dict]] = {}
    for c in leer_candidatos(assets / "candidatos"):
        por_slot.setdefault(c["slot_id"], []).append(c)
    slots = []
    for s in plan["slots"]:
        cands = []
        for c in sorted(por_slot.get(s["slot_id"], []), key=lambda x: x["candidato"]):
            ch = c.get("comprobaciones") or {}
            ocr = ch.get("ocr") or {}
            cands.append({
                "candidato": c["candidato"], "estado": c.get("estado"), "ruta_png": f"candidatos/{s['slot_id']}/{c['candidato']}.png",
                "ruta_json": f"candidatos/{s['slot_id']}/{c['candidato']}.json", "modelo": c.get("modelo"),
                "creditos_cotizados": c.get("creditos_cotizados"), "creditos_reales": c.get("creditos_reales"), "task_id": c.get("task_id"),
                "sha256": c.get("sha256"), "ancho": ch.get("ancho"), "alto": ch.get("alto"), "codigo_ok": ch.get("codigo_ok"),
                "peso_webp_kb_a_medida_final": ch.get("peso_webp_kb_a_medida_final"),
                "ocr_tasa_textos_exactos": ocr.get("tasa_exacta"), "ocr_no_encontrados": ocr.get("no_encontrados"),
                "correccion": c.get("correccion"), "ronda": c.get("ronda", 1), "tipo": c.get("tipo", "directo"),
                "excluir_de_revision": c.get("tipo") == "escena_con_marcadores", "derivada_de": c.get("derivada_de"),
            })
        slots.append({
            "slot_id": s["slot_id"], "slot_assets_json": s.get("asset_slot"), "seccion": s.get("seccion"), "funcion_en_pagina": s.get("funcion"),
            "textos_esperados": s.get("textos_esperados", []), "objetos_esperados": s.get("objetos_esperados", []),
            "no_debe_aparecer": list(dict.fromkeys((plan.get("no_debe_aparecer_global") or []) + (s.get("no_debe_aparecer") or []))),
            "dimensiones_requeridas": s.get("dimensiones_requeridas"), "ratio_generado": s["ratio"],
            "rubrica": {"estricto": bool(s.get("estricto")), "textos_estrictos": s.get("textos_estrictos", []),
                        "criterios": s.get("criterios", [])},
            **((flags_fn(s)) if flags_fn else {"ilustrativa": bool(s.get("ilustrativa")),
                                               "reemplazar_con_real_cuando_exista_producto": bool(s.get("reemplazar_con_real_cuando_exista_producto"))}),
            "ia_generado": True, "etiqueta_ia_visible": s.get("etiqueta_ia_visible", True),
            "referencias_planas": s.get("referencias", []), "candidatos": cands, "seleccion_maker": s.get("seleccion_maker"),
            "estado": (estados[s["slot_id"]]["estado"] if estados else (s.get("estado_revision") or ("con_candidatos" if cands else "sin_generar"))),
            "aprobado_por_revision": (estados[s["slot_id"]]["aprobado"] if estados else None),
            "condiciones": (estados[s["slot_id"]]["condiciones"] if estados else []),
            "notas_maker": s.get("notas_maker"),
            "re_revisar": ((estados[s["slot_id"]]["estado"].startswith("rehecho") or estados[s["slot_id"]]["estado"] == "pendiente_de_revision") if estados
                           else str(s.get("estado_revision", "")).startswith("rehecho")),
            "candidato_a_revisar": ((s.get("seleccion_maker") or {}).get("candidato") if (
                (estados[s["slot_id"]]["estado"].startswith("rehecho") or estados[s["slot_id"]]["estado"] == "pendiente_de_revision") if estados
                else str(s.get("estado_revision", "")).startswith("rehecho")) else None),
            "intentos_por_ronda": {f"ronda{r}": sum(1 for c in cands if c["ronda"] == r and c["tipo"] != "compuesta" and not c.get("derivada_de")) for r in sorted({c["ronda"] for c in cands})},
            "creditos_slot": sum((c["creditos_reales"] if isinstance(c["creditos_reales"], (int, float)) else (c["creditos_cotizados"] or 0)) for c in cands),
        })
    return {
        "schema_version": "0.1.0", "generado_por": f"scripts/imagenes/ranuras_kie.py {VERSION}", "ts": ahora(), "oferta_id": plan.get("oferta_id"),
        "ronda": plan.get("ronda"), "rondas": plan.get("rondas"), "gasto": ledger or {}, "rubrica_general": plan.get("rubrica_general", {}),
        "pendientes": plan.get("pendientes", []), "propuestas_cambio_assets_json": plan.get("propuestas_cambio_assets_json", []),
        "re_revisar": [{"slot_id": sl["slot_id"], "candidato": sl["candidato_a_revisar"], "ruta_png": f"candidatos/{sl['slot_id']}/{sl['candidato_a_revisar']}.png",
                        "final": f"final/{sl['slot_id']}.webp"} for sl in slots if sl["re_revisar"]],
        "slots": slots,
    }


# ── ledger de saldo ─────────────────────────────────────────────────────────
def ruta_ledger(assets: Path, nombre: str = "gasto-ronda.json") -> Path:
    return assets / nombre


def leer_ledger(assets: Path, nombre: str = "gasto-ronda.json") -> dict:
    r = ruta_ledger(assets, nombre)
    return json.loads(r.read_text(encoding="utf-8")) if r.is_file() else {}


def registrar_saldo(assets: Path, fase: str, saldo: float, tope: float, nombre: str = "gasto-ronda.json", ronda: int | None = None) -> dict:
    led = leer_ledger(assets, nombre)
    led["tope_creditos"] = tope
    led[f"saldo_{fase}"] = saldo
    led[f"ts_{fase}"] = ahora()
    if led.get("saldo_inicio") is not None and led.get("saldo_fin") is not None:
        led["gastado_real_por_saldo"] = round(led["saldo_inicio"] - led["saldo_fin"], 2)
    led["gastado_por_candidatos"] = round(gasto_acumulado(assets / "candidatos", ronda), 2)
    ruta_ledger(assets, nombre).write_text(json.dumps(led, ensure_ascii=False, indent=2), encoding="utf-8")
    return led


# ── CLI ─────────────────────────────────────────────────────────────────────
def _preparar_entorno(assets: Path, plan: dict) -> None:
    """Variables que usa kie.py para anotar el gasto previo y los eventos (rutas dentro de assets/)."""
    os.environ.setdefault("SKETCH_COSTOS_BORRADOR", str(assets / "costos-borrador.jsonl"))
    os.environ.setdefault("SKETCH_REGISTRO", str(assets / "registro-kie.jsonl"))
    os.environ.setdefault("SKETCH_OFERTA_ID", str(plan.get("oferta_id", "[SUPUESTO]")))
    os.environ.setdefault("SKETCH_EJECUCION_ID", str(plan.get("ejecucion_id", "d5-imagenes-r1")))
    os.environ.setdefault("SKETCH_AD_NAME", "d5-imagenes")


def estimar_prudente(estimar: Callable[[str, dict], int]) -> Callable[[str, dict], int]:
    """Cotización = max(estimación de kie.py, créditos medidos en la práctica)."""
    return lambda modelo, entrada: max(int(estimar(modelo, entrada)), CREDITOS_MEDIDOS.get(modelo, 0))


def estimador_por_defecto() -> Callable[[str, dict], int]:
    """Cotización de créditos sin red: ``estimar_creditos`` de kie.py (si se puede importar) o 0, siempre con el mínimo medido por modelo."""
    try:
        est = cargar_kie().estimar_creditos
    except Exception:  # noqa: BLE001 - p. ej. sin `requests` en el entorno de pruebas
        est = lambda m, e: 0  # noqa: E731
    return estimar_prudente(est)


def _cliente_real(env: Path | None):
    if not cargar_clave(env):
        print("Falta KIE_API_KEY (en .env). No se llamó a Kie.", file=sys.stderr)
        raise SystemExit(2)
    kie = cargar_kie()
    return kie.Kie(), estimar_prudente(kie.estimar_creditos)


def _importar_ciclo():
    try:
        from . import ciclo_revision as cr  # noqa: PLC0415
    except ImportError:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import ciclo_revision as cr  # type: ignore[no-redef]  # noqa: PLC0415
    return cr


def _ciclo(a: argparse.Namespace, plan: dict, assets: Path) -> int:
    """Comandos del ciclo de revisión (ver ``ciclo_revision.py``): manifiesto [--ciego], revisar-prompt, aplicar-revision y finalizar. Sin Kie."""
    cr = _importar_ciclo()
    raiz = cr.raiz_oferta(assets, getattr(a, "oferta_dir", None))
    aj_ruta = getattr(a, "assets_json", None) or (raiz / "05-landing" / "assets.json")
    aj = json.loads(Path(aj_ruta).read_text(encoding="utf-8")) if Path(aj_ruta).is_file() else None
    if a.cmd == "manifiesto":
        if a.ciego:
            solo = set(filter(None, a.solo_slots.split(","))) or None
            paquete, _ = cr.paquete_ciego(plan, assets, ronda=a.ronda, solo_slots=solo, solo_re_revisar=a.solo_re_revisar, oferta_dir=a.oferta_dir, assets_json=aj)
            ruta = cr.dir_ciega(assets) / f"ronda{paquete['ronda']}" / "paquete-ciego.json"
            print(json.dumps({"paquete_ciego": str(ruta), "ronda": paquete["ronda"], "slots": [s["slot_id"] for s in paquete["slots"]],
                              "candidatos": sum(len(s["candidatos"]) for s in paquete["slots"])}, ensure_ascii=False))
            return 0
        estados = cr.estado_slots(plan, assets)
        ledgers = {f"ronda{n}": leer_ledger(assets, "gasto-ronda.json" if n == 1 else f"gasto-ronda{n}.json") for n in (1, 2, 3, 4, 5)}
        man = construir_manifiesto(plan, assets, {k: v for k, v in ledgers.items() if v}, estados, lambda s: cr.resolver_ilustrativa(s, raiz, aj))
        salida = a.salida or assets / "paquete-revision.json"
        salida.write_text(json.dumps(man, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"escrito {salida}")
        return 0
    if a.cmd == "revisar-prompt":
        ronda = a.ronda or max([int(p.name[5:]) for p in cr.dir_ciega(assets).glob("ronda*") if p.name[5:].isdigit()] or [0])
        paquete = cr.dir_ciega(assets) / f"ronda{ronda}" / "paquete-ciego.json"
        if not paquete.is_file():
            print(f"no hay paquete ciego de la ronda {ronda}: ejecuta antes `manifiesto --ciego`", file=sys.stderr)
            return 2
        print(cr.escribir_prompt_revisor(paquete))
        return 0
    if a.cmd == "aplicar-revision":
        try:
            raw = json.loads(Path(a.revision).read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            print(f"REVISIÓN RECHAZADA: JSON ilegible ({e})", file=sys.stderr)
            return 3
        try:
            res = cr.aplicar_revision(plan, assets, raw, plan_ruta=a.plan, ronda=a.ronda, estimar=estimador_por_defecto(), tope=a.tope, gastado=a.gastado,
                                      n=a.n, max_intentos=a.max_intentos, sobrescribir=a.sobrescribir)
        except cr.RevisionRechazada as e:
            print("REVISIÓN RECHAZADA (no se aplicó nada; devuélvela al revisor):", file=sys.stderr)
            for err in e.errores:
                print(f"  - {err}", file=sys.stderr)
            return 3
        estados = cr.estado_slots(plan, assets)
        ledgers = {f"ronda{n}": leer_ledger(assets, "gasto-ronda.json" if n == 1 else f"gasto-ronda{n}.json") for n in (1, 2, 3, 4, 5)}
        man = construir_manifiesto(plan, assets, {k: v for k, v in ledgers.items() if v}, estados, lambda s: cr.resolver_ilustrativa(s, raiz, aj))
        (assets / "paquete-revision.json").write_text(json.dumps(man, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0
    res = cr.finalizar(plan, assets, aj, incluir_pendientes=a.incluir_pendientes, oferta_dir=a.oferta_dir)
    for aviso in res["avisos"]:
        print(f"AVISO: {aviso}", file=sys.stderr)
    print(json.dumps({k: res[k] for k in ("aprobados", "manifiesto")} | {"no_aprobados": [n["slot_id"] for n in res["no_aprobados"]]}, ensure_ascii=False))
    return 0 if res["aprobados"] or a.incluir_pendientes else 4


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Ranuras de imagen con Kie.ai (candidatos con tope de créditos).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for nombre in ("generar", "reintentar", "elegir", "manifiesto", "saldo", "derivar", "recomprobar"):
        sp = sub.add_parser(nombre)
        if nombre != "saldo":
            sp.add_argument("plan", type=Path)
        sp.add_argument("--assets", type=Path, required=True, help="carpeta assets/ de la oferta")
        sp.add_argument("--env", type=Path, default=None)
        sp.add_argument("--tope", type=float, default=TOPE_DEFECTO)
        if nombre == "generar":
            sp.add_argument("--solo", default="")
            sp.add_argument("--seco", action="store_true", help="solo cotiza, no envía")
        if nombre in ("reintentar", "elegir", "derivar"):
            sp.add_argument("--slot", required=True)
        if nombre == "derivar":
            sp.add_argument("--desde", type=Path, required=True, help="PNG ya compuesto")
            sp.add_argument("--base", required=True, help="candidato de Kie usado como placa")
            sp.add_argument("--nombre", required=True)
            sp.add_argument("--ronda", type=int, default=None, help="ronda del candidato derivado (por defecto, la del plan)")
        if nombre == "reintentar":
            sp.add_argument("--modelo", required=True)
            sp.add_argument("--correccion", required=True)
        if nombre == "elegir":
            sp.add_argument("--candidato", required=True)
            sp.add_argument("--motivo", required=True)
        if nombre == "manifiesto":
            sp.add_argument("--salida", type=Path, default=None)
        if nombre == "saldo":
            sp.add_argument("--fase", choices=("inicio", "fin"), required=True)
            sp.add_argument("--ledger", default="gasto-ronda.json")
            sp.add_argument("--ronda", type=int, default=None, help="cuenta solo los candidatos de esa ronda")
    sp = sub.choices["manifiesto"]
    sp.add_argument("--ciego", action="store_true", help="paquete de revisión CIEGO (sin prompts, modelos, créditos, OCR ni elección del Maker)")
    sp.add_argument("--solo-slots", default="", help="solo estos slots (separados por comas)")
    sp.add_argument("--solo-re-revisar", action="store_true", help="solo slots rehechos o sin revisar")
    sp.add_argument("--ronda", type=int, default=None)
    sp.add_argument("--oferta-dir", type=Path, default=None, help="carpeta de la oferta (por defecto, dos niveles sobre assets/)")
    sp.add_argument("--assets-json", type=Path, default=None)
    rp = sub.add_parser("revisar-prompt", help="escribe las instrucciones del agente revisor junto al paquete ciego")
    rp.add_argument("plan", type=Path)
    rp.add_argument("--assets", type=Path, required=True)
    rp.add_argument("--ronda", type=int, default=None, help="por defecto, el último paquete ciego")
    ar = sub.add_parser("aplicar-revision", help="valida el JSON del revisor, lo guarda y emite el plan de reintentos")
    ar.add_argument("plan", type=Path)
    ar.add_argument("revision", type=Path)
    ar.add_argument("--assets", type=Path, required=True)
    ar.add_argument("--ronda", type=int, default=None)
    ar.add_argument("--tope", type=float, default=None)
    ar.add_argument("--gastado", type=float, default=0.0)
    ar.add_argument("--n", type=int, default=1, help="intentos propuestos por slot REHACER")
    ar.add_argument("--max-intentos", type=int, default=3)
    ar.add_argument("--sobrescribir", action="store_true")
    fz = sub.add_parser("finalizar", help="final/ y manifiesto-final.json solo con slots aprobados")
    fz.add_argument("plan", type=Path)
    fz.add_argument("--assets", type=Path, required=True)
    fz.add_argument("--assets-json", type=Path, default=None)
    fz.add_argument("--oferta-dir", type=Path, default=None)
    fz.add_argument("--incluir-pendientes", action="store_true", help="incluye también los no aprobados (estado «asignado»)")
    a = ap.parse_args(argv)
    assets = a.assets.resolve()
    try:
        if a.cmd == "saldo":
            cliente, _ = _cliente_real(a.env)
            led = registrar_saldo(assets, a.fase, cliente.creditos(), a.tope, a.ledger, a.ronda)
            print(json.dumps(led, ensure_ascii=False))
            return 0
        plan = cargar_plan(a.plan)
        if a.cmd in ("manifiesto", "revisar-prompt", "aplicar-revision", "finalizar"):
            return _ciclo(a, plan, assets)
        if a.cmd == "recomprobar":
            print(f"recomprobados {recomprobar(plan, assets)} candidatos")
            return 0
        if a.cmd == "derivar":
            slot = next((s for s in plan["slots"] if s["slot_id"] == a.slot), None)
            if slot is None:
                print(f"no existe el slot {a.slot}", file=sys.stderr)
                return 2
            registrar_derivado({**plan, "ronda": a.ronda} if a.ronda else plan, slot, assets, a.desde, a.nombre, a.base)
            return 0
        if a.cmd == "elegir":
            for s in plan["slots"]:
                if s["slot_id"] == a.slot:
                    s["seleccion_maker"] = {"candidato": a.candidato, "motivo": a.motivo}
                    Path(a.plan).write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
                    return 0
            print(f"no existe el slot {a.slot}", file=sys.stderr)
            return 2
        _preparar_entorno(assets, plan)
        if a.cmd == "generar" and a.seco:
            from types import SimpleNamespace  # noqa: PLC0415
            est = estimar_prudente(cargar_kie().estimar_creditos)
            hechos = ejecutar_plan(SimpleNamespace(), lambda m, e: est(m, e), plan, assets, a.tope, set(filter(None, a.solo.split(","))), seco=True)
            print(json.dumps({"cotizado_total": sum(h["cotizado"] for h in hechos), "candidatos": hechos}, ensure_ascii=False))
            return 0
        cliente, estimar = _cliente_real(a.env)
        if a.cmd == "generar":
            ejecutar_plan(cliente, estimar, plan, assets, a.tope, set(filter(None, a.solo.split(","))))
        else:  # reintentar
            slot = next((s for s in plan["slots"] if s["slot_id"] == a.slot), None)
            if slot is None:
                print(f"no existe el slot {a.slot}", file=sys.stderr)
                return 2
            generar_candidato(cliente, estimar, plan, slot, a.modelo, assets, a.tope, correccion=a.correccion)
        return 0
    except TopeExcedido as e:
        print(f"TOPE: {e}", file=sys.stderr)
        return 5
    except PlanInvalido as e:
        print(f"PLAN: {e}", file=sys.stderr)
        return 2
    except Exception as e:  # noqa: BLE001
        print(f"KIE: {type(e).__name__}: {str(e)[:300]}", file=sys.stderr)
        return 6


if __name__ == "__main__":
    sys.exit(main())
