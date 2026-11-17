"""Bitácora de pulido del dueño (``empresa/panel/pulido.jsonl``; CONTRATO §6).

Registro de qué corregir en cada paso hasta que el sistema corra solo. **Append-only**: cada acción agrega UNA
línea (``O_APPEND`` + ``flock`` + ``fsync``, una sola ``write``) y nunca reescribe ni borra lo anterior.

Líneas (todas con ``id``, ``ts`` y ``autor: "dueno"``):

* alta: ``{id: "PUL-0001", ts, autor, evento: "alta", oferta_id|null, etapa, titulo, detalle, severidad, tipo, estado: "abierta"}``
  más, solo si se enviaron (lista única de pendientes del Cerebro; todo opcional y retrocompatible): ``responsable``
  (dueno|ia|robot|otro), ``prioridad`` (P0-P3), ``origen`` (cadena corta saneada), ``categoria`` (error|regla|pref|riesgo|
  contexto), ``bloquea`` (lista corta de ids/etapas) y ``vence`` (fecha ISO ``AAAA-MM-DD`` o ``AAAA-MM-DDTHH:MM:SSZ``).
  ``tipo``: ``pulido`` (por defecto), ``pendiente``, ``decision``, ``leccion``, ``regla_propuesta``; siguen válidos los tipos
  de las líneas antiguas (``observacion``, ``nota``). Un ``regla_propuesta`` es solo un pendiente para que el dueño la
  apruebe a mano: nada de aquí escribe reglas.
* cambio de estado: ``{id: "PUL-0001", ts, autor, evento: "estado", estado}``

``GET`` devuelve las líneas TAL CUAL (el cliente pliega los cambios de estado sobre cada alta).
Los textos son del dueño pero se tratan como datos: se guardan íntegros (HTML, U+202E…) sin interpretarlos.
"""
from __future__ import annotations

import datetime as _dt
import json
import re
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from dashboard.api_base import ETAPAS, RX_OFERTA, Ctx, Sobre
from dashboard.archivos import (
    anexar_calculado, cargar_json_estricto, iso_z, preparar_destino,
)
from dashboard.seguridad import ErrorHttp

__all__ = ["Pulido", "REL_PULIDO"]

REL_PULIDO = "empresa/panel/pulido.jsonl"
ETAPAS_PULIDO = frozenset([*ETAPAS, "O0", "D0", "F1", "F2", "X1", "X2"])
SEVERIDADES = ("baja", "media", "alta")
TIPOS_ANTIGUOS = ("observacion", "nota", "decision")
TIPOS = ("pulido", "observacion", "nota", "decision", "pendiente", "leccion", "regla_propuesta")
TIPO_DEFECTO = "pulido"
ESTADOS = ("abierta", "en_curso", "resuelta")
RESPONSABLES = ("dueno", "ia", "robot", "otro")
PRIORIDADES = ("P0", "P1", "P2", "P3")
CATEGORIAS = ("error", "regla", "pref", "riesgo", "contexto")
LIMITE_TITULO = 140
LIMITE_DETALLE = 4000
LIMITE_ORIGEN = 80
LIMITE_BLOQUEA = 8
LIMITE_ITEM_BLOQUEA = 40
_MAX_LECTURA = 5000
_CLAVES_OPCIONALES = ("responsable", "prioridad", "origen", "categoria", "bloquea", "vence")
_CLAVES_ALTA = frozenset({"oferta_id", "etapa", "titulo", "detalle", "severidad", "tipo", *_CLAVES_OPCIONALES})
_RX_ID = re.compile(r"^PUL-([0-9]{4,9})$")
_RX_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
# origen: letras/dígitos (Unicode) y unos pocos signos de rutas, ids, fechas y citas («docs/00 §0.B, J4»); sin <, >, comillas, `, $, \, saltos ni controles.
_RX_ORIGEN = re.compile(r"^[\w/#@][\w ._:/#@()+,§\-]*$")
_RX_ITEM_BLOQUEA = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:\-]{0,39}$")
_RX_FECHA = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
_RX_FECHA_HORA = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")


