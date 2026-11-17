"""``agentes.runner`` — ejecución desatendida de UNA corrida Maker o QA (docs/09-runtime-de-agentes.md §12).

``preparar(espec) -> PlanCorrida`` es puro (sin efectos, testeable). ``ejecutar(espec, *, modo,
fixture_dir=None)`` corre en tres modos: ``DRY_RUN`` (construye y muestra el plan, no ejecuta),
``FIXTURE`` (sin procesos ni red: reproduce una corrida grabada en ``tests/fixtures/agentes/``,
§12.8) y ``LIVE`` (todo el preflight de §12.3 y, si pasa, el proceso ``claude -p`` real). La
validación de la salida (§12.6) es la MISMA función para ``FIXTURE`` y ``LIVE``: lo que cambia es
de dónde viene el ``result`` y los artefactos.

CLI: ``python -m agentes.runner --espec espec.json [--fixture DIR] [--live]``.
Códigos de salida (convenciones §8; docs/09 §12.1): 0 ok · 1 interno · 2 uso · 3 inválido ·
4 bloqueado/pausa/preflight · 5 presupuesto/turnos · 6 timeout/bucle/error.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
from decimal import ROUND_DOWN, Decimal
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from agentes import perfil
from agentes.tipos import (
    CODIGO_POR_ESTADO, EspecCorrida, Modo, PlanCorrida, Presupuesto, ResultadoCorrida, espec_desde_mapa,
)
from engine import comun as motor
from engine import limites as motor_limites
from engine import parametros as motor_parametros
from engine.errores import ErrorFabrica

__all__ = [
    "CODIGO_POR_ESTADO", "EspecCorrida", "Modo", "PlanCorrida", "Presupuesto", "ResultadoCorrida",
    "ejecutar", "espec_desde_mapa", "main", "preparar",
]

# Exactamente las 18 claves de contratos/parametros.schema.json#/properties/grupos/properties/agentes
# (= docs/09 §12.2).
_CLAVES_PARAMETROS_AGENTES = (
    "claude_version_min", "modelo", "fallback_modelo", "esfuerzo", "tiempo_s_max", "turnos_max",
    "holgura_pct", "reintentos_transitorios_max", "backoff_base_s", "reintentos_validacion_max",
    "gracia_s", "pausa_poll_s", "bucle_repeticion_max", "bucle_sin_progreso_turnos",
    "estado_max_edad_h", "bash_timeout_defecto_ms", "bash_timeout_max_ms", "hook_timeout_s",
)


def _run_id_por_defecto(espec: EspecCorrida) -> str:
    """ID determinista (no UUID): hash de los campos que identifican la corrida + la ronda."""
    base = {"etapa": espec.etapa, "rol": espec.rol, "oferta_id": espec.oferta_id, "agente": espec.agente,
            "ronda": espec.ronda, "prompt_base": espec.prompt_base[:200]}
    resumen = motor.hash_objeto(base)  # "sha256:<hex>"
    return f"{espec.etapa}-{espec.rol}-r{espec.ronda}-{resumen[7:19]}"


def _nombre_schema(contrato_salida: str) -> str:
    base = Path(contrato_salida).name
    return base[: -len(".schema.json")] if base.endswith(".schema.json") else base


# ----------------------------------------------------------------------------------------------
# preparar(): puro
# ----------------------------------------------------------------------------------------------
def preparar(espec: EspecCorrida, *, raiz: Path | None = None, run_id: str | None = None,
            parametros_agentes: Mapping[str, Any] | None = None,
            env_externo: Mapping[str, str] | None = None) -> PlanCorrida:
    """Construye el plan completo de una corrida (argv, entorno, settings) SIN ejecutar nada."""
    base = raiz if raiz is not None else motor.raiz()
    rid = run_id or _run_id_por_defecto(espec)
    staging = perfil.ruta_staging_relativa(espec, rid)
    settings = perfil.construir_settings_efectivo(espec, base)
    settings_relativa = f"empresa/runs/{rid}/settings.efectivo.json"
    parametros_ag = dict(parametros_agentes or {})
    entorno = perfil.construir_entorno(espec, run_id=rid, raiz=base, staging_relativa=staging,
                                       parametros_agentes=parametros_ag, env_externo=env_externo)
    holgura_pct = parametros_ag.get("holgura_pct", 0)
    holgura = Decimal(str(holgura_pct)) / Decimal(100)
    presupuesto_usd = (Decimal(espec.presupuesto.usd_centavos_max) / Decimal(100)) * (Decimal(1) - holgura)
    if presupuesto_usd < 0:
        presupuesto_usd = Decimal(0)
    presupuesto_cli = str(presupuesto_usd.quantize(Decimal("0.01"), rounding=ROUND_DOWN))
    argv = perfil.construir_argv(espec, run_id=rid, raiz=base, settings_relativa=settings_relativa,
                                 presupuesto_cli_usd=presupuesto_cli)
    return PlanCorrida(run_id=rid, argv=tuple(argv), entorno=entorno, settings_efectivo=settings,
                       staging_relativa=staging, presupuesto_cli_usd=presupuesto_cli)


# ----------------------------------------------------------------------------------------------
# Validación de la salida (§12.6) — COMPARTIDA entre FIXTURE y LIVE
# ----------------------------------------------------------------------------------------------
def _costo_desde_resultado(resultado_cli: Mapping[str, Any], espec: EspecCorrida) -> dict[str, Any]:
    total = resultado_cli.get("total_cost_usd")
    confiable = total not in (None, 0)
    centavos = int(round(float(total) * 100)) if confiable else espec.presupuesto.usd_centavos_max
    return {
        "centavos_usd": centavos, "moneda": "USD", "es_estimacion": True, "confiable": confiable,
        "por_modelo": resultado_cli.get("modelUsage") or resultado_cli.get("model_usage") or {},
    }


def _base_resultado(espec: EspecCorrida, run_id: str, resultado_cli: Mapping[str, Any], *, registro_ruta: str) -> dict[str, Any]:
    return {
        "run_id": run_id, "rol": espec.rol, "etapa": espec.etapa, "oferta_id": espec.oferta_id,
        "turnos": int(resultado_cli.get("num_turns") or 0), "duracion_ms": int(resultado_cli.get("duration_ms") or 0),
        "session_id": resultado_cli.get("session_id"), "claude_version": resultado_cli.get("claude_version"),
        "denegaciones": list(resultado_cli.get("permission_denials") or ()), "registro_ruta": registro_ruta,
        "costo": _costo_desde_resultado(resultado_cli, espec),
    }


def _detectar_bucle(eventos: Sequence[Mapping[str, Any]], parametros_agentes: Mapping[str, Any]) -> str | None:
    """Misma ``(tool_name, hash(tool_input))`` repetida >= ``bucle_repeticion_max`` veces seguidas (§12.5)."""
    maximo = parametros_agentes.get("bucle_repeticion_max")
    if not eventos or not isinstance(maximo, int) or maximo < 1:
        return None
    contador = 0
    anterior: tuple[Any, Any] | None = None
    for ev in eventos:
        if ev.get("type") != "assistant":
            continue
        for bloque in (ev.get("message", {}) or {}).get("content") or ():
            if not isinstance(bloque, Mapping) or bloque.get("type") != "tool_use":
                continue
            clave = (bloque.get("name"), motor.hash_objeto(bloque.get("input") or {}))
            contador = contador + 1 if clave == anterior else 1
            anterior = clave
            if contador >= maximo:
                return f"«{bloque.get('name')}» con los mismos argumentos repetido {contador} veces seguidas"
    return None


def _validar_structured_output(espec: EspecCorrida, resultado_cli: Mapping[str, Any]) -> tuple[Any, str | None]:
    """``(structured_output, None)`` si valida contra ``contrato_salida``; si no, ``(None, motivo)``."""
    subtype = resultado_cli.get("subtype")
    if subtype != "success" or resultado_cli.get("is_error"):
        return None, f"subtype={subtype!r} is_error={bool(resultado_cli.get('is_error'))}"
    structured = resultado_cli.get("structured_output")
    if structured is None:
        return None, "éxito sin structured_output"
    problemas = motor.errores_de_esquema(_nombre_schema(espec.contrato_salida), structured)
    if problemas:
        primero = problemas[0]
        return None, f"{_nombre_schema(espec.contrato_salida)}: {getattr(primero, 'message', str(primero))[:160]}"
    return structured, None


def _validar_maker(espec: EspecCorrida, staging: Path, structured: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    """Cada ``artefactos_esperados[i]`` existe, valida contra su contrato y coincide con ``structured_output``.

    Ningún archivo fuera de ``staging`` (el escape se detecta ANTES de tocar disco: ``..`` o ruta
    absoluta en la lista de artefactos esperados ya es, por definición, «fuera de ruta»).
    """
    nombre_schema = _nombre_schema(espec.contrato_salida)
    errores: list[str] = []
    manifiesto: list[dict[str, Any]] = []
    for rel in espec.artefactos_esperados:
        ruta_rel = Path(rel)
        if ruta_rel.is_absolute() or ".." in ruta_rel.parts:
            errores.append(f"{rel}: artefacto fuera de ruta (escapa del staging)")
            continue
        destino = staging / ruta_rel
        if not destino.is_file():
            errores.append(f"{rel}: no existe en el staging")
            continue
        datos_bytes = destino.read_bytes()
        try:
            contenido = json.loads(datos_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            errores.append(f"{rel}: no es JSON válido ({exc})")
            continue
        problemas = motor.errores_de_esquema(nombre_schema, contenido)
        if problemas:
            errores.append(f"{rel} inválido: {getattr(problemas[0], 'message', str(problemas[0]))[:160]}")
            continue
        if len(espec.artefactos_esperados) == 1 and contenido != structured:
            errores.append(f"{rel}: no coincide con structured_output")
            continue
        manifiesto.append({"ruta": rel, "sha256": motor.hash_bytes(datos_bytes), "bytes": len(datos_bytes)})
    # ningún archivo FUERA de rutas_escribibles: todo lo que se validó ya vive bajo `staging`, que
    # ES la única ruta escribible del Maker (perfil.construir_settings_efectivo); un archivo
    # cualquiera que el agente hubiera escrito fuera de ahí lo habría denegado pretooluse_gasto.
    return manifiesto, errores


def _validar_qa(structured: Mapping[str, Any]) -> tuple[str | None, list[str]]:
    """Anti-sello-de-goma (>= 3 hallazgos o justificación) y coherencia del veredicto con severidades."""
    errores: list[str] = []
    hallazgos = structured.get("hallazgos") or []
    justificacion = structured.get("justificacion_sin_hallazgos")
    if len(hallazgos) < 3 and not (isinstance(justificacion, str) and len(justificacion) >= 20):
        errores.append("QA sin evidencia suficiente: menos de 3 hallazgos y sin justificación (sello de goma)")
    veredicto = structured.get("veredicto")
    abiertos_graves = [h for h in hallazgos if h.get("severidad") in ("BLOQUEANTE", "MAYOR") and h.get("estado") == "abierto"]
    if veredicto == "PASS" and abiertos_graves:
        errores.append("veredicto PASS incoherente: hay un hallazgo BLOQUEANTE o MAYOR abierto")
    return veredicto, errores


# ----------------------------------------------------------------------------------------------
# Modo FIXTURE (§12.8)
# ----------------------------------------------------------------------------------------------
def _ejecutar_fixture(espec: EspecCorrida, fixture_dir: Path, *, raiz: Path, run_id: str) -> ResultadoCorrida:
    resultado_cli = motor.cargar_json(fixture_dir / "resultado.json")
    parametros_agentes = motor.cargar_json(fixture_dir / "parametros_agentes.json")
    stream_ruta = fixture_dir / "stream.jsonl"
    eventos = motor.leer_jsonl(stream_ruta) if stream_ruta.is_file() else []
    comun = _base_resultado(espec, run_id, resultado_cli, registro_ruta=str(fixture_dir))

    if (raiz / "empresa" / "PAUSA").exists():
        return ResultadoCorrida(**comun, estado="pausa", veredicto=None, salida=None,
                                errores=["PAUSA activa a mitad de la corrida: staging descartado, sin reintento"])

    motivo_bucle = _detectar_bucle(eventos, parametros_agentes)
    if motivo_bucle:
        return ResultadoCorrida(**comun, estado="bucle", veredicto=None, salida=None, errores=[motivo_bucle])

    subtype = resultado_cli.get("subtype")
    if subtype == "error_max_turns":
        return ResultadoCorrida(**comun, estado="turnos", veredicto=None, salida=None, errores=["error_max_turns"])
    if subtype == "error_max_budget_usd":
        return ResultadoCorrida(**comun, estado="presupuesto", veredicto=None, salida=None, errores=["error_max_budget_usd"])

    structured, motivo = _validar_structured_output(espec, resultado_cli)
    if motivo and subtype not in (None, "success"):
        return ResultadoCorrida(**comun, estado="error", veredicto=None, salida=None, errores=[motivo])
    if motivo:
        return ResultadoCorrida(**comun, estado="invalido", veredicto=None, salida=None, errores=[motivo])

    if espec.rol == "qa":
        veredicto, errores_qa = _validar_qa(structured)
        if errores_qa:
            return ResultadoCorrida(**comun, estado="invalido", veredicto=veredicto, salida=structured, errores=errores_qa)
        return ResultadoCorrida(**comun, estado="ok", veredicto=veredicto, salida=structured, errores=[])

    # Maker: copia artefactos/ de la fixture a un staging temporal y valida ahí (sin tocar disco real).
    with tempfile.TemporaryDirectory(prefix=f"agente-fixture-{run_id}-") as tmp:
        staging = Path(tmp)
        origen = fixture_dir / "artefactos"
        if origen.is_dir():
            shutil.copytree(origen, staging, dirs_exist_ok=True)
        manifiesto, errores_maker = _validar_maker(espec, staging, structured)
        if errores_maker:
            return ResultadoCorrida(**comun, estado="invalido", veredicto=None, salida=structured, artefactos=[], errores=errores_maker)
        return ResultadoCorrida(**comun, estado="ok", veredicto=None, salida=structured, artefactos=manifiesto, errores=[])


# ----------------------------------------------------------------------------------------------
# Preflight de LIVE (§12.3) — cualquier fallo -> estado "preflight", SIN gastar
# ----------------------------------------------------------------------------------------------
def _preflight(espec: EspecCorrida, *, raiz: Path, env: Mapping[str, str], ahora: Callable[[], Any]) -> list[str]:
    violaciones: list[str] = []
    try:
        entorno_actual = motor.entorno(env)
    except ErrorFabrica as exc:
        return [f"entorno: {exc.mensaje}"]
    if entorno_actual != "produccion":
        return [f"--live solo con FABRICA_ENTORNO=produccion (es {entorno_actual!r})"]

    if (raiz / "empresa" / "PAUSA").exists():
        violaciones.append("existe empresa/PAUSA")

    max_horas_infra: int | None = None
    try:
        parametros = motor_parametros.cargar_parametros(raiz / "empresa" / "parametros.yaml")
        faltan = [c for c in _CLAVES_PARAMETROS_AGENTES if not parametros.tiene(f"agentes.{c}")]
        if faltan:
            violaciones.append("faltan parametros.agentes: " + ", ".join(faltan))
        elif int(parametros.valor("agentes.estado_max_edad_h")):
            max_horas_infra = int(parametros.valor("agentes.estado_max_edad_h"))
    except ErrorFabrica as exc:
        violaciones.append(f"parametros.yaml: {exc.mensaje}")

    try:
        lim = motor_limites.cargar_limites(raiz / "empresa" / "limites.yaml", env=env)
        presupuesto_max = lim.valor("max_budget_por_corrida_agente")
        if espec.presupuesto.usd_centavos_max > presupuesto_max:
            violaciones.append("presupuesto pedido > limites.max_budget_por_corrida_agente")
    except ErrorFabrica as exc:
        violaciones.append(f"limites.yaml: {exc.mensaje}")

    if max_horas_infra is not None:
        from scripts.validar_esquemas import infra_verde
        try:
            estado = motor.cargar_json(raiz / "empresa" / "infra" / "estado.json")
            verde, motivo_infra = infra_verde(estado, ahora, max_horas_infra)
            if not verde:
                violaciones.append(f"infra no verde: {motivo_infra}")
        except (OSError, ValueError, UnicodeDecodeError) as exc:
            violaciones.append(f"empresa/infra/estado.json: {exc}")

    if not (env.get("ANTHROPIC_API_KEY") or "").strip():
        violaciones.append("falta ANTHROPIC_API_KEY")
    return violaciones


# ----------------------------------------------------------------------------------------------
# Modo LIVE (§3, §12.4, §12.5) — solo corre si el preflight no encontró NINGUNA violación
# ----------------------------------------------------------------------------------------------
def _ejecutar_live(espec: EspecCorrida, *, raiz: Path, env: Mapping[str, str], ahora: Callable[[], Any]) -> ResultadoCorrida:
    run_id = _run_id_por_defecto(espec)
    violaciones = _preflight(espec, raiz=raiz, env=env, ahora=ahora)
    if violaciones:
        return ResultadoCorrida(run_id=run_id, rol=espec.rol, etapa=espec.etapa, oferta_id=espec.oferta_id,
                                estado="preflight", veredicto=None, salida=None, errores=violaciones)

    plan = preparar(espec, raiz=raiz, run_id=run_id, env_externo=env)
    (raiz / plan.staging_relativa).mkdir(parents=True, exist_ok=True) if espec.rol == "maker" else None
    carpeta_run = raiz / "empresa" / "runs" / run_id
    carpeta_run.mkdir(parents=True, exist_ok=True)
    (carpeta_run / "settings.efectivo.json").write_text(
        json.dumps(plan.settings_efectivo, ensure_ascii=False, indent=2), encoding="utf-8")

    t0 = time.monotonic()
    limite_s = espec.presupuesto.tiempo_s_max
    try:
        proc = subprocess.Popen(list(plan.argv), cwd=raiz, env=plan.entorno, stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except OSError as exc:
        return ResultadoCorrida(run_id=run_id, rol=espec.rol, etapa=espec.etapa, oferta_id=espec.oferta_id,
                                estado="error", veredicto=None, salida=None, errores=[f"no se pudo lanzar claude: {exc}"])

    eventos: list[dict[str, Any]] = []
    resultado_cli: dict[str, Any] = {}
    estado_proceso = "ok"
    try:
        proc.stdin.write(espec.prompt_base)
        proc.stdin.close()
        for linea in proc.stdout:
            if (raiz / "empresa" / "PAUSA").exists():
                proc.kill()
                estado_proceso = "pausa"
                break
            if time.monotonic() - t0 > limite_s:
                proc.kill()
                estado_proceso = "timeout"
                break
            try:
                ev = json.loads(linea)
            except json.JSONDecodeError:
                continue
            eventos.append(ev)
            if ev.get("type") == "result":
                resultado_cli = ev
            motivo_bucle = _detectar_bucle(eventos[-8:], {"bucle_repeticion_max": espec.presupuesto.turnos_max})
            if motivo_bucle:
                proc.kill()
                estado_proceso = "bucle"
                break
        proc.wait(timeout=30)
    finally:
        with __import__("contextlib").suppress(Exception):
            proc.kill()

    comun = _base_resultado(espec, run_id, resultado_cli, registro_ruta=str(carpeta_run))
    if estado_proceso in ("pausa", "timeout", "bucle"):
        return ResultadoCorrida(**comun, estado=estado_proceso, veredicto=None, salida=None,
                                errores=[f"corrida interrumpida: {estado_proceso}"])
    if not resultado_cli:
        return ResultadoCorrida(**comun, estado="error", veredicto=None, salida=None, errores=["sin evento «result» en el stream"])

    subtype = resultado_cli.get("subtype")
    if subtype == "error_max_turns":
        return ResultadoCorrida(**comun, estado="turnos", veredicto=None, salida=None, errores=["error_max_turns"])
    if subtype == "error_max_budget_usd":
        return ResultadoCorrida(**comun, estado="presupuesto", veredicto=None, salida=None, errores=["error_max_budget_usd"])

    structured, motivo = _validar_structured_output(espec, resultado_cli)
    if motivo and subtype not in (None, "success"):
        return ResultadoCorrida(**comun, estado="error", veredicto=None, salida=None, errores=[motivo])
    if motivo:
        return ResultadoCorrida(**comun, estado="invalido", veredicto=None, salida=None, errores=[motivo])

    if espec.rol == "qa":
        veredicto, errores_qa = _validar_qa(structured)
        estado_final = "invalido" if errores_qa else "ok"
        return ResultadoCorrida(**comun, estado=estado_final, veredicto=veredicto, salida=structured, errores=errores_qa)

    staging = raiz / plan.staging_relativa
    manifiesto, errores_maker = _validar_maker(espec, staging, structured)
    if errores_maker:
        return ResultadoCorrida(**comun, estado="invalido", veredicto=None, salida=structured, artefactos=[], errores=errores_maker)
    return ResultadoCorrida(**comun, estado="ok", veredicto=None, salida=structured, artefactos=manifiesto, errores=[])


# ----------------------------------------------------------------------------------------------
# Punto de entrada único
# ----------------------------------------------------------------------------------------------
def ejecutar(espec: EspecCorrida, *, modo: Modo = Modo.DRY_RUN, fixture_dir: Path | None = None,
            raiz: Path | None = None, env: Mapping[str, str] | None = None,
            ahora: Callable[[], Any] | None = None) -> ResultadoCorrida:
    """Ejecuta UNA corrida en el modo indicado. ``env``/``ahora``/``raiz`` son inyectables (pruebas)."""
    base = raiz if raiz is not None else motor.raiz()
    entorno_proc: Mapping[str, str] = env if env is not None else {}
    reloj = ahora if ahora is not None else motor.ahora_utc

    if modo == Modo.DRY_RUN:
        plan = preparar(espec, raiz=base, env_externo=entorno_proc)
        print(json.dumps({
            "run_id": plan.run_id, "argv": list(plan.argv), "staging_relativa": plan.staging_relativa,
            "presupuesto_cli_usd": plan.presupuesto_cli_usd, "settings_efectivo": plan.settings_efectivo,
            "entorno": {k: motor.enmascarar_secretos(v) for k, v in plan.entorno.items()},
        }, sort_keys=True, ensure_ascii=False, indent=2))
        return ResultadoCorrida(run_id=plan.run_id, rol=espec.rol, etapa=espec.etapa, oferta_id=espec.oferta_id,
                                estado="ok", veredicto=None, salida=None,
                                costo={"centavos_usd": 0, "moneda": "USD", "es_estimacion": True, "confiable": True},
                                registro_ruta="", errores=[])
    if modo == Modo.FIXTURE:
        if fixture_dir is None:
            raise ValueError("modo FIXTURE exige --fixture/fixture_dir")
        return _ejecutar_fixture(espec, Path(fixture_dir), raiz=base, run_id=_run_id_por_defecto(espec))
    if modo == Modo.LIVE:
        return _ejecutar_live(espec, raiz=base, env=entorno_proc, ahora=reloj)
    raise ValueError(f"modo desconocido: {modo!r}")


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m agentes.runner", description=__doc__.splitlines()[0])
    ap.add_argument("--espec", required=True, type=Path)
    ap.add_argument("--fixture", type=Path, default=None)
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--raiz", type=Path, default=None)
    args = ap.parse_args(argv)
    import os

    espec = espec_desde_mapa(json.loads(args.espec.read_text(encoding="utf-8")))
    modo = Modo.LIVE if args.live else (Modo.FIXTURE if args.fixture else Modo.DRY_RUN)
    resultado = ejecutar(espec, modo=modo, fixture_dir=args.fixture, raiz=args.raiz, env=os.environ)
    print(json.dumps(resultado.a_json(), sort_keys=True, ensure_ascii=False, indent=2))
    return CODIGO_POR_ESTADO.get(resultado.estado, 1)


if __name__ == "__main__":
    sys.exit(main())
