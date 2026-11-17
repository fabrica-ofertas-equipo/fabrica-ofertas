"""Pasos del pipeline de un sketch animado (formato «interrogatorio familiar» y similares).

guion.yaml → personajes (hojas) → escenarios → keyframes → voces → animar → montar (Remotion)
Cada paso deja sus archivos en la carpeta del proyecto y se salta lo que ya existe (usá --forzar para rehacer).
"""
from __future__ import annotations

import math
import re
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import yaml

from .kie import Kie
import os

from .util import MOTION, a_wav, duracion, guardar_json, leer_json, normalizar_pico, run, voz_sistema
from .voces import VOCES_GOOGLE, extension, sintetizar, texto_limpio

DEF_MODELOS = {
    "imagen": "nano-banana-pro",          # hojas de personaje, escenarios y keyframes (hasta 8 referencias)
    "resolucion_imagen": "2K",
    "dialogo": "kling/ai-avatar-pro",     # imagen + audio → plano hablando con lip-sync (1080p)
    "accion": "kling-3.0/video",          # imagen → plano sin diálogo (b-roll, reacciones, gestos)
    "modo_accion": "std",                 # std | pro | 4K (kling-3.0)
    "paralelo": 8,
}

NEGATIVO = "No text, no captions, no subtitles, no logos, no watermark, no split panels, no borders."


# ── guion ───────────────────────────────────────────────────────────────────
class Proyecto:
    def __init__(self, carpeta: str | Path):
        self.dir = Path(carpeta).resolve()
        f = self.dir / "guion.yaml"
        if not f.exists():
            raise SystemExit(f"No existe {f}")
        self.g = yaml.safe_load(f.read_text())
        self.slug = re.sub(r"[^a-z0-9-]+", "-", self.dir.name.lower()).strip("-")
        self.m = {**DEF_MODELOS, **(self.g.get("modelos") or {})}
        self.fps = int(self.g.get("fps", 30))
        self.estado_f = self.dir / "trabajo" / "estado.json"
        self.estado = leer_json(self.estado_f, {"audio": {}, "tareas": {}})
        for p in self.planos:
            p.setdefault("personajes", [p["habla"]] if p.get("habla") else [])
        # Contrato D6: registro de gasto antes de cada envío (06-creativos/costos.jsonl) y bitácora local.
        d6 = self.g.get("d6") or {}
        os.environ["SKETCH_REGISTRO"] = str(self.dir / "trabajo" / "gasto.jsonl")
        if d6.get("costos_borrador"):
            os.environ["SKETCH_COSTOS_BORRADOR"] = str(self.ruta_relativa(d6["costos_borrador"]))
        for k, env in (("oferta_id", "SKETCH_OFERTA_ID"), ("ad_name", "SKETCH_AD_NAME"),
                       ("ejecucion_id", "SKETCH_EJECUCION_ID"), ("moneda", "SKETCH_MONEDA")):
            if d6.get(k):
                os.environ[env] = str(d6[k])

    # rutas
    def d(self, *partes) -> Path:
        p = self.dir.joinpath(*partes)
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def ruta_relativa(self, r: str | None) -> Path | None:
        if not r:
            return None
        p = Path(r)
        return p if p.is_absolute() else (self.dir / p).resolve()

    @property
    def planos(self) -> list[dict]:
        return self.g["planos"]

    @property
    def personajes(self) -> dict:
        return self.g.get("personajes") or {}

    @property
    def escenarios(self) -> dict:
        return self.g.get("escenarios") or {}

    def guardar_estado(self):
        guardar_json(self.estado_f, self.estado)

    def filtrar(self, solo: str | None) -> list[dict]:
        if not solo:
            return self.planos
        ids = set(solo.split(","))
        return [p for p in self.planos if p["id"] in ids]


def _estilo(pr: Proyecto) -> str:
    return " ".join((pr.g.get("estilo_visual") or "").split())


def _imagen(kie: Kie, pr: Proyecto, prompt: str, refs: list[Path], destino: Path, ratio: str, etiqueta: str):
    modelo = pr.m["imagen"]
    urls = [kie.subir(r) for r in refs if r and r.exists()]
    if not urls and (modelo == "gpt-image-2-image-to-image" or modelo.startswith("seedream/")):
        raise SystemExit(f"{modelo} necesita al menos una imagen de referencia")
    if modelo == "nano-banana-pro":
        entrada = {"prompt": prompt, "image_input": urls[:8], "aspect_ratio": ratio,
                   "resolution": pr.m["resolucion_imagen"], "output_format": "png"}
    elif modelo == "nano-banana-2":
        entrada = {"prompt": prompt, "image_input": urls[:10], "aspect_ratio": ratio,
                   "resolution": pr.m["resolucion_imagen"], "output_format": "png"}
    elif modelo == "gpt-image-2-image-to-image":
        entrada = {"prompt": prompt, "input_urls": urls[:16], "aspect_ratio": ratio, "resolution": pr.m["resolucion_imagen"]}
    elif modelo.startswith("seedream/"):
        entrada = {"prompt": prompt[:5000], "image_urls": urls[:10], "aspect_ratio": ratio, "quality": "high", "output_format": "png"}
    else:
        raise SystemExit(f"Modelo de imagen no soportado: {modelo}")
    kie.generar(modelo, entrada, destino, etiqueta=etiqueta, max_seg=900)


