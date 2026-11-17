"""Registro de la LANDING ORIGINAL de cada página anunciante que modelamos: ``python -m scripts.referentes.landing``.

Por qué existe: el barrido de la Biblioteca de Anuncios solo guarda 7 campos por anuncio (id, página, título, fecha, moneda y la
ficha del anuncio); NO trae la dirección de la landing a la que lleva el botón. Esa dirección la encuentra una persona (haciendo
clic en el botón del anuncio) y se registra UNA vez aquí; el panel la muestra con un botón «Abrir la landing original» en la ficha
de la página (Radar de ofertas) y en la oferta que la modela.

* Archivo: ``empresa/barrido/referentes/landings.json`` (un registro por ``page_id``). Lo escribe SOLO este comando, y solo con
  ``--escribir`` (sin esa bandera simula y no cambia nada). Escritura atómica; nunca borra ni toca otros archivos.
* Sin red: no visita la dirección, no la descarga, no mide nada. Solo la valida y la guarda.
* La dirección es DATO de un tercero: se valida con reglas estrictas (``validar_url``) tanto al registrar como al leer en el panel,
  para que un archivo editado a mano no pueda producir un enlace ``javascript:``, local o a Meta.

Salida: 0 bien · 2 uso o dato inválido · 3 no se pudo leer/escribir con seguridad.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

__all__ = ["REL_REGISTRO", "ErrorRegistro", "buscar", "cargar", "main", "quitar", "registrar", "validar_page_id", "validar_url"]

REL_REGISTRO = "empresa/barrido/referentes/landings.json"
SCHEMA = "1.0.0"
MAX_URL = 500
MAX_NOTA = 300
TOPE_ARCHIVO = 1024 * 1024
RAIZ_REPO = Path(__file__).resolve().parent.parent.parent
_RX_PAGE_ID = re.compile(r"^[0-9]{5,20}$")
_RX_OFERTA = re.compile(r"^(OF-[0-9]{6}-[0-9]{2,4}|_ejemplo)$")
_RX_PROHIBIDOS = re.compile(r"[\s\x00-\x1f\x7f-\x9f​-‏‪-‮⁠-⁯﻿]")
# Hosts de Meta: la Biblioteca de Anuncios NO es la landing; guardarla aquí sería confundir una cosa con la otra.
_HOSTS_META = ("facebook.com", "fb.com", "fb.me", "fb.watch", "instagram.com", "meta.com", "messenger.com", "whatsapp.com", "wa.me")


class ErrorRegistro(Exception):
    """El archivo existe pero no se puede tratar con seguridad (ilegible, demasiado grande o con otra forma)."""


def validar_page_id(valor: Any) -> str:
    texto = str(valor).strip() if isinstance(valor, (str, int)) and not isinstance(valor, bool) else ""
    if not _RX_PAGE_ID.fullmatch(texto):
        raise ValueError("El identificador de la página tiene que ser un número de 5 a 20 cifras (sale en el panel, en «Detalle técnico de la página»).")
    return texto


def validar_url(valor: Any) -> tuple[str, str]:
    """Devuelve ``(url, dominio)`` o lanza ``ValueError`` con un mensaje para una persona.

    Reglas: texto de una línea sin espacios ni caracteres invisibles; ``https`` (nunca ``http``, ``javascript:`` ni ``data:``);
    dominio con punto y sin usuario ni contraseña; puerto solo 443; ni direcciones IP ni ``localhost``; ni hosts de Meta; ≤ 500 caracteres.
    El dominio se devuelve en forma ASCII (``xn--…`` si es internacional) para que un dominio disfrazado se vea tal cual es.
    """
    if not isinstance(valor, str) or not valor.strip():
        raise ValueError("Falta la dirección (URL) de la landing.")
    url = valor.strip()
    if len(url) > MAX_URL:
        raise ValueError(f"La dirección es demasiado larga (máximo {MAX_URL} caracteres).")
    if _RX_PROHIBIDOS.search(url):
        raise ValueError("La dirección no puede tener espacios, saltos de línea ni caracteres invisibles: cópiala de nuevo desde la barra del navegador.")
    try:
        partes = urlsplit(url)
        host = (partes.hostname or "").lower().rstrip(".")
        puerto = partes.port
    except ValueError as exc:
        raise ValueError("La dirección no es una URL válida.") from exc
    if partes.scheme.lower() != "https":
        raise ValueError("La dirección tiene que empezar con https:// (la landing de un anunciante real siempre lo usa).")
    if partes.username is not None or partes.password is not None or "@" in partes.netloc:
        raise ValueError("La dirección no puede llevar usuario ni contraseña.")
    if puerto not in (None, 443):
        raise ValueError("La dirección no puede usar un puerto raro (solo el estándar de https).")
    if not host or "." not in host or host == "localhost" or host.endswith((".local", ".internal", ".localhost")):
        raise ValueError("El dominio no es el de una landing pública (falta el dominio o es una dirección local).")
    if re.fullmatch(r"[0-9.]+", host) or ":" in host:
        raise ValueError("La dirección tiene que usar un nombre de dominio, no una dirección numérica (IP).")
    if any(host == h or host.endswith("." + h) for h in _HOSTS_META):
        raise ValueError("Eso es un enlace de Meta (Facebook, Instagram o WhatsApp), no la landing: busca la dirección a la que lleva el botón del anuncio.")
    try:
        dominio = host.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise ValueError("El dominio tiene caracteres que no se pueden verificar.") from exc
    return partes._replace(fragment="").geturl(), dominio


def _ruta(raiz: Path) -> Path:
    return raiz / REL_REGISTRO


def cargar(raiz: Path) -> list[dict[str, Any]]:
    """Registros vigentes (``[]`` si el archivo no existe). Lanza ``ErrorRegistro`` si existe pero no se puede leer con seguridad."""
    ruta = _ruta(raiz)
    if not ruta.exists():
        return []
    try:
        if ruta.stat().st_size > TOPE_ARCHIVO:
            raise ErrorRegistro(f"{REL_REGISTRO} pesa más de {TOPE_ARCHIVO // 1024} KB: no se toca.")
        doc = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ErrorRegistro(f"No se pudo leer {REL_REGISTRO}: {exc.__class__.__name__}.") from exc
    filas = doc.get("referentes") if isinstance(doc, dict) else None
    if not isinstance(filas, list) or not all(isinstance(f, dict) for f in filas):
        raise ErrorRegistro(f"{REL_REGISTRO} no tiene la forma esperada ({{\"referentes\": [...]}}).")
    return filas


def buscar(raiz: Path, page_id: str) -> dict[str, Any] | None:
    return next((f for f in cargar(raiz) if str(f.get("page_id")) == str(page_id)), None)


def _guardar(raiz: Path, filas: list[dict[str, Any]]) -> None:
    ruta = _ruta(raiz)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    cuerpo = json.dumps({"schema_version": SCHEMA, "referentes": sorted(filas, key=lambda f: str(f.get("page_id")))}, ensure_ascii=False, indent=2) + "\n"
    fd, tmp = tempfile.mkstemp(prefix=".landings-", suffix=".tmp", dir=str(ruta.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(cuerpo)
        os.replace(tmp, ruta)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _ahora_z() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def registrar(raiz: Path, page_id: Any, url: Any, *, nombre: str | None = None, nota: str | None = None, oferta_id: str | None = None,
              copia_local: str | None = None, escribir: bool = False, ahora: str | None = None) -> dict[str, Any]:
    """Valida y guarda (o reemplaza) la landing de una página. Sin ``escribir`` solo devuelve lo que guardaría."""
    pid = validar_page_id(page_id)
    direccion, dominio = validar_url(url)
    if oferta_id is not None and not _RX_OFERTA.fullmatch(oferta_id):
        raise ValueError("El código de la oferta no tiene el formato OF-AAAAMM-NN (o _ejemplo).")
    if copia_local is not None:
        rel = copia_local.strip().replace("\\", "/")
        if not rel or rel.startswith("/") or ".." in rel.split("/") or _RX_PROHIBIDOS.search(rel) or len(rel) > 300:
            raise ValueError("La copia local tiene que ser una ruta relativa dentro del proyecto (por ejemplo docs/_historial/…/pagina.html).")
        if not (raiz / rel).is_file():
            raise ValueError(f"No existe la copia local {rel} (se registra solo si el archivo ya está guardado).")
        copia_local = rel
    registro = {
        "page_id": pid,
        "page_name": _RX_PROHIBIDOS.sub(" ", nombre).strip()[:120] if nombre else None,
        "url": direccion,
        "dominio": dominio,
        "registrada_en": ahora or _ahora_z(),
        "origen": "dueno",
        "oferta_id": oferta_id,
        "nota": _RX_PROHIBIDOS.sub(" ", nota).strip()[:MAX_NOTA] if nota else None,
        "copia_local": copia_local,
    }
    if escribir:
        filas = [f for f in cargar(raiz) if str(f.get("page_id")) != pid]
        filas.append(registro)
        _guardar(raiz, filas)
    return registro


def quitar(raiz: Path, page_id: Any, *, escribir: bool = False) -> bool:
    """Quita el registro de una página (para corregir una dirección mal copiada). ``True`` si había algo que quitar."""
    pid = validar_page_id(page_id)
    filas = cargar(raiz)
    quedan = [f for f in filas if str(f.get("page_id")) != pid]
    if len(quedan) == len(filas):
        return False
    if escribir:
        _guardar(raiz, quedan)
    return True


def _nombre_de_pagina(raiz: Path, page_id: str) -> str | None:
    """Nombre de la página según el último barrido que la vio (solo lectura; ``None`` si no se encuentra)."""
    base = raiz / "empresa" / "barrido" / "paginas"
    if not base.is_dir():
        return None
    for archivo in sorted(base.glob("*.json"), reverse=True):
        try:
            if archivo.stat().st_size > 64 * 1024 * 1024:
                continue
            doc = json.loads(archivo.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for p in doc.get("paginas", []) if isinstance(doc, dict) else []:
            if isinstance(p, dict) and str(p.get("page_id")) == page_id and isinstance(p.get("page_name"), str):
                return p["page_name"]
    return None


def _argumentos(argv: list[str] | None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(prog="python -m scripts.referentes.landing", description="Registro de la landing original de cada página anunciante.")
    ap.add_argument("--raiz", default=str(RAIZ_REPO), help="raíz del proyecto (defecto: la de este código)")
    sub = ap.add_subparsers(dest="orden", required=True)
    sub.add_parser("listar", help="muestra las landings registradas")
    v = sub.add_parser("ver", help="muestra el registro de una página")
    v.add_argument("pagina", help="identificador numérico de la página")
    r = sub.add_parser("registrar", help="guarda (o reemplaza) la landing de una página; sin --escribir solo simula")
    r.add_argument("pagina", help="identificador numérico de la página (en el panel: Detalle técnico de la página)")
    r.add_argument("url", help="dirección https de la landing (la del botón del anuncio)")
    r.add_argument("--nombre", help="nombre de la página (si falta se busca en el último barrido)")
    r.add_argument("--nota", help="una nota corta (por ejemplo, cómo se llegó a ella)")
    r.add_argument("--oferta", help="código de la oferta nuestra que modela esta página (OF-AAAAMM-NN)")
    r.add_argument("--copia-local", help="ruta relativa de la copia guardada del HTML, si existe")
    r.add_argument("--escribir", action="store_true", help="guardar de verdad")
    q = sub.add_parser("quitar", help="quita el registro de una página; sin --escribir solo simula")
    q.add_argument("pagina")
    q.add_argument("--escribir", action="store_true")
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    a = _argumentos(argv)
    raiz = Path(a.raiz).resolve()
    try:
        if a.orden == "listar":
            filas = cargar(raiz)
            if not filas:
                print("Todavía no hay ninguna landing original registrada.")
            for f in filas:
                print(f"{f.get('page_id')}  {f.get('page_name') or '(sin nombre)'}  →  {f.get('url')}")
            return 0
        if a.orden == "ver":
            f = buscar(raiz, validar_page_id(a.pagina))
            print(json.dumps(f, ensure_ascii=False, indent=2) if f else "Esa página no tiene landing registrada.")
            return 0 if f else 2
        if a.orden == "registrar":
            pid = validar_page_id(a.pagina)
            nombre = a.nombre or _nombre_de_pagina(raiz, pid)
            reg = registrar(raiz, pid, a.url, nombre=nombre, nota=a.nota, oferta_id=a.oferta, copia_local=a.copia_local, escribir=a.escribir)
            print(json.dumps(reg, ensure_ascii=False, indent=2))
            print(f"Guardado en {REL_REGISTRO}." if a.escribir else "SIMULACRO: no se guardó nada. Repite con --escribir para guardarlo.")
            return 0
        if a.orden == "quitar":
            hubo = quitar(raiz, a.pagina, escribir=a.escribir)
            print(("Quitado." if a.escribir else "SIMULACRO: se quitaría el registro. Repite con --escribir.") if hubo else "Esa página no tenía landing registrada.")
            return 0
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except (ErrorRegistro, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3
    return 2


if __name__ == "__main__":
    sys.exit(main())