def _texto(cuerpo: Mapping[str, Any], clave: str, *, minimo: int, maximo: int, defecto: str | None = None) -> str:
    valor = cuerpo.get(clave, defecto)
    if not isinstance(valor, str):
        raise ErrorHttp(400, "campo_invalido", f"«{clave}» tiene que ser un texto.")
    valor = _RX_CONTROL.sub("", valor).strip()
    if len(valor) < minimo:
        raise ErrorHttp(400, "campo_invalido", f"«{clave}» es obligatorio.")
    if len(valor) > maximo:
        raise ErrorHttp(400, "campo_invalido", f"El campo {clave} supera {maximo} caracteres.")
    return valor


def _opcion(cuerpo: Mapping[str, Any], clave: str, validas: tuple[str, ...], defecto: str | None = None) -> str:
    valor = cuerpo.get(clave, defecto)
    if valor not in validas:
        raise ErrorHttp(400, "campo_invalido", f"«{clave}» tiene que ser uno de estos: {', '.join(validas)}.")
    return valor


def _opcion_opcional(cuerpo: Mapping[str, Any], clave: str, validas: tuple[str, ...]) -> str | None:
    """Campo opcional con lista blanca: ausente, ``null`` o ``""`` = no se envió; otro valor fuera de la lista = 400."""
    valor = cuerpo.get(clave)
    if valor is None or valor == "":
        return None
    if not isinstance(valor, str) or valor not in validas:
        raise ErrorHttp(400, "campo_invalido", f"«{clave}» tiene que ser uno de estos: {', '.join(validas)}.")
    return valor


def _origen(cuerpo: Mapping[str, Any]) -> str | None:
    """Cadena corta y saneada: quita controles y espacios sobrantes; solo letras, dígitos y ``._:/#@()+-`` (lista blanca)."""
    valor = cuerpo.get("origen")
    if valor is None or valor == "":
        return None
    if not isinstance(valor, str):
        raise ErrorHttp(400, "campo_invalido", "«origen» tiene que ser un texto.")
    limpio = " ".join(_RX_CONTROL.sub("", valor).split())
    if not limpio:
        return None
    if len(limpio) > LIMITE_ORIGEN:
        raise ErrorHttp(400, "campo_invalido", f"El campo origen supera {LIMITE_ORIGEN} caracteres.")
    if not _RX_ORIGEN.fullmatch(limpio):
        raise ErrorHttp(400, "campo_invalido", "El campo origen solo admite letras, números y los signos . _ : / # @ ( ) + , § -.")
    return limpio


def _bloquea(cuerpo: Mapping[str, Any]) -> list[str] | None:
    """Lista corta de ids o etapas que este pendiente frena (``D3``, ``OF-202611-01``, ``activar_campana``…); sin repetidos."""
    valor = cuerpo.get("bloquea")
    if valor is None or valor == []:
        return None
    if not isinstance(valor, list):
        raise ErrorHttp(400, "campo_invalido", "«bloquea» tiene que ser una lista de identificadores o etapas.")
    salida: list[str] = []
    for item in valor:
        if not isinstance(item, str):
            raise ErrorHttp(400, "campo_invalido", "Cada elemento de «bloquea» tiene que ser un texto.")
        item = item.strip()
        if not _RX_ITEM_BLOQUEA.fullmatch(item):
            raise ErrorHttp(400, "campo_invalido", f"Un elemento de bloquea no es válido (letras, números y . _ : -, hasta {LIMITE_ITEM_BLOQUEA}).")
        if item not in salida:
            salida.append(item)
    if len(salida) > LIMITE_BLOQUEA:
        raise ErrorHttp(400, "campo_invalido", f"El campo bloquea admite hasta {LIMITE_BLOQUEA} elementos.")
    return salida


