"""Cargador y comprobaciones de ``empresa/limites.yaml``: los techos duros del dueño.

Regla de diseño (fail-closed): si un dato de límites que la operación necesita falta o está en
``null``, no se gasta ni se activa y la salida es el código 5 (``ErrorLimite``). Este módulo NO
reimplementa la regla: usa ``scripts.validar_esquemas.evaluar_limites`` (incluye coherencia entre
topes, sello por hash y ``ancla_hash``) y le suma lo que solo el motor puede comprobar:

* ``exigir_operacion``: ¿están los límites completos, coherentes y sellados para esta operación?
* ``exigir_tope``: un importe cabe en un tope (moneda primero, importes después; tope exacto pasa,
  tope + 1 unidad menor no).
* ``exigir_agregados``: topes que miran TODAS las campañas activas de la cuenta (M05).
* ``exigir_ritmo``: separación mínima entre ediciones, cambios por hora y horas entre aumentos.
* ``verificar_firma_sello``: la firma Ed25519 de ``sello.hash`` con la clave PÚBLICA (D-23).
* ``max_teorico_diario``: peor caso de gasto de un día (presupuesto × factor de Meta), con ``Decimal``.

Ningún número de dinero, plazo o porcentaje de decisión está en el código: todo sale del archivo.
Los 7 pasos de ``--live`` que usan estas funciones viven en ``engine.guard``.

Núcleo sin ciclos (``tests/engine/test_convenciones.py``): este módulo es parte de
``engine/{errores,comun,limites,parametros,guard,registro,transporte}.py`` y por eso NO importa
``decision`` ni ``engine.parametros`` (ni ningún literal numérico de dos o más cifras dentro de una
función). ``engine.propuestas`` (ola 1, fuera del núcleo) construye la propuesta de presupuesto de
testeo y el sellado final; importa este módulo, nunca al revés.

CLI de solo lectura::

    python -m engine.limites estado [--operacion activar] [--raiz RUTA] [--json]

Salida: 0 límites suficientes · 5 faltan datos o son incoherentes · 3 archivo inválido · 2 uso.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import ROUND_CEILING, Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import yaml

from engine import comun
from engine.errores import ErrorBloqueado, ErrorLimite, ErrorUso, ErrorValidacion
from scripts.validar_esquemas import (
    ACCIONES_GATE_MINIMAS,
    CLAVES_CRITICAS,
    buscar_floats,
    evaluar_limites,
    sello_de_limites,
)

__all__ = [
    "ACCIONES_GATE_MINIMAS", "CLAVES_CRITICAS", "CampanaActiva", "Limites", "cargar_limites", "exigir_agregados",
    "exigir_agregados_del_efecto", "exigir_operacion", "exigir_ritmo", "exigir_tope", "hash_limites", "main",
    "max_teorico_diario", "ruta_por_defecto", "verificar_firma_sello",
]

VAR_ANCLA = "LIMITES_HASH_ANCLA"  # hash vigente de limites.yaml, guardado FUERA del volumen
_UNA_HORA = timedelta(hours=1)  # unidad de la clave max_cambios_presupuesto_por_hora_por_conjunto


def ruta_por_defecto(raiz: Path | None = None) -> Path:
    """Ruta de ``empresa/limites.yaml`` bajo la raíz (``FABRICA_RAIZ`` o la del repositorio)."""
    return (raiz or comun.raiz()) / "empresa" / "limites.yaml"


@dataclass(frozen=True)
class Limites:
    """Límites cargados (solo lectura por convención).

    ``datos``: contenido del YAML. ``entorno``: entorno con que se cargó (en producción el sello
    debe traer firma). ``ancla_hash``: valor de ``LIMITES_HASH_ANCLA`` si estaba definido.
    """

    datos: Mapping[str, Any]
    ruta: Path | None = None
    entorno: str = "desarrollo"
    ancla_hash: str | None = field(default=None, repr=False)

    def get(self, clave: str, defecto: Any = None) -> Any:
        """Valor de ``clave`` o ``defecto`` (no lanza)."""
        return self.datos.get(clave, defecto)

    def __getitem__(self, clave: str) -> Any:
        return self.datos[clave]

    def valor(self, clave: str) -> Any:
        """Valor de ``clave``; ``ErrorLimite`` (5) si falta, es ``null`` o es una lista/mapa vacío."""
        v = self.datos.get(clave)
        if v is None or (isinstance(v, (list, dict)) and not v):
            raise ErrorLimite(f"falta el límite {clave} en limites.yaml (obligatorio del dueño)", detalle={"faltantes": [clave]})
        return copy.deepcopy(v)

    @property
    def moneda(self) -> str:
        """Moneda de todos los importes del archivo (``moneda_limites``)."""
        return str(self.valor("moneda_limites"))

    @property
    def hash_calculado(self) -> str:
        """Hash del contenido sin ``sello`` (el que debe llevar ``sello.hash``)."""
        return sello_de_limites(dict(self.datos))


def hash_limites(lim: Limites) -> str:
    """Hash vigente del contenido de ``limites.yaml`` (para ``LIMITES_HASH_ANCLA`` y el sello)."""
    return lim.hash_calculado


def cargar_limites(ruta: Path | str | None = None, *, env: Mapping[str, str] | None = None,
                   entorno: str | None = None) -> Limites:
    """Lee ``limites.yaml`` (por defecto ``<raíz>/empresa/limites.yaml``) y lo valida contra su esquema.

    No exige que los límites estén completos: la plantilla con ``null`` se carga y
    :func:`exigir_operacion` decide si alcanza para una operación. ``env`` y ``entorno`` son
    inyectables para pruebas (por defecto ``os.environ`` y ``FABRICA_ENTORNO``).

    Errores: ``ErrorLimite`` (5) si el archivo falta o es ilegible; ``ErrorValidacion`` (3) si no
    cumple ``limites.schema.json`` o trae números de coma flotante.
    """
    env = os.environ if env is None else env
    destino = Path(ruta) if ruta is not None else ruta_por_defecto(comun.raiz(env))
    try:
        datos = comun.cargar_yaml(destino)
    except FileNotFoundError as exc:
        raise ErrorLimite(f"falta {destino.name}: sin límites no se gasta ni se activa") from exc
    except (OSError, UnicodeDecodeError, yaml.YAMLError, ValueError) as exc:
        raise ErrorLimite(f"{destino.name} ilegible: {exc}") from exc
    if not isinstance(datos, dict):
        raise ErrorLimite(f"{destino.name} ilegible: se esperaba un mapa")
    errores = comun.errores_de_esquema("limites", datos)
    if errores:
        raise ErrorValidacion(f"{destino.name} no cumple limites.schema.json: {comun.resumir_errores_esquema(errores)}")
    flotantes = buscar_floats(datos)
    if flotantes:
        raise ErrorValidacion(f"{destino.name}: números de coma flotante prohibidos en {', '.join(flotantes[:3])}")
    ancla = (env.get(VAR_ANCLA) or "").strip() or None
    return Limites(datos=copy.deepcopy(datos), ruta=destino, entorno=entorno or comun.entorno(env), ancla_hash=ancla)


def exigir_operacion(lim: Limites, operacion: str, *, exigir_ancla: bool = False) -> None:
    """Falla con ``ErrorLimite`` (5) si los límites no alcanzan para ``operacion``.

    Delega en ``evaluar_limites`` (claves críticas no nulas, ``macro_nichos_permitidos`` intacto, sello
    que coincide con el contenido, ``sello.firma`` con formato válido en producción y coherencia entre
    topes) y en ``LIMITES_HASH_ANCLA`` si estaba definido. Con ``exigir_ancla=True`` (el caso de
    ``--live``) un ancla ausente también bloquea: sin hash fuera del volumen, un archivo reescrito junto
    con su sello pasaría. ``ErrorLimite.detalle["faltantes"]`` lista lo que falta.
    """
    if not isinstance(lim, Limites):
        raise ErrorUso("exigir_operacion exige un objeto Limites")
    if exigir_ancla and not lim.ancla_hash:
        raise ErrorLimite(f"falta {VAR_ANCLA}: el hash vigente de limites.yaml debe anclarse fuera del volumen",
                          detalle={"faltantes": [VAR_ANCLA]})
    resultado = evaluar_limites(dict(lim.datos), operacion, entorno=lim.entorno, ancla_hash=lim.ancla_hash)
    if not resultado:
        raise ErrorLimite(resultado.motivo, detalle={"faltantes": list(resultado.faltantes), "operacion": operacion})


def verificar_firma_sello(lim: Limites, clave_publica: str | None) -> None:
    """Verifica la firma Ed25519 de ``sello.hash`` con la clave PÚBLICA (``FABRICA_FIRMA_PUBLICA``).

    El contenido firmado son los bytes UTF-8 de ``sello.hash`` (``sha256:<hex>``). Una firma HMAC no se
    acepta aquí (solo sirve para ``ofertas/_ejemplo``). Errores: ``ErrorLimite`` (5) si falta la clave
    pública, el sello o la firma, o si la firma no verifica.
    """
    if not clave_publica or not str(clave_publica).strip():
        raise ErrorLimite("falta FABRICA_FIRMA_PUBLICA: no se puede verificar el sello de limites.yaml",
                          detalle={"faltantes": ["FABRICA_FIRMA_PUBLICA"]})
    sello = lim.get("sello")
    if not isinstance(sello, Mapping) or not sello.get("hash"):
        raise ErrorLimite("limites.yaml sin sello", detalle={"faltantes": ["sello"]})
    firma = sello.get("firma")
    if not isinstance(firma, str) or not firma.startswith("ed25519:"):
        raise ErrorLimite("el sello de limites.yaml no trae firma Ed25519", detalle={"faltantes": ["sello.firma"]})
    try:
        valida = comun.verificar_ed25519(str(sello["hash"]).encode("utf-8"), firma, clave_publica)
    except ErrorBloqueado as exc:
        raise ErrorLimite(f"no se puede verificar la firma del sello: {exc.mensaje}") from exc
    if not valida:
        raise ErrorLimite("la firma del sello de limites.yaml no verifica con la clave pública",
                          detalle={"faltantes": ["sello.firma(inválida)"]})


def exigir_tope(lim: Limites, clave_tope: str, monto_minor: int, moneda: str) -> None:
    """Comprueba que ``monto_minor`` (entero, unidad menor de ``moneda``) cabe en el tope ``clave_tope``.

    Orden fijo (convenciones §3): primero la moneda (``ErrorValidacion`` 3 si difiere de
    ``moneda_limites``), después el importe (``ErrorLimite`` 5 si supera el tope; igual al tope pasa).
    Un tope en ``null`` es ``ErrorLimite``.
    """
    comun.exigir_moneda(moneda)
    comun.exigir_misma_moneda(moneda, lim.moneda, f"tope {clave_tope}")
    monto = comun.exigir_importe(monto_minor, "monto_minor")
    tope = lim.valor(clave_tope)
    if monto > tope:
        raise ErrorLimite(f"{clave_tope}: {monto} {moneda} supera el tope de {tope} {moneda}",
                          detalle={"clave": clave_tope, "monto": monto, "tope": tope})


def max_teorico_diario(lim: Limites, presupuesto_diario_minor: int) -> int:
    """Peor caso de gasto en un día: ``presupuesto × factor_techo_teorico_diario``, redondeado HACIA ARRIBA.

    Meta puede gastar hasta ~1,75 veces el presupuesto diario (``factor_techo_teorico_diario`` del
    archivo de límites). Aritmética con ``Decimal``; el redondeo hacia arriba es el lado conservador.
    """
    presupuesto = comun.exigir_importe(presupuesto_diario_minor, "presupuesto_diario_minor")
    try:
        factor = Decimal(str(lim.valor("factor_techo_teorico_diario")))
    except InvalidOperation as exc:
        raise ErrorLimite("factor_techo_teorico_diario ilegible") from exc
    return int((Decimal(presupuesto) * factor).to_integral_value(rounding=ROUND_CEILING))


@dataclass(frozen=True)
class CampanaActiva:
    """Una campaña que está (o quedaría) ACTIVE en la cuenta, con las cifras que miran los agregados.

    Todos los importes son enteros en la unidad menor de ``moneda``.
    ``max_teorico_diario_minor``: presupuesto diario × factor de Meta (ver :func:`max_teorico_diario`).
    ``spend_cap_restante_minor``: ``spend_cap`` menos lo ya gastado (>= 0).
    ``perdida_acumulada_minor``: pérdida neta acumulada de la OFERTA a la que pertenece (>= 0), o
    ``None`` si no se declaró (ver :func:`desde`: a partir de un mapa es obligatorio, nunca ``None``).
    El default ``None`` existe solo para quien construye el objeto directamente en Python sin pasar
    por :func:`desde`; :func:`exigir_agregados` rechaza (``ErrorLimite``) cualquier campaña con este
    campo en ``None`` antes de sumarlo, para no confundir «pérdida declarada en 0» con «dato omitido».
    """

    oferta_id: str
    campaign_id: str
    max_teorico_diario_minor: int
    spend_cap_restante_minor: int
    moneda: str
    perdida_acumulada_minor: int | None = None

    @staticmethod
    def desde(dato: "CampanaActiva | Mapping[str, Any]") -> "CampanaActiva":
        """Normaliza un mapa (p. ej. leído de Meta) a ``CampanaActiva``; ``ErrorValidacion`` si algo falta.

        ``perdida_acumulada_minor`` es OBLIGATORIO y explícito en el mapa: a diferencia de una versión
        anterior, que lo tomaba como ``0`` si la clave faltaba (fail-open silencioso en el tope
        ``perdida_neta_acumulada_max``, M05), aquí omitirlo es ``ErrorValidacion`` igual que omitir
        ``oferta_id``. Declararlo en ``0`` explícitamente («no hay pérdida, ya lo comprobé») sí vale.
        """
        if isinstance(dato, CampanaActiva):
            return dato
        if not isinstance(dato, Mapping):
            raise ErrorValidacion("campaña activa: se esperaba un mapa")
        if "perdida_acumulada_minor" not in dato:
            raise ErrorValidacion("campaña activa: falta el campo perdida_acumulada_minor (declarar 0 explícitamente si no hay pérdida; omitirlo no se asume)")
        try:
            return CampanaActiva(
                oferta_id=str(dato["oferta_id"]),
                campaign_id=str(dato["campaign_id"]),
                max_teorico_diario_minor=comun.exigir_importe(dato["max_teorico_diario_minor"], "max_teorico_diario_minor"),
                spend_cap_restante_minor=comun.exigir_importe(dato["spend_cap_restante_minor"], "spend_cap_restante_minor"),
                moneda=comun.exigir_moneda(dato["moneda"]),
                perdida_acumulada_minor=comun.exigir_importe(dato["perdida_acumulada_minor"], "perdida_acumulada_minor"),
            )
        except KeyError as exc:
            raise ErrorValidacion(f"campaña activa: falta el campo {exc.args[0]}") from exc


def exigir_agregados(lim: Limites, activas: Iterable["CampanaActiva | Mapping[str, Any]"], *,
                     nueva: "CampanaActiva | Mapping[str, Any] | None" = None,
                     gasto_vitalicio_minor: int | None = None, exigir_nueva: bool = False) -> None:
    """Topes AGREGADOS sobre TODAS las campañas ACTIVE de la cuenta (M05); ``ErrorLimite`` si alguno se rompe.

    ``activas`` son las campañas ACTIVE hoy; ``nueva`` la que se quiere activar o cuyo presupuesto sube
    (si su ``campaign_id`` ya está en ``activas`` la reemplaza). Con ``exigir_nueva=False`` (auditoría del
    estado actual de la cuenta) ``nueva`` puede omitirse; con ``exigir_nueva=True`` (todo efecto que
    añade gasto, como hace el guard) omitirla es ``ErrorLimite`` (5): sin el efecto en la suma, el
    veredicto sería sobre una cuenta que ya no existe. Se comprueba, con «igual al tope» permitido y
    «tope + 1» rechazado:

    1. Σ máximo teórico diario ≤ ``gasto_diario_global``, y por oferta ≤ ``gasto_diario_por_oferta``.
    2. Ofertas distintas en test ≤ ``ofertas_en_test_simultaneas_max``.
    3. Σ pérdida acumulada por oferta + Σ (``spend_cap`` − gasto) ≤ ``perdida_neta_acumulada_max``.
    4. ``gasto_vitalicio`` + Σ ``spend_cap`` restante ≤ ``limite_gasto_cuenta_meta``
       (``gasto_vitalicio_minor`` es obligatorio: sin él no se puede comprobar y se bloquea).

    Moneda primero: una campaña en otra moneda que ``moneda_limites`` es ``ErrorValidacion``.
    """
    if exigir_nueva and nueva is None:
        raise ErrorLimite("falta la campaña del efecto (nueva): sin ella no se puede sumar su gasto ni contar la oferta en los topes agregados",
                          detalle={"faltantes": ["nueva"]})
    campanas: dict[str, CampanaActiva] = {}
    for dato in activas:
        c = CampanaActiva.desde(dato)
        if c.campaign_id in campanas:
            raise ErrorValidacion(
                f"campaign_id duplicado en activas: {c.campaign_id!r} aparece más de una vez (dato incoherente; no puede venir así de Meta)",
                detalle={"campaign_id": c.campaign_id},
            )
        campanas[c.campaign_id] = c
    if nueva is not None:
        c = CampanaActiva.desde(nueva)
        existente = campanas.get(c.campaign_id)
        if existente is not None and existente.oferta_id != c.oferta_id:
            raise ErrorValidacion(
                f"cuenta.nueva reutiliza el campaign_id {c.campaign_id!r} de la oferta {existente.oferta_id}, "
                f"pero es de la oferta {c.oferta_id}: dato incoherente (dos ofertas no comparten campaign_id)",
                detalle={"campaign_id": c.campaign_id, "oferta_activa": existente.oferta_id, "oferta_nueva": c.oferta_id},
            )
        campanas[c.campaign_id] = c
    moneda = lim.moneda
    for c in campanas.values():
        comun.exigir_misma_moneda(c.moneda, moneda, f"campaña {c.campaign_id}")
        if c.perdida_acumulada_minor is None:
            raise ErrorLimite(
                f"campaña {c.campaign_id}: falta perdida_acumulada_minor declarado explícitamente (no se asume 0)",
                detalle={"faltantes": ["perdida_acumulada_minor"], "campaign_id": c.campaign_id},
            )

    suma_diaria = sum(c.max_teorico_diario_minor for c in campanas.values())
    tope_global = lim.valor("gasto_diario_global")
    if suma_diaria > tope_global:
        raise ErrorLimite(f"gasto_diario_global: Σ máximo teórico diario {suma_diaria} {moneda} supera el tope de {tope_global} {moneda}",
                          detalle={"clave": "gasto_diario_global", "suma": suma_diaria, "tope": tope_global})

    por_oferta: dict[str, int] = {}
    perdida_por_oferta: dict[str, int] = {}
    for c in campanas.values():
        por_oferta[c.oferta_id] = por_oferta.get(c.oferta_id, 0) + c.max_teorico_diario_minor
        perdida_por_oferta[c.oferta_id] = max(perdida_por_oferta.get(c.oferta_id, 0), c.perdida_acumulada_minor)
    tope_oferta = lim.valor("gasto_diario_por_oferta")
    for oferta, suma in por_oferta.items():
        if suma > tope_oferta:
            raise ErrorLimite(f"gasto_diario_por_oferta: {oferta} suma {suma} {moneda} y el tope es {tope_oferta} {moneda}",
                              detalle={"clave": "gasto_diario_por_oferta", "oferta_id": oferta, "suma": suma, "tope": tope_oferta})

    simultaneas = lim.valor("ofertas_en_test_simultaneas_max")
    if len(por_oferta) > simultaneas:
        raise ErrorLimite(f"ofertas_en_test_simultaneas_max: {len(por_oferta)} ofertas en test y el máximo es {simultaneas}",
                          detalle={"clave": "ofertas_en_test_simultaneas_max", "ofertas": len(por_oferta), "tope": simultaneas})

    restante = sum(c.spend_cap_restante_minor for c in campanas.values())
    perdida = sum(perdida_por_oferta.values())
    tope_perdida = lim.valor("perdida_neta_acumulada_max")
    if perdida + restante > tope_perdida:
        raise ErrorLimite(f"perdida_neta_acumulada_max: pérdida {perdida} + spend_cap restante {restante} {moneda} supera {tope_perdida} {moneda}",
                          detalle={"clave": "perdida_neta_acumulada_max", "suma": perdida + restante, "tope": tope_perdida})

    if gasto_vitalicio_minor is None:
        raise ErrorLimite("falta el gasto vitalicio de la cuenta: no se puede comprobar limite_gasto_cuenta_meta",
                          detalle={"faltantes": ["gasto_vitalicio_minor"]})
    vitalicio = comun.exigir_importe(gasto_vitalicio_minor, "gasto_vitalicio_minor")
    tope_cuenta = lim.valor("limite_gasto_cuenta_meta")
    if vitalicio + restante > tope_cuenta:
        raise ErrorLimite(f"limite_gasto_cuenta_meta: gasto vitalicio {vitalicio} + spend_cap restante {restante} {moneda} supera {tope_cuenta} {moneda}",
                          detalle={"clave": "limite_gasto_cuenta_meta", "suma": vitalicio + restante, "tope": tope_cuenta})


def exigir_agregados_del_efecto(lim: Limites, activas: Iterable["CampanaActiva | Mapping[str, Any]"],
                                nueva: "CampanaActiva | Mapping[str, Any]", *, gasto_vitalicio_minor: int | None = None) -> None:
    """Variante de :func:`exigir_agregados` que SIEMPRE suma el efecto (``exigir_nueva=True`` fijo).

    ``exigir_agregados(lim, activas)`` (la firma congelada de docs/06 §4.2, solo 2 posicionales) sigue
    sirviendo para auditar el estado actual de la cuenta sin ningún efecto nuevo, porque su
    ``exigir_nueva`` por defecto es ``False`` (ver Decisión 4/README). Ese default permisivo es útil
    para auditoría, pero es fácil de usar por error: un llamador directo (ola 1, ``meta``) que olvide
    pasar ``exigir_nueva=True`` recupera el fail-open de M05 sin darse cuenta. Esta función, con
    ``nueva`` POSICIONAL y obligatoria, no permite ese olvido: úsala en vez de la permisiva cuando el
    efecto SÍ gasta o activa algo (lo que ``engine.guard`` ya hace internamente).
    """
    exigir_agregados(lim, activas, nueva=nueva, gasto_vitalicio_minor=gasto_vitalicio_minor, exigir_nueva=True)


def exigir_ritmo(lim: Limites, ahora: datetime, *, ediciones_recientes: Sequence[str] = (),
                 ultimo_aumento: str | None = None) -> None:
    """Hora y rate limit de los cambios de presupuesto; ``ErrorLimite`` si el ritmo no lo permite.

    ``ahora``: instante UTC con zona. ``ediciones_recientes``: instantes (``...Z``) de los cambios
    de presupuesto ya hechos al conjunto. ``ultimo_aumento``: instante del último AUMENTO (o ``None``).
    Reglas: (1) cambios en la última hora + 1 ≤ ``max_cambios_presupuesto_por_hora_por_conjunto``;
    (2) desde la última edición ≥ ``segundos_min_entre_ediciones``; (3) desde el último aumento ≥
    ``horas_min_entre_aumentos``. Un instante futuro en el historial es ``ErrorValidacion`` (dato incoherente).
    """
    if not isinstance(ahora, datetime) or ahora.tzinfo is None or ahora.utcoffset() is None:
        raise ErrorValidacion("exigir_ritmo exige un instante UTC con zona")
    maximo_hora = lim.valor("max_cambios_presupuesto_por_hora_por_conjunto")
    minimo_seg = lim.valor("segundos_min_entre_ediciones")
    instantes = [comun.parsear_z(t) for t in ediciones_recientes]
    for t in instantes:
        if t > ahora:
            raise ErrorValidacion("historial de ediciones con un instante futuro")
    en_la_hora = [t for t in instantes if ahora - t < _UNA_HORA]
    if len(en_la_hora) + 1 > maximo_hora:
        raise ErrorLimite(f"max_cambios_presupuesto_por_hora_por_conjunto: ya hay {len(en_la_hora)} cambios en la última hora (máximo {maximo_hora})",
                          detalle={"clave": "max_cambios_presupuesto_por_hora_por_conjunto", "cambios": len(en_la_hora), "tope": maximo_hora})
    if instantes and ahora - max(instantes) < timedelta(seconds=minimo_seg):
        raise ErrorLimite(f"segundos_min_entre_ediciones: la última edición fue hace menos de {minimo_seg} s",
                          detalle={"clave": "segundos_min_entre_ediciones", "tope": minimo_seg})
    if ultimo_aumento:
        horas_min = lim.valor("horas_min_entre_aumentos")
        t_aumento = comun.parsear_z(ultimo_aumento)
        if t_aumento > ahora:
            raise ErrorValidacion("último aumento con un instante futuro")
        if ahora - t_aumento < timedelta(hours=horas_min):
            raise ErrorLimite(f"horas_min_entre_aumentos: el último aumento fue hace menos de {horas_min} h",
                              detalle={"clave": "horas_min_entre_aumentos", "tope": horas_min})


# ----------------------------------------------------------------------------------------------
# CLI (solo lectura)
# ----------------------------------------------------------------------------------------------
def main(argv: Sequence[str] | None = None) -> int:
    """CLI de solo lectura: ``estado`` informa si los límites alcanzan para una operación (sin efectos)."""
    ap = argparse.ArgumentParser(prog="python -m engine.limites", description="Estado de empresa/limites.yaml (solo lectura).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    pe = sub.add_parser("estado", help="¿alcanzan los límites para una operación?")
    pe.add_argument("--operacion", default="gastar", choices=sorted(CLAVES_CRITICAS))
    pe.add_argument("--raiz", help="raíz alternativa (solo con FABRICA_ENTORNO distinto de produccion)")
    pe.add_argument("--json", action="store_true", help="una línea JSON en stdout")
    try:
        args = ap.parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2

    def cuerpo() -> int:
        env = dict(os.environ)
        if args.raiz:
            if comun.entorno(env) == "produccion":
                raise ErrorUso("--raiz no existe con FABRICA_ENTORNO=produccion")
            env["FABRICA_RAIZ"] = str(Path(args.raiz).resolve())
        lim = cargar_limites(env=env)
        datos: dict[str, Any] = {"operacion": args.operacion, "hash_calculado": lim.hash_calculado}
        try:
            exigir_operacion(lim, args.operacion)
        except ErrorLimite as exc:
            datos["faltantes"] = exc.detalle.get("faltantes", [])
            if args.json:
                print(json.dumps({"ok": False, "modo": "dry_run", "codigo": exc.codigo_salida, "datos": datos, "avisos": [exc.mensaje]},
                                 sort_keys=True, ensure_ascii=False))
            else:
                print(f"LÍMITES INSUFICIENTES para {args.operacion}: {exc.mensaje}")
            return exc.codigo_salida
        if args.json:
            print(json.dumps({"ok": True, "modo": "dry_run", "codigo": 0, "datos": datos, "avisos": []}, sort_keys=True, ensure_ascii=False))
        else:
            print(f"LÍMITES SUFICIENTES para {args.operacion}")
        return 0

    return comun.ejecutar_cli(cuerpo)


if __name__ == "__main__":
    sys.exit(main())
