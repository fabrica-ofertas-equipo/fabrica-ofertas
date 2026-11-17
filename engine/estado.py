"""``estado``: máquina de estados de una oferta y almacén del motor (docs/06 §4.2 y §5).

Guarda ``estado.json`` de cada oferta en un almacén SQLite portable (``empresa/motor.db``), que es
la FUENTE de verdad; el archivo ``ofertas/<id>/estado.json`` es una vista exportada (atómica) para que
el dueño y otros componentes lo lean sin tocar la base (docs/06 §4.8 y §4.10). Solo el motor escribe
este archivo.

Firmas congeladas (docs/06 §4.2), ampliadas con ``raiz``/``ahora`` inyectables (mismo patrón que
``engine.guard``, Decisión 1 de su README): ``cargar``, ``guardar`` (bloqueo optimista por
``revision``), ``transicionar``, ``aprobar``, ``propagar_obsolescencia`` y ``gate_de``. Se agregan,
sin romper ninguna firma congelada: ``crear`` (alta idempotente por ``hash_contenido_brief``),
``transicionar_fase`` (ciclo de vida de la oferta, necesario para pausar/reanudar/cerrar) y las
funciones de ``PAUSA`` (``fijar_pausa``, ``quitar_pausa``, ``hay_pausa``).

La validación de transiciones, dependencias y gates NO se reimplementa: se delega en
``scripts.validar_esquemas`` (propiedad de CT): ``transicion_valida``, ``transicion_fase_valida``,
``DEPENDENCIAS``, ``cargar_gates``, ``gate_esperado``, ``nivel_efectivo``.

``PAUSA`` en los dos sitios que son propiedad de este componente (ver README, «Decisiones» y
«Pedidos»): la fila ``control('pausa')`` del almacén (fuente) y el archivo espejo
``empresa/PAUSA`` (el mismo que mira ``engine.guard.hay_pausa``). El tercer sitio del diseño de
docs/06 §4.8 (el KV del watchdog) es de ``infra`` (B8): :func:`hay_pausa` falla cerrado si
CUALQUIERA de los dos sitios propios dice que hay pausa, o si el control es ilegible.
"""
from __future__ import annotations

import copy
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Literal, Mapping

from engine import comun
from engine import guard as _guard
from engine.errores import ErrorBloqueado, ErrorUso, ErrorValidacion
from scripts.validar_esquemas import (
    ARCHIVOS_SELLADOS,
    DEPENDENCIAS,
    DIRECTORIOS_SELLADOS,
    NIVELES,
    cargar_gates,
    gate_esperado,
    hash_contenido_brief,
    hash_salida_etapa,
    nivel_efectivo,
    transicion_fase_valida,
    transicion_valida,
)

__all__ = [
    "ETAPAS_OFERTA", "CAMPOS_ETAPA_MUTABLES", "abrir_base", "aprobar", "cargar", "conectar", "crear",
    "fijar_pausa", "gate_de", "guardar", "hay_pausa", "propagar_obsolescencia", "quitar_pausa",
    "ruta_bd", "ruta_estado_json", "siguiente_etapa", "transicionar", "transicionar_fase",
]

ETAPAS_OFERTA: tuple[str, ...] = ("M1", "D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8", "D9", "D10")
# Campos de una etapa que un llamador puede fijar vía `cambios=` en `transicionar` (nunca `estado`,
# `version_aprobada` ni `aprobado_por`: esos solo los tocan la propia `transicionar`/`aprobar`).
CAMPOS_ETAPA_MUTABLES = frozenset({"hash_salida", "entradas", "ronda_qa", "intentos", "bloqueo", "idempotency_key"})
_NOMBRE_BD = "motor.db"
_ESQUEMA_SQL = """
CREATE TABLE IF NOT EXISTS control (
    clave TEXT PRIMARY KEY,
    valor TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 0,
    actualizado_en TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS fact_estado_oferta (
    oferta_id TEXT PRIMARY KEY,
    revision INTEGER NOT NULL,
    estado_json TEXT NOT NULL,
    actualizado_en TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS transiciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    oferta_id TEXT NOT NULL,
    etapa TEXT NOT NULL,
    de_estado TEXT NOT NULL,
    a_estado TEXT NOT NULL,
    actor TEXT NOT NULL,
    causa TEXT NOT NULL,
    firma TEXT,
    ts TEXT NOT NULL
);
"""