def _vence(cuerpo: Mapping[str, Any]) -> str | None:
    """Fecha ISO real: ``AAAA-MM-DD`` o ``AAAA-MM-DDTHH:MM:SSZ`` (nada de formatos semanales ni ordinales)."""
    valor = cuerpo.get("vence")
    if valor is None or valor == "":
        return None
    if not isinstance(valor, str):
        raise ErrorHttp(400, "campo_invalido", "«vence» tiene que ser una fecha con formato AAAA-MM-DD.")
    valor = valor.strip()
    try:
        if _RX_FECHA.fullmatch(valor):
            _dt.date.fromisoformat(valor)
        elif _RX_FECHA_HORA.fullmatch(valor):
            _dt.datetime.strptime(valor, "%Y-%m-%dT%H:%M:%SZ")
        else:
            raise ValueError(valor)
    except ValueError as exc:
        raise ErrorHttp(400, "campo_invalido", "«vence» tiene que ser una fecha real con formato AAAA-MM-DD.") from exc
    return valor


def _linea(obj: Mapping[str, Any], actual: bytes = b"") -> bytes:
    """Línea JSON ASCII terminada en salto; si lo ya escrito quedó a medias (sin ``\\n`` final) lo cierra antes."""
    cuerpo = json.dumps(obj, ensure_ascii=True, allow_nan=False, separators=(",", ":")).encode("ascii") + b"\n"
    return (b"\n" if actual and not actual.endswith(b"\n") else b"") + cuerpo


def _objetos(actual: bytes) -> list[dict[str, Any]]:
    salida: list[dict[str, Any]] = []
    for crudo in actual.split(b"\n"):
        if not crudo.strip():
            continue
        try:
            obj = cargar_json_estricto(crudo)
        except (ValueError, UnicodeDecodeError):
            continue
        if isinstance(obj, dict):
            salida.append(obj)
    return salida


