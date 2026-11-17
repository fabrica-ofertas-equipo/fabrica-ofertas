"""Ingreso de una señal de voz de cliente al banco (interfaces d1-v2 §3.2, §6.2 paso captura asistida).

Una persona abre una fuente de `fuentes.yaml` (captura asistida) y pega el extracto (≤ 25 palabras) en
un archivo de texto; este script **redacta PII antes de que cualquier agente lo lea**, calcula el
`senal_id` determinista, verifica la cita sobre el texto pegado y escribe UNA línea en
``empresa/descubrimiento/senales/AAAA-MM/<fuente-id>.jsonl`` (append-only). Sin red, sin LLM.

Qué NO existe todavía (documentado, no inventado):
  * El esquema ``senal`` en ``contratos/`` (pedido a CT §8.1 n.3): este módulo valida con sus PROPIAS
    reglas (las columnas de §3.2), no con `jsonschema`.
  * ``fuentes.yaml`` real (es una semilla pendiente de aprobación del dueño): este módulo lee
    cualquier YAML con la forma de la semilla (``{fuentes: [{id, modo, tipo_evidencia, familia,
    retencion_dias, ...}]}``); en producción apunta a ``empresa/descubrimiento/fuentes.yaml``.

Redacción de PII (``redactar``): reusa ``engine.comun.ocultar_datos_sensibles`` (correos, IP, tarjetas,
secretos) y agrega teléfonos y correos/teléfonos **ofuscados** («usuario arroba dominio punto com»,
«cero nueve... quince veinte»). Es una heurística [HIPÓTESIS] sobre casos simples, no un NER.

Salud y relaciones (categoría especial, nota 21 §9.1, VC-08; interfaces §3.2): con
``--categoria-especial`` el extracto, la URL y el autor_hash se guardan ``null`` y solo quedan
`senal_id`, `fuente_id`, `familia`, `tipo_evidencia`, `locale`, `fecha_consulta` y `etiquetas`
(paráfrasis impersonal) + un conteo. Una señal agregada no puede sostener un puntaje E3 por sí sola.

Uso::

    python -m scripts.descubrimiento.ingresar_senal ingresar --fuente-id youtube-comentarios \\
        --familia dolor --tipo-evidencia E3 --locale es-MX --pais MX \\
        --url https://example.com/post --extracto "no se en que se me va el dinero cada mes" \\
        --fecha-publicacion 2026-01-01 --fecha-consulta 2026-11-06 --modo-captura asistida \\
        --capturado-por humano --fuentes tests/fixtures/descubrimiento/fuentes.yaml [--aplicar] [--json]

Códigos de salida (convenciones §8): 0 ok (o dry-run) · 2 uso · 3 validación (fuente prohibida,
`cita_literal_verificada` no confirmable, forma inválida) · 4 bloqueado (`empresa/PAUSA`).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

from engine import comun
from engine.comun import anexar_jsonl, ejecutar_cli, ocultar_datos_sensibles
from engine.errores import ErrorBloqueado, ErrorUso, ErrorValidacion
from engine.guard import hay_pausa

SCHEMA_VERSION = "1.0.0"
FAMILIAS = ("dolor", "pago", "demanda", "oferta_persistente", "propia")
TIPOS_EVIDENCIA = ("E1", "E2", "E3", "E4")
MODOS_CAPTURA = ("conector", "sesion", "asistida", "propia", "frenos", "candados")
CAPTURADO_POR = ("humano", "maker", "script")
_MAX_PALABRAS_EXTRACTO = 25
_PARAMETROS_UTM = ("fbclid",)
_PREFIJO_UTM = "utm_"

_RX_PAIS = re.compile(r"^[A-Z]{2}$")
_RX_LOCALE = re.compile(r"^[a-z]{2,3}-[A-Z]{2}$")


# ---------------------------------------------------------------------------
# Redacción de PII (antes de que CUALQUIER agente lea el texto)
# ---------------------------------------------------------------------------
_RX_TELEFONO = re.compile(
    r"(?<![\w.])(?:\+|00)?[0-9][0-9\s.\-()]{6,17}[0-9](?![\w.])"
)
_RX_CORREO_OFUSCADO = re.compile(
    r"\b[a-z0-9._%+-]+\s*(?:\(?\s*at\s*\)?|arroba)\s*[a-z0-9.-]+\s*(?:\(?\s*dot\s*\)?|punto)\s*[a-z]{2,}\b",
    re.IGNORECASE,
)


def _solo_digitos(texto: str) -> str:
    return re.sub(r"[^0-9]", "", texto)


def _parece_telefono(coincidencia: str) -> bool:
    digitos = _solo_digitos(coincidencia)
    return 7 <= len(digitos) <= 15


def redactar(texto: str) -> str:
    """Quita PII de ``texto``: secretos/correos/IP/tarjetas (núcleo) + correos ofuscados + teléfonos.

    Heurística [HIPÓTESIS] sobre ofuscaciones simples («arroba», «punto», dígitos separados); no
    reemplaza un NER. Idempotente: redactar un texto ya redactado no cambia nada.
    """
    if not isinstance(texto, str):
        raise ErrorValidacion("redactar: se esperaba texto")
    salida = ocultar_datos_sensibles(texto)
    salida = _RX_CORREO_OFUSCADO.sub("[correo]", salida)

    def _tel(m: "re.Match[str]") -> str:
        return "[telefono]" if _parece_telefono(m.group(0)) else m.group(0)

    return _RX_TELEFONO.sub(_tel, salida)


# ---------------------------------------------------------------------------
# URL canónica y senal_id (interfaces §3.1)
# ---------------------------------------------------------------------------
def url_canonica(url: str) -> str:
    """Host en minúsculas, sin `utm_*`/`fbclid`, sin fragmento ni barra final."""
    partes = urlsplit(url)
    host = partes.netloc.lower()
    consultas = [(k, v) for k, v in parse_qsl(partes.query, keep_blank_values=True)
                if not k.lower().startswith(_PREFIJO_UTM) and k.lower() not in _PARAMETROS_UTM]
    ruta = partes.path.rstrip("/") or ""
    return urlunsplit((partes.scheme, host, ruta, urlencode(consultas), ""))


def calcular_senal_id(*, url: str | None, extracto: str | None, fuente_id: str, referencia: str | None) -> str:
    """``sha256(url_canonica + "\\n" + extracto_nfc)[:12]``; sin URL: ``fuente_id:referencia`` (§3.1)."""
    if url:
        base = url_canonica(url) + "\n" + unicodedata.normalize("NFC", extracto or "")
    else:
        if not referencia:
            raise ErrorValidacion("sin url: se exige --referencia para senal_id = fuente_id:referencia")
        base = f"{fuente_id}:{referencia}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()[:12]


# ---------------------------------------------------------------------------
# fuentes.yaml
# ---------------------------------------------------------------------------
def cargar_fuentes(ruta: Path) -> dict[str, Mapping[str, Any]]:
    datos = comun.cargar_yaml(ruta)
    lista = datos.get("fuentes") if isinstance(datos, Mapping) else None
    if not isinstance(lista, list):
        raise ErrorValidacion(f"{ruta}: se esperaba {{fuentes: [...]}}")
    por_id = {}
    for f in lista:
        if isinstance(f, Mapping) and isinstance(f.get("id"), str):
            por_id[f["id"]] = f
    return por_id


def _exigir_fuente_permitida(fuente: Mapping[str, Any] | None, fuente_id: str) -> Mapping[str, Any]:
    if fuente is None:
        raise ErrorValidacion(f"fuente_id {fuente_id!r} no existe en fuentes.yaml: el ingreso falla cerrado")
    if fuente.get("modo") == "no_usar":
        raise ErrorValidacion(f"fuente_id {fuente_id!r} está en modo no_usar: el ingreso falla cerrado")
    return fuente


# ---------------------------------------------------------------------------
# Construcción de la señal
# ---------------------------------------------------------------------------
def construir_senal(*, fuente_id: str, fuente: Mapping[str, Any], familia: str, tipo_evidencia: str,
                    locale: str, pais: str | None, url: str | None, extracto: str | None,
                    fecha_publicacion: str | None, fecha_consulta: str, modo_captura: str,
                    capturado_por: str, categoria_especial: bool, barrido_id: str | None,
                    etiquetas: Mapping[str, Any] | None, referencia: str | None) -> dict[str, Any]:
    """Arma el objeto `senal` (§3.2) ya con el extracto REDACTADO. No escribe nada."""
    if familia not in FAMILIAS:
        raise ErrorValidacion(f"familia {familia!r} no está en {FAMILIAS}")
    if tipo_evidencia not in TIPOS_EVIDENCIA:
        raise ErrorValidacion(f"tipo_evidencia {tipo_evidencia!r} no está en {TIPOS_EVIDENCIA}")
    if not _RX_LOCALE.fullmatch(locale):
        raise ErrorValidacion(f"locale {locale!r} inválido (BCP-47 con región, p. ej. es-MX)")
    if pais is not None and not _RX_PAIS.fullmatch(pais):
        raise ErrorValidacion(f"pais {pais!r} inválido (ISO-2 mayúsculas)")
    if modo_captura not in MODOS_CAPTURA:
        raise ErrorValidacion(f"modo_captura {modo_captura!r} no está en {MODOS_CAPTURA}")
    if capturado_por not in CAPTURADO_POR:
        raise ErrorValidacion(f"capturado_por {capturado_por!r} no está en {CAPTURADO_POR}")

    if categoria_especial:
        if not isinstance(etiquetas, Mapping) or not etiquetas:
            raise ErrorValidacion("categoria_especial=true exige --etiquetas (paráfrasis impersonal, nunca cita)")
        extracto_final: str | None = None
        url_final: str | None = None
        autor_hash: str | None = None
    else:
        if not extracto or not extracto.strip():
            raise ErrorValidacion("extracto vacío (o usar --categoria-especial)")
        n_palabras = len(extracto.split())
        if n_palabras > _MAX_PALABRAS_EXTRACTO:
            raise ErrorValidacion(f"extracto de {n_palabras} palabras; el máximo es {_MAX_PALABRAS_EXTRACTO}")
        extracto_final = redactar(extracto)
        url_final = url
        autor_hash = None

    senal_id = calcular_senal_id(url=url, extracto=extracto if not categoria_especial else None,
                                 fuente_id=fuente_id, referencia=referencia)
    retencion_dias = fuente.get("retencion_dias")
    return {
        "schema_version": SCHEMA_VERSION, "senal_id": senal_id, "fuente_id": fuente_id, "familia": familia,
        "tipo_evidencia": tipo_evidencia, "locale": locale, "pais": pais, "url": url_final,
        "fecha_publicacion": fecha_publicacion, "fecha_consulta": fecha_consulta[:10],
        "extracto": extracto_final, "extracto_idioma": locale.split("-")[0], "traduccion": None,
        "cita_literal_verificada": False if categoria_especial else True,
        "hash_copia_crudo": None, "autor_hash": autor_hash, "modo_captura": modo_captura,
        "capturado_por": capturado_por, "robots_ok": None, "categoria_especial": categoria_especial,
        "etiquetas": dict(etiquetas) if etiquetas else None, "problema_ids": [], "barrido_id": barrido_id,
        "retencion_hasta": _retencion_hasta(fecha_consulta[:10], retencion_dias),
    }


def _retencion_hasta(fecha_consulta: str, retencion_dias: Any) -> str | None:
    if not isinstance(retencion_dias, int) or isinstance(retencion_dias, bool):
        return None
    from datetime import date, timedelta

    y, m, d = (int(x) for x in fecha_consulta.split("-"))
    return (date(y, m, d) + timedelta(days=retencion_dias)).isoformat()


def ruta_senales(raiz: Path, fecha_consulta: str, fuente_id: str) -> Path:
    anio_mes = fecha_consulta[:7].replace("-", "-")  # AAAA-MM
    return raiz / "empresa" / "descubrimiento" / "senales" / anio_mes / f"{fuente_id}.jsonl"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m scripts.descubrimiento.ingresar_senal",
                                description="Ingreso de una señal de voz de cliente (interfaces §3.2)")
    sub = p.add_subparsers(dest="cmd", required=True)
    ing = sub.add_parser("ingresar")
    ing.add_argument("--fuente-id", required=True)
    ing.add_argument("--familia", required=True, choices=FAMILIAS)
    ing.add_argument("--tipo-evidencia", required=True, choices=TIPOS_EVIDENCIA)
    ing.add_argument("--locale", required=True)
    ing.add_argument("--pais")
    ing.add_argument("--url")
    ing.add_argument("--extracto")
    ing.add_argument("--referencia", help="para señales sin URL: senal_id = fuente_id:referencia")
    ing.add_argument("--fecha-publicacion")
    ing.add_argument("--fecha-consulta", required=True, help="AAAA-MM-DD")
    ing.add_argument("--modo-captura", required=True, choices=MODOS_CAPTURA)
    ing.add_argument("--capturado-por", required=True, choices=CAPTURADO_POR)
    ing.add_argument("--categoria-especial", action="store_true")
    ing.add_argument("--etiquetas", help="JSON, solo con --categoria-especial")
    ing.add_argument("--barrido-id")
    ing.add_argument("--fuentes", type=Path, required=True)
    ing.add_argument("--raiz", type=Path)
    ing.add_argument("--aplicar", action="store_true")
    ing.add_argument("--json", action="store_true")

    rd = sub.add_parser("redactar", help="solo redacta un texto y lo imprime (depuración, sin escribir)")
    rd.add_argument("texto")
    return p


def _cuerpo_ingresar(a: argparse.Namespace) -> int:
    raiz = a.raiz or comun.raiz()
    if hay_pausa(raiz):
        raise ErrorBloqueado("existe empresa/PAUSA: el ingreso de señales se detiene")
    fuentes = cargar_fuentes(a.fuentes)
    fuente = _exigir_fuente_permitida(fuentes.get(a.fuente_id), a.fuente_id)
    etiquetas = json.loads(a.etiquetas) if a.etiquetas else None
    senal = construir_senal(
        fuente_id=a.fuente_id, fuente=fuente, familia=a.familia, tipo_evidencia=a.tipo_evidencia,
        locale=a.locale, pais=a.pais, url=a.url, extracto=a.extracto, fecha_publicacion=a.fecha_publicacion,
        fecha_consulta=a.fecha_consulta, modo_captura=a.modo_captura, capturado_por=a.capturado_por,
        categoria_especial=a.categoria_especial, barrido_id=a.barrido_id, etiquetas=etiquetas,
        referencia=a.referencia)
    ruta = ruta_senales(raiz, senal["fecha_consulta"], a.fuente_id)
    if a.aplicar:
        anexar_jsonl(ruta, senal)
    salida = {"senal_id": senal["senal_id"], "ruta": str(ruta), "escrito": bool(a.aplicar), "senal": senal}
    if a.json:
        print(json.dumps(salida, ensure_ascii=False, sort_keys=True))
    else:
        print(f"senal_id={senal['senal_id']} ruta={ruta} escrito={a.aplicar}")
    return 0


def _cuerpo_redactar(a: argparse.Namespace) -> int:
    print(redactar(a.texto))
    return 0


def main(argv: list[str] | None = None) -> int:
    def _principal() -> int:
        try:
            args = _parser().parse_args(argv)
        except SystemExit as exc:
            if exc.code in (0, None):
                return 0
            raise ErrorUso("argumentos inválidos (ver --help)") from None
        return {"ingresar": _cuerpo_ingresar, "redactar": _cuerpo_redactar}[args.cmd](args)

    return ejecutar_cli(_principal)


if __name__ == "__main__":
    raise SystemExit(main())
