"""``meta.preflight``: P01-P24 (+P25) antes de poder activar una campaña (docs/06 N11, departamentos/08 Anexo A1).

Cada check es puro: recibe los **hechos ya leídos** (de Meta, de la landing, de ``campana.json``,
de ``limites.yaml``/``parametros.yaml``) en un :class:`Contexto` y devuelve ``(estado, evidencia)``.
Este módulo NUNCA llama a Meta ni abre red: quien orquesta (``scripts/meta_crear.py`` u otro) junta
las lecturas en :class:`Entradas` y llama a :func:`generar`. Un dato ausente es **ROJO** (fail-closed:
sin evidencia no se asume que algo está bien) con una evidencia que dice qué falta.

``semaforo`` es el peor de los 24 checks (``VERDE`` solo si todos son ``VERDE`` o ``NO_APLICA``,
contratos/preflight.schema.json). ``valido_hasta = generado_en + campana.preflight_vigencia_h``
(no confundir con las 6 h de ``empresa/infra/estado.json``, docs/06 N11).
"""
from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from engine import comun, limites as motor_limites, parametros as motor_parametros
from engine.errores import ErrorUso, ErrorValidacion
from engine.limites import Limites
from engine.parametros import Parametros
from meta import monedas

__all__ = [
    "CHECKS", "Contexto", "Entradas", "EntradasPX", "ESTADOS", "PX_CHECKS", "generar", "items_px", "main", "semaforo_de",
]

CHECKS = tuple(f"P{i:02d}" for i in range(1, 25))
ESTADOS = ("VERDE", "AMARILLO", "ROJO", "NO_APLICA")
_ORDEN_GRAVEDAD = {"ROJO": 3, "AMARILLO": 2, "NO_APLICA": 0, "VERDE": 1}
_SIN_DATO = "dato ausente: no se puede dar VERDE sin evidencia (fail-closed)"


@dataclass
class Entradas:
    """Hechos ya leídos (de Meta, la landing, D5/D6) que el preflight necesita, por check.

    Un campo en ``None`` (o un sub-mapa incompleto) hace ROJO el check correspondiente: este módulo
    no asume nada que no se le haya entregado.
    """

    pausa: bool = False
    cuenta: Mapping[str, Any] = field(default_factory=dict)
    dataset: Mapping[str, Any] = field(default_factory=dict)
    emq: Mapping[str, Any] = field(default_factory=dict)
    evento_prueba: Mapping[str, Any] = field(default_factory=dict)
    dominio_verificado: bool | None = None
    landing: Mapping[str, Any] = field(default_factory=dict)
    url: Mapping[str, Any] = field(default_factory=dict)
    paquete: Mapping[str, Any] = field(default_factory=dict)
    checkout: Mapping[str, Any] = field(default_factory=dict)
    lint_claims_ok: bool | None = None
    mejoras_meta_opt_out: bool | None = None
    self_ai_disclosure_ok: bool | None = None
    mercado: Mapping[str, Any] = field(default_factory=dict)
    nombres_ok: bool | None = None
    active_errors: tuple[str, ...] = ()
    objetos_ajenos: tuple[str, ...] = ()
    vistas_previas_ok: bool | None = None
    ofertas_en_test: int | None = None
    hash_config_sellado: bool | None = None
    categoria_especial_coincide_x1: bool | None = None


@dataclass
class Contexto:
    entradas: Entradas
    campana: Mapping[str, Any]
    limites: Limites
    parametros: Parametros


def _rojo_si_falta(valor: Any) -> tuple[str, str] | None:
    return ("ROJO", _SIN_DATO) if valor is None else None


def _p01(c: Contexto) -> tuple[str, str]:
    return ("ROJO", "existe empresa/PAUSA") if c.entradas.pausa else ("VERDE", "sin PAUSA")