class Pulido:
    """Lectura y escritura de la bitácora bajo una raíz (real o temporal)."""

    def __init__(self, ctx: Ctx, ahora: Callable[[], _dt.datetime] | None = None) -> None:
        self.ctx = ctx
        self._ahora = ahora or ctx.ahora

    def _ts(self) -> str:
        return iso_z(self._ahora())

    # -- lectura ------------------------------------------------------------------------------
    def listar(self) -> Sobre:
        """``{entradas: [líneas en orden de archivo], total}``; ``vacio`` si la bitácora aún no existe."""
        base = self.ctx.raiz_confinada
        lec = base.jsonl_cola(REL_PULIDO, maximo=_MAX_LECTURA)
        avisos = list(lec.avisos)
        if lec.estado != "ok":
            avisos.append("Todavía no hay anotaciones: la bitácora se crea con la primera (empresa/panel/pulido.jsonl).")
            return Sobre({"entradas": [], "total": 0}, [REL_PULIDO], vacio=True, avisos=avisos)
        entradas = [obj for _, obj, _ in lec.lineas if obj is not None]
        return Sobre({"entradas": entradas, "total": lec.total or 0}, [REL_PULIDO], vacio=not entradas, avisos=avisos)

    # -- escritura ----------------------------------------------------------------------------
    def _destino(self) -> Path:
        return preparar_destino(self.ctx.raiz, REL_PULIDO)

    def crear(self, cuerpo: Mapping[str, Any]) -> dict[str, Any]:
        """Agrega una entrada nueva (``alta``). Valida tipos, largos y valores; ignora nada: los campos extra son 400.

        Los campos de la lista única (``responsable``, ``prioridad``, ``origen``, ``categoria``, ``bloquea``, ``vence``) son
        opcionales: solo se escriben si llegan, con lista blanca y largos máximos. Una alta antigua sigue siendo válida."""
        extras = set(cuerpo) - _CLAVES_ALTA
        if extras:
            raise ErrorHttp(400, "campo_no_permitido", f"Campos no admitidos: {', '.join(sorted(map(str, extras)))}.")
        oferta_id = cuerpo.get("oferta_id")
        if oferta_id is not None and oferta_id != "":
            if not isinstance(oferta_id, str) or not RX_OFERTA.fullmatch(oferta_id):
                raise ErrorHttp(400, "campo_invalido", "El campo oferta_id no tiene el formato de una oferta.")
        else:
            oferta_id = None
        etapa = cuerpo.get("etapa")
        if etapa not in ETAPAS_PULIDO:
            raise ErrorHttp(400, "campo_invalido", "La etapa no es válida. Elige una de la lista (M1, D1 a D10, O0, D0, F1, F2, X1, X2).")
        titulo = _texto(cuerpo, "titulo", minimo=1, maximo=LIMITE_TITULO)
        detalle = _texto(cuerpo, "detalle", minimo=0, maximo=LIMITE_DETALLE, defecto="")
        severidad = _opcion(cuerpo, "severidad", SEVERIDADES, "media")
        tipo = _opcion(cuerpo, "tipo", TIPOS, TIPO_DEFECTO)
        opcionales: dict[str, Any] = {}
        for clave, valor in (("responsable", _opcion_opcional(cuerpo, "responsable", RESPONSABLES)),
                             ("prioridad", _opcion_opcional(cuerpo, "prioridad", PRIORIDADES)),
                             ("origen", _origen(cuerpo)),
                             ("categoria", _opcion_opcional(cuerpo, "categoria", CATEGORIAS)),
                             ("bloquea", _bloquea(cuerpo)),
                             ("vence", _vence(cuerpo))):
            if valor is not None:
                opcionales[clave] = valor
        destino = self._destino()
        resultado: dict[str, Any] = {}

        def construir(actual: bytes) -> bytes:
            numeros = [int(m.group(1)) for o in _objetos(actual) if isinstance(o.get("id"), str) and (m := _RX_ID.fullmatch(o["id"]))]
            nuevo_id = f"PUL-{(max(numeros) if numeros else 0) + 1:04d}"
            resultado.update({"id": nuevo_id, "ts": self._ts(), "autor": "dueno", "evento": "alta", "oferta_id": oferta_id,
                              "etapa": etapa, "titulo": titulo, "detalle": detalle, "severidad": severidad,
                              "tipo": tipo, "estado": "abierta", **opcionales})
            return _linea(resultado, actual)

        anexar_calculado(destino, construir)
        return dict(resultado)

    def cambiar_estado(self, cuerpo: Mapping[str, Any]) -> dict[str, Any]:
        """Agrega una línea ``estado`` para una entrada existente. Mismo estado que el vigente: no escribe nada."""
        extras = set(cuerpo) - {"id", "estado"}
        if extras:
            raise ErrorHttp(400, "campo_no_permitido", f"Campos no admitidos: {', '.join(sorted(map(str, extras)))}.")
        pid = cuerpo.get("id")
        if not isinstance(pid, str) or not _RX_ID.fullmatch(pid):
            raise ErrorHttp(400, "campo_invalido", "El campo id debe tener la forma PUL-0001.")
        estado = _opcion(cuerpo, "estado", ESTADOS)
        destino = self._destino()
        resultado: dict[str, Any] = {}

        def construir(actual: bytes) -> bytes | None:
            vigente: str | None = None
            existe = False
            for o in _objetos(actual):
                if o.get("id") != pid:
                    continue
                if o.get("evento") == "alta" or isinstance(o.get("titulo"), str):
                    existe = True
                    vigente = o.get("estado") if o.get("estado") in ESTADOS else "abierta"
                elif existe and o.get("estado") in ESTADOS:
                    vigente = o["estado"]
            if not existe:
                raise ErrorHttp(404, "entrada_no_encontrada", "No encontramos esa anotación en la bitácora.")
            if vigente == estado:
                resultado.update({"id": pid, "estado": estado, "sin_cambios": True})
                return None
            resultado.update({"id": pid, "ts": self._ts(), "autor": "dueno", "evento": "estado", "estado": estado})
            return _linea(resultado, actual)

        anexar_calculado(destino, construir)
        return dict(resultado)

    def escribir(self, cuerpo: Any) -> dict[str, Any]:
        """``POST /pulido``: ``{id, estado}`` cambia estado; cualquier otra forma es un alta."""
        if not isinstance(cuerpo, Mapping):
            raise ErrorHttp(400, "cuerpo_invalido", "Lo que se envió no tiene el formato esperado.")
        if "id" in cuerpo or ("estado" in cuerpo and "titulo" not in cuerpo):
            return self.cambiar_estado(cuerpo)
        return self.crear(cuerpo)
