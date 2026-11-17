"""``propuestas``: ``proponer_limites`` y ``sellar_limites`` -- la herramienta del dueño para fijar la pérdida máxima.

docs/06 §4.2 las nombra ``engine.limites proponer/sellar``, pero ``engine/limites.py`` es NÚCLEO congelado
(``tests/engine/test_convenciones.py``: no puede importar ``decision`` ni ``engine.parametros`` ni traer
literales de decisión). Viven aquí, en su propio módulo (antes colgaban del final de ``engine.d8``).
CLI: ``python -m engine.propuestas {proponer,sellar}``. ``proponer`` no toca ``empresa/limites.yaml``;
``sellar`` solo lo escribe con ``--live`` y ``FABRICA_ENTORNO=produccion`` (convenciones §9).
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from decision import entradas as ent
from decision.reglas import LimitesCelda
from engine import comun
from engine.d8 import _cargar_economia
from engine.errores import ErrorBloqueado, ErrorLimite, ErrorUso, ErrorValidacion
from engine.limites import ruta_por_defecto as _ruta_limites_por_defecto
from engine.parametros import Parametros

__all__ = ["proponer_limites", "ruta_propuesta_por_defecto", "sellar_limites"]

_RAZONES_TABLA_PROPUESTA = (
    ("ganador_en_objetivo", Decimal("0.6")), ("ganador_justo", Decimal("0.85")), ("equilibrio", Decimal(1)),
    ("perdedor_moderado", Decimal("1.5")), ("perdedor_severo", Decimal(4)),
)
_MACRO_NICHOS_FIJOS = ["salud", "relaciones", "dinero"]
_CLAVES_LIMITES_TODAS: tuple[str, ...] = (
    "moneda_limites", "capital_en_riesgo_total", "reserva_no_publicitaria_pct", "gasto_diario_global",
    "gasto_diario_por_oferta", "gasto_total_test_por_oferta", "perdida_max_test_por_oferta", "perdida_neta_acumulada_max",
    "stop_loss_escala", "ofertas_en_test_simultaneas_max", "limite_gasto_cuenta_meta", "factor_techo_teorico_diario",
    "aumento_presupuesto_max_pct_por_paso", "horas_min_entre_aumentos", "max_cambios_presupuesto_por_hora_por_conjunto",
    "segundos_min_entre_ediciones", "cuentas_permitidas", "paises_permitidos", "locales_permitidos",
    "macro_nichos_permitidos", "subnichos_prohibidos", "lineas_rojas", "precio_neto_minimo", "autoaprobar_hasta",
    "reembolso_auto_max", "reembolsos_auto_max_por_dia", "ratio_disputas_pausa", "cupon_descuento_max_pct",
    "politica_reembolso_dias", "creditos_max_pieza", "creditos_max_oferta", "max_budget_por_corrida_agente",
    "costo_max_validacion", "costo_max_producto", "max_costo_por_barrido", "politica_divulgacion_ia",
    "dias_cobertura_caja", "correos_max_por_dia", "correos_max_por_semana", "max_consultas_biblioteca",
    "ventana_veto_min", "fuentes_permitidas", "fuentes_prohibidas", "max_busquedas_por_barrido",
    "max_barridos_por_semana", "acciones_gate_humano",
)


def _frac_texto(x: float) -> str:
    """Probabilidad (0-1) de la simulación a cadena decimal corta (convenciones §3: sin ``float``)."""
    if x in (0.0, 1.0):
        return f"{x:.0f}"
    s = f"{round(x, 4):.4f}".rstrip("0")
    return s[:-1] if s.endswith(".") else s


def ruta_propuesta_por_defecto(raiz: Path | None = None) -> Path:
    """Ruta de ``empresa/propuestas/limites.propuesta.yaml`` (la escribe :func:`proponer_limites`)."""
    return (raiz or comun.raiz()) / "empresa" / "propuestas" / "limites.propuesta.yaml"


def proponer_limites(oferta_id: str, par: Parametros, *, multiplos: Sequence[int] = (10, 15, 25),
                     raiz: Path | None = None, corridas: int = 400, semilla: int = 20261106) -> dict:
    """Propone ``gasto_total_test_por_oferta``/``perdida_max_test_por_oferta`` desde ``economia.json``.

    Para cada múltiplo del CPA de equilibrio, simula (``decision.simulacion``, ya probado) cinco
    escenarios -- ganador en el objetivo, ganador justo, equilibrio, perdedor moderado y severo -- y
    devuelve el % de corridas MATAR/ESCALAR/INCONCLUSO y el gasto medio hasta la decisión. Escribe
    ``empresa/propuestas/limites.propuesta.yaml`` con el múltiplo intermedio como punto de partida
    (claves con guion bajo, como ``_candidatos``, son solo informativas: :func:`sellar_limites` las
    descarta). **No modifica** ``empresa/limites.yaml``.

    Errores: ``ErrorBloqueado`` (4) si falta ``economia.json``; ``ParametroFaltante`` (5) si falta un
    umbral -- incluye hoy ``estadistica.alfa_descarte_tope``/``n_min_escala`` (el esquema de parámetros
    todavía no las tiene, grupo con ``additionalProperties: false``; ver NOTAS_B1b «Pedidos» a CT).
    """
    from decision.simulacion import ConfigSim, Escenario, simular_escenario

    multiplos_ok = sorted({int(m) for m in multiplos})
    if not multiplos_ok or any(m <= 0 for m in multiplos_ok):
        raise ErrorValidacion("multiplos exige enteros positivos")
    base = raiz or comun.raiz()
    economia = _cargar_economia(oferta_id, base)
    par_decision = ent.parametros_decision(par, economia)
    dias_defecto = int(par.valor("campana.dias_test_defecto"))

    candidatos: list[dict[str, Any]] = []
    for m in multiplos_ok:
        tope = m * par_decision.cpa_equilibrio_minor
        diario = max(1, tope // dias_defecto)
        cfg = ConfigSim(presupuesto_diario_minor=diario, tope_gasto_minor=tope, max_dias=max(3 * dias_defecto, 40),
                        sigma_gasto=0.15, sigma_cpc=0.20, sigma_conv=0.0)
        lim_celda = LimitesCelda(tope)
        filas = []
        for nombre, razon in _RAZONES_TABLA_PROPUESTA:
            conv = par_decision.cpc_prior_minor / float(razon * par_decision.cpa_equilibrio_minor)
            esc = Escenario(nombre, par_decision.cpc_prior_minor, conv, f"CPA real = {razon} x equilibrio")
            r = simular_escenario(esc, par_decision, lim_celda, cfg, corridas, semilla)
            filas.append({
                "escenario": nombre, "razon_cpa_sobre_equilibrio": str(razon), "p_matar": _frac_texto(r.p_matar),
                "p_escalar": _frac_texto(r.p_escalar), "p_inconcluso": _frac_texto(r.p_inconcluso),
                "gasto_medio_minor": int(round(r.gasto_medio_minor)),
            })
        candidatos.append({"multiplo": m, "gasto_total_test_por_oferta": tope, "perdida_max_test_por_oferta": tope, "tabla": filas})
    recomendado = candidatos[len(candidatos) // 2]

    ruta_actual = _ruta_limites_por_defecto(base)
    try:
        previa = comun.cargar_yaml(ruta_actual)
        if not isinstance(previa, dict):
            previa = {}
    except FileNotFoundError:
        previa = {}
    salida: dict[str, Any] = {clave: previa.get(clave) for clave in _CLAVES_LIMITES_TODAS}
    salida["schema_version"] = previa.get("schema_version", "1.0.0")
    salida["version"] = int(previa.get("version") or 0) + 1
    salida["moneda_limites"] = salida["moneda_limites"] or par_decision.moneda
    salida["gasto_total_test_por_oferta"] = recomendado["gasto_total_test_por_oferta"]
    salida["perdida_max_test_por_oferta"] = recomendado["perdida_max_test_por_oferta"]
    if not salida["macro_nichos_permitidos"]:
        salida["macro_nichos_permitidos"] = list(_MACRO_NICHOS_FIJOS)
    salida["_oferta_id"] = oferta_id
    salida["_multiplo_recomendado"] = recomendado["multiplo"]
    salida["_candidatos"] = candidatos

    ruta_salida = ruta_propuesta_por_defecto(base)
    ruta_salida.parent.mkdir(parents=True, exist_ok=True)
    import yaml as _yaml

    comun.escribir_atomico(ruta_salida, _yaml.safe_dump(salida, sort_keys=False, allow_unicode=True).encode("utf-8"))
    return {"ruta": str(ruta_salida), "multiplo_recomendado": recomendado["multiplo"], "candidatos": candidatos}


def sellar_limites(ruta_propuesta: Path | str, *, como: str, modo: str = "dry_run", raiz: Path | None = None,
                   ruta_clave_privada: Path | str | None = None, env: Mapping[str, str] | None = None,
                   ahora: Callable[[], datetime] = comun.ahora_utc) -> dict:
    """Verifica, calcula el sello y (solo en ``--live``) escribe ``empresa/limites.yaml``.

    **Único** escritor de ``empresa/limites.yaml``; corre en el terminal del dueño. ``modo="dry_run"``
    (por defecto) no escribe nada; ``modo="live"`` exige ``FABRICA_ENTORNO=produccion``. Descarta las
    claves con guion bajo de la propuesta (metadatos de :func:`proponer_limites`).

    Errores: ``ErrorUso`` (2) si ``como != "dueno"``; ``ErrorValidacion`` (3) si la propuesta no cumple
    el esquema; ``ErrorLimite`` (5) si, con el sello puesto, los límites no alcanzan para ``activar``;
    ``ErrorBloqueado`` (4) si ``--live`` se pide fuera de producción.
    """
    import yaml as _yaml

    from scripts.validar_esquemas import buscar_floats, evaluar_limites, sello_de_limites

    if como != "dueno":
        raise ErrorValidacion("sellar exige --como dueno (quien tiene la clave privada Ed25519)")
    if modo not in ("dry_run", "live"):
        raise ErrorValidacion(f"modo desconocido: {modo!r} (se esperaba dry_run o live)")
    env = __import__("os").environ if env is None else env
    if modo == "live" and comun.entorno(env) != "produccion":
        raise ErrorBloqueado("sellar --live exige FABRICA_ENTORNO=produccion; sin --live, dry-run")
    datos = comun.cargar_yaml(Path(ruta_propuesta))
    if not isinstance(datos, dict):
        raise ErrorValidacion(f"{ruta_propuesta}: se esperaba un mapa")
    limpio: dict[str, Any] = {k: v for k, v in datos.items() if not str(k).startswith("_")}
    faltan = [k for k in _CLAVES_LIMITES_TODAS if k not in limpio]
    if faltan:
        raise ErrorValidacion(f"la propuesta no trae estas claves del esquema: {', '.join(faltan)}")
    limpio.setdefault("schema_version", "1.0.0")
    base = raiz or comun.raiz()
    ruta_actual = _ruta_limites_por_defecto(base)
    try:
        previo = comun.cargar_yaml(ruta_actual)
        version_previa = int(previo.get("version", 0)) if isinstance(previo, dict) else 0
    except FileNotFoundError:
        version_previa = 0
    limpio["version"] = max(int(limpio.get("version") or 0), version_previa + 1)
    hash_contenido = sello_de_limites(limpio)
    firma = comun.firmar_ed25519(hash_contenido.encode("utf-8"), Path(ruta_clave_privada)) if ruta_clave_privada else None
    sello: dict[str, Any] = {"hash": hash_contenido, "firmado_por": como, "firmado_en": comun.iso_z(comun.instante(ahora))}
    if firma:
        sello["firma"] = firma
    limpio["sello"] = sello
    errores = comun.errores_de_esquema("limites", limpio)
    if errores:
        raise ErrorValidacion(f"la propuesta sellada no cumple limites.schema.json: {comun.resumir_errores_esquema(errores)}")
    if buscar_floats(limpio):
        raise ErrorValidacion("números de coma flotante prohibidos en la propuesta sellada")
    resultado = evaluar_limites(limpio, "activar", entorno=(comun.entorno(env) if modo == "live" else "desarrollo"))
    if not resultado:
        raise ErrorLimite(resultado.motivo, detalle={"faltantes": list(resultado.faltantes)})
    if modo == "live":
        comun.escribir_atomico(ruta_actual, _yaml.safe_dump(limpio, sort_keys=False, allow_unicode=True).encode("utf-8"))
    return {"hash": hash_contenido, "firmado": firma is not None, "modo": modo, "ruta": str(ruta_actual), "version": limpio["version"]}


# ----------------------------------------------------------------------------------------------
# CLI: python -m engine.propuestas {proponer,sellar}   (docs/06 §4.2 «engine.limites proponer/sellar»)
# ----------------------------------------------------------------------------------------------
def main(argv: "Sequence[str] | None" = None) -> int:
    import argparse
    import json

    from engine.parametros import cargar_parametros

    ap = argparse.ArgumentParser(prog="python -m engine.propuestas", description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    pp = sub.add_parser("proponer", help="simula escenarios y escribe empresa/propuestas/limites.propuesta.yaml (no toca limites.yaml)")
    pp.add_argument("--oferta", required=True)
    pp.add_argument("--multiplos", type=int, nargs="+", default=[10, 15, 25])
    pp.add_argument("--corridas", type=int, default=400)
    pp.add_argument("--semilla", type=int, default=20261106)
    pp.add_argument("--json", action="store_true")
    ps = sub.add_parser("sellar", help="verifica y sella la propuesta; escribe empresa/limites.yaml SOLO con --live (producción)")
    ps.add_argument("--propuesta")
    ps.add_argument("--como", required=True)
    ps.add_argument("--live", action="store_true")
    ps.add_argument("--clave-privada")
    ps.add_argument("--json", action="store_true")

    def cuerpo() -> int:
        try:
            a = ap.parse_args(argv)
        except SystemExit as exc:
            if exc.code in (0, None):
                return 0
            raise ErrorUso("argumentos inválidos (ver --help)") from None
        if a.cmd == "proponer":
            par = cargar_parametros()
            resultado = proponer_limites(a.oferta, par, multiplos=tuple(a.multiplos), corridas=a.corridas, semilla=a.semilla)
        else:
            ruta = a.propuesta or str(ruta_propuesta_por_defecto())
            resultado = sellar_limites(ruta, como=a.como, modo="live" if a.live else "dry_run", ruta_clave_privada=a.clave_privada)
        print(json.dumps(resultado, ensure_ascii=False, sort_keys=True, default=str) if a.json else json.dumps(resultado, ensure_ascii=False, indent=2, default=str))
        return 0

    return comun.ejecutar_cli(cuerpo)


if __name__ == "__main__":
    raise SystemExit(main())