def _en_paralelo(pr: Proyecto, trabajos: list[tuple[str, callable]]):
    errores = []
    with ThreadPoolExecutor(max_workers=int(pr.m["paralelo"])) as ex:
        fut = {ex.submit(fn): nombre for nombre, fn in trabajos}
        for f in as_completed(fut):
            try:
                f.result()
            except Exception as e:  # noqa: BLE001
                errores.append(f"{fut[f]}: {e}")
                print(f"  ✗ {fut[f]}: {e}", flush=True)
    if errores:
        print(f"\n{len(errores)} con error. Volvé a correr el mismo comando para reintentar solo esos.")


# ── 1. personajes ───────────────────────────────────────────────────────────
def personajes(pr: Proyecto, forzar=False, solo: str | None = None, variantes: int = 1):
    kie = Kie()
    trabajos = []
    for pid, pj in pr.personajes.items():
        if solo and pid not in solo.split(","):
            continue
        ref = pr.ruta_relativa(pj.get("referencia"))
        for v in range(1, variantes + 1):
            destino = pr.d("personajes", f"{pid}.png" if variantes == 1 else f"{pid}_v{v}.png")
            if destino.exists() and not forzar:
                print(f"  = {destino.name} ya existe")
                continue
            base = ("Use the attached photo ONLY as likeness reference for this person: keep face shape, hairstyle, "
                    "skin tone and distinctive features, but restyle them completely as a stylized 3D animated character. "
                    if ref else "")
            prompt = (
                f"{_estilo(pr)} Character model sheet for an animated feature film. {base}"
                f"Character: {pj['nombre']} — {' '.join(pj['descripcion'].split())} "
                "Layout on a plain neutral light-grey studio background: left, full body front view standing; centre, "
                "three-quarter view from the waist up; right column, three head close-ups showing neutral, angry and "
                "surprised expressions. Exactly the same character, outfit and proportions in every panel. "
                "Soft even studio lighting. " + NEGATIVO
            )
            trabajos.append((destino.name, lambda p=prompt, r=ref, d=destino: _imagen(kie, pr, p, [r] if r else [], d, "16:9", d.stem)))
    _en_paralelo(pr, trabajos)


# ── 2. escenarios ───────────────────────────────────────────────────────────
def escenarios(pr: Proyecto, forzar=False):
    kie = Kie()
    trabajos = []
    for eid, es in pr.escenarios.items():
        destino = pr.d("escenarios", f"{eid}.png")
        if destino.exists() and not forzar:
            print(f"  = {destino.name} ya existe")
            continue
        prompt = (f"{_estilo(pr)} Establishing shot of an empty set from an animated feature film, vertical 9:16 composition. "
                  f"Set: {' '.join(es['descripcion'].split())} No characters, no people. " + NEGATIVO)
        refs = [pr.ruta_relativa(es["referencia"])] if es.get("referencia") else []
        trabajos.append((destino.name, lambda p=prompt, d=destino, r=refs: _imagen(kie, pr, p, r, d, "9:16", d.stem)))
    _en_paralelo(pr, trabajos)


# ── 3. keyframes ────────────────────────────────────────────────────────────
# Encuadre: el modelo tiende a copiar la composición de la imagen del set, así que el tamaño de plano
# se pide de forma explícita y los planos cerrados se generan SIN la imagen del set.
ENCUADRES = [  # (clave en «encuadre», instrucción, ¿es cerrado?)
    ("extreme close-up", "EXTREME CLOSE-UP: only the face fills the whole frame, cropped from the forehead to the chin; "
                         "the background is a soft blur", True),
    ("medium close-up", "MEDIUM CLOSE-UP: framed from the middle of the chest up, the head in the upper third; "
                        "background softly out of focus", True),
    ("close-up", "CLOSE-UP: head and the top of the shoulders fill the frame, the face takes about half of the image "
                 "height, eyes on the upper third; background strongly out of focus (bokeh)", True),
    ("medium shot", "MEDIUM SHOT: camera close to the character, framed from the waist up, the character fills most "
                    "of the frame width and the head is in the upper third; background out of focus", True),
    ("over-the-shoulder", "OVER-THE-SHOULDER SHOT as described; the foreground shoulder is blurred", False),
    ("medium-wide", "MEDIUM-WIDE SHOT as described", False),
    ("wide", "WIDE SHOT as described, the whole action readable", False),
    ("low shot", "LOW ANGLE SHOT at table height as described", False),
]


def _encuadre(p: dict) -> tuple[str, bool]:
    e = (p.get("encuadre") or "medium shot").lower()
    for clave, instr, cerrado in ENCUADRES:
        if clave in e:
            return instr, cerrado
    return "", False


def _elenco(pr: Proyecto, p: dict, cerrado: bool) -> list[str]:
    """Planos abiertos: todo el elenco como referencia (si no, el modelo inventa extras para «la familia»)."""
    ids = list(p.get("personajes", []))
    if p.get("elenco") == "solo":   # contraplanos y planos dirigidos: solo los personajes listados
        return ids
    if not cerrado and pr.g.get("elenco_completo_en_generales", True) and pr.g.get("puesta"):
        ids += [x for x in pr.personajes if x not in ids]
    return ids


