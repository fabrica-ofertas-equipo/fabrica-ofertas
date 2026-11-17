"""Voces de los personajes. Cada personaje tiene UNA voz fija en todo el sketch (consistencia).

Proveedores:
- google     : Google AI Studio / Gemini API (GEMINI_API_KEY). Modelo gemini-3.8-flash-tts (o
               gemini-3.8-flash-lite-tts, más barato). Voz = nombre prebuilt (Puck, Kore…) o el ID de
               una voz diseñada en AI Studio (voice_…). El acento se fija en la voz diseñada.
               [etiqueta] al inicio del texto → «style» de la línea (cómo se dice).
               <sigh>, <laugh>, <whispering>, <short pause>… → etiquetas sonoras dentro del texto
               (en inglés y entre < >).
- elevenlabs : API directa (ELEVENLABS_API_KEY). Modelo eleven_v3; [etiquetas] dentro del texto.
- kie        : ElevenLabs v3 vía Kie.ai (modelo elevenlabs/text-to-dialogue-v3).
- say        : voz del sistema de macOS, gratis y offline. Solo para animatic / probar tiempos.
"""
from __future__ import annotations

import base64
import os
import re
import time
from pathlib import Path

import requests

from .kie import Kie
from .util import run

ETIQUETA = re.compile(r"\[[^\]]*\]")
SONIDO = re.compile(r"<[^>]*>")
GEMINI = "https://generativelanguage.googleapis.com/v1beta"

# 30 voces prebuilt de Gemini TTS (nombre – carácter, según la doc oficial).
# El género es aproximado (no figura en la doc): solo sirve para preseleccionar en la audición.
VOCES_GOOGLE = {
    "Zephyr": ("Bright", "f"), "Puck": ("Upbeat", "m"), "Charon": ("Informative", "m"), "Kore": ("Firm", "f"),
    "Fenrir": ("Excitable", "m"), "Leda": ("Youthful", "f"), "Orus": ("Firm", "m"), "Aoede": ("Breezy", "f"),
    "Callirrhoe": ("Easy-going", "f"), "Autonoe": ("Bright", "f"), "Enceladus": ("Breathy", "m"),
    "Iapetus": ("Clear", "m"), "Umbriel": ("Easy-going", "m"), "Algieba": ("Smooth", "m"),
    "Despina": ("Smooth", "f"), "Erinome": ("Clear", "f"), "Algenib": ("Gravelly", "m"),
    "Rasalgethi": ("Informative", "m"), "Laomedeia": ("Upbeat", "f"), "Achernar": ("Soft", "f"),
    "Alnilam": ("Firm", "m"), "Schedar": ("Even", "m"), "Gacrux": ("Mature", "f"),
    "Pulcherrima": ("Forward", "f"), "Achird": ("Friendly", "m"), "Zubenelgenubi": ("Casual", "m"),
    "Vindemiatrix": ("Gentle", "f"), "Sadachbia": ("Lively", "m"), "Sadaltager": ("Knowledgeable", "m"),
    "Sulafat": ("Warm", "f"),
}


def texto_limpio(t: str) -> str:
    """Texto sin etiquetas de emoción ni sonidos (para subtítulos y para `say`)."""
    return re.sub(r"\s+", " ", SONIDO.sub("", ETIQUETA.sub("", t))).strip()


def extension(voz: dict) -> str:
    return ".wav" if voz.get("proveedor") == "google" else ".mp3"


def sintetizar(texto: str, voz: dict, destino: Path, kie: Kie | None = None) -> Path:
    prov = voz.get("proveedor", "google")
    destino.parent.mkdir(parents=True, exist_ok=True)
    if prov == "google":
        return _google(texto, voz, destino)
    if prov == "elevenlabs":
        return _elevenlabs(texto, voz, destino)
    if prov == "kie":
        if kie is None:
            kie = Kie()
        entrada = {
            "dialogue": [{"text": texto, "voice": voz["voice_id"]}],
            "stability": voz.get("estabilidad", 0.5),
        }
        if voz.get("idioma"):
            entrada["language_code"] = voz["idioma"]
        kie.generar("elevenlabs/text-to-dialogue-v3", entrada, destino, etiqueta=destino.stem, max_seg=600)
        return destino
    if prov == "say":
        aiff = destino.with_suffix(".aiff")
        cmd = ["say", "-o", str(aiff)]
        if voz.get("voice_id"):
            cmd += ["-v", voz["voice_id"]]
        if voz.get("velocidad"):
            cmd += ["-r", str(voz["velocidad"])]
        run(cmd + [texto_limpio(texto)])
        run(["ffmpeg", "-v", "error", "-y", "-i", str(aiff), str(destino)])
        aiff.unlink(missing_ok=True)
        return destino
    raise ValueError(f"Proveedor de voz desconocido: {prov}")


def _elevenlabs(texto: str, voz: dict, destino: Path) -> Path:
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        raise RuntimeError("Falta ELEVENLABS_API_KEY en sketch-ia/.env (o usá proveedor: kie / say)")
    modelo = voz.get("modelo", "eleven_v3")
    cuerpo: dict = {"text": texto, "model_id": modelo}
    ajustes = {}
    if "estabilidad" in voz:
        ajustes["stability"] = voz["estabilidad"]   # en v3: 0 (creativa) · 0.5 (natural) · 1 (robusta)
    if "similitud" in voz:
        ajustes["similarity_boost"] = voz["similitud"]
    if "estilo" in voz:
        ajustes["style"] = voz["estilo"]
    if "velocidad" in voz:
        ajustes["speed"] = voz["velocidad"]
    if ajustes:
        cuerpo["voice_settings"] = ajustes
    if voz.get("idioma"):
        cuerpo["language_code"] = voz["idioma"]
    r = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voz['voice_id']}",
        params={"output_format": "mp3_44100_128"},
        headers={"xi-api-key": key, "Content-Type": "application/json"},
        json=cuerpo,
        timeout=180,
    )
    if r.status_code != 200:
        raise RuntimeError(f"ElevenLabs {r.status_code}: {r.text[:400]}")
    destino.write_bytes(r.content)
    return destino


