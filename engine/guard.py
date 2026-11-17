"""``guard``: la ÚNICA función de comprobaciones de ``--live`` (docs/convenciones-de-codigo.md §9).

Todo efecto externo con dinero, activación o publicación llama a :func:`comprobar_live` antes de
tocar nada. Dry-run y ``--live`` ejecutan el mismo código de decisión; la diferencia es solo la última
llamada. Los 7 pasos corren **en este orden fijo** y el primero que falla detiene todo:

=====  ==========================  =====================================================  ======
paso   nombre                      condición                                              salida
=====  ==========================  =====================================================  ======
1      ``entorno``                 ``FABRICA_ENTORNO=produccion``                         4
2      ``pausa``                   ``empresa/PAUSA`` no existe                            4
3      ``infra``                   ``empresa/infra/estado.json`` firmado (HMAC), ``modo``  4
                                   ``vivo``, todos los ítems VERDE, no futuro y con menos
                                   de ``min(infra.hc_preflight_vigencia_horas, 6)`` h
4      ``limites``                 límites completos, coherentes, sello por hash, igual   5
                                   a ``LIMITES_HASH_ANCLA`` y firma Ed25519 válida
5      ``topes``                   el efecto cabe en los topes, en los AGREGADOS de la    5
                                   cuenta y en la hora/rate limit (moneda: 3)
6      ``credenciales``            variables de entorno presentes                         2
7      ``aprobacion``              orden firmada (Ed25519) vigente si la acción exige     4
                                   gate humano (``limites.acciones_gate_humano``)
=====  ==========================  =====================================================  ======

``simulacion=True`` (solo B0): exige un ``TransporteFixture``; reemplaza SOLO el paso 1 por «entorno ∈
{prueba, desarrollo}» y el paso 3 por «``modo`` ∈ {prueba, simulado}» (con ``valido_hasta`` vigente);
los demás pasos no cambian (credenciales ficticias, firma de prueba) y devuelve ``ContextoLive`` con
``modo="fixture"``. Con ``FABRICA_ENTORNO=produccion`` se NIEGA (4).

Paso 5 y los agregados (M05): para ``activar``, ``reactivar``, ``aumentar_presupuesto`` y ``escalar`` el
gasto del propio efecto y su oferta entran SIEMPRE en la suma. Por eso ``cuenta.nueva`` (la campaña del
efecto) es obligatoria, y su ``oferta_id`` y su ``max_teorico_diario_minor`` deben ser los de la llamada
(``oferta_id`` y ``monto_minor``); si falta o no coincide, el paso 5 bloquea con 5 (fail-closed).

El reloj, el entorno, las variables y la raíz son inyectables: las pruebas de los 7 pasos NO usan
variables de entorno del proceso. Los parámetros adicionales (``transporte``, ``entorno``, ``env``,
``raiz``, ``cuenta``) son opcionales y van después de los de la firma congelada de docs/06 §4.2.

El guard no escribe nada (no registra, no consume órdenes): quien lo llama anota el resultado en el
registro. CLI de diagnóstico (sin efectos)::

    python -m engine.guard comprobar --operacion activar --oferta OF-202611-01 --monto 8750 --moneda EUR --sello sha256:… --cuenta cuenta.json [--json]

con ``cuenta.json`` = ``{"activas": […], "gasto_vitalicio_minor": 0, "nueva": {…}}`` (``nueva`` obligatoria al activar o subir presupuesto).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Literal, Mapping, Sequence

from engine import comun, limites, parametros
from engine.errores import ErrorBloqueado, ErrorFabrica, ErrorLimite, ErrorUso, ErrorValidacion
from engine.limites import CampanaActiva, Limites
from engine.transporte import Transporte, TransporteFixture
from scripts.validar_esquemas import ACCIONES_GATE_MINIMAS, comparar_hash, firma_hmac, infra_verde

__all__ = [
    "ALIAS_OPERACION", "ContextoLive", "EstadoCuenta", "OPERACIONES", "PASOS", "ReglaOperacion", "SIN_DECLARAR",
    "comprobar_live", "hay_pausa", "main", "regla_de",
]

PASOS = ("entorno", "pausa", "infra", "limites", "topes", "credenciales", "aprobacion")

VAR_FIRMA_PUBLICA = "FABRICA_FIRMA_PUBLICA"
VAR_CLAVE_PREFLIGHT = "PREFLIGHT_HMAC_KEY"
# Parámetro que acota cuánto vive una orden firmada. Hasta que parametros.yaml tenga uno propio, una
# aprobación no puede ser más vieja que el preflight de campaña que aprueba (ver README, «Decisiones»).
PARAMETRO_VIGENCIA_ORDEN = "campana.preflight_vigencia_h"
PARAMETRO_VIGENCIA_INFRA = "infra.hc_preflight_vigencia_horas"

# Anclada con "^...$" pero usada con .fullmatch(): "$" solo, con .match(), deja pasar un salto de línea
# final (p. ej. un sello "sha256:<64 hex>\n"); .fullmatch() exige cubrir la cadena completa.
_RX_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
_LARGO_SELLO_VISIBLE = 19  # «sha256:» + 12 hex: lo bastante para identificarlo en un mensaje
_CREDENCIALES_META = ("META_TOKEN_OPERADOR", "META_AD_ACCOUNT_ID", "META_APP_SECRET")


class _Centinela:
    """Marca «nunca declarado explícitamente», distinta de un valor vacío o ``None`` real.

    ``EstadoCuenta.ediciones_recientes`` y ``.ultimo_aumento`` la usan como default: un llamador que
    de verdad comprobó que no hay historial debe pasar ``()`` o ``None`` EXPLÍCITAMENTE; quien no pasa
    nada (y así, sin querer, se queda con el default) no debe colar silenciosamente «sin historial» en
    el rate limit (ver README, observación de la ronda de endurecimiento sobre M05).
    """

    def __repr__(self) -> str:  # pragma: no cover - solo para mensajes de depuración
        return "SIN_DECLARAR"


SIN_DECLARAR = _Centinela()


@dataclass(frozen=True)
class ReglaOperacion:
    """Qué exige el guard a una operación. Todo son NOMBRES de claves o de variables, nunca valores.

    ``clave_limites``: operación de ``CLAVES_CRITICAS`` cuyas claves deben estar completas.
    ``tope``: clave de ``limites.yaml`` contra la que se compara ``monto_minor`` (``None`` = sin importe).
    ``agregados``: comprobar los topes agregados de la cuenta; ``ritmo``: hora y rate limit de presupuesto.
    ``accion_gate``: acción de ``contratos/gates.json`` que, si está en ``acciones_gate_humano``, exige
    una orden firmada. ``credenciales``: variables de entorno necesarias (``infra/plantillas/variables-entorno.yaml``).
    """

    clave_limites: str
    tope: str | None = None
    agregados: bool = False
    ritmo: bool = False
    accion_gate: str | None = None
    credenciales: tuple[str, ...] = ()


OPERACIONES: Mapping[str, ReglaOperacion] = {
    "gastar": ReglaOperacion("gastar", tope="gasto_diario_por_oferta", credenciales=_CREDENCIALES_META),
    "activar": ReglaOperacion("activar", tope="gasto_diario_por_oferta", agregados=True, accion_gate="activar_campana",
                              credenciales=_CREDENCIALES_META),
    "reactivar": ReglaOperacion("activar", tope="gasto_diario_por_oferta", agregados=True, accion_gate="reactivar_tras_pausa",
                                credenciales=_CREDENCIALES_META),
    "aumentar_presupuesto": ReglaOperacion("aumentar_presupuesto", tope="gasto_diario_por_oferta", agregados=True, ritmo=True,
                                           credenciales=_CREDENCIALES_META),
    "escalar": ReglaOperacion("escalar", tope="gasto_diario_por_oferta", agregados=True, ritmo=True, credenciales=_CREDENCIALES_META),
    "reembolsar_auto": ReglaOperacion("reembolsar_auto", tope="reembolso_auto_max", credenciales=("STRIPE_RK_REEMBOLSO",)),
    "descubrir": ReglaOperacion("descubrir", tope="max_costo_por_barrido"),
    "generar_creativos": ReglaOperacion("generar_creativos"),
    "enviar_correo": ReglaOperacion("enviar_correo", credenciales=("CORREO_API_KEY",)),
}
ALIAS_OPERACION: Mapping[str, str] = {
    "activar_campana": "activar", "reactivar_tras_pausa": "reactivar", "crear_borrador": "gastar", "meta_crear": "gastar",
    "subir_presupuesto": "aumentar_presupuesto", "reembolso_automatico": "reembolsar_auto",
}


def regla_de(operacion: str) -> ReglaOperacion:
    """Regla de una operación (acepta alias). ``ErrorLimite`` si la operación no existe: lo desconocido no se permite."""
    nombre = ALIAS_OPERACION.get(operacion, operacion)
    regla = OPERACIONES.get(nombre) if isinstance(nombre, str) else None
    if regla is None:
        raise ErrorLimite(f"operación desconocida para el guard: {operacion!r}", detalle={"operacion": str(operacion)})
    return regla


@dataclass(frozen=True)
class EstadoCuenta:
    """Lo que el guard no puede saber solo y debe leer quien lo llama (p. ej. ``meta.activar`` leyendo Meta).

    ``activas``: campañas ACTIVE hoy en la cuenta (TODAS). ``nueva``: la campaña del efecto (la que se activa
    o cuyo presupuesto sube); es **obligatoria** en toda operación con topes agregados (``activar``,
    ``reactivar``, ``aumentar_presupuesto``, ``escalar``) y debe coincidir con ``oferta_id`` y con
    ``monto_minor`` de la llamada (su ``max_teorico_diario_minor`` ES el ``monto_minor``); sin ella o con
    otra cifra el paso 5 bloquea (5). Si su ``campaign_id`` ya está en ``activas`` la reemplaza (subir el
    presupuesto no duplica la campaña). ``gasto_vitalicio_minor``: gasto acumulado de la cuenta.
    ``ediciones_recientes`` y ``ultimo_aumento``: historial de cambios de presupuesto del conjunto
    (instantes ``...Z``). Su default es :data:`SIN_DECLARAR`, NO ``()``/``None``: para las operaciones
    con ``ritmo`` (``aumentar_presupuesto``, ``escalar``) el paso 5 exige que el llamador pase
    EXPLÍCITAMENTE ``()`` (sin ediciones) o ``None`` (sin aumento previo) si ese es el estado real;
    dejar el default puesto (quien lo construyó se olvidó de leer el historial) bloquea con
    ``ErrorLimite``, en vez de colar silenciosamente «sin historial» como antes.
    """

    activas: tuple["CampanaActiva | Mapping[str, Any]", ...] = ()
    gasto_vitalicio_minor: int | None = None
    nueva: "CampanaActiva | Mapping[str, Any] | None" = None
    ediciones_recientes: "tuple[str, ...] | _Centinela" = SIN_DECLARAR
    ultimo_aumento: "str | None | _Centinela" = SIN_DECLARAR


@dataclass(frozen=True)
class ContextoLive:
    """Resultado de un ``comprobar_live`` aprobado. No contiene credenciales.

    ``modo``: ``"live"`` o ``"fixture"`` (simulación de B0). ``pasos``: los pasos superados, en orden.
    ``aprobacion``: ``nonce`` de la orden firmada usada (o ``None`` si la acción no exige gate humano).
    ``clave_idempotencia``: hash determinista de (operación, oferta, importe, sello) para el efecto.
    """

    modo: Literal["live", "fixture"]
    operacion: str
    oferta_id: str | None
    monto_minor: int | None
    moneda: str | None
    instante: str
    hash_limites: str
    infra_generado_en: str
    sello: str | None
    aprobacion: str | None
    clave_idempotencia: str
    pasos: tuple[str, ...] = field(default_factory=tuple)


# ----------------------------------------------------------------------------------------------
# Paso 1 y 2
# ----------------------------------------------------------------------------------------------
def _paso_entorno(entorno: "str | Callable[[], str] | None", env: Mapping[str, str], simulacion: bool,
                  transporte: Transporte | None) -> str:
    """Paso 1: ``FABRICA_ENTORNO=produccion`` (o, en simulación, prueba/desarrollo con ``TransporteFixture``)."""
    try:
        if callable(entorno):
            actual = entorno()
        elif isinstance(entorno, str):
            actual = entorno
        else:
            actual = comun.entorno(env)
    except ErrorUso as exc:
        raise ErrorBloqueado(f"entorno ilegible: {exc.mensaje}") from exc
    if actual not in comun.ENTORNOS:
        raise ErrorBloqueado("entorno desconocido: no se asume ninguno")
    if simulacion:
        if not isinstance(transporte, TransporteFixture):
            raise ErrorBloqueado("simulacion=True exige un TransporteFixture: sin él se niega")
        if actual == "produccion":
            raise ErrorBloqueado("simulacion=True está prohibida con FABRICA_ENTORNO=produccion")
    elif actual != "produccion":
        raise ErrorBloqueado(f"--live solo con FABRICA_ENTORNO=produccion (el entorno es {actual})")
    return actual


def _paso_pausa(base: Path) -> None:
    """Paso 2: no debe existir ``empresa/PAUSA``."""
    if hay_pausa(base):
        raise ErrorBloqueado("existe empresa/PAUSA: se detiene todo gasto y activación")


def hay_pausa(base: Path) -> bool:
    """¿Existe ``<base>/empresa/PAUSA``? Cualquier error al comprobarlo cuenta como «hay pausa» (falla cerrado).

    Borrar el archivo no reactiva nada por sí mismo (docs/06 §5); aquí solo se comprueba su presencia.
    """
    try:
        os.lstat(base / "empresa" / "PAUSA")
    except FileNotFoundError:
        return False
    except OSError:
        return True
    return True


# ----------------------------------------------------------------------------------------------
# Paso 3
# ----------------------------------------------------------------------------------------------
def _paso_infra(base: Path, env: Mapping[str, str], t: datetime, simulacion: bool) -> str:
    """Paso 3: ``estado.json`` válido contra su esquema, firmado, en el modo correcto, VERDE y fresco."""
    ruta = base / "empresa" / "infra" / "estado.json"
    try:
        estado = comun.cargar_json(ruta)
    except FileNotFoundError as exc:
        raise ErrorBloqueado("falta empresa/infra/estado.json: sin infraestructura verde no se gasta ni se activa") from exc
    except (OSError, ValueError, UnicodeDecodeError) as exc:
        raise ErrorBloqueado("empresa/infra/estado.json ilegible") from exc
    if not isinstance(estado, dict):
        raise ErrorBloqueado("empresa/infra/estado.json ilegible: se esperaba un objeto")
    if comun.errores_de_esquema("infra_estado", estado):
        raise ErrorBloqueado("empresa/infra/estado.json no cumple infra_estado.schema.json (¿items ausentes o campos extra?)")
    clave = (env.get(VAR_CLAVE_PREFLIGHT) or "").encode("utf-8")
    if not clave:
        raise ErrorBloqueado(f"falta {VAR_CLAVE_PREFLIGHT}: no se puede verificar la firma de estado.json")
    esperada = firma_hmac({k: v for k, v in estado.items() if k != "firma"}, clave)
    if not comparar_hash(esperada, estado["firma"]):
        raise ErrorBloqueado("firma de estado.json inválida: el archivo fue alterado o la clave no coincide")
    modo = estado.get("modo")
    if simulacion:
        if modo not in ("prueba", "simulado"):
            raise ErrorBloqueado(f"simulación: el modo de infraestructura debe ser prueba o simulado (es {modo!r})")
    elif modo != "vivo":
        raise ErrorBloqueado(f"infraestructura en modo {modo!r}: solo «vivo» habilita gastar o activar")
    try:
        maximo_h = parametros.cargar_parametros(base / "empresa" / "parametros.yaml").valor(PARAMETRO_VIGENCIA_INFRA)
    except ErrorFabrica as exc:
        raise ErrorBloqueado(f"no se pudo leer {PARAMETRO_VIGENCIA_INFRA}: {exc.mensaje}") from exc
    if isinstance(maximo_h, bool) or not isinstance(maximo_h, int) or maximo_h < 1:
        raise ErrorBloqueado(f"{PARAMETRO_VIGENCIA_INFRA} inválido")
    verde, motivo = infra_verde(estado, lambda: t, maximo_h, exigir_modo=None)
    if not verde:
        raise ErrorBloqueado(f"infraestructura no verde: {motivo}")
    return str(estado["generado_en"])


# ----------------------------------------------------------------------------------------------
# Paso 4 y 5
# ----------------------------------------------------------------------------------------------
def _paso_limites(base: Path, env: Mapping[str, str], entorno_actual: str, regla: ReglaOperacion) -> Limites:
    """Paso 4: límites cargados, completos para la operación, coherentes, sellados, anclados y firmados."""
    try:
        lim = limites.cargar_limites(base / "empresa" / "limites.yaml", env=env, entorno=entorno_actual)
    except ErrorLimite:
        raise
    except ErrorFabrica as exc:  # esquema inválido, etc.: para el guard «límites no válidos» es siempre 5
        raise ErrorLimite(exc.mensaje, detalle=exc.detalle) from exc
    limites.exigir_operacion(lim, regla.clave_limites, exigir_ancla=True)
    limites.verificar_firma_sello(lim, env.get(VAR_FIRMA_PUBLICA))
    return lim


def _campana_del_efecto(cuenta: EstadoCuenta, oferta_id: str | None, monto_minor: int | None) -> CampanaActiva:
    """La campaña que el efecto activa o cuyo presupuesto sube, ATADA a lo que el llamador declara aprobar.

    Los topes agregados suman el gasto del propio efecto y cuentan su oferta. Si el llamador pudiera
    omitir ``cuenta.nueva`` (o dar una con otro importe u otra oferta), el paso 5 aprobaría contra una
    cuenta sin el efecto (fail-open). Por eso, para toda operación con ``agregados``:

    * ``cuenta.nueva`` es obligatoria (``ErrorLimite`` 5, ``faltantes=["cuenta.nueva"]``);
    * ``oferta_id`` y ``monto_minor`` también (``ErrorValidacion`` 3: son entradas del llamador);
    * ``nueva.oferta_id`` debe ser ``oferta_id`` y ``nueva.max_teorico_diario_minor`` debe ser EXACTAMENTE
      ``monto_minor`` (el peor caso del efecto): un importe distinto es un dato incoherente, no se elige
      uno (``ErrorLimite`` 5). La moneda ya la ata ``exigir_agregados`` a ``moneda_limites``, igual que
      ``exigir_tope`` ata la de ``monto_minor``.
    """
    if cuenta.nueva is None:
        raise ErrorLimite("falta la campaña del efecto (cuenta.nueva): sin ella no se puede sumar su gasto ni contar su oferta en los topes agregados",
                          detalle={"faltantes": ["cuenta.nueva"]})
    if not isinstance(oferta_id, str) or not oferta_id.strip():
        raise ErrorValidacion("esta operación exige oferta_id: los topes agregados cuentan las ofertas distintas en test")
    if monto_minor is None:
        raise ErrorValidacion("esta operación exige monto_minor (el peor caso del efecto, en la unidad menor)")
    nueva = CampanaActiva.desde(cuenta.nueva)
    if nueva.oferta_id != oferta_id:
        raise ErrorLimite(f"cuenta.nueva es de la oferta {nueva.oferta_id} y la operación es de {oferta_id}: dato incoherente",
                          detalle={"clave": "cuenta.nueva", "oferta_id": oferta_id, "oferta_nueva": nueva.oferta_id})
    if nueva.max_teorico_diario_minor != monto_minor:
        raise ErrorLimite(f"cuenta.nueva declara un máximo teórico diario de {nueva.max_teorico_diario_minor} y monto_minor es {monto_minor}: "
                          "deben coincidir (monto_minor es el peor caso del efecto)",
                          detalle={"clave": "cuenta.nueva", "nueva": nueva.max_teorico_diario_minor, "monto_minor": monto_minor})
    return nueva


def _historial_de_ritmo(cuenta: EstadoCuenta) -> tuple[Sequence[str], str | None]:
    """``(ediciones_recientes, ultimo_aumento)`` de ``cuenta``, EXIGIENDO que estén declarados explícitamente.

    Si quien construyó ``EstadoCuenta`` dejó el default (:data:`SIN_DECLARAR`) en vez de pasar ``()``
    o ``None`` a propósito, el ritmo no se puede comprobar: antes eso se leía como «sin historial» y
    saltaba el ``max_cambios_presupuesto_por_hora_por_conjunto``/``horas_min_entre_aumentos`` sin que
    nadie lo decidiera (fail-open). Aquí se bloquea con ``ErrorLimite`` (5) en vez de asumir nada.
    """
    faltan = [nombre for nombre, valor in (("ediciones_recientes", cuenta.ediciones_recientes), ("ultimo_aumento", cuenta.ultimo_aumento))
             if valor is SIN_DECLARAR]
    if faltan:
        raise ErrorLimite(
            "falta declarar explícitamente el historial de ritmo de la cuenta (" + ", ".join(faltan) + "): "
            "pasar () o None a propósito si de verdad no hay historial, no dejar el valor por defecto",
            detalle={"faltantes": faltan},
        )
    return cuenta.ediciones_recientes, cuenta.ultimo_aumento  # type: ignore[return-value]


def _paso_topes(lim: Limites, regla: ReglaOperacion, oferta_id: str | None, monto_minor: int | None, moneda: str | None,
                cuenta: EstadoCuenta | None, t: datetime) -> None:
    """Paso 5: el importe cabe en su tope, en los agregados de la cuenta (con el propio efecto) y en el ritmo permitido."""
    if regla.tope is not None:
        if monto_minor is None or moneda is None:
            raise ErrorValidacion("esta operación exige monto_minor y moneda (el peor caso del efecto, en la unidad menor)")
        limites.exigir_tope(lim, regla.tope, monto_minor, moneda)
    elif monto_minor is not None:
        comun.exigir_importe(monto_minor, "monto_minor")
    if regla.agregados or regla.ritmo:
        if cuenta is None:
            raise ErrorLimite("falta el estado de la cuenta (campañas ACTIVE y gasto vitalicio): no se pueden comprobar los topes agregados",
                              detalle={"faltantes": ["cuenta"]})
        if regla.agregados:
            nueva = _campana_del_efecto(cuenta, oferta_id, monto_minor)
            limites.exigir_agregados_del_efecto(lim, cuenta.activas, nueva, gasto_vitalicio_minor=cuenta.gasto_vitalicio_minor)
        if regla.ritmo:
            ediciones, ultimo = _historial_de_ritmo(cuenta)
            limites.exigir_ritmo(lim, t, ediciones_recientes=ediciones, ultimo_aumento=ultimo)


# ----------------------------------------------------------------------------------------------
# Paso 6 y 7
# ----------------------------------------------------------------------------------------------
def _paso_credenciales(regla: ReglaOperacion, env: Mapping[str, str], simulacion: bool) -> None:
    """Paso 6: variables de credenciales presentes (en simulación, y solo ficticias)."""
    faltan = [n for n in regla.credenciales if not (env.get(n) or "").strip()]
    if faltan:
        raise ErrorUso(f"faltan credenciales en el entorno: {', '.join(faltan)}", detalle={"faltantes": faltan})
    if simulacion:
        reales = [n for n in regla.credenciales if comun.enmascarar_secretos(str(env[n])) != str(env[n])]
        if reales:
            raise ErrorBloqueado(f"simulación con credenciales que parecen reales: {', '.join(reales)}")


def _paso_aprobacion(base: Path, env: Mapping[str, str], lim: Limites, regla: ReglaOperacion, oferta_id: str | None,
                     sello: str | None, t: datetime) -> str | None:
    """Paso 7: si la acción exige gate humano, debe existir una orden firmada, vigente y exacta para ``sello``.

    La orden (``empresa/ordenes/<nonce>.json``: ``accion, oferta_id, etapa?, hash_objetivo, ts, nonce, firma``)
    la registra ``POST /ordenes`` o ``orq firmar``; aquí solo se consume en lectura. Devuelve su ``nonce``.
    """
    accion = regla.accion_gate
    if accion is None or accion not in (set(ACCIONES_GATE_MINIMAS) | set(lim.get("acciones_gate_humano") or ())):
        return None
    if not isinstance(sello, str) or not _RX_SHA256.fullmatch(sello):
        raise ErrorBloqueado(f"la acción {accion} exige aprobación humana: falta el sello (hash del objeto aprobado)")
    clave_publica = env.get(VAR_FIRMA_PUBLICA)
    if not clave_publica or not clave_publica.strip():
        raise ErrorBloqueado(f"falta {VAR_FIRMA_PUBLICA}: no se puede verificar la orden firmada")
    try:
        vigencia_h = parametros.cargar_parametros(base / "empresa" / "parametros.yaml").valor(PARAMETRO_VIGENCIA_ORDEN)
    except ErrorFabrica as exc:
        raise ErrorBloqueado(f"no se pudo leer {PARAMETRO_VIGENCIA_ORDEN}: {exc.mensaje}") from exc
    if isinstance(vigencia_h, bool) or not isinstance(vigencia_h, int) or vigencia_h < 1:
        raise ErrorBloqueado(f"{PARAMETRO_VIGENCIA_ORDEN} inválido")
    carpeta = base / "empresa" / "ordenes"
    archivos = sorted(carpeta.glob("*.json")) if carpeta.is_dir() else []
    motivos: list[str] = []
    for archivo in archivos:
        try:
            orden = comun.cargar_json(archivo)
        except (OSError, ValueError, UnicodeDecodeError):
            motivos.append("orden ilegible")
            continue
        if not isinstance(orden, dict) or orden.get("accion") != accion or orden.get("oferta_id") != oferta_id:
            continue
        if orden.get("hash_objetivo") != sello:
            motivos.append("orden para otro hash")
            continue
        try:
            momento = comun.parsear_z(orden.get("ts"))
        except ErrorValidacion:
            motivos.append("orden con ts ilegible")
            continue
        if momento > t:
            motivos.append("orden con fecha futura")
            continue
        if t - momento > timedelta(hours=vigencia_h):
            motivos.append("orden vencida")
            continue
        cuerpo = {k: v for k, v in orden.items() if k != "firma"}
        if not isinstance(orden.get("nonce"), str) or not comun.verificar_ed25519(comun.json_canonico(cuerpo), str(orden.get("firma")), clave_publica):
            motivos.append("firma de la orden inválida")
            continue
        return str(orden["nonce"])
    detalle = f" ({'; '.join(sorted(set(motivos)))})" if motivos else ""
    raise ErrorBloqueado(f"sin orden firmada vigente para {accion} sobre {sello[:_LARGO_SELLO_VISIBLE]}…{detalle}")


# ----------------------------------------------------------------------------------------------
# Función pública
# ----------------------------------------------------------------------------------------------
def comprobar_live(operacion: str, *, oferta_id: str | None = None, monto_minor: int | None = None,
                   moneda: str | None = None, sello: str | None = None,
                   ahora: Callable[[], datetime] = comun.ahora_utc, simulacion: bool = False,
                   transporte: Transporte | None = None, entorno: "str | Callable[[], str] | None" = None,
                   env: Mapping[str, str] | None = None, raiz: Path | None = None,
                   cuenta: EstadoCuenta | None = None) -> ContextoLive:
    """Ejecuta los 7 pasos de ``--live`` en orden fijo y devuelve un :class:`ContextoLive`, o lanza el primer error.

    Entradas de la firma congelada: ``operacion`` (``gastar``, ``activar``, ``reembolsar_auto``…; acepta
    alias), ``oferta_id``, ``monto_minor`` + ``moneda`` (el PEOR CASO del efecto, en la unidad menor, p. ej.
    el máximo teórico diario de ``limites.max_teorico_diario``), ``sello`` (hash del objeto aprobado, p. ej.
    ``hash_config``), ``ahora`` (reloj) y ``simulacion``. Entradas adicionales, todas opcionales:
    ``transporte`` (obligatorio y de tipo ``TransporteFixture`` con ``simulacion``), ``entorno`` (texto o
    función; por defecto ``FABRICA_ENTORNO``), ``env`` (variables; por defecto ``os.environ``), ``raiz``
    (por defecto ``comun.raiz``) y ``cuenta`` (:class:`EstadoCuenta`, necesaria para los topes agregados).
    Para ``activar``, ``reactivar``, ``aumentar_presupuesto`` y ``escalar`` también son obligatorios
    ``oferta_id`` y ``cuenta.nueva`` (la campaña del efecto, con ``oferta_id`` y ``max_teorico_diario_minor``
    iguales a los de la llamada): el gasto del propio efecto y su oferta entran SIEMPRE en la suma.

    Errores (todos ``ErrorFabrica``; ``detalle["paso"]`` dice cuál falló y ``detalle["pasos_ok"]`` cuáles
    pasaron): 4 entorno, PAUSA, infraestructura o aprobación; 5 límites, topes, agregados, ritmo; 3 moneda
    distinta o dato inválido; 2 credenciales ausentes. No escribe nada.
    """
    variables: Mapping[str, str] = os.environ if env is None else env
    t = comun.instante(ahora)
    superados: list[str] = []

    def paso(nombre: str, accion: Callable[[], Any]) -> Any:
        try:
            resultado = accion()
        except ErrorFabrica as exc:
            exc.detalle.setdefault("paso", nombre)
            exc.detalle.setdefault("pasos_ok", tuple(superados))
            raise
        superados.append(nombre)
        return resultado

    def resolver_entorno_y_raiz() -> tuple[str, Path]:
        # La raíz del repositorio es parte del paso «entorno»: con ``FABRICA_RAIZ`` inexistente el
        # guard falla CERRADO (BLOQUEADO, exit 4, paso «entorno») en vez de escapar como ``ErrorUso``
        # (exit 2) sin paso asignado (CT2-14).
        actual = _paso_entorno(entorno, variables, simulacion, transporte)
        if raiz is not None:
            return actual, Path(raiz)
        try:
            return actual, comun.raiz(variables)
        except ErrorUso as exc:
            raise ErrorBloqueado(f"raíz del repositorio inválida: {exc.mensaje}") from exc

    entorno_actual, base = paso("entorno", resolver_entorno_y_raiz)
    paso("pausa", lambda: _paso_pausa(base))
    generado_en = paso("infra", lambda: _paso_infra(base, variables, t, simulacion))

    def cargar_y_comprobar_limites() -> tuple[ReglaOperacion, Limites]:
        regla_op = regla_de(operacion)
        return regla_op, _paso_limites(base, variables, entorno_actual, regla_op)

    regla, lim = paso("limites", cargar_y_comprobar_limites)
    paso("topes", lambda: _paso_topes(lim, regla, oferta_id, monto_minor, moneda, cuenta, t))
    paso("credenciales", lambda: _paso_credenciales(regla, variables, simulacion))
    nonce = paso("aprobacion", lambda: _paso_aprobacion(base, variables, lim, regla, oferta_id, sello, t))
    return ContextoLive(
        modo="fixture" if simulacion else "live",
        operacion=ALIAS_OPERACION.get(operacion, operacion),
        oferta_id=oferta_id,
        monto_minor=monto_minor,
        moneda=moneda,
        instante=comun.iso_z(t),
        hash_limites=lim.hash_calculado,
        infra_generado_en=generado_en,
        sello=sello,
        aprobacion=nonce,
        clave_idempotencia=comun.clave_idempotencia(ALIAS_OPERACION.get(operacion, operacion), oferta_id or "empresa",
                                                    {"monto_minor": monto_minor, "moneda": moneda, "sello": sello}),
        pasos=tuple(superados),
    )


# ----------------------------------------------------------------------------------------------
# CLI de diagnóstico
# ----------------------------------------------------------------------------------------------
def _cuenta_desde_archivo(ruta: Path) -> EstadoCuenta:
    """Lee un ``EstadoCuenta`` de un JSON ``{activas, gasto_vitalicio_minor, nueva, ediciones_recientes?, ultimo_aumento?}``.

    ``nueva`` es opcional para ESTE lector, pero el paso 5 la exige en toda operación con agregados.
    ``ediciones_recientes``/``ultimo_aumento`` AUSENTES del JSON quedan en :data:`SIN_DECLARAR` (no en
    ``()``/``None``): si la operación necesita el ritmo, el paso 5 bloqueará en vez de asumir «sin
    historial». Un archivo inexistente o ilegible es ``ErrorUso`` (2, argumento de la CLI), no un
    ``FileNotFoundError`` sin tipo.
    """
    try:
        datos = comun.cargar_json(ruta)
    except FileNotFoundError as exc:
        raise ErrorUso(f"--cuenta no existe: {ruta}") from exc
    except (OSError, ValueError, UnicodeDecodeError) as exc:
        raise ErrorUso(f"--cuenta ilegible: {exc}") from exc
    if not isinstance(datos, dict):
        raise ErrorValidacion("el archivo de cuenta debe ser un objeto JSON")
    ediciones = tuple(datos["ediciones_recientes"]) if "ediciones_recientes" in datos else SIN_DECLARAR
    ultimo = datos["ultimo_aumento"] if "ultimo_aumento" in datos else SIN_DECLARAR
    return EstadoCuenta(
        activas=tuple(datos.get("activas") or ()), gasto_vitalicio_minor=datos.get("gasto_vitalicio_minor"),
        nueva=datos.get("nueva"), ediciones_recientes=ediciones, ultimo_aumento=ultimo,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """CLI ``comprobar``: evalúa los 7 pasos y dice cuál falla. No ejecuta ningún efecto."""
    ap = argparse.ArgumentParser(prog="python -m engine.guard", description="Diagnóstico de los 7 pasos de --live (sin efectos).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    pc = sub.add_parser("comprobar", help="evalúa los 7 pasos para una operación")
    pc.add_argument("--operacion", required=True)
    pc.add_argument("--oferta")
    pc.add_argument("--monto", type=int, help="peor caso del efecto en la unidad menor")
    pc.add_argument("--moneda")
    pc.add_argument("--sello")
    pc.add_argument("--cuenta", help="JSON con el estado de la cuenta: activas, gasto_vitalicio_minor y nueva (la campaña del efecto; obligatoria al activar o subir presupuesto)")
    pc.add_argument("--modo", choices=("live", "fixture"), default="live",
                    help="fixture = simulación de B0 (TransporteFixture vacío); exige entorno prueba o desarrollo")
    pc.add_argument("--raiz", help="raíz alternativa (solo con FABRICA_ENTORNO distinto de produccion)")
    pc.add_argument("--ahora", help="instante UTC con Z (solo con FABRICA_ENTORNO distinto de produccion)")
    pc.add_argument("--json", action="store_true", help="una línea JSON en stdout")
    try:
        args = ap.parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2

    def cuerpo() -> int:
        env = dict(os.environ)
        if (args.raiz or args.ahora) and comun.entorno(env) == "produccion":
            raise ErrorUso("--raiz y --ahora no existen con FABRICA_ENTORNO=produccion")
        raiz = Path(args.raiz).resolve() if args.raiz else None
        reloj = (lambda: comun.parsear_z(args.ahora)) if args.ahora else comun.ahora_utc
        simulacion = args.modo == "fixture"
        # Se lee ANTES del try de los 7 pasos (como el --raiz/--ahora de arriba): un --cuenta inexistente
        # o ilegible es un error de USO (2/3) de argumentos de la CLI, no un fallo de un paso con nombre;
        # mezclarlo con el try de abajo daba código 1 (FileNotFoundError sin tipo) o "paso": None.
        cuenta = _cuenta_desde_archivo(Path(args.cuenta)) if args.cuenta else None
        try:
            ctx = comprobar_live(
                args.operacion, oferta_id=args.oferta, monto_minor=args.monto, moneda=args.moneda, sello=args.sello, ahora=reloj,
                simulacion=simulacion, transporte=TransporteFixture() if simulacion else None, env=env, raiz=raiz,
                cuenta=cuenta,
            )
        except ErrorFabrica as exc:
            datos = {"paso": exc.detalle.get("paso"), "pasos_ok": list(exc.detalle.get("pasos_ok", ()))}
            if args.json:
                print(json.dumps({"ok": False, "modo": args.modo, "codigo": exc.codigo_salida, "datos": datos, "avisos": [exc.mensaje]},
                                 sort_keys=True, ensure_ascii=False))
            else:
                print(f"BLOQUEADO en el paso «{datos['paso']}»: {exc.mensaje}")
            return exc.codigo_salida
        datos = {"pasos": list(ctx.pasos), "clave_idempotencia": ctx.clave_idempotencia, "hash_limites": ctx.hash_limites}
        if args.json:
            print(json.dumps({"ok": True, "modo": ctx.modo, "codigo": 0, "datos": datos, "avisos": []}, sort_keys=True, ensure_ascii=False))
        else:
            print(f"LIVE PERMITIDO ({ctx.modo}): " + " → ".join(ctx.pasos))
        return 0

    return comun.ejecutar_cli(cuerpo)


if __name__ == "__main__":
    sys.exit(main())
