"""Controladores puros de la ingesta del servicio `api` (`POST /ingesta/evento`, `POST /ingesta/entrega`;
docs/06 §4.7, alineados con la implementación real de `dashboard.api`, que es quien los monta).

Cada función es ``(cuerpo, cabeceras) -> (status HTTP, cuerpo de respuesta)``: no abre sockets, no
depende de un framework y nunca ejecuta nada a partir del contenido del cuerpo (convenciones §10, el
cuerpo es un DATO). Autenticación interna (docs/06 §4.7, idéntica a ``dashboard.api.firmar``):
cabeceras ``X-Fabrica-Ts`` (UTC ISO con ``Z``) y ``X-Fabrica-Firma: hmac-sha256=<hex>`` = HMAC-SHA256 de
``ts + "." + cuerpo_exacto``, comparación en tiempo constante. Orden de las comprobaciones (todas fallan
cerradas): parámetros de ``ingesta`` y secreto disponibles (500) → tamaño del cuerpo (413) → cabeceras de
firma presentes (401) → ``ts`` válido y dentro de ``ingesta.tolerancia_seg`` (400) → firma (401) → JSON y
forma (400) → efecto con idempotencia (200 ``duplicado`` si idéntico; 409 si el mismo identificador trae
otro contenido).

Nota para quien integre (B10, `dashboard.api.manejar_entrega`): la llamada real es
``manejar_ingesta_entrega(cuerpo, cabeceras, conexion, lambda: ahora)`` (4 posicionales, sin `raiz`); por
eso `raiz` es un argumento con nombre, por defecto `engine.comun.raiz()` (resuelve `FABRICA_RAIZ`).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import sqlite3
from collections.abc import Callable, Mapping
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Literal

from engine import comun
from engine.errores import ErrorValidacion, ParametroFaltante
from engine.parametros import Parametros, cargar_parametros
from scripts.validar_esquemas import errores_de_esquema, hash_objeto

from datos.db import Conexion

__all__ = [
    "VISITOR_SIN_ATRIBUCION", "aplicar_entrega", "aplicar_evento", "manejar_ingesta_entrega", "manejar_ingesta_evento",
    "ruta_entregas",
]

_RX_OFERTA = re.compile(r"^OF-[0-9]{6}-[0-9]{2}$")
_RX_VISITOR = re.compile(r"^[A-Za-z0-9_-]{16,64}$")
_RX_EVENTO_ID = re.compile(r"^[A-Za-z0-9_.:-]{8,128}$")
_RX_ATRIB = re.compile(r"^([0-9]{6,20}|desconocido)$")
_RX_SESION = re.compile(r"^cs_[A-Za-z0-9_]+$")
_RX_SHA = re.compile(r"^sha256:[0-9a-f]{64}$")
_RX_MONEDA = re.compile(r"^[A-Z]{3}$")

_TIPOS_EVENTO = ("PageView", "ViewContent", "InitiateCheckout", "Purchase")
_FUENTES_EVENTO = ("pixel", "capi", "landing")
_ESTADOS_ENTREGA = ("encolado", "enviado", "entregado", "fallido")
_CLAVES_EVENTO = {"event_id", "oferta_id", "tipo", "ts", "visitor_id", "cid", "asid", "adid", "fuente",
                  "consentimiento", "valor_minor", "moneda"}
#: ``visitor_id`` que se persiste cuando el evento llega SIN consentimiento (nunca el real).
VISITOR_SIN_ATRIBUCION = "sin-atribucion"
_OBLIGATORIAS_EVENTO = ("event_id", "oferta_id", "tipo", "ts", "visitor_id", "fuente", "consentimiento")
_CLAVES_ENTREGA = {"checkout_session_id", "oferta_id", "estado", "intento", "producto_sha256", "ts"}

_CABECERA_FIRMA, _CABECERA_TS = "X-Fabrica-Firma", "X-Fabrica-Ts"
SCHEMA_VERSION_ENTREGA = "1.0.0"


def _cabecera(cabeceras: Mapping[str, str], nombre: str) -> str | None:
    """Busca una cabecera sin distinguir mayúsculas (los servidores HTTP normalizan distinto)."""
    objetivo = nombre.lower()
    for clave, valor in cabeceras.items():
        if clave.lower() == objetivo:
            return valor
    return None


def _firmar(secreto: bytes, cuerpo: bytes, ts: str) -> str:
    """``hmac-sha256=<hex>`` de ``ts + "." + cuerpo`` (docs/06 §4.7; misma fórmula que `dashboard.api.firmar`)."""
    return "hmac-sha256=" + hmac.new(secreto, ts.encode("utf-8") + b"." + cuerpo, hashlib.sha256).hexdigest()


def _autenticar(cuerpo: bytes, cabeceras: Mapping[str, str], ahora: Callable[[], datetime], tolerancia_seg: int,
                secreto: bytes) -> tuple[int, str] | None:
    """``None`` si la petición está bien firmada; si no, ``(status, motivo)`` (docs/06 §4.7, orden fijo)."""
    ts_cabecera = _cabecera(cabeceras, _CABECERA_TS)
    firma_cabecera = _cabecera(cabeceras, _CABECERA_FIRMA)
    if not ts_cabecera or not firma_cabecera:
        return 401, "firma_ausente"
    try:
        momento_cabecera = comun.parsear_z(ts_cabecera)
    except ErrorValidacion:
        return 400, "ts_invalido"
    if abs((comun.instante(ahora) - momento_cabecera).total_seconds()) > tolerancia_seg:
        return 400, "ts_fuera_de_tolerancia"
    esperada = _firmar(secreto, cuerpo, ts_cabecera)
    if not hmac.compare_digest(esperada.encode("ascii"), firma_cabecera.strip().encode("utf-8", "ignore")):
        return 401, "firma_invalida"
    return None


def _parametros_ingesta(parametros: Parametros | None) -> tuple[Parametros, int, int] | tuple[int, dict[str, Any]]:
    """``(parametros, tolerancia_seg, cuerpo_max_bytes)`` o ``(500, cuerpo_de_error)`` si falta el grupo."""
    try:
        par = parametros if parametros is not None else cargar_parametros()
        return par, int(par.valor("ingesta.tolerancia_seg")), int(par.valor("ingesta.cuerpo_max_bytes"))
    except ParametroFaltante as exc:
        return 500, {"ok": False, "motivo": "parametros_ingesta_faltantes", "detalle": exc.mensaje}


def _secreto_o_env(secreto: bytes | None) -> bytes:
    return secreto if secreto is not None else (os.environ.get("INGEST_HMAC_SECRET") or "").encode("utf-8")


# ----------------------------------------------------------------------------------------------
# POST /ingesta/evento
# ----------------------------------------------------------------------------------------------
def _validar_evento(obj: Any) -> list[str]:
    """Problemas de forma del cuerpo ya decodificado (lista vacía = válido; docs/06 §4.7)."""
    if not isinstance(obj, Mapping):
        return ["el cuerpo no es un objeto JSON"]
    problemas = [f"campo no permitido: {k}" for k in sorted(set(obj) - _CLAVES_EVENTO, key=str)]
    problemas += [f"falta {c}" for c in _OBLIGATORIAS_EVENTO if c not in obj]
    if problemas:
        return problemas
    if not isinstance(obj["event_id"], str) or not _RX_EVENTO_ID.fullmatch(obj["event_id"]):
        problemas.append("event_id inválido")
    if not isinstance(obj["oferta_id"], str) or not _RX_OFERTA.fullmatch(obj["oferta_id"]):
        problemas.append("oferta_id inválido")
    if obj["tipo"] not in _TIPOS_EVENTO:
        problemas.append(f"tipo debe ser uno de {', '.join(_TIPOS_EVENTO)}")
    if not isinstance(obj["ts"], str):
        problemas.append("ts ausente")
    else:
        try:
            comun.parsear_z(obj["ts"])
        except ErrorValidacion:
            problemas.append("ts inválido (se exige AAAA-MM-DDTHH:MM:SSZ)")
    if not isinstance(obj["visitor_id"], str) or not _RX_VISITOR.fullmatch(obj["visitor_id"]):
        problemas.append("visitor_id inválido")
    for c in ("cid", "asid", "adid"):
        if c in obj and obj[c] is not None and (not isinstance(obj[c], str) or not _RX_ATRIB.fullmatch(obj[c])):
            problemas.append(f"{c} inválido")
    if obj["fuente"] not in _FUENTES_EVENTO:
        problemas.append(f"fuente debe ser una de {', '.join(_FUENTES_EVENTO)}")
    if not isinstance(obj["consentimiento"], bool):
        problemas.append("consentimiento debe ser booleano")
    if "valor_minor" in obj and obj["valor_minor"] is not None and (
            not isinstance(obj["valor_minor"], int) or isinstance(obj["valor_minor"], bool) or obj["valor_minor"] < 0):
        problemas.append("valor_minor debe ser un entero >= 0")
    if "moneda" in obj and obj["moneda"] is not None and (
            not isinstance(obj["moneda"], str) or not _RX_MONEDA.fullmatch(obj["moneda"])):
        problemas.append("moneda inválida")
    if (obj.get("valor_minor") is None) != (obj.get("moneda") is None):
        problemas.append("valor_minor y moneda van juntos")
    return problemas


def aplicar_evento(conn: Conexion, obj: Mapping[str, Any], *,
                   ahora: Callable[[], datetime] = comun.ahora_utc) -> Literal["nuevo", "duplicado", "conflicto"]:
    """Inserta en `fact_evento` (idempotente por `event_id`); `obj` ya pasó :func:`_validar_evento`.

    ``"conflicto"`` si el `event_id` ya existe con otro contenido (docs/06 §4.7: 409).
    """
    # Sin consentimiento el evento se guarda (cuenta en los totales agregados) pero SIN atribución: ningún
    # identificador (cid/asid/adid) ni el visitor_id real se persiste (minimización; mismo criterio que
    # ``dashboard.api``: ``visitor_id = "sin-atribucion"`` y anuncio nulo).
    atribuible = bool(obj["consentimiento"])
    valores = (
        obj["event_id"], obj["oferta_id"], obj["tipo"], obj["ts"], obj["visitor_id"] if atribuible else VISITOR_SIN_ATRIBUCION,
        obj.get("cid") if atribuible else None, obj.get("asid") if atribuible else None, obj.get("adid") if atribuible else None,
        obj["fuente"], 1 if atribuible else 0, obj.get("valor_minor"), obj.get("moneda"),
    )
    try:
        conn.ejecutar(
            "INSERT INTO fact_evento (event_id, oferta_id, tipo, ts, visitor_id, cid, asid, adid, fuente, "
            "consentimiento, valor_minor, moneda, recibido_en) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (*valores, comun.iso_z(comun.instante(ahora))),
        )
        conn.commit()
        return "nuevo"
    except sqlite3.IntegrityError:
        conn.cruda.rollback()
    existente = conn.ejecutar(
        "SELECT oferta_id, tipo, ts, visitor_id, cid, asid, adid, fuente, consentimiento, valor_minor, moneda "
        "FROM fact_evento WHERE event_id = ?", (obj["event_id"],),
    ).fetchone()
    if existente is not None and tuple(existente) == valores[1:]:
        return "duplicado"
    return "conflicto"


def manejar_ingesta_evento(cuerpo: bytes, cabeceras: Mapping[str, str], conn: Conexion,
                           ahora: Callable[[], datetime] = comun.ahora_utc, *,
                           parametros: Parametros | None = None, secreto: bytes | None = None) -> tuple[int, dict[str, Any]]:
    """Controlador puro de `POST /ingesta/evento` (docs/06 §4.7): ver el orden de comprobaciones arriba."""
    resultado = _parametros_ingesta(parametros)
    if isinstance(resultado[0], int):
        return resultado  # type: ignore[return-value]
    _par, tolerancia_seg, cuerpo_max_bytes = resultado
    clave = _secreto_o_env(secreto)
    if not clave:
        return 500, {"ok": False, "motivo": "secreto_ausente"}
    if len(cuerpo) > cuerpo_max_bytes:
        return 413, {"ok": False, "motivo": "cuerpo_demasiado_grande"}
    falla = _autenticar(cuerpo, cabeceras, ahora, tolerancia_seg, clave)
    if falla is not None:
        estado, motivo = falla
        return estado, {"ok": False, "motivo": motivo}
    try:
        obj = json.loads(cuerpo.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return 400, {"ok": False, "motivo": "cuerpo_no_json"}
    problemas = _validar_evento(obj)
    if problemas:
        return 400, {"ok": False, "motivo": "evento_invalido", "problemas": problemas}
    resultado_aplicar = aplicar_evento(conn, obj, ahora=ahora)
    if resultado_aplicar == "conflicto":
        return 409, {"ok": False, "motivo": "event_id_con_otro_contenido"}
    return 200, {"ok": True, "resultado": resultado_aplicar, "atribuible": bool(obj["consentimiento"])}


# ----------------------------------------------------------------------------------------------
# POST /ingesta/entrega
# ----------------------------------------------------------------------------------------------
def _validar_entrega(obj: Any) -> list[str]:
    """Problemas de forma del cuerpo ya decodificado (lista vacía = válido; docs/06 §4.7).

    El cuerpo normativo NO trae datos personales: un campo ``email`` (u otro no listado) se rechaza
    como campo no permitido, nunca se guarda en texto plano (convenciones §10).
    """
    if not isinstance(obj, Mapping):
        return ["el cuerpo no es un objeto JSON"]
    problemas = [f"campo no permitido: {k}" for k in sorted(set(obj) - _CLAVES_ENTREGA, key=str)]
    problemas += [f"falta {c}" for c in sorted(_CLAVES_ENTREGA - set(obj))]
    if problemas:
        return problemas
    if not isinstance(obj["checkout_session_id"], str) or not _RX_SESION.fullmatch(obj["checkout_session_id"]):
        problemas.append("checkout_session_id inválido")
    if not isinstance(obj["oferta_id"], str) or not _RX_OFERTA.fullmatch(obj["oferta_id"]):
        problemas.append("oferta_id inválido")
    if obj["estado"] not in _ESTADOS_ENTREGA:
        problemas.append(f"estado debe ser uno de {', '.join(_ESTADOS_ENTREGA)}")
    if not isinstance(obj["intento"], int) or isinstance(obj["intento"], bool) or obj["intento"] < 0:
        problemas.append("intento debe ser un entero >= 0")
    if not isinstance(obj["producto_sha256"], str) or not _RX_SHA.fullmatch(obj["producto_sha256"]):
        problemas.append("producto_sha256 inválido")
    if not isinstance(obj["ts"], str):
        problemas.append("ts ausente")
    else:
        try:
            comun.parsear_z(obj["ts"])
        except ErrorValidacion:
            problemas.append("ts inválido (se exige AAAA-MM-DDTHH:MM:SSZ)")
    return problemas


def ruta_entregas(raiz: Path, oferta_id: str) -> Path:
    """``<raíz>/ofertas/<oferta_id>/10-postcompra/entregas.jsonl`` (docs/contratos.md fila 27)."""
    return raiz / "ofertas" / oferta_id / "10-postcompra" / "entregas.jsonl"


def _entrega_id(checkout_session_id: str) -> str:
    """``ENT-<12 hex>`` determinista a partir de `checkout_session_id` (una entrega = un `entrega_id`)."""
    return "ENT-" + hashlib.sha256(checkout_session_id.encode("utf-8")).hexdigest()[:12]


def _linea_entrega(obj: Mapping[str, Any], par: Parametros) -> dict[str, Any]:
    """Línea de `entregas.jsonl` conforme a `contratos/entrega.schema.json`.

    El cuerpo normativo de `POST /ingesta/entrega` (docs/06 §4.7, confirmado por `dashboard.api`:
    `_CLAVES_ENTREGA`) no trae `producto_version`, `email_hmac`, `enlace`, `idempotency_key` ni
    `ejecutor`, que el esquema exige. Decisión de esta sesión (README «Decisiones», sin dato mejor):
    `email_hmac=None` (nunca llega un email por este endpoint), `enlace` se calcula con los parámetros
    paramétricos `entrega.enlace_vence_dias`/`enlace_max_descargas` (nunca un número fijo) y
    `descargas=0` (el contador real vive en `infra/workers/descarga`, fuera de este módulo),
    `idempotency_key` se deriva (convenciones §7: hash del JSON canónico de la operación),
    `ejecutor="script"` (esta vía siempre es automática) y `producto_version="v1"` por falta de mejor
    dato (PEDIDO a B7/D4 en el README).
    """
    dias = int(par.valor("entrega.enlace_vence_dias"))
    max_descargas = int(par.valor("entrega.enlace_max_descargas"))
    vence_en = comun.iso_z(comun.parsear_z(obj["ts"]) + timedelta(days=dias))
    idempotency_key = hash_objeto({
        "operacion": "ingesta_entrega", "checkout_session_id": obj["checkout_session_id"],
        "estado": obj["estado"], "intento": int(obj["intento"]),
    })
    return {
        "schema_version": SCHEMA_VERSION_ENTREGA,
        "entrega_id": _entrega_id(obj["checkout_session_id"]),
        "ts": obj["ts"],
        "oferta_id": obj["oferta_id"],
        "checkout_session_id": obj["checkout_session_id"],
        "email_hmac": None,
        "estado": obj["estado"],
        "producto_version": "v1",
        "producto_sha256": obj["producto_sha256"],
        "enlace": {"vence_en": vence_en, "max_descargas": max_descargas, "descargas": 0},
        "intentos": int(obj["intento"]),
        "idempotency_key": idempotency_key,
        "ejecutor": "script",
    }


def aplicar_entrega(conn: Conexion, obj: Mapping[str, Any], raiz: Path, par: Parametros, *,
                    ahora: Callable[[], datetime] = comun.ahora_utc) -> Literal["nuevo", "duplicado", "conflicto"]:
    """Upsert en `fact_entrega` (clave `session_id` = `checkout_session_id`) y apéndice idempotente en
    `entregas.jsonl` (único productor de ese artefacto: convenciones «un artefacto, un productor»).

    ``"conflicto"`` si la MISMA transición (`checkout_session_id`, `estado`, `intento`) ya quedó
    registrada con otro contenido (p. ej. otro `producto_sha256` u otro `ts`): docs/06 §4.7, 409.
    """
    # La línea se construye y valida ANTES de escribir nada (si falta un parámetro de `entrega.*`,
    # ParametroFaltante sube sin dejar un upsert a medias ni una línea a medias).
    linea = _linea_entrega(obj, par)
    errores = errores_de_esquema("entrega", linea)
    if errores:
        raise ErrorValidacion(f"línea de entrega inválida: {comun.resumir_errores_esquema(errores)}")
    ruta = ruta_entregas(raiz, obj["oferta_id"])
    clave_transicion = (obj["checkout_session_id"], obj["estado"], int(obj["intento"]))
    for existente in comun.leer_jsonl(ruta):
        if (existente.get("checkout_session_id"), existente.get("estado"), existente.get("intentos")) == clave_transicion:
            if hash_objeto(existente) == hash_objeto(linea):
                return "duplicado"  # contenido idéntico: no se toca fact_entrega ni entregas.jsonl
            return "conflicto"  # contenido distinto para la misma transición: tampoco se escribe nada
    conn.upsert("fact_entrega", ["session_id"], {
        "session_id": obj["checkout_session_id"], "oferta_id": obj["oferta_id"], "estado": obj["estado"],
        "intentos": int(obj["intento"]), "producto_sha256": obj["producto_sha256"], "ts": obj["ts"],
        "actualizado_en": comun.iso_z(comun.instante(ahora)),
    })
    conn.commit()
    comun.anexar_jsonl(ruta, linea)
    return "nuevo"


def manejar_ingesta_entrega(cuerpo: bytes, cabeceras: Mapping[str, str], conn: Conexion,
                            ahora: Callable[[], datetime] = comun.ahora_utc, *,
                            parametros: Parametros | None = None, secreto: bytes | None = None,
                            raiz: Path | None = None) -> tuple[int, dict[str, Any]]:
    """Controlador puro de `POST /ingesta/entrega` (docs/06 §4.7): MISMA autenticación y códigos que
    :func:`manejar_ingesta_evento`. Llamado por `dashboard.api.manejar_entrega` como
    ``manejar_ingesta_entrega(cuerpo, cabeceras, conexion, lambda: ahora)`` (sin `raiz`): por eso
    `raiz` resuelve `FABRICA_RAIZ` por defecto (`engine.comun.raiz`).
    """
    resultado = _parametros_ingesta(parametros)
    if isinstance(resultado[0], int):
        return resultado  # type: ignore[return-value]
    par, tolerancia_seg, cuerpo_max_bytes = resultado
    clave = _secreto_o_env(secreto)
    if not clave:
        return 500, {"ok": False, "motivo": "secreto_ausente"}
    if len(cuerpo) > cuerpo_max_bytes:
        return 413, {"ok": False, "motivo": "cuerpo_demasiado_grande"}
    falla = _autenticar(cuerpo, cabeceras, ahora, tolerancia_seg, clave)
    if falla is not None:
        estado, motivo = falla
        return estado, {"ok": False, "motivo": motivo}
    try:
        obj = json.loads(cuerpo.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return 400, {"ok": False, "motivo": "cuerpo_no_json"}
    problemas = _validar_entrega(obj)
    if problemas:
        return 400, {"ok": False, "motivo": "entrega_invalida", "problemas": problemas}
    try:
        resultado_aplicar = aplicar_entrega(conn, obj, raiz if raiz is not None else comun.raiz(), par, ahora=ahora)
    except ParametroFaltante as exc:
        # `entrega.enlace_vence_dias`/`enlace_max_descargas` se leen recién al construir la línea de
        # `entregas.jsonl` (_linea_entrega): si faltan, falla cerrado igual que si faltara `ingesta.*`.
        return 500, {"ok": False, "motivo": "parametros_ingesta_faltantes", "detalle": exc.mensaje}
    if resultado_aplicar == "conflicto":
        return 409, {"ok": False, "motivo": "entrega_con_otro_contenido"}
    return 200, {"ok": True, "resultado": resultado_aplicar}