# ── Google AI Studio (Gemini TTS, Interactions API) ─────────────────────────
def _clave_google() -> str:
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        raise RuntimeError("Falta GEMINI_API_KEY en sketch-ia/.env (clave de https://aistudio.google.com/apikey)")
    return key


def _google(texto: str, voz: dict, destino: Path) -> Path:
    """Una línea = una llamada. El texto se lee literal: las indicaciones van en «style», nunca en el texto."""
    estilos = [m.strip("[] ") for m in ETIQUETA.findall(texto)]
    if voz.get("estilo_base"):
        estilos.insert(0, voz["estilo_base"])
    transcripcion = re.sub(r"\s+", " ", ETIQUETA.sub("", texto)).strip()
    parte = {"type": "text", "text": transcripcion}
    if estilos:
        parte["annotations"] = [{"type": "speech_metadata", "style": ", ".join(estilos)}]
    cuerpo = {
        "model": voz.get("modelo", "gemini-3.8-flash-tts"),
        "input": [{"type": "user_input", "content": [parte]}],
        "response_format": {"type": "audio", "mime_type": "audio/wav"},
        "generation_config": {"speech_config": [{"voice": voz["voice_id"]}]},
    }
    for intento in range(6):  # 429/5xx son transitorios: espera creciente y reintenta
        try:
            r = requests.post(f"{GEMINI}/interactions", headers={"x-goog-api-key": _clave_google()}, json=cuerpo, timeout=180)
        except requests.RequestException as e:
            if intento == 5:
                raise RuntimeError(f"Gemini TTS sin conexión: {e}") from e
            time.sleep(2 ** intento * 2)
            continue
        if r.status_code in (429, 500, 502, 503, 504) and intento < 5:
            print(f"    · Gemini {r.status_code}, reintento en {2 ** intento * 2} s", flush=True)
            time.sleep(2 ** intento * 2)
            continue
        break
    if r.status_code != 200:
        raise RuntimeError(f"Gemini TTS {r.status_code}: {r.text[:500]}")
    datos = r.json()
    audios = [c for s in datos.get("steps", []) if s.get("type") == "model_output"
              for c in s.get("content", []) if c.get("type") == "audio"]
    if not audios and datos.get("output_audio"):
        audios = [datos["output_audio"]]
    if not audios:
        raise RuntimeError(f"Gemini TTS no devolvió audio: {str(datos)[:500]}")
    crudo = base64.b64decode(audios[-1]["data"])
    if crudo[:4] != b"RIFF":  # PCM sin cabecera (audio/l16, 24 kHz mono 16 bit) → lo envolvemos en WAV
        pcm = destino.with_suffix(".pcm")
        pcm.write_bytes(crudo)
        run(["ffmpeg", "-v", "error", "-y", "-f", "s16le", "-ar", "24000", "-ac", "1", "-i", str(pcm), str(destino)])
        pcm.unlink(missing_ok=True)
    else:
        destino.write_bytes(crudo)
    return destino


def listar_voces_google(filtro: str | None = None) -> list[dict]:
    """Biblioteca de voces de AI Studio (+ las tuyas). `filtro` busca en acento, idioma, género y descripción.
    La API no filtra bien por parámetros: se bajan todas las páginas y se filtra acá."""
    voces, token = [], None
    while True:
        r = requests.get(f"{GEMINI}/voices", headers={"x-goog-api-key": _clave_google()},
                         params={"page_token": token} if token else {}, timeout=60)
        if r.status_code != 200:
            raise RuntimeError(f"Gemini voices {r.status_code}: {r.text[:500]}")
        d = r.json()
        voces += d.get("voices", [])
        token = d.get("next_page_token") or d.get("nextPageToken")
        if not token:
            break
    if filtro:
        terminos = filtro.lower().split()
        voces = [v for v in voces if all(t in " ".join(str(x) for x in v.values()).lower() for t in terminos)]
    return voces


def efecto_elevenlabs(texto: str, destino: Path, duracion_s: float | None = None, influencia: float = 0.5) -> Path:
    """ElevenLabs Sound Effects: descripción en inglés → mp3. duracion_s entre 0,5 y 30 (None = automática)."""
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        raise RuntimeError("Falta ELEVENLABS_API_KEY en sketch-ia/.env")
    cuerpo = {"text": texto, "prompt_influence": influencia}
    if duracion_s:
        cuerpo["duration_seconds"] = max(0.5, min(30.0, float(duracion_s)))
    for intento in range(4):
        r = requests.post("https://api.elevenlabs.io/v1/sound-generation", headers={"xi-api-key": key},
                          params={"output_format": "mp3_44100_128"}, json=cuerpo, timeout=180)
        if r.status_code in (429, 500, 502, 503) and intento < 3:
            time.sleep(3 * (intento + 1))
            continue
        break
    if r.status_code != 200:
        raise RuntimeError(f"ElevenLabs SFX {r.status_code}: {r.text[:400]}")
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(r.content)
    return destino

