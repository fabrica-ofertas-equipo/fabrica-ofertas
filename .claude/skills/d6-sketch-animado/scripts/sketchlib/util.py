from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent          # .claude/skills/d6-sketch-animado/scripts/
MOTION = RAIZ / "motor"                                  # proyecto Remotion propio de la skill


def raiz_repo() -> Path:
    """Raíz del proyecto (la carpeta que contiene .claude/)."""
    for p in [RAIZ, *RAIZ.parents]:
        if (p / ".claude").is_dir() and p != Path.home():
            return p
    return Path.cwd()


def cargar_env() -> None:
    """Lee el .env de la raíz del proyecto (gitignored) sin pisar variables ya definidas."""
    for f in (raiz_repo() / ".env", RAIZ / ".env"):
        if not f.exists():
            continue
        for linea in f.read_text().splitlines():
            linea = linea.strip()
            if not linea or linea.startswith("#") or "=" not in linea:
                continue
            k, v = linea.split("=", 1)
            v = v.strip().strip('"').strip("'")
            if v:
                os.environ.setdefault(k.strip(), v)


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode != 0:
        raise RuntimeError(f"Falló: {' '.join(map(str, cmd))}\n{r.stderr[-1500:]}")
    return r


def duracion(ruta: str | Path) -> float:
    r = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(ruta)])
    return float(json.loads(r.stdout)["format"]["duration"])


def a_wav(origen: str | Path, destino: str | Path, pausa_ini: float = 0.0, pausa_fin: float = 0.0) -> float:
    """WAV 48 kHz mono: recorta silencios de borde, acorta pausas internas largas, normaliza y agrega pausas."""
    filtros = [
        "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.04",
        "areverse",
        "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.06",
        "areverse",
        # acorta pausas internas largas (> 0,3 s) que meten los TTS al «actuar»
        "silenceremove=stop_periods=-1:stop_duration=0.3:stop_threshold=-40dB:stop_silence=0.3",
        # todas las voces al mismo nivel (diálogo de reel ≈ −16 LUFS, pico −1,5 dBTP)
        "loudnorm=I=-16:TP=-1.5:LRA=11",
    ]
    if pausa_ini > 0:
        filtros.append(f"adelay={int(pausa_ini * 1000)}:all=1")
    if pausa_fin > 0:
        filtros.append(f"apad=pad_dur={pausa_fin}")
    run(["ffmpeg", "-v", "error", "-y", "-i", str(origen), "-af", ",".join(filtros), "-ar", "48000", "-ac", "1", str(destino)])
    return duracion(destino)


def normalizar_pico(ruta: str | Path, objetivo_db: float = -3.0) -> None:
    """Lleva el pico del archivo a objetivo_db (para SFX: la mezcla la decide «volumen» en el guion)."""
    r = subprocess.run(["ffmpeg", "-nostats", "-i", str(ruta), "-af", "volumedetect", "-f", "null", "/dev/null"],
                       capture_output=True, text=True)
    pico = next((float(l.split()[-2]) for l in r.stderr.splitlines() if "max_volume" in l), None)
    if pico is None or abs(pico - objetivo_db) < 0.5:
        return
    p = Path(ruta)
    tmp = p.with_name(p.stem + ".norm" + p.suffix)
    run(["ffmpeg", "-v", "error", "-y", "-i", str(p), "-af", f"volume={objetivo_db - pico:.1f}dB", str(tmp)])
    tmp.replace(p)


def hay(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def guardar_json(ruta: str | Path, datos) -> None:
    Path(ruta).parent.mkdir(parents=True, exist_ok=True)
    Path(ruta).write_text(json.dumps(datos, ensure_ascii=False, indent=1))


def leer_json(ruta: str | Path, defecto=None):
    p = Path(ruta)
    return json.loads(p.read_text()) if p.exists() else defecto


def voz_sistema(locale: str) -> str | None:
    """Voz de macOS (`say`) para el animatic según el locale (es-ES → es_ES). None = voz por defecto."""
    if not hay("say"):
        return None
    pref = locale.replace("-", "_")
    r = subprocess.run(["say", "-v", "?"], capture_output=True, text=True)
    lineas = r.stdout.splitlines()
    for clave in (pref, pref.split("_")[0] + "_"):
        for l in lineas:
            if clave in l:
                return l.split("  ")[0].strip()
    return None