def _p02(c: Contexto) -> tuple[str, str]:
    estado = c.entradas.cuenta.get("estado")
    if (r := _rojo_si_falta(estado)):
        return r
    return ("VERDE", f"cuenta {estado}") if estado == "ACTIVE" else ("ROJO", f"cuenta en estado {estado}")


def _p03(c: Contexto) -> tuple[str, str]:
    v = c.entradas.cuenta.get("metodo_pago")
    if (r := _rojo_si_falta(v)):
        return r
    return ("VERDE", "método de pago configurado") if v else ("ROJO", "sin método de pago")


def _p04(c: Contexto) -> tuple[str, str]:
    v = c.entradas.cuenta.get("saludable")
    if (r := _rojo_si_falta(v)):
        return r
    return ("VERDE", "cuenta saludable") if v else ("ROJO", "cuenta con advertencias ('needs attention')")


def _p05(c: Contexto) -> tuple[str, str]:
    limite = c.entradas.cuenta.get("limite_diario_minor")
    diario = c.campana.get("presupuesto", {}).get("diario")
    if limite is None or diario is None:
        return "ROJO", _SIN_DATO
    factor = c.limites.valor("factor_techo_teorico_diario")
    from decimal import Decimal

    minimo = Decimal(diario) * Decimal(str(factor))
    if Decimal(limite) >= minimo:
        return "VERDE", f"límite diario de Meta {limite} >= {minimo}"
    return "ROJO", f"límite diario de Meta {limite} < {minimo} (1,75 x diario)"


def _p06(c: Contexto) -> tuple[str, str]:
    limite = c.entradas.cuenta.get("limite_gasto_cuenta_minor")
    if (r := _rojo_si_falta(limite)):
        return r
    if c.entradas.cuenta.get("tipo_pago") == "prepago":
        saldo_dias = c.entradas.cuenta.get("saldo_prepago_dias")
        if saldo_dias is None:
            return "ROJO", _SIN_DATO
        if saldo_dias > 3:
            return "ROJO", f"saldo prepago cubre {saldo_dias} días (máximo 3)"
    return "VERDE", "límite de gasto de cuenta fijado por el dueño"


def _p07(c: Contexto) -> tuple[str, str]:
    """P07: la cuenta tiene página vinculada. Sin dato o falso → ROJO.

    Decisión 15 del dueño (2026-11-06): el segundo administrador queda descartado por ahora. `administradores_humanos`
    es solo un dato informativo: se muestra si viene, pero NUNCA vuelve rojo este check (ni con None ni con 1).
    """
    pagina = c.entradas.cuenta.get("pagina_vinculada")
    if pagina is None:
        return "ROJO", _SIN_DATO
    if not pagina:
        return "ROJO", "sin página vinculada"
    admins = c.entradas.cuenta.get("administradores_humanos")
    return "VERDE", "página vinculada" + (f" ({admins} administrador(es) humano(s), informativo)" if admins is not None else "")


def _p08(c: Contexto) -> tuple[str, str]:
    activo = c.entradas.dataset.get("activo")
    recientes = c.entradas.dataset.get("eventos_recientes")
    if activo is None or recientes is None:
        return "ROJO", _SIN_DATO
    return ("VERDE", "dataset activo con eventos recientes") if activo and recientes else ("ROJO", "dataset inactivo o sin eventos recientes")


def _p09(c: Contexto) -> tuple[str, str]:
    valor, objetivo = c.entradas.emq.get("valor"), c.entradas.emq.get("objetivo")
    if valor is None or objetivo is None:
        return "ROJO", _SIN_DATO
    from decimal import Decimal

    return ("VERDE", f"EMQ {valor} >= {objetivo}") if Decimal(str(valor)) >= Decimal(str(objetivo)) else ("ROJO", f"EMQ {valor} < objetivo {objetivo}")