def ruta_bd(raiz: Path | None = None) -> Path:
    """Ruta de ``empresa/motor.db`` bajo la raíz (``FABRICA_RAIZ`` o la del repositorio)."""
    return (raiz or comun.raiz()) / "empresa" / _NOMBRE_BD


def ruta_estado_json(oferta_id: str, raiz: Path | None = None) -> Path:
    """Ruta de la vista exportada ``ofertas/<id>/estado.json`` (el almacén es la fuente de verdad)."""
    return (raiz or comun.raiz()) / "ofertas" / oferta_id / "estado.json"


def conectar(raiz: Path | None = None) -> sqlite3.Connection:
    """Abre una conexión al almacén portable del motor (``empresa/motor.db``): control/PAUSA,
    ``fact_estado_oferta`` (estado.json) y ``transiciones``. Quien la pide la cierra.

    Solo las funciones de ESTE módulo (``cargar``/``guardar``/``transicionar``/``fijar_pausa``...) usan
    este almacén: no tiene los hechos de ``datos`` (``dim_anuncio``, ``fact_meta_ad_dia``,
    ``fact_pedido``...). ``orq ciclo-d8``/``veredicto`` (``engine.d8``, B1b) necesitan AMBOS conjuntos
    de tablas en la MISMA conexión: usan :func:`abrir_base`, no esta función (ver README, «Decisiones»:
    antes de esa función, ``ciclo-d8``/``veredicto`` abrían este almacén -vacío de hechos- mientras los
    ETL reales escribían en otro archivo, ``empresa/datos/fabrica.db``, y ninguna lectura real podía
    funcionar).
    """
    return _conectar(raiz)