def _prompt_keyframe(pr: Proyecto, p: dict, con_set: bool, ids: list[str] | None = None, cerrado: bool = False) -> str:
    es = pr.escenarios.get(p.get("escenario"), {})
    ids = ids if ids is not None else p.get("personajes", [])
    quienes = []
    for k, pid in enumerate(ids, start=1):
        quienes.append(f"{pr.personajes[pid]['nombre']} (matches reference image {k})")
    hablando = ""
    if p.get("habla"):
        hablando = (f"{pr.personajes[p['habla']]['nombre']} is speaking, mouth slightly open mid-word, "
                    f"expression: {p.get('emocion', 'natural')}. ")
    instr, _ = _encuadre(p)
    if p.get("elenco") == "solo":
        puesta = (f"Only {', '.join(pr.personajes[i]['nombre'] for i in ids)} in frame; the rest of the family is off-screen. "
                  "The background is the dining room, softly blurred.")
    elif cerrado:
        nombres = " and ".join(pr.personajes[i]["nombre"] for i in ids) or "the subject"
        puesta = (f"Tight framing on {nombres}, seated at the dining table and filling most of the frame. "
                  "Any other family member is outside the frame. The background is the dining room, softly blurred.")
    else:
        puesta = " ".join((pr.g.get("puesta") or "").split()) + " Every person visible is one of the reference characters."
    set_txt = ("The last reference image shows the set: use it ONLY for decor, colors and lighting. "
               "Do NOT copy its camera angle or composition; reframe completely as asked. ") if con_set else ""
    return (
        f"{_estilo(pr)} Single vertical 9:16 frame from an animated feature film. "
        f"CAMERA: {instr} Requested shot: {p.get('encuadre', 'medium shot')}. "
        f"In frame: {', '.join(quienes) if quienes else 'no characters'}. "
        f"Action: {p.get('accion', '')} {hablando}"
        f"Staging: {puesta} "
        f"Location (seen behind the characters): {' '.join(es.get('descripcion', '').split())} "
        "Only the listed characters appear: no other people, no extras, no background figures. "
        "Every character must match their reference sheet exactly (face, hair, outfit, body proportions), "
        "but in a new pose and camera angle, never the sheet layout. "
        f"{set_txt}" + NEGATIVO
    )


def keyframes(pr: Proyecto, forzar=False, solo: str | None = None):
    kie = Kie()
    trabajos = []
    for p in pr.filtrar(solo):
        destino = pr.d("keyframes", f"{p['id']}.png")
        if destino.exists() and not forzar:
            print(f"  = {destino.name} ya existe")
            continue
        _, cerrado = _encuadre(p)
        ids = _elenco(pr, p, cerrado)
        refs = [pr.d("personajes", f"{pid}.png") for pid in ids]
        faltan = [r.name for r in refs if not r.exists()]
        if faltan:
            raise SystemExit(f"{p['id']}: faltan hojas de personaje {faltan}. Corré primero: personajes")
        con_set = bool(p.get("escenario")) and not cerrado and p.get("usar_set", True)
        if con_set:
            refs.append(pr.d("escenarios", f"{p['escenario']}.png"))
        prompt = p.get("prompt_imagen") or _prompt_keyframe(pr, p, con_set, ids, cerrado)
        trabajos.append((p["id"], lambda pp=prompt, r=refs, d=destino: _imagen(kie, pr, pp, r, d, "9:16", d.stem)))
    _en_paralelo(pr, trabajos)


# ── 4. voces ────────────────────────────────────────────────────────────────
def voces(pr: Proyecto, forzar=False, solo: str | None = None, animatic=False):
    kie = None
    for p in pr.filtrar(solo):
        if not p.get("habla"):
            continue
        pj = pr.personajes[p["habla"]]
        voz = pj.get("voz_animatic") if animatic else pj.get("voz")
        if animatic and not voz:
            voz = {"proveedor": "say", "voice_id": voz_sistema(pr.g.get("locale", "es-ES"))}
        if not voz:
            raise SystemExit(f"{p['habla']} no tiene voz definida en el guion")
        voz = dict(voz)
        if voz.get("proveedor") == "google" and pr.g.get("ritmo_voces") and "estilo_base" not in voz:
            voz["estilo_base"] = pr.g["ritmo_voces"]   # ritmo de sitcom para todo el reparto
        tag = "animatic" if animatic else "final"
        crudo = pr.d("trabajo", "voces", tag, f"{p['id']}{extension(voz)}")
        wav = pr.d("audio", tag, f"{p['id']}.wav")
        if wav.exists() and crudo.exists() and not forzar:
            print(f"  = {wav.name} ya existe")
        else:
            if voz.get("proveedor") == "kie" and kie is None:
                kie = Kie()
            print(f"  → {p['id']} ({pj['nombre']}): {texto_limpio(p['texto'])}", flush=True)
            sintetizar(p["texto"], voz, crudo, kie)
        voz_dur = a_wav(crudo, wav)                       # sin pausa: para subtítulos
        pausa = float(p.get("pausa", pr.g.get("pausa", 0.12)))
        con_pausa = pr.d("audio", tag, f"{p['id']}_pausa.wav")
        total = a_wav(crudo, con_pausa, pausa_fin=pausa)  # con pausa: lo que se anima y se monta
        pr.estado["audio"].setdefault(tag, {})[p["id"]] = {"voz": round(voz_dur, 3), "total": round(total, 3)}
    pr.guardar_estado()
    tot = sum(v["total"] for v in pr.estado["audio"].get("animatic" if animatic else "final", {}).values())
    print(f"  Diálogo total: {tot:.1f} s")


