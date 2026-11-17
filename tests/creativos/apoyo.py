"""Utilidades compartidas de las pruebas de tests/creativos (sin red; los archivos se generan en cada prueba)."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
SKILL = RAIZ / ".claude" / "skills" / "d6-creativos"
SCRIPTS = SKILL / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import render_estatico as rr  # noqa: E402  (scripts de la skill)


def hay_navegador() -> bool:
    try:
        rr.buscar_navegador()
        return True
    except rr.ErrorRender:
        return False


HAY_FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))
HAY_SWIFT = bool(shutil.which("swiftc")) and sys.platform == "darwin"
HAY_PDFTOPPM = bool(shutil.which("pdftoppm"))
HAY_WHISPER = bool(shutil.which("whisper-cli")) and any((Path.home() / ".cache" / "whisper").glob("ggml-*.bin"))
HAY_SAY = bool(shutil.which("say")) and sys.platform == "darwin"


def correr(cmd: list[str], timeout: int = 120) -> None:
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(f"{cmd[0]} salió {r.returncode}: {r.stderr[-300:]}")


def copies_de_prueba(idioma: str, gancho: str, apoyo: str, ad_name: str = "c01-koszt_img_h1_v1", marca: str = "Arkusz Studio") -> dict:
    return {"idioma": idioma,
            "marca": {"nombre": marca, "color_fondo": "#fdf6ec", "color_texto": "#1f1a17", "color_acento": "#b5461f", "fuente": "Helvetica Neue, Arial"},
            "anuncios": [{"ad_name": ad_name, "texto_en_pieza": {"gancho": gancho, "apoyo": apoyo, "rotulo": "", "aviso": ""}}]}


def renderizar_estatico(copies: dict, directorio: Path, ad_name: str = "c01-koszt_img_h1_v1", ratio: str = "4:5") -> Path:
    """PNG real con el mismo render de la Ruta A (render_estatico.py), a partir de un copies.json."""
    import json
    ruta_copies = directorio / "copies.json"
    ruta_copies.write_text(json.dumps(copies, ensure_ascii=False), encoding="utf-8")
    png = directorio / "assets" / f"{ad_name}.png"
    png.parent.mkdir(parents=True, exist_ok=True)
    codigo = rr.main(["--plantilla", str(SKILL / "templates" / "estatico.html"), "--copies", str(ruta_copies), "--ad-name", ad_name, "--ratio", ratio,
                      "--html-salida", str(directorio / "assets" / "src" / f"{ad_name}.html"), "--png-salida", str(png)])
    if codigo != 0:
        raise RuntimeError(f"render_estatico salió {codigo}")
    return png