def _p10(c: Contexto) -> tuple[str, str]:
    nav, srv = c.entradas.evento_prueba.get("navegador_event_id"), c.entradas.evento_prueba.get("servidor_event_id")
    if not nav or not srv:
        return "ROJO", _SIN_DATO
    return ("VERDE", "event_id coincide en navegador y servidor") if nav == srv else ("ROJO", "event_id distinto entre navegador y servidor: Purchase se duplicaría")


def _p11(c: Contexto) -> tuple[str, str]:
    if (r := _rojo_si_falta(c.entradas.dominio_verificado)):
        return r
    return ("VERDE", "dominio verificado") if c.entradas.dominio_verificado else ("ROJO", "dominio sin verificar en el portfolio")


def _p12(c: Contexto) -> tuple[str, str]:
    estado, redir = c.entradas.landing.get("status_code"), c.entradas.landing.get("redirecciones")
    if estado is None or redir is None:
        return "ROJO", _SIN_DATO
    if estado != 200:
        return "ROJO", f"la landing responde {estado}, no 200"
    if redir:
        return "ROJO", f"la landing tiene {redir} redirecciones"
    return "VERDE", "landing 200 sin redirecciones"


def _p13(c: Contexto) -> tuple[str, str]:
    vacios, macros = c.entradas.url.get("vacios"), c.entradas.url.get("macros_presentes")
    if vacios is None or macros is None:
        return "ROJO", _SIN_DATO
    if vacios:
        return "ROJO", "la URL tiene parámetros vacíos"
    if not macros:
        return "ROJO", "la URL no lleva las macros de atribución"
    return "VERDE", "URL sin vacíos, con macros"


def _p14(c: Contexto) -> tuple[str, str]:
    paq, chk = c.entradas.paquete, c.entradas.checkout
    campos = ("landing_hash", "precio_minor", "moneda")
    if any(paq.get(k) is None or chk.get(k) is None for k in campos):
        return "ROJO", _SIN_DATO
    if paq["landing_hash"] != chk["landing_hash"]:
        return "ROJO", "landing_hash distinto entre paquete y checkout"
    if paq["precio_minor"] != chk["precio_minor"] or paq["moneda"] != chk["moneda"]:
        return "ROJO", "precio o moneda distintos entre paquete y checkout"
    return "VERDE", "landing_hash, precio y moneda coinciden"


def _p15(c: Contexto) -> tuple[str, str]:
    ok, textos = c.entradas.lint_claims_ok, c.entradas.paquete.get("textos_iguales")
    if ok is None or textos is None:
        return "ROJO", _SIN_DATO
    return ("VERDE", "copys = paquete y lint_claims OK") if ok and textos else ("ROJO", "lint_claims con ROJO o copys distintos del paquete")


def _p16(c: Contexto) -> tuple[str, str]:
    if (r := _rojo_si_falta(c.entradas.mejoras_meta_opt_out)):
        return r
    return ("VERDE", "mejoras de Meta en OPT_OUT") if c.entradas.mejoras_meta_opt_out else ("ROJO", "mejoras automáticas de Meta activas")


def _p17(c: Contexto) -> tuple[str, str]:
    if (r := _rojo_si_falta(c.entradas.self_ai_disclosure_ok)):
        return r
    return ("VERDE", "self_ai_disclosure = política") if c.entradas.self_ai_disclosure_ok else ("ROJO", "self_ai_disclosure no coincide con la política")


def _p18(c: Contexto) -> tuple[str, str]:
    locale_ok, paises_ok = c.entradas.mercado.get("locale_ok"), c.entradas.mercado.get("paises_ok")
    if locale_ok is None or paises_ok is None:
        return "ROJO", _SIN_DATO
    return ("VERDE", "locale y países = mercado.json") if locale_ok and paises_ok else ("ROJO", "locale o países distintos de mercado.json")


def _p19(c: Contexto) -> tuple[str, str]:
    if (r := _rojo_si_falta(c.entradas.nombres_ok)):
        return r
    return ("VERDE", "nombres 5.2 válidos") if c.entradas.nombres_ok else ("ROJO", "algún nombre no cumple el patrón de Meta (5.2)")