# ── 5. animar ───────────────────────────────────────────────────────────────
def _prompt_movimiento(pr: Proyecto, p: dict) -> str:
    base = p.get("movimiento") or p.get("accion", "")
    if p.get("habla"):
        nombre = pr.personajes[p["habla"]]["nombre"]
        intensidad = ("Big, exaggerated animated-feature acting: strong eyebrow movement, expressive eyes, clear head moves "
                      "and hand gestures that sell the emotion. ") if p.get("actuacion") == "intensa" else ""
        return (f"{intensidad}{nombre} says the line with {p.get('emocion', 'natural')} emotion, expressive animated-film acting, "
                f"natural blinking, subtle head and shoulder movement. {base} Static camera, no cuts. "
                "Other characters stay mostly still, only breathing and blinking. "
                "No captions, no subtitles, no on-screen text, letters or words of any kind; keep the image clean.")
    return (f"{base} Animated feature film motion, smooth and expressive. Static or very slow camera push-in, no cuts. "
            "No captions, no subtitles, no on-screen text of any kind.")


def animar(pr: Proyecto, forzar=False, solo: str | None = None):
    kie = Kie()
    trabajos = []
    for p in pr.filtrar(solo):
        destino = pr.d("clips", f"{p['id']}.mp4")
        if destino.exists() and not forzar:
            print(f"  = {destino.name} ya existe")
            continue
        kf = pr.d("keyframes", f"{p['id']}.png")
        if not kf.exists():
            print(f"  ! {p['id']}: falta keyframe, se salta")
            continue
        prompt = p.get("prompt_video") or _prompt_movimiento(pr, p)
        if p.get("habla"):
            audio = pr.d("audio", "final", f"{p['id']}_pausa.wav")
            if not audio.exists():
                print(f"  ! {p['id']}: falta audio final (corré voces), se salta")
                continue
            if duracion(audio) < 1.2:   # Kie rechaza audios muy cortos («price payAmount missing»): se rellena con silencio
                largo = pr.d("trabajo", "animar", f"{p['id']}_min.wav")
                run(["ffmpeg", "-v", "error", "-y", "-i", str(audio), "-af", "apad=whole_dur=1.2", str(largo)])
                audio = largo
            modelo = p.get("modelo") or pr.m["dialogo"]

            def tarea(p=p, kf=kf, audio=audio, modelo=modelo, prompt=prompt, destino=destino):
                img, aud = kie.subir(kf), kie.subir(audio)
                if modelo.startswith("kling/ai-avatar"):
                    entrada = {"image_url": img, "audio_url": aud, "prompt": prompt[:5000]}
                elif modelo == "infinitalk/from-audio":
                    entrada = {"image_url": img, "audio_url": aud, "prompt": prompt[:5000], "resolution": "720p"}
                elif modelo == "wan/2-2-a14b-speech-to-video-turbo":
                    entrada = {"image_url": img, "audio_url": aud, "prompt": prompt, "resolution": "720p"}
                else:
                    raise SystemExit(f"Modelo de diálogo no soportado: {modelo}")
                kie.generar(modelo, entrada, destino, etiqueta=p["id"], max_seg=2400, dur=duracion(audio))
        else:
            modelo = p.get("modelo") or pr.m["accion"]
            dur = float(p.get("duracion", 2.0))

            def tarea(p=p, kf=kf, modelo=modelo, prompt=prompt, destino=destino, dur=dur):
                img = kie.subir(kf)
                if modelo == "kling-3.0/video":
                    entrada = {"prompt": prompt[:2500], "image_urls": [img], "sound": False,
                               "duration": str(max(3, math.ceil(dur))), "aspect_ratio": "9:16",
                               "mode": pr.m["modo_accion"], "multi_shots": False}
                elif modelo.startswith("bytedance/seedance"):
                    # Con primer cuadro, Seedance 2.5 solo acepta «adaptive» (toma la proporción del keyframe 9:16).
                    entrada = {"prompt": prompt, "first_frame_url": img, "generate_audio": False,
                               "resolution": "720p", "aspect_ratio": "adaptive", "duration": max(4, math.ceil(dur))}
                elif modelo == "veo-3-1":
                    entrada = {"prompt": prompt, "model": "veo3_fast", "image_urls": [img],
                               "generation_type": "FIRST_AND_LAST_FRAMES_2_VIDEO", "aspect_ratio": "9:16",
                               "duration": 4 if dur <= 4 else 6 if dur <= 6 else 8}
                else:
                    raise SystemExit(f"Modelo de acción no soportado: {modelo}")
                kie.generar(modelo, entrada, destino, etiqueta=p["id"], max_seg=2400)

        trabajos.append((p["id"], tarea))
    _en_paralelo(pr, trabajos)