def _conectar(raiz: Path | None) -> sqlite3.Connection:
    """Abre (y crea si falta) el almacén SQLite del motor, con ``journal_mode=WAL`` y FK estrictas."""
    ruta = ruta_bd(raiz)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(ruta, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(_ESQUEMA_SQL)
    return conn


def abrir_base(raiz: Path | None = None) -> sqlite3.Connection:
    """Conexión ÚNICA con los dos almacenes que ``orq ciclo-d8``/``veredicto`` necesitan a la vez:

    * el control del motor (``control``, ``fact_estado_oferta``, ``transiciones``: el esquema de
      :func:`conectar`, de solo este módulo), y
    * los hechos de ``datos`` (``dim_anuncio``, ``fact_meta_ad_dia``, ``fact_pedido``... y las vistas
      ``v_d8_*`` que ``engine.d8``/``decision.entradas`` consultan, ``datos/migraciones/*.sql``).

    Mismo ARCHIVO que ``datos.etl_meta``/``datos.etl_stripe``/``datos.ledger``/``datos.kpi`` abren por
    defecto (``datos.etl_stripe.ruta_db_por_defecto``: ``<raíz>/empresa/datos/fabrica.db``), no
    ``empresa/motor.db`` (docs/06 §4.8, D-21: «UN almacén», no dos). Import diferido de ``datos.db``
    (``engine.estado`` no es parte del núcleo congelado de ``engine/{errores,comun,limites,parametros,
    guard,registro,transporte}.py``, así que importar hacia afuera no rompe «núcleo sin ciclos», pero
    se hace perezoso para no acoplar la carga del módulo a que ``datos`` exista).

    Idempotente de llamar varias veces (``CREATE TABLE/VIEW IF NOT EXISTS`` y el control de
    ``_migraciones``): cada llamada aplica solo las migraciones nuevas de ``datos`` y el esquema del
    motor, nunca repite nada. Quien la pide la cierra (como :func:`conectar`).
    """
    from datos.db import Conexion as _ConexionDatos
    from datos.db import migrar as _migrar_datos
    from datos.etl_stripe import ruta_db_por_defecto as _ruta_datos

    ruta = _ruta_datos(raiz or comun.raiz())
    ruta.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(ruta, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(_ESQUEMA_SQL)  # control / fact_estado_oferta / transiciones (motor)
    _migrar_datos(_ConexionDatos(conn, "sqlite", f"sqlite:///{ruta}"))  # dim_anuncio, fact_*, v_d8_* (datos)
    return conn


def _registrar_transicion(conn: sqlite3.Connection, oferta_id: str, etapa: str, de_estado: str, a_estado: str, *,
                          actor: str, causa: str, firma: str | None, ts: str) -> None:
    """Anota una fila de auditoría interna (no forma parte de ningún contrato: es bookkeeping propio)."""
    conn.execute(
        "INSERT INTO transiciones(oferta_id, etapa, de_estado, a_estado, actor, causa, firma, ts) VALUES (?,?,?,?,?,?,?,?)",
        (oferta_id, etapa, de_estado, a_estado, str(actor), str(causa), firma, ts),
    )


def _validar_estado(estado: Mapping[str, Any]) -> None:
    errores = comun.errores_de_esquema("estado", estado)
    if errores:
        raise ErrorValidacion(f"estado.json inválido: {comun.resumir_errores_esquema(errores)}")


def _exportar(oferta_id: str, estado: Mapping[str, Any], raiz: Path | None) -> None:
    """Escritura atómica de la vista en disco (``ofertas/<id>/estado.json``)."""
    comun.escribir_atomico(ruta_estado_json(oferta_id, raiz), comun.json_canonico(dict(estado)))


def cargar(oferta_id: str, *, raiz: Path | None = None) -> dict:
    """Lee el ``estado.json`` vigente de ``oferta_id`` desde el almacén (fuente de verdad).

    Si el almacén no conoce la oferta pero existe su vista en disco (p. ej. una fixture copiada a
    mano, como ``ofertas/_ejemplo/``), la importa una vez y sigue desde ahí. Errores: ``ErrorValidacion``
    (3) si la oferta no existe en ninguno de los dos sitios o si el contenido no cumple el esquema.
    """
    conn = _conectar(raiz)
    try:
        fila = conn.execute("SELECT estado_json FROM fact_estado_oferta WHERE oferta_id=?", (oferta_id,)).fetchone()
        if fila is not None:
            return json.loads(fila[0])
        ruta_disco = ruta_estado_json(oferta_id, raiz)
        try:
            datos = comun.cargar_json(ruta_disco)
        except FileNotFoundError:
            raise ErrorValidacion(f"oferta desconocida: {oferta_id}") from None
        _validar_estado(datos)
        conn.execute(
            "INSERT INTO fact_estado_oferta(oferta_id, revision, estado_json, actualizado_en) VALUES (?,?,?,?)",
            (oferta_id, int(datos["revision"]), comun.json_canonico(datos).decode("utf-8"), str(datos["actualizado_en"])),
        )
        return datos
    finally:
        conn.close()


def guardar(oferta_id: str, estado: Mapping[str, Any], *, revision_esperada: int | None, raiz: Path | None = None) -> dict:
    """Escribe ``estado`` si ``revision_esperada`` coincide con la revisión actual (bloqueo optimista).

    ``estado["revision"]`` debe ser ``revision_esperada + 1`` (o ``1`` si la oferta es nueva, con
    ``revision_esperada=None``). Escribe primero en el almacén y luego exporta atómicamente
    ``ofertas/<id>/estado.json``. Errores: ``ErrorValidacion`` (3) si ``estado`` no cumple el esquema o
    si la revisión no coincide (conflicto de escritura concurrente: alguien más ya escribió).
    """
    if not isinstance(estado, Mapping) or estado.get("oferta_id") != oferta_id:
        raise ErrorValidacion("guardar: el estado no corresponde a oferta_id")
    _validar_estado(estado)
    conn = _conectar(raiz)
    try:
        fila = conn.execute("SELECT revision FROM fact_estado_oferta WHERE oferta_id=?", (oferta_id,)).fetchone()
        actual = int(fila[0]) if fila is not None else None
        if actual != revision_esperada:
            raise ErrorValidacion(
                f"revisión desactualizada para {oferta_id}: esperada {revision_esperada}, almacenada {actual} "
                "(otra escritura ya ocurrió; vuelva a leer con cargar())",
                detalle={"esperada": revision_esperada, "actual": actual},
            )
        if int(estado["revision"]) != (0 if actual is None else actual) + 1:
            raise ErrorValidacion("guardar: la nueva revisión debe ser exactamente la anterior + 1")
        datos = copy.deepcopy(dict(estado))
        linea = comun.json_canonico(datos).decode("utf-8")
        if actual is None:
            conn.execute(
                "INSERT INTO fact_estado_oferta(oferta_id, revision, estado_json, actualizado_en) VALUES (?,?,?,?)",
                (oferta_id, datos["revision"], linea, datos["actualizado_en"]),
            )
        else:
            conn.execute(
                "UPDATE fact_estado_oferta SET revision=?, estado_json=?, actualizado_en=? WHERE oferta_id=?",
                (datos["revision"], linea, datos["actualizado_en"], oferta_id),
            )
        _exportar(oferta_id, datos, raiz)
        return datos
    finally:
        conn.close()


def _etapa_inicial() -> dict:
    return {
        "estado": "pendiente", "version_aprobada": None, "hash_salida": None, "entradas": {},
        "ronda_qa": 0, "intentos": 0, "gate": "H", "gate_pendiente": False, "nivel": "N0",
        "aprobado_por": None, "bloqueo": None, "idempotency_key": None, "obsoleta": False,
    }


def crear(brief: Mapping[str, Any], *, oferta_id: str, familia_id: str, nivel: str = "N0",
         raiz: Path | None = None, ahora: Callable[[], datetime] = comun.ahora_utc) -> dict:
    """Crea el ``estado.json`` inicial de una oferta nueva (idempotente por contenido del brief).

    Si YA existe una oferta cuyo brief tiene el mismo ``hash_contenido_brief`` que ``brief``, se
    espera que el llamador (``engine.orq crear``, que es quien conoce y resuelve ese ``oferta_id``) no
    vuelva a llamar aquí: esta función solo construye el ``estado.json`` inicial y es, en sí misma,
    idempotente por ``oferta_id`` (si ya existe, la devuelve sin tocarla, sin exigir que el contenido
    coincida: esa comparación de contenido la hace el llamador con ``hash_contenido_brief``).
    """
    try:
        return cargar(oferta_id, raiz=raiz)
    except ErrorValidacion:
        pass
    if nivel not in NIVELES:
        raise ErrorUso(f"nivel inválido: {nivel}")
    gates = cargar_gates()
    t = comun.instante(ahora)
    etapas: dict[str, dict] = {}
    for etapa in ETAPAS_OFERTA:
        campo = _etapa_inicial()
        campo["gate"] = gate_esperado(f"etapa:{etapa}", nivel, gates)
        campo["nivel"] = nivel
        etapas[etapa] = campo
    estado_inicial = {
        "schema_version": "1.1.0", "oferta_id": oferta_id, "familia_id": familia_id, "revision": 1,
        "nivel": nivel, "pausa": False, "fase": "borrador", "skills_pin": {}, "etapas": etapas,
        "candidato_elegido": None, "gasto": {"acumulado": {"monto": 0, "moneda": str(brief["mercado_objetivo"]["moneda_cobro"])},
                                            "hoy": {"monto": 0, "moneda": str(brief["mercado_objetivo"]["moneda_cobro"])}},
        "costo_ia": {"monto": 0, "moneda": str(brief["mercado_objetivo"]["moneda_cobro"])},
        "actualizado_en": comun.iso_z(t),
    }
    return guardar(oferta_id, estado_inicial, revision_esperada=None, raiz=raiz)


def transicionar(oferta_id: str, etapa: str, a: str, *, actor: str, causa: str, firma: str | None = None,
                 cambios: Mapping[str, Any] | None = None, raiz: Path | None = None,
                 ahora: Callable[[], datetime] = comun.ahora_utc) -> dict:
    """Mueve ``etapas[etapa].estado`` de su valor actual a ``a`` (docs/06 §5, tabla de transiciones).

    ``cambios`` (opcional) actualiza a la vez otros campos mutables de la etapa (ver
    :data:`CAMPOS_ETAPA_MUTABLES`); nunca ``estado``, ``version_aprobada`` ni ``aprobado_por`` (eso es
    de :func:`aprobar`). ``actor``/``causa``/``firma`` no viven en ``estado.json`` (su esquema no los
    admite): quedan en la tabla de auditoría interna ``transiciones`` del almacén.

    Errores: ``ErrorUso`` (2) si la etapa no existe; ``ErrorValidacion`` (3) si la transición no es
    válida o si ``cambios`` trae un campo no permitido.
    """
    t = comun.instante(ahora)
    est = cargar(oferta_id, raiz=raiz)
    if etapa not in est["etapas"]:
        raise ErrorUso(f"etapa desconocida: {etapa}")
    actual = est["etapas"][etapa]["estado"]
    if not transicion_valida(actual, a):
        raise ErrorValidacion(f"transición inválida de etapa para {etapa}: {actual} -> {a}")
    if cambios:
        sobran = set(cambios) - CAMPOS_ETAPA_MUTABLES
        if sobran:
            raise ErrorValidacion(f"transicionar: campos no permitidos en cambios: {', '.join(sorted(sobran))}")
    nuevo = copy.deepcopy(est)
    campo = nuevo["etapas"][etapa]
    campo["estado"] = a
    campo["gate_pendiente"] = a == "en_QA" and campo["gate"] in ("S", "H")
    if cambios:
        campo.update(copy.deepcopy(dict(cambios)))
    nuevo["revision"] = est["revision"] + 1
    nuevo["actualizado_en"] = comun.iso_z(t)
    conn = _conectar(raiz)
    try:
        guardado = guardar(oferta_id, nuevo, revision_esperada=est["revision"], raiz=raiz)
        _registrar_transicion(conn, oferta_id, etapa, actual, a, actor=actor, causa=causa, firma=firma, ts=comun.iso_z(t))
        return guardado
    finally:
        conn.close()


def aprobar(oferta_id: str, etapa: str, *, version: str, aprobado_por: Mapping[str, Any],
           raiz: Path | None = None, ahora: Callable[[], datetime] = comun.ahora_utc) -> dict:
    """Aprueba ``etapa`` (transición a ``aprobado``), fijando ``version_aprobada`` y ``aprobado_por``.

    ``aprobado_por`` sigue la forma de ``comunes#/$defs/firma_humana``: ``{tipo, id, fecha, firma}``
    con ``tipo`` en ``humano|regla|qa_pass``. Errores: ``ErrorUso`` si la etapa no existe;
    ``ErrorValidacion`` si la transición no es válida o ``aprobado_por`` está mal formado.
    """
    t = comun.instante(ahora)
    est = cargar(oferta_id, raiz=raiz)
    if etapa not in est["etapas"]:
        raise ErrorUso(f"etapa desconocida: {etapa}")
    actual = est["etapas"][etapa]["estado"]
    if not transicion_valida(actual, "aprobado"):
        raise ErrorValidacion(f"{etapa}: no se puede aprobar desde {actual}")
    if not isinstance(aprobado_por, Mapping) or aprobado_por.get("tipo") not in ("humano", "regla", "qa_pass"):
        raise ErrorValidacion("aprobado_por.tipo debe ser humano, regla o qa_pass")
    if not isinstance(aprobado_por.get("id"), str) or not aprobado_por["id"]:
        raise ErrorValidacion("aprobado_por.id es obligatorio")
    comun.parsear_z(str(aprobado_por.get("fecha")))
    nuevo = copy.deepcopy(est)
    campo = nuevo["etapas"][etapa]
    campo["estado"] = "aprobado"
    campo["version_aprobada"] = version
    campo["aprobado_por"] = dict(aprobado_por)
    campo["gate_pendiente"] = False
    campo["obsoleta"] = False
    nuevo["revision"] = est["revision"] + 1
    nuevo["actualizado_en"] = comun.iso_z(t)
    conn = _conectar(raiz)
    try:
        guardado = guardar(oferta_id, nuevo, revision_esperada=est["revision"], raiz=raiz)
        _registrar_transicion(conn, oferta_id, etapa, actual, "aprobado", actor=str(aprobado_por.get("id")),
                              causa=f"aprobación {etapa} {version}", firma=aprobado_por.get("firma"), ts=comun.iso_z(t))
        return guardado
    finally:
        conn.close()


def transicionar_fase(oferta_id: str, a: str, *, actor: str, causa: str, raiz: Path | None = None,
                      ahora: Callable[[], datetime] = comun.ahora_utc) -> dict:
    """Mueve ``fase`` (ciclo de vida de la oferta, docs/06 §5) de su valor actual a ``a``.

    No está en la lista congelada de docs/06 §4.2 (que solo lista transiciones de ETAPA); se agrega
    porque pausar, reanudar y cerrar la oferta mueven la FASE, no una etapa. Errores: ``ErrorValidacion``
    si la transición de fase no es válida (``scripts.validar_esquemas.transicion_fase_valida``).
    """
    t = comun.instante(ahora)
    est = cargar(oferta_id, raiz=raiz)
    actual = est["fase"]
    if not transicion_fase_valida(actual, a):
        raise ErrorValidacion(f"transición de fase inválida: {actual} -> {a}")
    nuevo = copy.deepcopy(est)
    nuevo["fase"] = a
    nuevo["revision"] = est["revision"] + 1
    nuevo["actualizado_en"] = comun.iso_z(t)
    conn = _conectar(raiz)
    try:
        guardado = guardar(oferta_id, nuevo, revision_esperada=est["revision"], raiz=raiz)
        _registrar_transicion(conn, oferta_id, "_fase", actual, a, actor=actor, causa=causa, firma=None, ts=comun.iso_z(t))
        return guardado
    finally:
        conn.close()


def _descendientes(etapa: str) -> list[str]:
    """Cierre transitivo de etapas que dependen (directa o indirectamente) de ``etapa``, en orden de ``ETAPAS_OFERTA``."""
    directos: dict[str, list[str]] = {e: [] for e in ETAPAS_OFERTA}
    for e, deps in DEPENDENCIAS.items():
        for d in deps:
            directos.setdefault(d, []).append(e)
    vistos: set[str] = set()
    pendientes = list(directos.get(etapa, []))
    while pendientes:
        e = pendientes.pop()
        if e in vistos:
            continue
        vistos.add(e)
        pendientes.extend(directos.get(e, []))
    return [e for e in ETAPAS_OFERTA if e in vistos]


def propagar_obsolescencia(oferta_id: str, etapa_cambiada: str, *, raiz: Path | None = None,
                           ejecutor: Any = None, ahora: Callable[[], datetime] = comun.ahora_utc) -> list[str]:
    """Vuelve ``pendiente`` (con ``obsoleta=true``) toda etapa APROBADA que dependa de ``etapa_cambiada``.

    Si la oferta estaba ``en_test`` (campaña activa), también la pausa (fase ``pausada``); si se pasa un
    ``ejecutor`` (protocolo de ``engine.ejecutor``), le pide pausar la campaña viva de la oferta.
    Devuelve la lista de etapas que se volvieron obsoletas (vacía si no hubo nada que propagar).
    """
    est = cargar(oferta_id, raiz=raiz)
    afectadas = _descendientes(etapa_cambiada)
    nuevo = copy.deepcopy(est)
    vueltas: list[str] = []
    for etapa in afectadas:
        campo = nuevo["etapas"].get(etapa)
        if campo is not None and campo["estado"] == "aprobado":
            campo["estado"] = "pendiente"
            campo["obsoleta"] = True
            vueltas.append(etapa)
    pausar_campana = vueltas and nuevo["fase"] == "en_test"
    if pausar_campana:
        nuevo["fase"] = "pausada"
    if vueltas or pausar_campana:
        t = comun.instante(ahora)
        nuevo["revision"] = est["revision"] + 1
        nuevo["actualizado_en"] = comun.iso_z(t)
        conn = _conectar(raiz)
        try:
            guardar(oferta_id, nuevo, revision_esperada=est["revision"], raiz=raiz)
            for etapa in vueltas:
                _registrar_transicion(conn, oferta_id, etapa, "aprobado", "pendiente", actor="motor",
                                      causa=f"entrada {etapa_cambiada} cambió (obsolescencia propagada)",
                                      firma=None, ts=comun.iso_z(t))
            if pausar_campana:
                _registrar_transicion(conn, oferta_id, "_fase", "en_test", "pausada", actor="motor",
                                      causa=f"campaña pausada por obsolescencia desde {etapa_cambiada}", firma=None, ts=comun.iso_z(t))
        finally:
            conn.close()
    if pausar_campana and ejecutor is not None:
        ejecutor.pausar(oferta_id, motivo=f"obsolescencia propagada desde {etapa_cambiada}")
    return vueltas


def gate_de(oferta_id: str, clave: str, *, raiz: Path | None = None) -> Literal["A", "S", "H", "NA"]:
    """Gate efectivo (docs/contratos.md §2) de ``"etapa:Dn"`` o ``"accion:xxx"`` para esta oferta.

    Para ``etapa:Dn`` usa el nivel EFECTIVO (el menor entre el de la oferta, el de la etapa y
    ``autonomia.yaml`` si existe); para ``accion:xxx`` usa el nivel de la oferta. Sin ``autonomia.yaml``
    se opera solo con los niveles de ``estado.json`` (coherente con ``nivel_efectivo``, que ignora la
    autonomía si no se le pasa).
    """
    est = cargar(oferta_id, raiz=raiz)
    gates = cargar_gates()
    autonomia = _cargar_autonomia(raiz)
    if clave.startswith("etapa:"):
        etapa = clave.split(":", 1)[1]
        nivel = nivel_efectivo(etapa, est, autonomia) if etapa in est["etapas"] else est["nivel"]
    else:
        nivel = est["nivel"]
    return gate_esperado(clave, nivel, gates)


def _cargar_autonomia(raiz: Path | None) -> dict | None:
    ruta = (raiz or comun.raiz()) / "empresa" / "autonomia.yaml"
    try:
        return comun.cargar_yaml(ruta)
    except FileNotFoundError:
        return None


def siguiente_etapa(oferta_id: str, *, raiz: Path | None = None) -> str | None:
    """Próxima etapa ejecutable: la primera (en orden de dependencias) que está ``pendiente`` y cuyas
    dependencias están ``aprobado`` y no ``obsoleta``. ``None`` si no hay ninguna (todo aprobado,
    bloqueado o en curso)."""
    est = cargar(oferta_id, raiz=raiz)
    for etapa in ("D1", "M1", "D2", "D3", "D4", "D5", "D6", "D7"):
        campo = est["etapas"][etapa]
        if campo["estado"] != "pendiente":
            continue
        deps_ok = all(est["etapas"][d]["estado"] == "aprobado" and not est["etapas"][d]["obsoleta"] for d in DEPENDENCIAS.get(etapa, []))
        if deps_ok:
            return etapa
    return None


# ----------------------------------------------------------------------------------------------
# PAUSA en los dos sitios propios (el tercero, el KV del watchdog, es de infra/B8: ver README)
# ----------------------------------------------------------------------------------------------
def fijar_pausa(motivo: str, *, raiz: Path | None = None, ahora: Callable[[], datetime] = comun.ahora_utc) -> None:
    """Crea ``PAUSA``: fila ``control('pausa')`` del almacén + archivo espejo ``empresa/PAUSA``."""
    base = raiz or comun.raiz()
    t = comun.iso_z(comun.instante(ahora))
    conn = _conectar(base)
    try:
        valor = comun.json_canonico({"activa": True, "motivo": str(motivo)}).decode("utf-8")
        conn.execute(
            "INSERT INTO control(clave, valor, version, actualizado_en) VALUES ('pausa', ?, 1, ?) "
            "ON CONFLICT(clave) DO UPDATE SET valor=excluded.valor, version=control.version+1, actualizado_en=excluded.actualizado_en",
            (valor, t),
        )
    finally:
        conn.close()
    comun.escribir_atomico(base / "empresa" / "PAUSA", comun.json_canonico({"motivo": str(motivo), "desde": t}))


def quitar_pausa(*, raiz: Path | None = None, ahora: Callable[[], datetime] = comun.ahora_utc) -> None:
    """Quita ``PAUSA`` de los dos sitios propios. Borrar solo el archivo NO reactiva nada (docs/06 §5):
    use siempre esta función (o ``engine.orq reanudar``, que además exige firma y preflight VERDE)."""
    base = raiz or comun.raiz()
    t = comun.iso_z(comun.instante(ahora))
    conn = _conectar(base)
    try:
        valor = comun.json_canonico({"activa": False}).decode("utf-8")
        conn.execute(
            "INSERT INTO control(clave, valor, version, actualizado_en) VALUES ('pausa', ?, 1, ?) "
            "ON CONFLICT(clave) DO UPDATE SET valor=excluded.valor, version=control.version+1, actualizado_en=excluded.actualizado_en",
            (valor, t),
        )
    finally:
        conn.close()
    (base / "empresa" / "PAUSA").unlink(missing_ok=True)


def hay_pausa(*, raiz: Path | None = None) -> bool:
    """¿Hay ``PAUSA`` en alguno de los dos sitios propios? Falla cerrado: un control ilegible cuenta
    como pausa. El archivo lo comprueba ``engine.guard.hay_pausa`` (el mismo que usa ``comprobar_live``)."""
    base = raiz or comun.raiz()
    if _guard.hay_pausa(base):
        return True
    conn = _conectar(base)
    try:
        fila = conn.execute("SELECT valor FROM control WHERE clave='pausa'").fetchone()
    finally:
        conn.close()
    if fila is None:
        return False
    try:
        return bool(json.loads(fila[0]).get("activa"))
    except (ValueError, AttributeError, TypeError):
        return True