def _p20(c: Contexto) -> tuple[str, str]:
    p = c.campana.get("presupuesto", {})
    tope_diario, tope_total = c.limites.get("gasto_diario_por_oferta"), c.limites.get("gasto_total_test_por_oferta")
    if p.get("max_teorico_diario") is None or p.get("total_test") is None or tope_diario is None or tope_total is None:
        return "ROJO", _SIN_DATO
    if p["max_teorico_diario"] > tope_diario:
        return "ROJO", f"max_teorico_diario {p['max_teorico_diario']} > gasto_diario_por_oferta {tope_diario}"
    if p["total_test"] > tope_total:
        return "ROJO", f"total_test {p['total_test']} > gasto_total_test_por_oferta {tope_total}"
    try:
        if p.get("spend_cap") is not None:
            monedas.a_unidad_meta(p["spend_cap"], p["moneda"])
    except ErrorValidacion as exc:
        return "ROJO", f"spend_cap no convierte a la unidad de Meta: {exc.mensaje}"
    return "VERDE", "presupuesto y spend_cap dentro de los límites, con offset de Meta"


def _p21(c: Contexto) -> tuple[str, str]:
    if c.entradas.active_errors is None or c.entradas.objetos_ajenos is None:
        return "ROJO", _SIN_DATO
    if c.entradas.active_errors:
        return "ROJO", f"active_errors no vacío: {list(c.entradas.active_errors)[:3]}"
    if c.entradas.objetos_ajenos:
        return "ROJO", f"objetos ajenos a ids_meta.json: {list(c.entradas.objetos_ajenos)[:3]}"
    return "VERDE", "active_errors vacío, 0 objetos ajenos"


def _p22(c: Contexto) -> tuple[str, str]:
    if (r := _rojo_si_falta(c.entradas.vistas_previas_ok)):
        return r
    return ("VERDE", "vistas previas revisadas") if c.entradas.vistas_previas_ok else ("ROJO", "vistas previas no revisadas o con defecto")


def _p23(c: Contexto) -> tuple[str, str]:
    actuales = c.entradas.ofertas_en_test
    if actuales is None:
        return "ROJO", _SIN_DATO
    maximo = c.limites.get("ofertas_en_test_simultaneas_max")
    if maximo is None:
        return "ROJO", _SIN_DATO
    return ("VERDE", f"{actuales} ofertas en test (máximo {maximo})") if actuales < maximo else ("ROJO", f"{actuales} ofertas en test >= máximo {maximo}")


def _p24(c: Contexto) -> tuple[str, str]:
    if (r := _rojo_si_falta(c.entradas.hash_config_sellado)):
        return r
    return ("VERDE", "hash_config sellado") if c.entradas.hash_config_sellado else ("ROJO", "hash_config aún no sellado")


def _p25(c: Contexto) -> tuple[str, str]:
    cats = c.campana.get("special_ad_categories") or []
    if not cats:
        return "NO_APLICA", "special_ad_categories vacío"
    if (r := _rojo_si_falta(c.entradas.categoria_especial_coincide_x1)):
        return r
    return ("VERDE", "special_ad_categories = dictamen de X1") if c.entradas.categoria_especial_coincide_x1 else ("ROJO", "special_ad_categories no coincide con el dictamen de X1")


_FUNCIONES: Mapping[str, Callable[[Contexto], tuple[str, str]]] = {
    "P01": _p01, "P02": _p02, "P03": _p03, "P04": _p04, "P05": _p05, "P06": _p06, "P07": _p07, "P08": _p08,
    "P09": _p09, "P10": _p10, "P11": _p11, "P12": _p12, "P13": _p13, "P14": _p14, "P15": _p15, "P16": _p16,
    "P17": _p17, "P18": _p18, "P19": _p19, "P20": _p20, "P21": _p21, "P22": _p22, "P23": _p23, "P24": _p24,
    "P25": _p25,
}


