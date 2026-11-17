"""B0-08 (``agentes``, dueño B9): los 10 casos de ``agentes.runner`` en modo FIXTURE, la sonda de
hooks al 100 % ``exit 2`` y el entorno del hijo sin claves prohibidas.

Ejercita el componente REAL (``agentes.runner.ejecutar``, ``agentes.sonda_hooks.correr``,
``agentes.perfil.construir_entorno``) sobre los fixtures de ``tests/fixtures/agentes/`` (de B9,
solo lectura) y sobre una «empresa» de prueba desechable que construye la propia sonda. Sin red,
sin ``empresa/`` real.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

RAIZ = Path(__file__).resolve().parents[2]
FIXTURES_AGENTES = RAIZ / "tests" / "fixtures" / "agentes"

# Los 10 casos mínimos de docs/09 §12.8 (mismo banco que tests/agentes/test_runner.py, de B9).
CASOS_RUNNER: tuple[str, ...] = (
    "D3_maker_ok", "D3_maker_invalido_esquema", "D3_maker_artefacto_fuera_de_ruta",
    "D3_maker_sin_structured_output", "D3_maker_max_turns", "D3_maker_max_budget",
    "D3_maker_crash_costo_cero", "D3_maker_stream_bucle", "D3_qa_sello_de_goma",
    "D3_maker_pausa_a_mitad",
)

# Claves que JAMÁS deben llegar al entorno del hijo (docs/09 §3.3): se intentan colar por
# ``env_externo`` para comprobar que ``agentes.perfil.construir_entorno`` las filtra de verdad.
_CLAVES_PROHIBIDAS_DE_PRUEBA: dict[str, str] = {
    "STRIPE_RK_CHECKOUT": "rk_live_falsa_0000000000000000",  # lint-estatico: permitir=d (valor ficticio, nunca una clave real)
    "META_CAPI_TOKEN__OF_202611_01": "EAA_falso_0000000000000000",  # lint-estatico: permitir=d (valor ficticio)
    "SELLO_X1_CLAVE": "clave-falsa-de-prueba",
    "GITHUB_TOKEN": "ghp_falsotoken000000000000000000",
    "LATIDO_HMAC": "clave-falsa-latido",
}


def _comparar_resultado(resultado: Any, esperado: Mapping[str, Any]) -> tuple[bool, str]:
    """Pura: ``True`` si ``resultado`` (de ``agentes.runner.ejecutar``) cumple ``esperado.json``."""
    if resultado.estado != esperado["estado"]:
        return False, f"estado={resultado.estado!r} != esperado {esperado['estado']!r} ({resultado.errores})"
    if "contiene_en_errores" in esperado:
        pista = esperado["contiene_en_errores"]
        if not any(pista in e for e in resultado.errores):
            return False, f"ningún error contiene {pista!r}: {resultado.errores}"
    if "artefactos_cuenta" in esperado and len(resultado.artefactos) != esperado["artefactos_cuenta"]:
        return False, f"artefactos_cuenta={len(resultado.artefactos)} != {esperado['artefactos_cuenta']}"
    return True, "ok"


def _casos_runner(fixtures_dir: Path = FIXTURES_AGENTES, nombres: tuple[str, ...] = CASOS_RUNNER) -> list[tuple[str, bool, str]]:
    """Corre los 10 fixtures en modo FIXTURE contra ``agentes.runner`` real; devuelve ``(nombre, ok, motivo)``."""
    import json
    import tempfile as _tempfile

    from agentes.runner import ejecutar
    from agentes.tipos import Modo, espec_desde_mapa

    salidas: list[tuple[str, bool, str]] = []
    for nombre in nombres:
        carpeta = fixtures_dir / nombre
        espec = espec_desde_mapa(json.loads((carpeta / "espec.json").read_text(encoding="utf-8")))
        esperado = json.loads((carpeta / "esperado.json").read_text(encoding="utf-8"))
        if nombre == "D3_maker_pausa_a_mitad":
            # Esperado "pausa": la empresa de prueba necesita su propio empresa/PAUSA (no la real).
            with _tempfile.TemporaryDirectory(prefix="b0-agentes-pausa-") as tmp:
                raiz_tmp = Path(tmp)
                (raiz_tmp / "empresa").mkdir(parents=True)
                (raiz_tmp / "empresa" / "PAUSA").write_text("", encoding="utf-8")
                resultado = ejecutar(espec, modo=Modo.FIXTURE, fixture_dir=carpeta, raiz=raiz_tmp)
        else:
            resultado = ejecutar(espec, modo=Modo.FIXTURE, fixture_dir=carpeta, raiz=RAIZ)
        ok, motivo = _comparar_resultado(resultado, esperado)
        salidas.append((nombre, ok, motivo))
    return salidas


def _entorno_sin_claves_prohibidas() -> tuple[bool, str]:
    """``agentes.perfil.construir_entorno`` nunca deja pasar lo que no está en la lista blanca."""
    import json

    from agentes import perfil
    from agentes.tipos import espec_desde_mapa

    espec = espec_desde_mapa(json.loads((FIXTURES_AGENTES / "D3_maker_ok" / "espec.json").read_text(encoding="utf-8")))
    staging = perfil.ruta_staging_relativa(espec, "RUN-B0-08")
    entorno = perfil.construir_entorno(
        espec, run_id="RUN-B0-08", raiz=RAIZ, staging_relativa=staging, parametros_agentes={},
        env_externo=_CLAVES_PROHIBIDAS_DE_PRUEBA,
    )
    coladas = [clave for clave in _CLAVES_PROHIBIDAS_DE_PRUEBA if clave in entorno]
    if coladas:
        return False, f"se colaron al entorno del hijo: {coladas}"
    try:
        perfil.exigir_sin_secretos_prohibidos(entorno)
    except ValueError as exc:
        return False, f"exigir_sin_secretos_prohibidos encontró algo propio sospechoso: {exc}"
    return True, f"{len(_CLAVES_PROHIBIDAS_DE_PRUEBA)} claves externas intentadas, ninguna llegó al hijo"


def evaluar_b0_08():
    from scripts.b0_e2e import _con_captura_de_error, _rojo, _verde

    def cuerpo():
        casos = _casos_runner()
        fallos_runner = [(n, m) for n, ok, m in casos if not ok]

        from agentes import sonda_hooks
        resumen_sonda = sonda_hooks.correr()
        fallos_sonda = [n for n, r in resumen_sonda["casos"].items() if not r["ok"]]

        ok_entorno, motivo_entorno = _entorno_sin_claves_prohibidas()

        problemas: list[str] = []
        if fallos_runner:
            problemas.append(f"runner: {len(fallos_runner)}/10 caso(s) no dieron el estado esperado: {fallos_runner}")
        if fallos_sonda:
            problemas.append(f"sonda_hooks: {len(fallos_sonda)} caso(s) no dieron exit 2: {fallos_sonda}")
        if not ok_entorno:
            problemas.append(f"entorno del hijo: {motivo_entorno}")
        if problemas:
            return _rojo("B0-08", "; ".join(problemas))
        return _verde(
            "B0-08",
            f"agentes.runner: 10/10 casos FIXTURE con el estado esperado; agentes.sonda_hooks: "
            f"{len(resumen_sonda['casos'])}/{len(resumen_sonda['casos'])} hooks dieron exit 2; "
            f"agentes.perfil.construir_entorno: {motivo_entorno}",
        )

    return _con_captura_de_error("B0-08", cuerpo)
