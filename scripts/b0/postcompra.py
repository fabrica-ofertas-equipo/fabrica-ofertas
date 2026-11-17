"""B0-10, B0-20 y la mitad de B0-19 (``postcompra``, dueño B7): entrega pagada (Worker ``fulfill``
real + ``correo.SimuladoCorreo`` real), disputa abierta rechaza el reembolso automático + paquete de
evidencia, y la mitad pura de ``metricas.calcular_senal`` (reembolsos para B0-19, disputas para
B0-20). Sin red: ``TransporteFixture`` y un ``node`` por subproceso para el Worker de JavaScript.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
ARNES_FULFILL = RAIZ / "tests" / "fixtures" / "b0" / "fulfill_entrega_pagada.mjs"
OFERTA = "OF-202611-01"


# --------------------------------------------------------------------------------------------------------------------
# B0-10: Worker fulfill real (entregado, enlace con vencimiento/cuota, sin reenvío) + outbox real
# --------------------------------------------------------------------------------------------------------------------
def _correr_arnes_fulfill() -> dict:
    if shutil.which("node") is None:
        raise RuntimeError("node no está disponible en PATH")
    proc = subprocess.run(["node", str(ARNES_FULFILL)], cwd=RAIZ, capture_output=True, text=True, timeout=30)
    if proc.returncode != 0:
        raise RuntimeError(f"arnés fulfill salió {proc.returncode}: {proc.stderr[-500:]}")
    return json.loads(proc.stdout.strip().splitlines()[-1])


def _interpretar_fulfill(salida: dict) -> tuple[bool, str]:
    problemas: list[str] = []
    if salida.get("primero_codigo") != "entregado":
        problemas.append(f"primero_codigo={salida.get('primero_codigo')!r} != 'entregado'")
    enlace = salida.get("primero_enlace") or {}
    if not enlace.get("vence_en") or enlace.get("max_descargas") != 3:
        problemas.append(f"enlace sin vencimiento/cuota correctos: {enlace}")
    if salida.get("segundo_codigo") != "duplicado":
        problemas.append(f"segundo_codigo={salida.get('segundo_codigo')!r} != 'duplicado' (debería no reenviar)")
    if salida.get("llamadas_correo") != 1 or salida.get("llamadas_api") != 1:
        problemas.append(f"llamadas_correo={salida.get('llamadas_correo')} / llamadas_api={salida.get('llamadas_api')} != 1/1 (sin reenvío)")
    if not salida.get("enlace_valido_dentro_de_cuota"):
        problemas.append("el enlace firmado no verificó como válido dentro de cuota y antes de vencer")
    if not salida.get("enlace_null_con_cuota_agotada"):
        problemas.append("el enlace NO se invalidó al agotar la cuota de descargas")
    if not salida.get("enlace_null_si_vencido"):
        problemas.append("el enlace NO se invalidó tras su vencimiento")
    if problemas:
        return False, "; ".join(problemas)
    return True, "entregado, enlace con vencimiento/cuota verificados de verdad (HMAC real), duplicado sin reenvío"


def _escenario_outbox() -> tuple[bool, str]:
    from postcompra.correo import Correo, SimuladoCorreo

    with tempfile.TemporaryDirectory(prefix="b0-postcompra-outbox-") as tmp_str:
        tmp = Path(tmp_str)
        reloj = lambda: datetime(2026, 11, 12, 9, 0, 0, tzinfo=timezone.utc)
        proveedor = SimuladoCorreo(tmp, ahora=reloj)
        correo = Correo(oferta_id=OFERTA, referencia="cs_test_b0_0001", plantilla="confirmacion_entrega",
                        asunto="Tu guía está lista", cuerpo_texto="Aquí tienes tu enlace de descarga.")
        resultado = proveedor.enviar(correo, destinatario="cliente-real@ejemplo.com")
        if not resultado.enviado or resultado.proveedor != "simulado":
            return False, f"SimuladoCorreo.enviar no confirmó el envío: {resultado}"
        outbox = tmp / "ofertas" / OFERTA / "10-postcompra" / "outbox"
        archivos = list(outbox.glob("*.json")) if outbox.is_dir() else []
        if len(archivos) != 1:
            return False, f"se esperaba 1 archivo en outbox/, hay {len(archivos)}"
        contenido = archivos[0].read_text(encoding="utf-8")
        if "cliente-real@ejemplo.com" in contenido:
            return False, "el email en texto plano llegó al outbox (debería ser solo el hash)"
        datos = json.loads(contenido)
        if "destinatario_hash" not in datos or "@" in datos.get("destinatario_hash", ""):
            return False, f"destinatario_hash ausente o con forma de email: {datos}"
        return True, f"correo.SimuladoCorreo escribió 1 archivo en outbox/ con destinatario_hash (sin email en texto plano)"


def evaluar_b0_10():
    from scripts.b0_e2e import _con_captura_de_error, _rojo, _verde

    def cuerpo():
        try:
            salida = _correr_arnes_fulfill()
        except (RuntimeError, subprocess.TimeoutExpired, json.JSONDecodeError, OSError) as exc:
            return _rojo("B0-10", f"arnés de fulfill: {exc}")
        ok_fulfill, m_fulfill = _interpretar_fulfill(salida)
        ok_outbox, m_outbox = _escenario_outbox()
        if not (ok_fulfill and ok_outbox):
            return _rojo("B0-10", f"fulfill={ok_fulfill} ({m_fulfill}); outbox={ok_outbox} ({m_outbox})")
        return _verde("B0-10", f"Worker fulfill (real, sin red): {m_fulfill}. {m_outbox}.")

    return _con_captura_de_error("B0-10", cuerpo)


# --------------------------------------------------------------------------------------------------------------------
# B0-20: disputa abierta rechaza el reembolso automático; postcompra.evidencia; dos disputas -> pausa
# --------------------------------------------------------------------------------------------------------------------
def _escenario_disputa_rechaza_reembolso() -> tuple[bool, str]:
    from engine.errores import ErrorLimite
    from engine.transporte import TransporteFixture
    from postcompra.cliente_stripe import ClienteStripe
    from postcompra.reembolsar import reembolsar
    from tests.engine import apoyo
    from tests.postcompra import apoyo as apoyo_pc

    with tempfile.TemporaryDirectory(prefix="b0-postcompra-disputa-") as tmp_str:
        tmp = Path(tmp_str)
        emp = apoyo.crear_empresa(tmp, modo_infra="prueba", entorno="prueba")
        ahora = datetime(2026, 11, 12, 9, 0, 0, tzinfo=timezone.utc)
        apoyo_pc.refrescar_infra(emp, ahora)
        session_id = "cs_test_b0_disputa"
        reglas = apoyo_pc.reglas_stripe(session_id, monto_pagado=1900, moneda="EUR",
                                        pagado_en=ahora - timedelta(days=2), disputa=True)
        transporte = TransporteFixture(reglas)
        stripe = ClienteStripe(transporte, clave_api="rk_prueba")
        try:
            reembolsar(session_id=session_id, motivo="dentro_de_garantia", oferta_id=OFERTA, raiz=emp.raiz,
                      env=emp.env, ahora=lambda: ahora, modo="fixture", stripe=stripe, transporte=transporte)
            return False, "se esperaba ErrorLimite (disputa_abierta); el reembolso no fue rechazado"
        except ErrorLimite as exc:
            motivo = (exc.detalle or {}).get("motivo") if hasattr(exc, "detalle") else None
            if motivo != "disputa_abierta":
                return False, f"ErrorLimite con motivo {motivo!r} != 'disputa_abierta'"
            posts = transporte.llamadas_a("POST")
            if posts:
                return False, f"con disputa abierta NO debería llamar a POST /refunds; hubo {len(posts)}"
            return True, "reembolsar() rechaza con ErrorLimite(motivo=disputa_abierta) y nunca llama a Stripe POST /refunds"


def _escenario_evidencia() -> tuple[bool, str]:
    from engine.transporte import TransporteFixture
    from postcompra.cliente_stripe import ClienteStripe
    from postcompra.evidencia import armar_paquete
    from tests.postcompra import apoyo as apoyo_pc

    with tempfile.TemporaryDirectory(prefix="b0-postcompra-evidencia-") as tmp_str:
        tmp = Path(tmp_str)
        session_id = "cs_test_b0_evidencia"
        ahora = datetime(2026, 11, 12, 9, 0, 0, tzinfo=timezone.utc)
        reglas = apoyo_pc.reglas_stripe(session_id, monto_pagado=1900, moneda="EUR", pagado_en=ahora - timedelta(days=1), disputa=True)
        transporte = TransporteFixture(reglas)
        stripe = ClienteStripe(transporte, clave_api="rk_prueba")
        salida = tmp / "evidencia"
        resultado = armar_paquete(session_id=session_id, oferta_id=OFERTA, raiz=tmp, salida=salida, stripe=stripe)
        if not resultado.archivos or not (salida / "resumen.json").is_file() or not (salida / "manifiesto.json").is_file():
            return False, f"el paquete no tiene resumen.json/manifiesto.json: {resultado.archivos}"
        resumen = json.loads((salida / "resumen.json").read_text(encoding="utf-8"))
        if resumen.get("disputa_abierta") is not True:
            return False, "resumen.json no refleja disputa_abierta=true"
        texto_completo = (salida / "resumen.json").read_text(encoding="utf-8") + (salida / "manifiesto.json").read_text(encoding="utf-8")
        if "@" in texto_completo:
            return False, "el paquete de evidencia contiene un «@» (posible dato personal)"
        return True, "postcompra.evidencia.armar_paquete produce resumen.json + manifiesto.json, disputa_abierta=true, sin «@»"


def _escenario_dos_disputas_pausa() -> tuple[bool, str]:
    from engine.limites import Limites
    from engine.parametros import Parametros
    from postcompra.metricas import calcular_senal

    lim = Limites(datos={"ratio_disputas_pausa": "0.02", "moneda_limites": "EUR"}, entorno="prueba")
    par = Parametros({"schema_version": "1.1.0", "version": 1, "grupos": {"salud_operativa": {
        "disputas_muestra_min_pagos": {"valor": 20}, "disputas_alerta_pct": {"valor": "1.0"},
        "disputas_casos_alerta": {"valor": 1}, "disputas_casos_pausa": {"valor": 2},
        "reembolsos_n_min": {"valor": 20}, "reembolsos_alerta_pct": {"valor": "8.0"}, "reembolsos_pausa_pct": {"valor": "12.0"},
    }}})
    # 2 disputas sobre 60 pagos = 3,33 % >= 2 % de ratio_disputas_pausa (muestra >= 20): rojo/pausar.
    senal = calcular_senal(pagos_ventana=60, casos_disputa_efw=2, reembolsos_num=0, reembolsos_den=60, lim=lim, par=par)
    if senal.nivel != "rojo" or senal.motivo != "disputas" or senal.accion_solicitada != "pausar":
        return False, f"2 disputas/60 pagos no dio rojo/disputas/pausar: {senal}"
    senal_1 = calcular_senal(pagos_ventana=60, casos_disputa_efw=1, reembolsos_num=0, reembolsos_den=60, lim=lim, par=par)
    if senal_1.nivel == "rojo":
        return False, f"con 1 sola disputa ya daba rojo (el umbral no distingue): {senal_1}"
    return True, "calcular_senal: 2 disputas/60 pagos -> rojo/disputas/pausar; 1 disputa no alcanza (control negativo)"


def evaluar_b0_20():
    from scripts.b0_e2e import _con_captura_de_error, _rojo, _verde

    def cuerpo():
        ok1, m1 = _escenario_disputa_rechaza_reembolso()
        ok2, m2 = _escenario_evidencia()
        ok3, m3 = _escenario_dos_disputas_pausa()
        if not (ok1 and ok2 and ok3):
            return _rojo("B0-20", f"disputa_rechaza={ok1} ({m1}); evidencia={ok2} ({m2}); dos_disputas={ok3} ({m3})")
        return _verde("B0-20", f"{m1}. {m2}. {m3}.")

    return _con_captura_de_error("B0-20", cuerpo)


# --------------------------------------------------------------------------------------------------------------------
# B0-19 (SOLO la mitad de postcompra.metricas.calcular_senal: reembolsos cruzando el umbral -> pausar)
# --------------------------------------------------------------------------------------------------------------------
def _escenario_reembolsos_pausa() -> tuple[bool, str]:
    from engine.limites import Limites
    from engine.parametros import Parametros
    from postcompra.metricas import calcular_senal

    lim = Limites(datos={"ratio_disputas_pausa": "0.02", "moneda_limites": "EUR"}, entorno="prueba")
    par = Parametros({"schema_version": "1.1.0", "version": 1, "grupos": {"salud_operativa": {
        "disputas_muestra_min_pagos": {"valor": 20}, "disputas_alerta_pct": {"valor": "1.0"},
        "disputas_casos_alerta": {"valor": 1}, "disputas_casos_pausa": {"valor": 2},
        "reembolsos_n_min": {"valor": 20}, "reembolsos_alerta_pct": {"valor": "8.0"}, "reembolsos_pausa_pct": {"valor": "12.0"},
    }}})
    # 8/60 reembolsos = 13,33 % >= reembolsos_pausa_pct (12 %), con reembolsos_den >= reembolsos_n_min (20).
    senal = calcular_senal(pagos_ventana=60, casos_disputa_efw=0, reembolsos_num=8, reembolsos_den=60, lim=lim, par=par)
    if senal.nivel != "rojo" or senal.motivo != "reembolsos" or senal.accion_solicitada != "pausar":
        return False, f"8/60 reembolsos (13,3%) no dio rojo/reembolsos/pausar: {senal}"
    senal_bajo = calcular_senal(pagos_ventana=60, casos_disputa_efw=0, reembolsos_num=2, reembolsos_den=60, lim=lim, par=par)
    if senal_bajo.nivel == "rojo":
        return False, f"2/60 reembolsos (3,3%, bajo el umbral) ya daba rojo: {senal_bajo}"
    return True, "calcular_senal: 8/60 reembolsos (13,3% >= reembolsos_pausa_pct) -> rojo/reembolsos/pausar; 2/60 no alcanza (control negativo)"


def evaluar_b0_19():
    from scripts.b0_e2e import _con_captura_de_error, _pendiente

    def cuerpo():
        ok, motivo = _escenario_reembolsos_pausa()
        detalle = motivo if ok else f"FALLO REAL en postcompra.metricas.calcular_senal: {motivo}"
        return _pendiente(
            "B0-19",
            f"{detalle} — mitad de B0-19 que me toca (postcompra.metricas.calcular_senal, pura, sin "
            "engine.d8), verificada con un escenario propio. Falta, y depende de engine.d8/orq (en "
            "construcción esta noche por B1a/B1b, no debo tocarlos): que D8 LEA senal_pausa.json en "
            "cada ciclo, pause la campaña y rellene consumida_por con su decision_id (R08). Lo hace I1a.",
        )

    return _con_captura_de_error("B0-19", cuerpo)
