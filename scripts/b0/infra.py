"""B0-14 (``infra``, dueño B8): latido detenido → pausa simulada y alerta por ambos canales; el
Worker ``watchdog`` no tiene ninguna ruta de activación.

Ejercita el Worker REAL (``infra/workers/watchdog/src/index.mjs``) con ``node`` por subproceso: un
KV falso, un ``fetch`` global reemplazado (nunca sale a la red: ninguna URL se resuelve de verdad,
solo se registra la llamada) y el ``scheduled()`` real del Worker. Arnés en
``tests/fixtures/b0/watchdog_latido_detenido.mjs``.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
ARNES = RAIZ / "tests" / "fixtures" / "b0" / "watchdog_latido_detenido.mjs"


def _interpretar(salida: dict) -> tuple[bool, str]:
    """Pura: ``True`` si el resultado del arnés cumple el contrato de B0-14 (para poder sembrar fallos en pruebas)."""
    problemas: list[str] = []
    if salida.get("pausa_global") != "true":
        problemas.append(f"pausa_global={salida.get('pausa_global')!r} != 'true' (latido detenido debería pausar)")
    llamadas = salida.get("llamadas_fetch") or []
    canales = {"https://api.correo.ejemplo/enviar", "https://api.push.ejemplo/enviar"}
    if set(llamadas) != canales:
        problemas.append(f"llamadas_fetch={llamadas} != los dos canales esperados {sorted(canales)}")
    if salida.get("activar_status") != 404:
        problemas.append(f"activar_status={salida.get('activar_status')!r} != 404 (no debe existir ruta de activación)")
    if problemas:
        return False, "; ".join(problemas)
    return True, "pausa_global=true; alertó por los 2 canales (correo y push); /activar -> 404"


def _correr_arnes() -> dict:
    if shutil.which("node") is None:
        raise RuntimeError("node no está disponible en PATH")
    proc = subprocess.run(["node", str(ARNES)], cwd=RAIZ, capture_output=True, text=True, timeout=30)
    if proc.returncode != 0:
        raise RuntimeError(f"el arnés de watchdog salió {proc.returncode}: {proc.stderr[-500:]}")
    ultima_linea = proc.stdout.strip().splitlines()[-1]
    return json.loads(ultima_linea)


def _correr_suite_watchdog() -> tuple[bool, str]:
    """``node --test`` sobre la batería REAL de B8 (índice + lógica): confirma, entre otras cosas,
    que ninguna ruta del Worker activa nada (``/activar`` -> 404) con sus propios casos."""
    if shutil.which("node") is None:
        return False, "node no está disponible en PATH"
    proc = subprocess.run(
        ["node", "--test", "infra/workers/watchdog/test/index.test.mjs", "infra/workers/watchdog/test/logica.test.mjs"],
        cwd=RAIZ, capture_output=True, text=True, timeout=60,
    )
    if proc.returncode != 0:
        return False, f"node --test (watchdog) salió {proc.returncode}: {proc.stdout[-500:]}{proc.stderr[-500:]}"
    return True, "node --test infra/workers/watchdog/test/{index,logica}.test.mjs -> 0"


def evaluar_b0_14():
    from scripts.b0_e2e import _con_captura_de_error, _rojo, _verde

    def cuerpo():
        ok_suite, motivo_suite = _correr_suite_watchdog()
        if not ok_suite:
            return _rojo("B0-14", motivo_suite)
        try:
            salida = _correr_arnes()
        except (RuntimeError, subprocess.TimeoutExpired, json.JSONDecodeError, OSError) as exc:
            return _rojo("B0-14", f"arnés de watchdog: {exc}")
        ok, motivo = _interpretar(salida)
        if not ok:
            return _rojo("B0-14", motivo)
        return _verde("B0-14", f"{motivo_suite}. Arnés propio (scheduled real, KV y fetch falsos, sin red): {motivo}")

    return _con_captura_de_error("B0-14", cuerpo)