# ----------------------------------------------------------------------------------------------
# PX1-PX4 (A4, ola 2 B5b; departamentos/08 Anexo A1, references/preflight-p01-p25.md).
#
# `contratos/preflight.schema.json` (CT, intocable) rechaza P26+ (`additionalProperties: false` en
# `checks`, enumerado cerrado de claves): estos 4 ítems NUNCA entran en el objeto que devuelve
# `generar()` (el que se sella), así que viven en una función y un informe APARTE (`items_px`).
# Pedido a CT (MINOR, ver meta/README.md «Pedidos»): un esquema propio para que esto deje de ser
# informal. Mismo criterio fail-closed que P01-P24: dato ausente = ROJO.
# ----------------------------------------------------------------------------------------------
PX_CHECKS = ("PX1", "PX2", "PX3", "PX4")

# ISO-3166 alfa-2 de los 27 países de la Unión Europea (para decidir si PX1/DSA aplica); "*" marca
# "mundial" (campana.paises de alcance global, también sujeto a DSA por si incluye UE).
_PAISES_UE = frozenset({
    "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU", "IE", "IT", "LV",
    "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK", "SI", "ES", "SE",
})


@dataclass
class EntradasPX:
    """Hechos para PX1-PX4, del mismo estilo que :class:`Entradas` (fail-closed: ``None`` es ROJO).

    ``beneficiario_esperado`` es el nombre legal de la LLC (de ``limites``/``parametros``, nunca un
    literal); ``tarifa_en_techo``/``tarifa_en_tarjeta`` los declara quien orquesta (el primero ya lo
    exige :func:`meta.payloads.calcular_presupuesto`, A6: si se calculó con ``tarifa_meta_bp`` real,
    es ``True``). ``riesgo_matriz_pais_nivel_ok`` y la cuota/envíos de PX3 siguen sin claves de
    ``limites`` (dependencias.md B1): mientras falten, un nivel de riesgo presente pero sin matriz da
    ROJO informativo, nunca `VERDE` por omisión.
    """

    paises: tuple[str, ...] = ()
    dsa_beneficiario: str | None = None
    dsa_pagador: str | None = None
    beneficiario_esperado: str | None = None
    tarifa_en_techo: bool | None = None
    tarifa_en_tarjeta: bool | None = None
    riesgo_nivel: str | None = None
    riesgo_matriz_pais_nivel_ok: bool | None = None
    terminos_sensibles_hallados: tuple[str, ...] = ()


def _destino_sujeto_a_dsa(paises: tuple[str, ...]) -> bool:
    return "*" in paises or bool(set(paises) & _PAISES_UE)


def _px1(e: EntradasPX) -> tuple[str, str]:
    if not _destino_sujeto_a_dsa(e.paises):
        return "NO_APLICA", "sin destino UE ni mundial: DSA no aplica"
    if e.dsa_beneficiario is None or e.dsa_pagador is None or e.beneficiario_esperado is None:
        return "ROJO", _SIN_DATO
    if e.dsa_beneficiario != e.beneficiario_esperado or e.dsa_pagador != e.beneficiario_esperado:
        return "ROJO", f"DSA beneficiario/pagador ({e.dsa_beneficiario}/{e.dsa_pagador}) != {e.beneficiario_esperado}"
    return "VERDE", "DSA: beneficiario y pagador son la LLC"


def _px2(e: EntradasPX) -> tuple[str, str]:
    if e.tarifa_en_techo is None or e.tarifa_en_tarjeta is None:
        return "ROJO", _SIN_DATO
    if not e.tarifa_en_techo:
        return "ROJO", "la tarifa de ubicación de Meta no está incluida en el techo del test"
    if not e.tarifa_en_tarjeta:
        return "ROJO", "la tarifa de ubicación de Meta no se declara en la tarjeta de gate"
    return "VERDE", "tarifa de ubicación incluida en el techo y en la tarjeta"


