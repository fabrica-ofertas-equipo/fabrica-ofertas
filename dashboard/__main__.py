"""Arranque del panel: ``python -m dashboard [--puerto 8765] [--raiz RUTA] [--abrir | --no-abrir]``.

Escucha SOLO en ``127.0.0.1`` e imprime ``http://127.0.0.1:<puerto>/#t=<token>`` (el token es aleatorio de 32 bytes
y cambia en cada arranque; viaja en el fragmento de la URL, que el navegador nunca envía al servidor).
``--clave-fija [RUTA]`` (pedido del dueño, 13-nov: «tenerlo fijado y no pedirte que lo abras»): usa siempre la misma clave,
guardada en ``~/.config/fabrica-panel/clave`` (solo legible por el usuario; se crea la primera vez), para que la dirección
se pueda guardar como marcador. El panel lo arranca solo el agente de inicio ``~/Library/LaunchAgents/com.fabrica.panel.plist``.
``--puerto 0`` elige un puerto libre. Sin red externa, sin dependencias fuera de la biblioteca estándar y PyYAML.
"""
from __future__ import annotations

import argparse
import os
import sys
import webbrowser
from collections.abc import Sequence
from pathlib import Path

from dashboard.api_base import VERSION
from dashboard.servidor import Panel, servir

__all__ = ["main"]

PUERTO_DEFECTO = 8765
RAIZ_REPO = Path(__file__).resolve().parent.parent
CLAVE_FIJA_DEFECTO = Path.home() / ".config" / "fabrica-panel" / "clave"


def clave_fija(ruta: Path) -> str:
    """Lee la clave guardada o crea una nueva (32 bytes al azar) con permisos 600. Nunca la imprime."""
    from dashboard.seguridad import nuevo_token
    try:
        texto = ruta.read_text(encoding="utf-8").strip()
        if len(texto) >= 32:
            return texto
    except OSError:
        pass
    ruta.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(ruta.parent, 0o700)
    token = nuevo_token()
    fd = os.open(ruta, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(token + "\n")
    return token


def _argumentos(argv: Sequence[str] | None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(prog="python -m dashboard", description="Panel local del dueño (solo 127.0.0.1).")
    ap.add_argument("--puerto", type=int, default=PUERTO_DEFECTO, help=f"puerto en 127.0.0.1 (defecto {PUERTO_DEFECTO}; 0 = libre)")
    ap.add_argument("--raiz", default=None, help="raíz del repositorio (defecto: FABRICA_RAIZ o la carpeta de este código)")
    ap.add_argument("--abrir", action="store_true", help="abrir el navegador con la URL")
    ap.add_argument("--clave-fija", nargs="?", const=str(CLAVE_FIJA_DEFECTO), default=None, metavar="RUTA",
                    help=f"usar siempre la misma clave, guardada en RUTA (defecto {CLAVE_FIJA_DEFECTO}), para poder guardar la dirección como marcador")
    ap.add_argument("--host-publico", action="append", default=[], metavar="DOMINIO",
                    help="dominio público por el que se entra a través del túnel de Cloudflare (p. ej. panel.tu-dominio.com); se puede repetir")
    ap.add_argument("--no-abrir", action="store_true", help="no abrir el navegador (es lo que hace por defecto; sirve para dejarlo explícito en scripts)")
    return ap.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Código de salida: 0 normal · 2 uso (puerto o raíz inválidos, puerto ocupado)."""
    args = _argumentos(argv)
    if not 0 <= args.puerto <= 65535:
        print("error: --puerto debe estar entre 0 y 65535", file=sys.stderr)
        return 2
    raiz = Path(args.raiz or os.environ.get("FABRICA_RAIZ") or RAIZ_REPO)
    if not raiz.is_dir():
        print("error: --raiz no es una carpeta", file=sys.stderr)
        return 2
    panel = Panel(raiz, token=clave_fija(Path(args.clave_fija).expanduser()) if args.clave_fija else None,
                  publicos=tuple(h.strip().lower() for h in args.host_publico if h.strip()))

    def _al_iniciar(p: Panel) -> None:
        print(f"Panel {VERSION} · raíz {p.ctx.raiz}", flush=True)
        print(p.url(), flush=True)
        print("Ctrl-C para salir.", flush=True)
        if args.abrir and not args.no_abrir:
            webbrowser.open(p.url())

    try:
        servir(panel, args.puerto, al_iniciar=_al_iniciar)
    except OSError as exc:
        panel.cerrar()
        print(f"error: no se pudo abrir 127.0.0.1:{args.puerto} ({exc.strerror or exc.__class__.__name__})", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