# ── 6. montar (Remotion) ────────────────────────────────────────────────────
def _trozos(texto: str, maxp: int) -> list[str]:
    """Parte la frase en grupos de ≤maxp palabras, cortando de preferencia tras signos de puntuación."""
    palabras = texto.split()
    grupos, actual = [], []
    for w in palabras:
        actual.append(w)
        fin_frase = re.search(r"[.!?…]$", w)
        coma = re.search(r"[,;:]$", w) and len(actual) >= 2
        if len(actual) >= maxp or fin_frase or coma:
            grupos.append(" ".join(actual))
            actual = []
    if actual:
        if grupos and len(actual) == 1 and len(grupos[-1].split()) < maxp + 1:
            grupos[-1] += " " + actual[0]
        else:
            grupos.append(" ".join(actual))
    return grupos


def _srt_t(s: float) -> str:
    ms = int(round(s * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def montar(pr: Proyecto, animatic=False, salida: str | None = None, sin_render=False):
    fps = pr.fps
    tag = "animatic" if animatic else "final"
    audio_est = pr.estado.get("audio", {}).get(tag, {})
    pub_rel = Path("sketch") / pr.slug / tag
    pub = MOTION / "public" / pub_rel
    if pub.exists():
        shutil.rmtree(pub)
    pub.mkdir(parents=True)
    sub_cfg = pr.g.get("subtitulos") or {}
    maxp = int(sub_cfg.get("palabras_max", 3))

    planos, audios, subs, sfx, cortes_musica = [], [], [], [], []
    f = 0
    for p in pr.planos:
        pid = p["id"]
        info = audio_est.get(pid)
        solapa_f = 0
        if p.get("habla"):
            if not info:
                raise SystemExit(f"{pid}: falta audio {tag}. Corré: voces{' --animatic' if animatic else ''}")
            dur_f = max(1, round(info["total"] * fps))
            if p.get("solapa") and planos:   # J-cut: la voz entra antes del corte (como en la referencia)
                solapa_f = min(round(float(p["solapa"]) * fps), max(0, planos[-1]["dur"] - 6))
                dur_f -= solapa_f
        else:
            dur_f = max(1, round(float(p.get("duracion", 1.5)) * fps))

        clip = pr.dir / "clips" / f"{pid}.mp4"
        kf = pr.dir / "keyframes" / f"{pid}.png"
        if clip.exists() and not animatic:
            recorte = float(p.get("recorte", 0))
            falta = dur_f / fps + recorte - duracion(clip)
            if falta > 0.02:   # el clip es más corto que el plano: congela el último frame lo que falte
                run(["ffmpeg", "-v", "error", "-y", "-i", str(clip), "-vf", f"tpad=stop_mode=clone:stop_duration={falta + 0.1:.3f}",
                     "-an", "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", str(pub / clip.name)])
            else:
                shutil.copy(clip, pub / clip.name)
            media = {"tipo": "video", "src": str(pub_rel / clip.name), "inicio": round(recorte * fps) + solapa_f}
        elif kf.exists():
            shutil.copy(kf, pub / kf.name)
            media = {"tipo": "imagen", "src": str(pub_rel / kf.name)}
        else:
            media = {"tipo": "vacio"}
        planos.append({"id": pid, "ini": f, "dur": dur_f, **media,
                       "nota": f"{pid} · {p.get('encuadre', '')} · {pr.personajes.get(p.get('habla'), {}).get('nombre', '')}",
                       "zoom": p.get("zoom", 1.0), "camara": p.get("camara", "fijo")})

        if p.get("habla"):
            wav = pr.dir / "audio" / tag / f"{pid}.wav"
            shutil.copy(wav, pub / wav.name)
            audios.append({"src": str(pub_rel / wav.name), "ini": f - solapa_f, "fin": f - solapa_f + round(info["voz"] * fps),
                           "vol": float(p.get("volumen", 1.0))})
            texto = p.get("subtitulo") or texto_limpio(p["texto"])
            grupos = _trozos(texto, maxp)
            ini_voz = f - solapa_f
            voz_f = round(info["voz"] * fps)
            tiempos = _tiempos_grupos(pr, tag, pid, wav, grupos)   # segundos de inicio de cada grupo (Whisper)
            if tiempos is None:   # sin Whisper: reparto proporcional a las letras
                largo = sum(len(g) for g in grupos) or 1
                tiempos, acc = [], 0
                for g in grupos:
                    tiempos.append(acc / largo * info["voz"])
                    acc += len(g)
            inicios = [ini_voz + round(x * fps) for x in tiempos]
            for k, g in enumerate(grupos):
                a = inicios[k]
                b = inicios[k + 1] if k + 1 < len(grupos) else ini_voz + voz_f + 3
                subs.append({"ini": a, "fin": max(a + 4, b), "texto": g})
        if p.get("musica") == "corta":      # silencio cómico: la música se corta durante este plano
            cortes_musica.append({"ini": f, "fin": f + dur_f})
        for k, s in enumerate(p.get("sfx") or [], start=1):
            if s.get("generar"):
                src = pr.dir / "sfx" / f"{pid}-{k}.mp3"
                if not src.exists():
                    print(f"  ! {pid}: falta el efecto generado {src.name} (corré: efectos)")
                    continue
            else:
                src = pr.ruta_relativa(s["archivo"])
            if src.exists():
                shutil.copy(src, pub / src.name)
                sfx.append({"src": str(pub_rel / src.name), "ini": f + round(float(s.get("en", 0)) * fps),
                            "vol": float(s.get("volumen", 0.35))})
        f += dur_f

    cierre = None
    if pr.g.get("cierre"):
        c = dict(pr.g["cierre"])
        dur_c = round(float(c.pop("duracion", 6)) * fps)
        cierre = {"ini": f, "dur": dur_c, **c}
        f += dur_c

    def pista(clave):
        cfg = pr.g.get(clave)
        if not cfg:
            return None
        src = pr.ruta_relativa(cfg["archivo"])
        if not src or not src.exists():
            print(f"  ! {clave}: no encuentro {src}, va sin {clave}")
            return None
        shutil.copy(src, pub / src.name)
        pista_ = {"src": str(pub_rel / src.name), "vol": float(cfg.get("volumen", 0.12))}
        if "sin_voz" in cfg:
            pista_["sinVoz"] = float(cfg["sin_voz"])      # volumen en huecos sin diálogo
        if "cierre" in cfg:
            pista_["cierre"] = float(cfg["cierre"])       # volumen durante el CTA
        return pista_

    # Música por secciones (como la referencia): cada cue cubre un tramo de planos.
    musicas = []
    rango = {x["id"]: (x["ini"], x["ini"] + x["dur"]) for x in planos}
    if cierre:
        rango["cierre"] = (cierre["ini"], cierre["ini"] + cierre["dur"])
    for cue in pr.g.get("musicas") or []:
        src = pr.ruta_relativa(cue["archivo"])
        if not src or not src.exists():
            print(f"  ! musicas: no encuentro {src}")
            continue
        shutil.copy(src, pub / src.name)
        a, b = rango[cue["desde"]][0], rango[cue.get("hasta", cue["desde"])][1]
        musicas.append({"src": str(pub_rel / src.name), "ini": a, "dur": b - a, "inicio": round(float(cue.get("inicio", 0)) * fps),
                        "vol": float(cue.get("volumen", 0.3)), "sinVoz": float(cue.get("sin_voz", cue.get("volumen", 0.3))),
                        "fundido": round(float(cue.get("fundido", 0.25)) * fps)})

    props = {
        "fps": fps, "frames": f, "planos": planos, "audios": audios, "subtitulos": subs, "sfx": sfx,
        "musica": pista("musica"), "ambiente": pista("ambiente"), "cierre": cierre, "cortesMusica": cortes_musica, "musicas": musicas,
        "estiloSub": {"y": sub_cfg.get("y", 1150), "tam": sub_cfg.get("tamano", 46)},
        "marca": _marca(pr, pub, pub_rel),
        "etiquetaIA": (pr.g.get("etiqueta_ia") or None),
        "animatic": animatic,
    }
    props_f = pr.d("trabajo", f"props-{tag}.json")
    guardar_json(props_f, props)

    # .srt de los diálogos
    srt = []
    for i, s in enumerate(subs, 1):
        srt.append(f"{i}\n{_srt_t(s['ini'] / fps)} --> {_srt_t(s['fin'] / fps)}\n{s['texto']}\n")
    nombre = salida or f"{pr.slug}{'-animatic' if animatic else ''}"
    pr.d("entrega", f"{nombre}.srt").write_text("\n".join(srt))
    print(f"  Duración: {f / fps:.1f} s · {len(planos)} planos · {len(subs)} subtítulos")

    if sin_render:
        print(f"  Props en {props_f}")
        return
    out = pr.d("entrega", f"{nombre}.mp4")
    print("  Renderizando con Remotion…", flush=True)
    run(["npx", "remotion", "render", "src/index.ts", "Sketch", str(out), f"--props={props_f}",
         "--concurrency=50%", "--log=error"], cwd=MOTION)
    print(f"  ✓ {out}")
    ad = (pr.g.get("d6") or {}).get("ad_name")
    destino_d6 = (pr.g.get("d6") or {}).get("assets_dir")
    if ad and destino_d6 and not animatic:
        dst = pr.ruta_relativa(destino_d6) / f"{ad}.mp4"
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(out, dst)
        print(f"  ✓ copiado a {dst}")


# ── costo estimado ──────────────────────────────────────────────────────────
PRECIOS = {  # USD, «desde» según kie.ai/pricing el 2026-11-06; el real sale en creditsConsumed
    "nano-banana-pro": 0.09, "nano-banana-2": 0.04, "gpt-image-2-image-to-image": 0.03,
    "kling/ai-avatar-pro": 0.0505, "infinitalk/from-audio": 0.015, "wan/2-2-a14b-speech-to-video-turbo": 0.06,
    "kling-3.0/video": 0.0755, "bytedance/seedance-2-5": 0.085,
}


def costo(pr: Proyecto):
    img = PRECIOS.get(pr.m["imagen"], 0.09)
    n_img = len(pr.personajes) + len(pr.escenarios) + len(pr.planos)
    seg_dialogo, seg_accion = 0.0, 0.0
    chars = 0
    for p in pr.planos:
        if p.get("habla"):
            info = pr.estado.get("audio", {}).get("final", {}).get(p["id"]) or pr.estado.get("audio", {}).get("animatic", {}).get(p["id"])
            seg_dialogo += info["total"] if info else max(1.2, len(texto_limpio(p["texto"]).split()) / 2.6 + 0.15)
            chars += len(p["texto"])
        else:
            seg_accion += max(3, math.ceil(float(p.get("duracion", 2))))
    c_img = n_img * img
    c_dia = seg_dialogo * PRECIOS.get(pr.m["dialogo"], 0.05)
    c_acc = seg_accion * PRECIOS.get(pr.m["accion"], 0.08)
    proveedores = {(pj.get("voz") or {}).get("proveedor", "google") for pj in pr.personajes.values()}
    # Gemini 3.8 Flash TTS: ≈ $0.000225 por segundo de audio; ElevenLabs v3 ≈ $0.10 / 1000 caracteres
    c_voz = seg_dialogo * 0.000225 if proveedores == {"google"} else chars / 1000 * 0.10
    print(f"  Imágenes  {n_img:>3} × ${img:.3f}            = ${c_img:6.2f}")
    print(f"  Diálogo   {seg_dialogo:5.1f} s × ${PRECIOS.get(pr.m['dialogo'], 0.05):.4f}/s   = ${c_dia:6.2f}  ({pr.m['dialogo']})")
    print(f"  Acción    {seg_accion:5.1f} s × ${PRECIOS.get(pr.m['accion'], 0.08):.4f}/s   = ${c_acc:6.2f}  ({pr.m['accion']})")
    print(f"  Voces     {chars} caracteres          ≈ ${c_voz:6.2f}")
    total = c_img + c_dia + c_acc + c_voz
    print(f"  TOTAL estimado (una pasada, sin rehacer planos): ${total:.2f}  · con 30 % de rehechos ≈ ${total * 1.3:.2f}")


# ── audición de voces (Google) ──────────────────────────────────────────────
def audicion(pr: Proyecto, solo: str | None = None, voces_lista: str | None = None, texto: str | None = None):
    """Dice la primera línea de cada personaje con varias voces y arma un archivo por personaje para escuchar."""
    from .voces import _clave_google
    try:
        _clave_google()
    except RuntimeError as e:
        raise SystemExit(str(e)) from None
    for pid, pj in pr.personajes.items():
        if solo and pid not in solo.split(","):
            continue
        linea = texto or next((p["texto"] for p in pr.planos if p.get("habla") == pid), "Hola, ¿cómo andás?")
        base = dict(pj.get("voz") or {})
        base["proveedor"] = "google"
        if voces_lista:
            candidatas = [v.strip() for v in voces_lista.split(",") if v.strip()]
        else:
            g = pj.get("genero")
            candidatas = [v for v, (_, gv) in VOCES_GOOGLE.items() if not g or gv == g]
        carpeta = pr.d("trabajo", "audicion", pid, "x").parent
        print(f"\n  {pj['nombre']}: «{texto_limpio(linea)}» · {len(candidatas)} voces", flush=True)
        hechos = []
        for i, v in enumerate(candidatas, 1):
            destino = carpeta / f"{i:02d}-{v}.wav"
            if not destino.exists():
                try:
                    sintetizar(linea, {**base, "voice_id": v}, destino)
                except Exception as e:  # noqa: BLE001
                    print(f"    ✗ {v}: {e}")
                    continue
            hechos.append((v, destino))
        if not hechos:
            continue
        # todas seguidas, con 0,7 s de silencio, para escucharlas de corrido
        lista = carpeta / "lista.txt"
        silencio = carpeta / "_silencio.wav"
        run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", "0.7", str(silencio)])
        partes, t = [], 0.0
        for v, d in hechos:
            norm = carpeta / f"_n-{d.name}"
            run(["ffmpeg", "-v", "error", "-y", "-i", str(d), "-ar", "24000", "-ac", "1", str(norm)])
            partes += [norm, silencio]
            print(f"    {t:5.1f} s  {v:<14} {VOCES_GOOGLE.get(v, ("biblioteca AI Studio", ""))[0]}")
            t += duracion(norm) + 0.7
        lista.write_text("".join(f"file '{p}'\n" for p in partes))
        salida_f = pr.d("trabajo", "audicion", f"{pid}.wav")
        run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lista), str(salida_f)])
        for p in carpeta.glob("_*"):
            p.unlink()
        lista.unlink()
        print(f"    → {salida_f}")