def _px3(e: EntradasPX) -> tuple[str, str]:
    if e.riesgo_nivel is None:
        return "ROJO", _SIN_DATO
    if e.riesgo_matriz_pais_nivel_ok is None:
        return "ROJO", "matriz país x nivel y cuota/envíos de riesgo sin claves en limites.yaml (dependencias.md B1): pedido abierto"
    return ("VERDE", f"riesgo {e.riesgo_nivel}; matriz país x nivel OK") if e.riesgo_matriz_pais_nivel_ok else (
        "ROJO", f"riesgo {e.riesgo_nivel} fuera de la matriz país x nivel permitida")


def _px4(e: EntradasPX) -> tuple[str, str]:
    if not e.terminos_sensibles_hallados:
        return "VERDE", "sin términos sensibles en nombres, slug, URL, UTM ni eventos"
    return "ROJO", f"términos sensibles encontrados: {list(e.terminos_sensibles_hallados)[:3]}"


_FUNCIONES_PX: Mapping[str, Callable[[EntradasPX], tuple[str, str]]] = {"PX1": _px1, "PX2": _px2, "PX3": _px3, "PX4": _px4}


def items_px(entradas: EntradasPX) -> dict[str, Any]:
    """Informe APARTE de PX1-PX4 (DSA, tarifa de ubicación, riesgo, términos sensibles).

    Nunca se pega al objeto de :func:`generar` (el esquema sellado de ``preflight`` rechaza P26+):
    este dict es solo para ``lanzamiento.log`` o la tarjeta de gate, con la MISMA forma de severidad
    (``semaforo``, ``checks``) que P01-P25 para que se lea igual, pero sin pretender cumplir
    ``contratos/preflight.schema.json``.
    """
    checks: dict[str, dict[str, str]] = {}
    for clave in PX_CHECKS:
        estado, evidencia = _FUNCIONES_PX[clave](entradas)
        checks[clave] = {"estado": estado, "evidencia": evidencia}
    return {"semaforo": semaforo_de(checks), "checks": checks}


def semaforo_de(checks: Mapping[str, Mapping[str, str]]) -> str:
    """El peor estado entre todos los checks (``VERDE`` solo si todos son ``VERDE`` o ``NO_APLICA``)."""
    peor = max((c["estado"] for c in checks.values()), key=lambda e: _ORDEN_GRAVEDAD[e], default="VERDE")
    return "VERDE" if _ORDEN_GRAVEDAD[peor] <= _ORDEN_GRAVEDAD["VERDE"] else peor


def generar(*, oferta_id: str, campana: Mapping[str, Any], limites: Limites, parametros: Parametros,
           entradas: Entradas, hash_config: str, ahora: Callable[[], datetime] = comun.ahora_utc) -> dict[str, Any]:
    """Corre los 24 (+25 si aplica) checks y devuelve el objeto listo para ``preflight.schema.json``."""
    ctx = Contexto(entradas=entradas, campana=campana, limites=limites, parametros=parametros)
    checks: dict[str, dict[str, str]] = {}
    for clave in CHECKS:
        estado, evidencia = _FUNCIONES[clave](ctx)
        checks[clave] = {"estado": estado, "evidencia": evidencia}
    cats = campana.get("special_ad_categories") or []
    if cats:
        estado, evidencia = _p25(ctx)
        checks["P25"] = {"estado": estado, "evidencia": evidencia}
    generado_en = comun.instante(ahora)
    vigencia_h = parametros.valor("campana.preflight_vigencia_h")
    return {
        "schema_version": "1.0.0", "oferta_id": oferta_id, "hash_config": hash_config,
        "generado_en": comun.iso_z(generado_en), "valido_hasta": comun.iso_z(generado_en + timedelta(hours=vigencia_h)),
        "semaforo": semaforo_de(checks), "checks": checks,
    }


