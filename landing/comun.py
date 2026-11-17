"""Utilidades compartidas de `landing`: rutas, carga de artefactos y argumentos de CLI comunes.

No decide nada de dinero ni de límites: solo localiza archivos de la oferta y los carga con los
lectores canónicos de ``scripts.validar_esquemas`` (vía ``engine.comun``, núcleo sin ciclos).
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

from engine import comun
from engine.errores import ErrorUso, ErrorValidacion

SCRIPT_PERMITIDO = "/js/consentimiento.js"
PIXEL = "/js/pixel.js"

# Arranque de pago (docs/_historial/decision-arranque-de-pago.md): /comprar es estática con UN formulario hacia /api/sesion.
RUTA_COMPRAR = "/comprar"
RUTA_SESION = "/api/sesion"
URL_TURNSTILE = "https://challenges.cloudflare.com/turnstile/v0/api.js"
ORIGEN_TURNSTILE = "https://challenges.cloudflare.com"
# CSP CANÓNICA (decisión de S-A, LT-38): el validador exige EXACTAMENTE estas directivas y estos orígenes (comparación por directiva, sin importar el orden).
# ``form-action`` EXACTO: con solo 'self' Chrome bloquea la redirección 303 a Stripe. El píxel solo lo inyecta pixel.js tras el consentimiento de marketing.
CSP_CANONICA: dict[str, tuple[str, ...]] = {
    "default-src": ("'self'",),
    "script-src": ("'self'", "https://connect.facebook.net"),
    "connect-src": ("'self'", "https://www.facebook.com", "https://connect.facebook.net"),
    "img-src": ("'self'", "data:", "https://www.facebook.com"),       # data: SOLO aquí
    "frame-src": ("https://www.facebook.com", "https://connect.facebook.net"),
    "style-src": ("'self'",),
    "font-src": ("'self'",),
    "object-src": ("'none'",),
    "base-uri": ("'self'",),
    "frame-ancestors": ("'none'",),
    "form-action": ("'self'", "https://checkout.stripe.com"),
}
CSP_FORM_ACTION = CSP_CANONICA["form-action"]
TOPE_DIAS_COOKIE = 395     # tope de vida de fab_vid y fab_attr (Chrome limita las cookies a 400 días); parametros.landing.cookie_*_dias no puede pasarlo
CLAVES_SECRETAS_TURNSTILE = ("secret", "secreto", "secreta")


def csp_directivas(*, turnstile: bool = False) -> dict[str, tuple[str, ...]]:
    """Directivas de la CSP: la canónica o, para ``/comprar`` con Turnstile, la canónica con el origen de Turnstile en ``script-src`` Y ``frame-src``."""
    d = dict(CSP_CANONICA)
    if turnstile:
        d["script-src"] = (*d["script-src"], ORIGEN_TURNSTILE)
        d["frame-src"] = (*d["frame-src"], ORIGEN_TURNSTILE)
    return d


def csp_texto(*, turnstile: bool = False) -> str:
    """Valor del encabezado ``Content-Security-Policy`` (las directivas en el orden canónico de ``CSP_CANONICA``). ÚNICO lugar que define la CSP: ``_headers``
    (``landing.plantillas``) y ``L1-CSP`` (``landing.validar``) salen de aquí."""
    return "; ".join(f"{k} {' '.join(v)}" for k, v in csp_directivas(turnstile=turnstile).items())


# UE-27 y Reino Unido: criterio PROVISIONAL por locale para la casilla de renuncia al desistimiento, mientras
# ``checkout.json › compra.renuncia.requerido`` (que manda cuando existe) no llegue a los contratos.
PAISES_UE_UK = frozenset({
    "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU", "IE", "IT", "LV", "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK", "SI", "ES", "SE",
    "GB",
})


def dir_oferta(oferta_id: str, *, raiz: Path | None = None) -> Path:
    """Carpeta ``ofertas/<oferta_id>`` bajo la raíz (``FABRICA_RAIZ`` o la del repositorio)."""
    if not isinstance(oferta_id, str) or not oferta_id:
        raise ErrorUso("falta --oferta")
    d = (raiz or comun.raiz()) / "ofertas" / oferta_id
    if not d.is_dir():
        raise ErrorValidacion(f"no existe la carpeta de la oferta: {d}")
    return d


def cargar_oferta(d: Path) -> dict[str, Any]:
    return comun.cargar_json(d / "03-oferta" / "oferta.json")


def cargar_checkout(d: Path) -> dict[str, Any]:
    return comun.cargar_json(d / "05-landing" / "checkout.json")


def cargar_tracking(d: Path) -> dict[str, Any]:
    return comun.cargar_json(d / "05-landing" / "tracking.json")


def cargar_rutas(d: Path) -> dict[str, str]:
    p = d / "05-landing" / "rutas.json"
    return comun.cargar_json(p) if p.is_file() else {}


def cargar_producto(d: Path) -> dict[str, Any] | None:
    p = d / "04-producto" / "producto.json"
    return comun.cargar_json(p) if p.is_file() else None


def parametro_landing(dir_oferta: Path, clave: str) -> int | None:
    """``grupos.landing.<clave>.valor`` (entero) de ``empresa/parametros.yaml`` de la raíz de datos de la oferta; ``None`` si no existe.

    La raíz de datos es ``dir_oferta/../..`` (``ofertas/<id>`` bajo la raíz). Solo lee; un archivo ilegible se trata como ausente.
    """
    from scripts import validar_esquemas as V   # import local: este módulo no depende de V al importarse
    ruta = dir_oferta.parent.parent / "empresa" / "parametros.yaml"
    if not ruta.is_file():
        return None
    try:
        valor = ((V.cargar_yaml(ruta).get("grupos") or {}).get("landing") or {}).get(clave, {}).get("valor")
    except Exception:  # noqa: BLE001 - un YAML ilegible se trata como parámetro ausente (se usa el valor por defecto y se avisa)
        return None
    return valor if isinstance(valor, int) and not isinstance(valor, bool) and valor > 0 else None


def region_de(locale: str) -> str | None:
    """Región BCP-47 en mayúsculas de ``es-ES`` -> ``ES``; ``None`` si el locale no trae región alfabética (``es``, ``es-419``)."""
    partes = locale.split("-")
    return partes[1].upper() if len(partes) > 1 and len(partes[1]) == 2 and partes[1].isalpha() else None


def compra_de(checkout: dict[str, Any]) -> dict[str, Any]:
    """Bloque opcional ``checkout.compra`` (aditivo; nombres de S-A/S-B): ``bump_modo``, ``renuncia{requerido, texto_version}`` y ``landing_version``."""
    c = checkout.get("compra")
    return c if isinstance(c, dict) else {}


def landing_version(checkout: dict[str, Any]) -> str | None:
    """``checkout.compra.landing_version`` (opcional) o ``None``."""
    v = compra_de(checkout).get("landing_version")
    return v if isinstance(v, str) and v else None


def modo_bump(checkout: dict[str, Any]) -> str | None:
    """``oferta_previa`` | ``casilla_en_checkout`` | ``None`` (sin bump): ``compra.bump_modo`` manda; si falta, ``bump.modo``."""
    if not checkout.get("bump"):
        return None
    return compra_de(checkout).get("bump_modo") or checkout["bump"].get("modo")


def renuncia(oferta: dict[str, Any], checkout: dict[str, Any]) -> tuple[bool, str | None, bool]:
    """``(requerida, version_del_texto, desde_contrato)``: ¿lleva /comprar la casilla ``renuncia_desistimiento``?

    Manda ``checkout.compra.renuncia.requerido`` (booleano) y ``checkout.compra.renuncia.texto_version`` es la versión del texto. Si ``requerido`` falta
    (``desde_contrato`` = ``False``; los nombres planos anteriores ya no se leen) cae al criterio PROVISIONAL por locale: región del ``locale`` en UE-27 o
    Reino Unido; sin región, los ``paises_segmentacion``; sin ninguno, se exige (ante duda, la casilla).
    """
    c = compra_de(checkout)
    r = c.get("renuncia") if isinstance(c.get("renuncia"), dict) else {}
    version = r.get("texto_version") if isinstance(r.get("texto_version"), str) and r.get("texto_version") else None
    if isinstance(r.get("requerido"), bool):
        return r["requerido"], version, True
    region = region_de(oferta.get("locale", ""))
    if region:
        return region in PAISES_UE_UK, version, False
    paises = [str(p).upper() for p in oferta.get("paises_segmentacion") or []]
    return (any(p in PAISES_UE_UK for p in paises) if paises else True), version, False


def turnstile(checkout: dict[str, Any]) -> dict[str, Any] | None:
    """``checkout.turnstile`` si ``habilitado`` es ``True`` (apagado por defecto; ``sitekey`` es la clave pública del widget); si no, ``None``."""
    t = checkout.get("turnstile")
    return t if isinstance(t, dict) and t.get("habilitado") is True else None


def argparser_base(descripcion: str) -> argparse.ArgumentParser:
    """Argumentos comunes a toda CLI de ``landing``: ``--oferta``, ``--raiz``, ``--live``, ``--json``."""
    ap = argparse.ArgumentParser(description=descripcion)
    ap.add_argument("--oferta", required=True, help="OF-AAAAMM-NN")
    ap.add_argument("--raiz", help="raíz alternativa (solo con FABRICA_ENTORNO distinto de produccion)")
    ap.add_argument("--live", action="store_true", help="ejecuta el efecto (por defecto: dry-run)")
    ap.add_argument("--json", action="store_true", help="una línea JSON en stdout")
    return ap


def raiz_de_argumentos(args: argparse.Namespace, env: dict[str, str]) -> Path:
    """Aplica ``--raiz`` a ``env`` (copia) si el entorno no es producción; devuelve la raíz resultante."""
    if args.raiz:
        if comun.entorno(env) == "produccion":
            raise ErrorUso("--raiz no existe con FABRICA_ENTORNO=produccion")
        env["FABRICA_RAIZ"] = str(Path(args.raiz).resolve())
    return comun.raiz(env)


def entorno_de_proceso() -> dict[str, str]:
    return dict(os.environ)