# ── efectos de sonido (ElevenLabs Sound Effects) ────────────────────────────
def efectos(pr: Proyecto, forzar=False, solo: str | None = None):
    """Genera los sfx con «generar: descripción» de cada plano → proyecto/sfx/pNN-K.mp3."""
    from .voces import efecto_elevenlabs
    n = 0
    for p in pr.filtrar(solo):
        for k, s in enumerate(p.get("sfx") or [], start=1):
            if not s.get("generar"):
                continue
            destino = pr.d("sfx", f"{p['id']}-{k}.mp3")
            if destino.exists() and not forzar:
                print(f"  = {destino.name} ya existe")
                continue
            print(f"  → {destino.name}: {s['generar'][:80]}", flush=True)
            efecto_elevenlabs(s["generar"], destino, duracion_s=s.get("dur"), influencia=s.get("influencia", 0.5))
            normalizar_pico(destino)
            n += 1
    print(f"  {n} efectos generados")


# ── recuperar tareas pagadas que se perdieron por cortes de red ─────────────
CARPETA_POR_PASO = {"keyframes": "keyframes", "animar": "clips", "personajes": "personajes", "escenarios": "escenarios"}


def recuperar(pr: Proyecto):
    """Lee los logs de trabajo/ y descarga las tareas creadas cuyo archivo no llegó (no se vuelven a pagar)."""
    import re as _re
    kie = Kie()
    vistos = {}
    for log in sorted((pr.dir / "trabajo").glob("log-*.txt")):
        for m in _re.finditer(r"→ (\S+): tarea ([0-9a-f]{32}) \(([^)]+)\)", log.read_text()):
            vistos[m.group(1)] = (m.group(2), m.group(3))
    n = 0
    for nombre, (tid, modelo) in vistos.items():
        ext = ".mp4" if ("video" in modelo or "avatar" in modelo or "infinitalk" in modelo or "seedance" in modelo or "wan/" in modelo) else ".png"
        if ext == ".mp4":
            carpeta = "clips"
        elif _re.fullmatch(r"p\d+", nombre):
            carpeta = "keyframes"
        else:
            carpeta = "personajes"
        if nombre in pr.escenarios:
            carpeta = "escenarios"
        destino = pr.dir / carpeta / f"{nombre}{ext}"
        if destino.exists():
            continue
        try:
            kie.recuperar(tid, destino, etiqueta=nombre, max_seg=900)
            n += 1
        except Exception as e:  # noqa: BLE001
            print(f"  ✗ {nombre}: {e}")
    print(f"  {n} recuperadas")


