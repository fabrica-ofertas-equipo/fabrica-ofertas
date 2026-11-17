"""B0-09 (``tracking``, dueño B2): sesión con metadata completa, firma falsa → 400, duplicado → una
entrega, ``event_id`` correcto en CAPI.

Lanza ``node`` por subproceso contra un arnés propio (``tests/fixtures/b0/tracking_sesion_webhook_capi.mjs``)
que encadena los tres Workers REALES de ``tracking/workers/`` (``crear-sesion`` → ``webhook-stripe``
→ ``capi``), sin red (transporte y almacenes en memoria).
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
ARNES = RAIZ / "tests" / "fixtures" / "b0" / "tracking_sesion_webhook_capi.mjs"


def _correr_arnes() -> dict:
    if shutil.which("node") is None:
        raise RuntimeError("node no está disponible en PATH")
    proc = subprocess.run(["node", str(ARNES)], cwd=RAIZ, capture_output=True, text=True, timeout=30)
    if proc.returncode != 0:
        raise RuntimeError(f"el arnés de tracking salió {proc.returncode}: {proc.stderr[-800:]}")
    return json.loads(proc.stdout.strip().splitlines()[-1])


def _interpretar(salida: dict) -> tuple[bool, str]:
    """Pura: ``True`` si el resultado del arnés cumple el contrato de B0-09 (para sembrar fallos en pruebas)."""
    problemas: list[str] = []
    if salida.get("sesion_status") != 200:
        problemas.append(f"sesion_status={salida.get('sesion_status')!r} != 200")
    metadata_completa = all(salida.get(k) for k in ("metadata_adid", "metadata_asid", "metadata_cid",
                                                     "metadata_consent", "metadata_visitor_id"))
    if not metadata_completa:
        problemas.append(f"metadata incompleta en la sesión: adid={salida.get('metadata_adid')!r}, "
                         f"asid={salida.get('metadata_asid')!r}, cid={salida.get('metadata_cid')!r}, "
                         f"consent={salida.get('metadata_consent')!r}, visitor_id={salida.get('metadata_visitor_id')!r}")
    if salida.get("firma_falsa_status") != 400:
        problemas.append(f"firma_falsa_status={salida.get('firma_falsa_status')!r} != 400")
    if salida.get("ok_status") != 200 or salida.get("ok_codigo") != "encolado":
        problemas.append(f"webhook válido no quedó encolado: status={salida.get('ok_status')!r} codigo={salida.get('ok_codigo')!r}")
    if salida.get("duplicada_status") != 200 or salida.get("duplicada_codigo") != "duplicado":
        problemas.append(f"el duplicado no se detectó: status={salida.get('duplicada_status')!r} codigo={salida.get('duplicada_codigo')!r}")
    if salida.get("llamadas_graph") != 1:
        problemas.append(f"llamadas_graph={salida.get('llamadas_graph')!r} != 1 (duplicado no debe reenviar a CAPI: «una entrega»)")
    if salida.get("event_id_capi") != salida.get("event_id_esperado"):
        problemas.append(f"event_id_capi={salida.get('event_id_capi')!r} != esperado {salida.get('event_id_esperado')!r}")
    if problemas:
        return False, "; ".join(problemas)
    return True, ("sesión 200 con metadata completa (adid/asid/cid del catálogo + consent + visitor_id); "
                  "firma falsa -> 400; webhook válido -> encolado; duplicado -> «duplicado» sin 2da llamada "
                  "a Graph (una entrega); event_id CAPI = purchase_<session_id>")


def evaluar_b0_09():
    from scripts.b0_e2e import _con_captura_de_error, _rojo, _verde

    def cuerpo():
        try:
            salida = _correr_arnes()
        except (RuntimeError, subprocess.TimeoutExpired, json.JSONDecodeError, OSError) as exc:
            return _rojo("B0-09", f"arnés de tracking: {exc}")
        ok, motivo = _interpretar(salida)
        if not ok:
            return _rojo("B0-09", motivo)
        return _verde("B0-09", motivo)

    return _con_captura_de_error("B0-09", cuerpo)
