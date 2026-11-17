#!/usr/bin/env python3
"""Limpieza de los archivos intermedios de las ofertas cerradas (regla del dueño, 15-nov: «Borrar intermedios»).

Por qué: cada oferta ocupa 1,5-5 GB (clips crudos, audios de voz, fotogramas, rondas descartadas, copias para subir, páginas
sueltas del producto) y con 2 lanzamientos por día el disco se llenaba en 3-6 días. Con el disco lleno falla todo a la vez
(renders, el libro, el panel, la vigilancia).

Qué se CONSERVA de cada carpeta `ofertas/_borrador-<slug>/` (alcanza para rehacer o replicar la oferta):
  - todo lo que no está en 04-producto/ ni en 06-creativos/ (estado.md, desarme, modelado, marca, landing, backend…);
  - todo archivo de texto o código, y todo archivo de menos de 300 KB;
  - todos los PDF (producto y bonos);
  - los anuncios finales: .mp4 y miniaturas que están DIRECTAMENTE en una carpeta 06-creativos/videos* (no en subcarpetas como
    descartes/);
  - hojas de contacto y galerías (nombre con «hoja», «contacto» o «galeria»), y las portadas.
Qué se BORRA: el resto de los audios, videos e imágenes de 04-producto/ y 06-creativos/, más __pycache__ y node_modules.

Uso:
  python3 limpiar_oferta.py plan    [--estados cerrado] [--carpeta _borrador-x ...]      → qué se borraría y cuánto libera
  python3 limpiar_oferta.py aplicar [--estados cerrado] [--carpeta ...] --papelera      → lo mueve a ~/.Trash/limpieza-<fecha>/
  python3 limpiar_oferta.py aplicar [...] --borrar                                       → borrado definitivo (modo automático, R15)
  python3 limpiar_oferta.py espacio [--minimo-gb 20]                                     → GB libres; sale 3 si está bajo el mínimo
Cada carpeta limpiada recibe LIMPIEZA.md con fecha, modo, cantidad y GB. Las carpetas se toman del libro de tests (rutas
`ofertas/_borrador-…` que aparecen en cada test) filtrando por estado; nunca se toca una oferta activa o programada.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[4]
OFERTAS = RAIZ / "ofertas"
LIBRO = OFERTAS / "_funnels" / "libro-de-tests.json"
ZONAS_LIMPIABLES = ("04-producto", "06-creativos")
MEDIA = {".wav", ".mp3", ".m4a", ".aac", ".ogg", ".flac", ".mp4", ".mov", ".webm", ".mkv", ".png", ".jpg", ".jpeg", ".webp", ".gif",
         ".tif", ".tiff", ".bmp", ".heic", ".psd"}
DIRS_BASURA = {"__pycache__", "node_modules", ".cache"}
CHICO = 300 * 1024
CONSERVAR_NOMBRE = re.compile(r"hoja|contacto|galeria|portada", re.I)
NUNCA = {"activo", "programado", "en_test", "test", "armada", "armado"}   # estados que jamás se limpian


def conservar(rel: Path, tam: int) -> bool:
    """rel: ruta relativa a la carpeta de la oferta."""
    partes = rel.parts
    if not partes or partes[0] not in ZONAS_LIMPIABLES:
        return True
    if any(p in DIRS_BASURA for p in partes):
        return False
    ext = rel.suffix.lower()
    if ext not in MEDIA or tam < CHICO or ext == ".pdf":
        return True
    if CONSERVAR_NOMBRE.search(rel.name) or any(p.lower().startswith("portada") for p in partes):
        return True
    # anuncios finales: 06-creativos/videos*/<archivo> (directo, sin subcarpeta)
    if len(partes) == 3 and partes[0] == "06-creativos" and partes[1].lower().startswith("videos"):
        return True
    return False


def plan_carpeta(carpeta: Path) -> list[tuple[Path, int]]:
    out = []
    for raiz, dirs, archivos in os.walk(carpeta):
        for a in archivos:
            p = Path(raiz) / a
            if p.is_symlink():
                continue
            try:
                tam = p.stat().st_size
            except OSError:
                continue
            if not conservar(p.relative_to(carpeta), tam):
                out.append((p, tam))
    return out


def carpetas_por_estado(estados: set[str]) -> list[tuple[str, str, Path]]:
    libro = json.loads(LIBRO.read_text(encoding="utf-8"))
    por_carpeta: dict[str, list[tuple[str, str]]] = {}
    for t in libro.get("tests") or []:
        if not isinstance(t, dict):
            continue
        for c in set(re.findall(r"ofertas/(_borrador-[a-z0-9-]+)", json.dumps(t, ensure_ascii=False))):
            por_carpeta.setdefault(c, []).append((str(t.get("nombre")), str(t.get("estado") or "").lower()))
    out = []
    for c, tests in sorted(por_carpeta.items()):
        estados_c = {e for _, e in tests}
        # una carpeta compartida por varios tests solo se limpia si TODOS están en los estados pedidos (y ninguno anda)
        if estados_c & NUNCA or not estados_c <= estados:
            continue
        if (OFERTAS / c).is_dir():
            out.append((", ".join(sorted({n for n, _ in tests})), "/".join(sorted(estados_c)), OFERTAS / c))
    return out


def gb(n: int) -> str:
    return f"{n / 1e9:.2f} GB".replace(".", ",")


def anotar(carpeta: Path, modo: str, n: int, tam: int, destino: Path | None) -> None:
    linea = (f"- {dt.datetime.now().astimezone().isoformat(timespec='minutes')} · {modo} · {n} archivos · {gb(tam)}"
             + (f" · movidos a {destino}" if destino else "") + "\n")
    f = carpeta / "LIMPIEZA.md"
    if not f.exists():
        f.write_text("# Limpieza de intermedios\n\nRegla del dueño (15-nov): de una oferta cerrada se borran clips crudos, audios, "
                     "fotogramas, rondas descartadas y copias; se conservan anuncios finales, hojas de contacto, PDF, landing, "
                     "desarme y estado. Script: .claude/skills/escalar-oferta/scripts/limpiar_oferta.py\n\n", encoding="utf-8")
    with f.open("a", encoding="utf-8") as h:
        h.write(linea)


def espacio_libre() -> int:
    return shutil.disk_usage(RAIZ).free


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for nombre in ("plan", "aplicar"):
        s = sub.add_parser(nombre)
        s.add_argument("--estados", default="cerrado", help="estados del libro a limpiar, separados por coma (por defecto: cerrado)")
        s.add_argument("--carpeta", action="append", help="limitar a estas carpetas (_borrador-…)")
        s.add_argument("--json", action="store_true")
        if nombre == "aplicar":
            g = s.add_mutually_exclusive_group(required=True)
            g.add_argument("--papelera", action="store_true")
            g.add_argument("--borrar", action="store_true")
    e = sub.add_parser("espacio")
    e.add_argument("--minimo-gb", type=float, default=20.0)
    a = ap.parse_args(argv)

    if a.cmd == "espacio":
        libre = espacio_libre()
        bajo = libre < a.minimo_gb * 1e9
        print(f"{'BAJO' if bajo else 'ok'}: {gb(libre)} libres (mínimo {a.minimo_gb:g} GB)")
        return 3 if bajo else 0

    estados = {x.strip().lower() for x in a.estados.split(",") if x.strip()}
    if estados & NUNCA:
        print(f"no se limpian ofertas en estado {sorted(estados & NUNCA)}", file=sys.stderr)
        return 2
    objetivo = carpetas_por_estado(estados)
    if a.carpeta:
        pedidas = {c.strip("/").split("/")[-1] for c in a.carpeta}
        objetivo = [x for x in objetivo if x[2].name in pedidas]
    total_n = total_b = 0
    filas = []
    destino_base = Path.home() / ".Trash" / f"limpieza-{dt.datetime.now():%Y%m%d-%H%M}"
    for nombres, est, carpeta in objetivo:
        lista = plan_carpeta(carpeta)
        n, b = len(lista), sum(t for _, t in lista)
        total_n += n
        total_b += b
        filas.append({"carpeta": carpeta.name, "ofertas": nombres, "estado": est, "archivos": n, "bytes": b})
        if a.cmd == "aplicar" and n:
            destino = destino_base / carpeta.name if a.papelera else None
            for p, _ in lista:
                if destino:
                    d = destino / p.relative_to(carpeta)
                    d.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(p), str(d))
                else:
                    p.unlink(missing_ok=True)
            for raiz, dirs, archivos in os.walk(carpeta, topdown=False):   # carpetas que quedaron vacías
                r = Path(raiz)
                if r != carpeta and not any(r.iterdir()):
                    r.rmdir()
            anotar(carpeta, "a la Papelera" if destino else "borrado definitivo", n, b, destino)
    if a.json:
        print(json.dumps({"carpetas": filas, "archivos": total_n, "bytes": total_b, "libre": espacio_libre()}, ensure_ascii=False))
        return 0
    for f in filas:
        print(f"{f['carpeta']:42} {f['ofertas'][:30]:30} {f['estado']:10} {f['archivos']:6} archivos  {gb(f['bytes'])}")
    verbo = {"plan": "liberaría", "aplicar": "liberó" if getattr(a, "borrar", False) else "movió a la Papelera"}[a.cmd]
    print(f"Total: {total_n} archivos · {verbo} {gb(total_b)} · libres ahora {gb(espacio_libre())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