# ── tiempos reales de palabras (Whisper) para los subtítulos ────────────────
WHISPER_MODELO = Path.home() / ".cache" / "whisper" / "ggml-large-v3-turbo.bin"


def _norm(t: str) -> str:
    import unicodedata
    t = unicodedata.normalize("NFD", t.lower())
    return "".join(c for c in t if c.isalnum())


def _tiempos_grupos(pr: Proyecto, tag: str, pid: str, wav: Path, grupos: list[str]) -> list[float] | None:
    """Inicio (s) de cada grupo de subtítulo según los tiempos por palabra de Whisper, mapeados por posición de letras."""
    import shutil as _sh
    import tempfile
    if not _sh.which("whisper-cli") or not WHISPER_MODELO.exists():
        return None
    cache = pr.estado.setdefault("palabras", {}).setdefault(tag, {})
    clave = f"{wav.stat().st_mtime_ns}"
    if cache.get(pid, {}).get("clave") != clave:
        with tempfile.TemporaryDirectory() as tmp:
            w16 = Path(tmp) / "a.wav"
            run(["ffmpeg", "-v", "error", "-y", "-i", str(wav), "-ar", "16000", "-ac", "1", str(w16)])
            subprocess_run = __import__("subprocess").run
            subprocess_run(["whisper-cli", "-m", str(WHISPER_MODELO), "-l", "es", "-f", str(w16), "-ml", "1", "-sow",
                            "-oj", "-of", str(Path(tmp) / "w")], capture_output=True)
            import json as _json
            j = Path(tmp) / "w.json"
            palabras = []
            if j.exists():
                for seg in _json.loads(j.read_text()).get("transcription", []):
                    txt = _norm(seg.get("text", ""))
                    if txt:
                        palabras.append([seg["offsets"]["from"] / 1000, txt])
        cache[pid] = {"clave": clave, "palabras": palabras}
        pr.guardar_estado()
    palabras = cache[pid]["palabras"]
    if not palabras:
        return None
    # línea de tiempo de Whisper: posición relativa en letras → tiempo
    tot_w = sum(len(w) for _, w in palabras)
    pos_w, acc = [], 0
    for t, w in palabras:
        pos_w.append((acc / tot_w, t))
        acc += len(w)
    tot_g = sum(len(_norm(g)) for g in grupos) or 1
    res, acc = [], 0
    for g in grupos:
        rel = acc / tot_g
        # interpolación lineal sobre la línea de tiempo de Whisper
        t = pos_w[0][1]
        for (p0, t0), (p1, t1) in zip(pos_w, pos_w[1:] + [(1.0, pos_w[-1][1])]):
            if p0 <= rel <= p1:
                t = t0 + (t1 - t0) * ((rel - p0) / (p1 - p0) if p1 > p0 else 0)
                break
        res.append(max(0.0, t))
        acc += len(_norm(g))
    res[0] = min(res[0], palabras[0][0])
    return res


# ── marca de la oferta (D5) para el cierre y los subtítulos ──────────────────
def _marca(pr: Proyecto, pub: Path, pub_rel: Path) -> dict:
    """Colores y fuentes del cierre. Sale de `marca:` del guion, que copia 05-landing/paleta.json (D5)."""
    m = dict(pr.g.get("marca") or {})
    fuentes = []
    for f in m.pop("fuentes", []) or []:
        src = pr.ruta_relativa(f["archivo"])
        if src and src.exists():
            shutil.copy(src, pub / src.name)
            fuentes.append({"familia": f["familia"], "src": str(pub_rel / src.name), "peso": f.get("peso", "100 900")})
    m["fuentes"] = fuentes
    return m
