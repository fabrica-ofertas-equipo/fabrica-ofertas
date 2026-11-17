"""OCR a 1 fotograma/segundo de D6 (``departamentos/07-creativos.md`` §6 L1.6-7).

Extrae fotogramas de un video a 1 fps con ``ffmpeg`` (rutas de binarios INYECTABLES; sin el binario
configurado, sale 2 con un mensaje claro — nunca se marca verde sin comprobar) o lee directamente una
carpeta de imágenes ya extraídas (estáticos), reconoce el texto de cada fotograma con un
``MotorOCR`` inyectable (``Protocol``; en pruebas, un motor falso) y compara el texto reconocido con
``copies.json`` y con los claims prohibidos (``compliance.lint_claims.lint_texto``, por ``locale``).

Este módulo NO instala ni invoca Tesseract (nota 25 / ``references/dependencias.md`` de la skill
D6): queda como adaptador opcional, documentado en el README.

CLI::

    python -m scripts.creativos.ocr_check --ad-name c01-hueco_img_h1_v1 --copies COPIES.json
        --fotogramas DIR_O_VIDEO --locale es-ES [--macro-nicho dinero] [--ffmpeg RUTA] [--json]

``COPIES.json``: ``{"<ad_name>": {"texto_principal": "...", "titular": "...", "descripcion": "..."}}``.

Salida (convenciones §8): 0 texto coincide y sin ROJO · 3 no coincide o hay un claim ROJO ·
2 sin binario de ``ffmpeg`` configurado (al pedir extraer de un video) · 6 ``ffmpeg`` falló al correr.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import unicodedata
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence

from engine import comun
from engine.errores import ErrorExterno, ErrorUso, ErrorValidacion

from compliance.hallazgos import peor_nivel
from compliance.lint_claims import lint_texto
from compliance.reglas import cargar_reglas

__all__ = ["MotorOCR", "comparar_texto", "extraer_fotogramas", "main", "verificar"]

_EXT_IMAGEN = (".png", ".jpg", ".jpeg")
_EXT_VIDEO = (".mp4", ".mov", ".webm", ".mkv")


class MotorOCR(Protocol):
    """Reconoce el texto visible de UNA imagen. Implementaciones reales quedan fuera de esta entrega."""

    def reconocer(self, ruta_imagen: Path) -> str: ...


def _normalizar(texto: str) -> str:
    return " ".join(unicodedata.normalize("NFC", texto).lower().split())


def extraer_fotogramas(video: Path, destino: Path, *, ffmpeg: Path | str | None) -> list[Path]:
    """Fotogramas a 1 fps de ``video`` en ``destino`` (creada si falta). Sin ``ffmpeg`` configurado: ``ErrorUso`` (2)."""
    if not ffmpeg:
        raise ErrorUso("falta --ffmpeg: no hay binario configurado para extraer fotogramas (nunca se asume uno del PATH)")
    binario = Path(ffmpeg)
    if not binario.is_file() or not os.access(binario, os.X_OK):
        raise ErrorUso(f"--ffmpeg no es un ejecutable: {binario}")
    destino.mkdir(parents=True, exist_ok=True)
    comando = [str(binario), "-y", "-i", str(video), "-vf", "fps=1", str(destino / "frame_%04d.png")]
    try:
        subprocess.run(comando, check=True, capture_output=True, timeout=120)
    except subprocess.CalledProcessError as exc:
        raise ErrorExterno(f"ffmpeg falló al extraer fotogramas: {comun.ocultar_datos_sensibles(exc.stderr.decode('utf-8', 'replace')[:300])}") from exc
    except (OSError, subprocess.SubprocessError) as exc:
        raise ErrorExterno(f"no se pudo ejecutar ffmpeg: {exc}") from exc
    return sorted(destino.glob("frame_*.png"))


def _imagenes_de(ruta: Path, *, ffmpeg: Path | str | None, destino_fotogramas: Path | None) -> list[Path]:
    if ruta.is_dir():
        return sorted(p for p in ruta.iterdir() if p.suffix.lower() in _EXT_IMAGEN)
    if ruta.suffix.lower() in _EXT_VIDEO:
        tmp = destino_fotogramas or ruta.with_suffix("")
        return extraer_fotogramas(ruta, tmp, ffmpeg=ffmpeg)
    if ruta.suffix.lower() in _EXT_IMAGEN:
        return [ruta]
    raise ErrorValidacion(f"--fotogramas no es una carpeta, una imagen ni un video reconocido: {ruta}")


def comparar_texto(texto_reconocido: str, copy_esperado: Mapping[str, Any]) -> list[str]:
    """Campos de ``copy_esperado`` cuyo texto NO aparece (normalizado) en ``texto_reconocido``."""
    reconocido = _normalizar(texto_reconocido)
    faltantes: list[str] = []
    for campo, valor in copy_esperado.items():
        if not isinstance(valor, str) or not valor.strip():
            continue
        if _normalizar(valor) not in reconocido:
            faltantes.append(campo)
    return faltantes


def verificar(imagenes: Sequence[Path], motor: MotorOCR, copy_esperado: Mapping[str, Any], *, locale: str,
             macro_nicho: str | None = None, reglas=None) -> dict[str, Any]:
    """Texto reconocido por fotograma, campos de copy que no coinciden y hallazgos de claims prohibidos."""
    if not imagenes:
        raise ErrorValidacion("no hay fotogramas que leer")
    reglas = reglas if reglas is not None else cargar_reglas()
    textos = [motor.reconocer(img) for img in imagenes]
    texto_total = " ".join(textos)
    faltantes = comparar_texto(texto_total, copy_esperado)
    hallazgos = lint_texto(texto_total, reglas, locale=locale, macro_nicho=macro_nicho, origen="ocr")
    return {
        "textos_por_fotograma": textos, "campos_sin_coincidir": faltantes,
        "hallazgos": [h.asdict() for h in hallazgos], "semaforo": peor_nivel(hallazgos),
    }


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m scripts.creativos.ocr_check", description="OCR a 1 fps contra copies.json y claims prohibidos.")
    p.add_argument("--ad-name", required=True, dest="ad_name")
    p.add_argument("--copies", required=True, type=Path)
    p.add_argument("--fotogramas", required=True, type=Path, help="carpeta de imágenes, UNA imagen o un video")
    p.add_argument("--locale", required=True)
    p.add_argument("--macro-nicho", default=None, dest="macro_nicho")
    p.add_argument("--ffmpeg", default=None, help="ruta del binario (solo si --fotogramas es un video)")
    p.add_argument("--json", action="store_true")
    return p


def main(argv: list[str] | None = None, *, motor: MotorOCR | None = None) -> int:
    """``motor`` es inyectable para pruebas; sin uno, esta CLI no puede ofrecer OCR real (ver README)."""
    try:
        a = _parser().parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2

    def cuerpo() -> int:
        if motor is None:
            raise ErrorUso("sin --motor-ocr real disponible en esta entrega: inyecta un MotorOCR para usar la CLI (ver README)")
        try:
            copies = comun.cargar_json(a.copies)
        except FileNotFoundError as exc:
            raise ErrorUso(f"--copies no existe: {a.copies}") from exc
        if not isinstance(copies, Mapping) or a.ad_name not in copies:
            raise ErrorValidacion(f"--copies no tiene «{a.ad_name}»")
        imagenes = _imagenes_de(a.fotogramas, ffmpeg=a.ffmpeg, destino_fotogramas=None)
        resultado = verificar(imagenes, motor, copies[a.ad_name], locale=a.locale, macro_nicho=a.macro_nicho)
        codigo = 3 if resultado["campos_sin_coincidir"] or resultado["semaforo"] == "rojo" else 0
        salida = {"ok": codigo == 0, "modo": "dry_run", "codigo": codigo, "datos": resultado, "avisos": []}
        if a.json:
            print(json.dumps(salida, sort_keys=True, ensure_ascii=False))
        else:
            print(f"semáforo={resultado['semaforo']} campos_sin_coincidir={resultado['campos_sin_coincidir']}")
        return codigo

    return comun.ejecutar_cli(cuerpo)


if __name__ == "__main__":
    raise SystemExit(main())