def _entradas_desde_json(datos: Mapping[str, Any]) -> Entradas:
    """``Entradas`` desde un mapa (``--entradas entradas.json``): las claves ausentes o ``null`` dejan
    el default de :class:`Entradas` (fail-closed: cada check las trata como «dato ausente»)."""
    return Entradas(**{k: v for k, v in datos.items() if v is not None})


# ----------------------------------------------------------------------------------------------
# CLI (A3, ola 2 B5b): puro sobre hechos ya leídos (ningún check llama a Meta ni abre red).
# ----------------------------------------------------------------------------------------------
def main(argv: Sequence[str] | None = None) -> int:
    """``python -m meta.preflight --oferta OF-… --entradas entradas.json --campana campana.json [--salida preflight.json]``.

    Sin ``--modo``: no hay efecto externo propio (quien junta ``entradas.json`` sí pudo haber leído
    Meta, pero eso ya pasó antes de invocar este CLI). Salidas: 0 correcto (sea el semáforo el que
    sea: un preflight ROJO no es un error de CLI) · 2 uso · 3 validación · 5 límite o parámetro faltante.
    """
    ap = argparse.ArgumentParser(prog="python -m meta.preflight", description="P01-P24(+P25) sobre hechos ya leídos (docs/06 N11).")
    ap.add_argument("--oferta", required=True, dest="oferta_id")
    ap.add_argument("--entradas", required=True, dest="entradas_ruta", help="JSON con los campos de Entradas (hechos ya leídos)")
    ap.add_argument("--campana", required=True, dest="campana_ruta", help="ruta a campana.json")
    ap.add_argument("--hash-config", dest="hash_config", help="por defecto, campana.hash_config")
    ap.add_argument("--salida", help="ruta donde escribir preflight.json; si se omite, solo se imprime")
    ap.add_argument("--raiz", help="raíz alternativa (solo con FABRICA_ENTORNO distinto de produccion)")
    ap.add_argument("--ahora", help="instante UTC con Z (solo con FABRICA_ENTORNO distinto de produccion)")
    ap.add_argument("--json", action="store_true")
    try:
        args = ap.parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2

    def cuerpo() -> int:
        env = dict(os.environ)
        if (args.raiz or args.ahora) and comun.entorno(env) == "produccion":
            raise ErrorUso("--raiz y --ahora no existen con FABRICA_ENTORNO=produccion")
        raiz = Path(args.raiz).resolve() if args.raiz else comun.raiz(env)
        reloj = (lambda: comun.parsear_z(args.ahora)) if args.ahora else comun.ahora_utc
        campana = comun.cargar_json(Path(args.campana_ruta))
        if campana.get("oferta_id") != args.oferta_id:
            raise ErrorUso(f"--oferta {args.oferta_id!r} no coincide con campana.oferta_id {campana.get('oferta_id')!r}")
        entradas = _entradas_desde_json(comun.cargar_json(Path(args.entradas_ruta)))
        hash_config = args.hash_config or campana.get("hash_config")
        if not hash_config:
            raise ErrorUso("--hash-config o campana.hash_config: ninguno de los dos está presente")
        lim = motor_limites.cargar_limites(raiz / "empresa" / "limites.yaml", env=env)
        par = motor_parametros.cargar_parametros(raiz / "empresa" / "parametros.yaml")
        resultado = generar(oferta_id=args.oferta_id, campana=campana, limites=lim, parametros=par,
                            entradas=entradas, hash_config=hash_config, ahora=reloj)
        if args.salida:
            comun.escribir_atomico(Path(args.salida), comun.json_canonico(resultado))
        if args.json:
            print(comun.json_canonico({"ok": True, "modo": "dry_run", "codigo": 0, "datos": resultado, "avisos": []}).decode("utf-8"))
        else:
            import json as _json

            print(_json.dumps(resultado, indent=2, ensure_ascii=False, sort_keys=True))
        return 0

    return comun.ejecutar_cli(cuerpo)


if __name__ == "__main__":
    sys.exit(main())
