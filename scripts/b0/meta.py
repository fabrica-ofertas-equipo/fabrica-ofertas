"""B0-12, B0-13, B0-21 (``meta``, dueño B5): ejercita ``meta.crear``, ``meta.preflight``,
``meta.activar`` y ``meta.monitor`` REALES con ``engine.transporte.TransporteFixture`` (sin red).

Escenarios propios de esta ola (no reutiliza los fixtures de ``tests/meta/`` de B5; construye los
suyos, estructuralmente equivalentes, para ejercer el componente real de forma independiente).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qsl

_AD_ACCOUNT = "act_100000000000001"
_OFERTA = "OF-202611-01"


def _campana_borrador(oferta_id: str = _OFERTA) -> dict[str, Any]:
    return {
        "oferta_id": oferta_id, "estado": "borrador", "objetivo": "VENTAS", "evento_optimizacion": "PURCHASE",
        "paises": ["ES"], "ubicaciones": "automaticas", "special_ad_categories": [],
        "nombres": {"campana": f"{oferta_id}_TEST_VENTAS_CBO_20261106", "conjunto": "amplia_automaticas_es-ES",
                    "anuncios": ["concepto_video_hook_v1"]},
        "audiencia": {"edad_min": 18, "edad_max": 65, "genero": "todos", "intereses": []},
        "presupuesto": {"moneda": "EUR", "diario": 500, "spend_cap": 5500, "candado_alternativo": None},
        "anuncios": [{"ad_name": "concepto_video_hook_v1", "concepto_id": "concepto", "asset_sha256": "sha256:" + "a" * 64, "claim_ids": []}],
    }


def _payloads_creativo() -> dict[str, Any]:
    return {"concepto_video_hook_v1": {"name": "concepto_video_hook_v1_creativo", "object_story_spec": {}}}


# --------------------------------------------------------------------------------------------------------------------
# B0-12: meta.crear idempotente (desde cero y por reutilización) + meta.preflight detecta cada P rojo
# --------------------------------------------------------------------------------------------------------------------
def _escenario_crear_desde_cero() -> tuple[bool, str]:
    from engine.transporte import TransporteFixture
    from meta import crear
    from meta.cliente import ClienteMeta

    transporte = TransporteFixture([
        {"metodo": "GET", "url_prefijo": f"https://graph.facebook.com/v21.0/{_AD_ACCOUNT}/campaigns", "cuerpo": {"data": []}},
        {"metodo": "POST", "url_prefijo": f"https://graph.facebook.com/v21.0/{_AD_ACCOUNT}/campaigns", "cuerpo": {"id": "B0-1001"}},
        {"metodo": "GET", "url_prefijo": f"https://graph.facebook.com/v21.0/{_AD_ACCOUNT}/adsets", "cuerpo": {"data": []}},
        {"metodo": "POST", "url_prefijo": f"https://graph.facebook.com/v21.0/{_AD_ACCOUNT}/adsets", "cuerpo": {"id": "B0-2001"}},
        {"metodo": "GET", "url_prefijo": f"https://graph.facebook.com/v21.0/{_AD_ACCOUNT}/adcreatives", "cuerpo": {"data": []}},
        {"metodo": "POST", "url_prefijo": f"https://graph.facebook.com/v21.0/{_AD_ACCOUNT}/adcreatives", "cuerpo": {"id": "B0-3001"}},
        {"metodo": "GET", "url_prefijo": f"https://graph.facebook.com/v21.0/{_AD_ACCOUNT}/ads", "cuerpo": {"data": []}},
        {"metodo": "POST", "url_prefijo": f"https://graph.facebook.com/v21.0/{_AD_ACCOUNT}/ads", "cuerpo": {"id": "B0-4001"}},
    ])
    cliente = ClienteMeta(transporte, token="T", app_secret="S", segundos_min_entre_ediciones=30, max_cambios_presupuesto_por_hora=4)
    resultado = crear.crear(oferta_id=_OFERTA, campana=_campana_borrador(), cliente=cliente, ad_account_id=_AD_ACCOUNT,
                            pixel_id="PX1", payloads_creativo=_payloads_creativo())
    if (resultado.campaign_id, resultado.adset_ids, resultado.ad_ids) != ("B0-1001", ["B0-2001"], ["B0-4001"]):
        return False, f"ids inesperados: {resultado.campaign_id, resultado.adset_ids, resultado.ad_ids}"
    posts_sin_status = []
    for p in transporte.llamadas_a("POST"):
        if "adcreatives" in p.url:
            continue
        cuerpo = dict(parse_qsl(p.cuerpo.decode("utf-8")))
        if cuerpo.get("status") != "PAUSED":
            posts_sin_status.append(p.url)
    if posts_sin_status:
        return False, f"objetos creados sin status=PAUSED: {posts_sin_status}"
    return True, "campaña, conjunto y anuncio creados, los tres PAUSED; 4 POST"


def _escenario_crear_reutiliza() -> tuple[bool, str]:
    from engine.transporte import TransporteFixture
    from meta import crear
    from meta.cliente import ClienteMeta

    prefijo = crear.prefijo_test(_OFERTA)
    transporte = TransporteFixture([
        {"metodo": "GET", "url_prefijo": f"https://graph.facebook.com/v21.0/{_AD_ACCOUNT}/campaigns",
         "cuerpo": {"data": [{"id": "B0-1001", "name": f"{prefijo}VENTAS_CBO_20261106"}]}},
        {"metodo": "GET", "url_prefijo": f"https://graph.facebook.com/v21.0/{_AD_ACCOUNT}/adsets",
         "cuerpo": {"data": [{"id": "B0-2001", "name": f"{prefijo}amplia"}]}},
        {"metodo": "GET", "url_prefijo": f"https://graph.facebook.com/v21.0/{_AD_ACCOUNT}/adcreatives",
         "cuerpo": {"data": [{"id": "B0-3001", "name": "concepto_video_hook_v1"}]}},
        {"metodo": "GET", "url_prefijo": f"https://graph.facebook.com/v21.0/{_AD_ACCOUNT}/ads",
         "cuerpo": {"data": [{"id": "B0-4001", "name": "concepto_video_hook_v1"}]}},
    ])
    cliente = ClienteMeta(transporte, token="T", app_secret="S", segundos_min_entre_ediciones=30, max_cambios_presupuesto_por_hora=4)
    resultado = crear.crear(oferta_id=_OFERTA, campana=_campana_borrador(), cliente=cliente, ad_account_id=_AD_ACCOUNT,
                            pixel_id="PX1", payloads_creativo=_payloads_creativo())
    n_post = len(transporte.llamadas_a("POST"))
    if n_post != 0:
        return False, f"reutilizando por prefijo/nombre no debería crear nada; hubo {n_post} POST"
    if (resultado.campaign_id, resultado.adset_ids, resultado.ad_ids) != ("B0-1001", ["B0-2001"], ["B0-4001"]):
        return False, f"no reutilizó los IDs existentes: {resultado.campaign_id, resultado.adset_ids, resultado.ad_ids}"
    return True, "segunda corrida reutiliza los 4 objetos por prefijo/nombre, 0 POST (idempotente)"


def _preflight_entradas_base() -> dict[str, Any]:
    return {
        "pausa": False,
        "cuenta": {"estado": "ACTIVE", "metodo_pago": True, "saludable": True, "limite_diario_minor": 10000,
                   "limite_gasto_cuenta_minor": 500000, "tipo_pago": "tarjeta", "pagina_vinculada": True},
        "dataset": {"activo": True, "eventos_recientes": True},
        "emq": {"valor": "7.0", "objetivo": "6.0"},
        "evento_prueba": {"navegador_event_id": "ev1", "servidor_event_id": "ev1"},
        "dominio_verificado": True,
        "landing": {"status_code": 200, "redirecciones": 0},
        "url": {"vacios": False, "macros_presentes": True},
        "paquete": {"landing_hash": "sha256:" + "a" * 64, "precio_minor": 1900, "moneda": "EUR", "textos_iguales": True},
        "checkout": {"landing_hash": "sha256:" + "a" * 64, "precio_minor": 1900, "moneda": "EUR"},
        "lint_claims_ok": True, "mejoras_meta_opt_out": True, "self_ai_disclosure_ok": True,
        "mercado": {"locale_ok": True, "paises_ok": True}, "nombres_ok": True,
        "active_errors": (), "objetos_ajenos": (), "vistas_previas_ok": True, "ofertas_en_test": 1,
        "hash_config_sellado": True, "categoria_especial_coincide_x1": None,
    }


def _preflight_entradas(mutaciones: dict[str, Any]):
    from meta import preflight

    datos = _preflight_entradas_base()
    for ruta, valor in mutaciones.items():
        partes = ruta.split(".")
        destino = datos
        for p in partes[:-1]:
            destino[p] = dict(destino[p])
            destino = destino[p]
        destino[partes[-1]] = valor
    return preflight.Entradas(**datos)


# Un mutación por P (menos P20, P25, probados aparte): mismo criterio que el banco de B5, escenario propio.
_MUTACIONES_POR_P: dict[str, dict[str, Any]] = {
    "P01": {"pausa": True}, "P02": {"cuenta.estado": "DISABLED"}, "P03": {"cuenta.metodo_pago": False},
    "P04": {"cuenta.saludable": False}, "P05": {"cuenta.limite_diario_minor": 100}, "P06": {"cuenta.limite_gasto_cuenta_minor": None},
    "P07": {"cuenta.pagina_vinculada": False}, "P08": {"dataset.activo": False}, "P09": {"emq.valor": "3.0"},
    "P10": {"evento_prueba.servidor_event_id": "otro"}, "P11": {"dominio_verificado": False}, "P12": {"landing.status_code": 500},
    "P13": {"url.macros_presentes": False}, "P14": {"checkout.precio_minor": 1234}, "P15": {"lint_claims_ok": False},
    "P16": {"mejoras_meta_opt_out": False}, "P17": {"self_ai_disclosure_ok": False}, "P18": {"mercado.paises_ok": False},
    "P19": {"nombres_ok": False}, "P21": {"active_errors": ("1234567890:budget_too_low",)}, "P22": {"vistas_previas_ok": False},
    "P23": {"ofertas_en_test": 10}, "P24": {"hash_config_sellado": False},
}


def _escenario_preflight() -> tuple[bool, str]:
    from engine.limites import Limites
    from engine.parametros import Parametros
    from meta import preflight

    lim = Limites(datos={"moneda_limites": "EUR", "factor_techo_teorico_diario": "1.75", "gasto_diario_por_oferta": 2000,
                         "gasto_total_test_por_oferta": 20000, "ofertas_en_test_simultaneas_max": 5}, entorno="prueba")
    par = Parametros({"schema_version": "1.1.0", "version": 1, "grupos": {"campana": {"preflight_vigencia_h": {"valor": 24}}}})
    campana = {"presupuesto": {"diario": 1000, "max_teorico_diario": 1750, "total_test": 10000, "spend_cap": 11000, "moneda": "EUR"},
              "special_ad_categories": []}
    ahora = lambda: datetime(2026, 11, 6, 12, 0, 0, tzinfo=timezone.utc)

    def generar(entradas):
        return preflight.generar(oferta_id=_OFERTA, campana=campana, limites=lim, parametros=par, entradas=entradas,
                                 hash_config="sha256:" + "b" * 64, ahora=ahora)

    base = generar(_preflight_entradas({}))
    if base["semaforo"] != "VERDE" or set(base["checks"]) != set(preflight.CHECKS):
        return False, f"caso base no quedó VERDE con los {len(preflight.CHECKS)} checks: semaforo={base['semaforo']}"

    fallos: list[str] = []
    for clave, mutacion in _MUTACIONES_POR_P.items():
        resultado = generar(_preflight_entradas(mutacion))
        estado = resultado["checks"][clave]["estado"]
        if estado != "ROJO":
            fallos.append(f"{clave}: esperaba ROJO, dio {estado}")
        elif resultado["semaforo"] != "ROJO":
            fallos.append(f"{clave}: el check dio ROJO pero el semáforo global no")
    if fallos:
        return False, "; ".join(fallos)
    return True, f"caso base VERDE (24 checks) y {len(_MUTACIONES_POR_P)} mutaciones, cada una ROJO SOLO en su propio check"


def evaluar_b0_12():
    from scripts.b0_e2e import _con_captura_de_error, _rojo, _verde

    def cuerpo():
        ok1, m1 = _escenario_crear_desde_cero()
        ok2, m2 = _escenario_crear_reutiliza()
        ok3, m3 = _escenario_preflight()
        if not (ok1 and ok2 and ok3):
            return _rojo("B0-12", f"crear_desde_cero={ok1} ({m1}); crear_reutiliza={ok2} ({m2}); preflight={ok3} ({m3})")
        return _verde("B0-12", f"meta.crear: {m1}; {m2}. meta.preflight: {m3}.")

    return _con_captura_de_error("B0-12", cuerpo)


# --------------------------------------------------------------------------------------------------------------------
# B0-13: meta.activar — 5 negativos, 1 positivo (modo=fixture), «falla el segundo POST»
# --------------------------------------------------------------------------------------------------------------------
_CAMPAIGN_ID, _ADSET_ID, _AD_ID, _CREATIVE_ID = "B0-C1", "B0-A1", "B0-D1", "B0-CR1"


def _ids_meta_activar() -> dict[str, Any]:
    return {"campaign_id": _CAMPAIGN_ID, "adset_ids": [_ADSET_ID], "ad_ids": [_AD_ID], "creative_ids": [_CREATIVE_ID]}


def _sello_activar(*, hash_config: str, object_ids):
    return {"artefacto_sha256": hash_config, "emitido_en": "2026-11-09T06:00:00Z", "vigencia_hasta": "2026-11-10T06:00:00Z",
            "object_ids": sorted(object_ids)}


def _cuenta_activar():
    from engine.guard import EstadoCuenta
    from engine.limites import CampanaActiva

    nueva = CampanaActiva(oferta_id=_OFERTA, campaign_id="c-b0", max_teorico_diario_minor=5000, spend_cap_restante_minor=0,
                          moneda="EUR", perdida_acumulada_minor=0)
    return EstadoCuenta(gasto_vitalicio_minor=0, nueva=nueva, ediciones_recientes=(), ultimo_aumento=None)


def _regla(metodo: str, object_id: str, cuerpo: dict, *, estado: int = 200) -> dict:
    return {"metodo": metodo, "url_prefijo": f"https://graph.facebook.com/v21.0/{object_id}", "estado": estado, "cuerpo": cuerpo}


def _reglas_arbol_vivo() -> list[dict]:
    return [
        _regla("GET", _CAMPAIGN_ID, {"id": _CAMPAIGN_ID}),
        {"metodo": "GET", "url_prefijo": f"https://graph.facebook.com/v21.0/{_CAMPAIGN_ID}/adsets", "cuerpo": {"data": [{"id": _ADSET_ID}]}},
        {"metodo": "GET", "url_prefijo": f"https://graph.facebook.com/v21.0/{_CAMPAIGN_ID}/ads", "cuerpo": {"data": [{"id": _AD_ID}]}},
    ]


def _reglas_config_viva(campana: dict, ids_meta: dict) -> list[dict]:
    """GET de ``meta.activar.leer_estado_vivo`` (A5): el estado vivo que ``diferencias_config_viva``
    compara contra ``campana`` debe coincidir EXACTO (lo construimos con los mismos ``meta.payloads``
    que usa el propio módulo, para no arriesgar un desacuerdo manual)."""
    from meta import payloads

    esperado_campana = payloads.payload_campana(campana)
    esperado_conjunto = payloads.payload_conjunto(campana, campaign_id=str(ids_meta["campaign_id"]), pixel_id="_")
    cuerpo_campana = {"id": ids_meta["campaign_id"], "spend_cap": esperado_campana.get("spend_cap"),
                      "special_ad_categories": list(campana.get("special_ad_categories") or [])}
    cuerpo_conjunto = {"id": ids_meta["adset_ids"][0], "optimization_goal": esperado_conjunto["optimization_goal"],
                       "promoted_object": esperado_conjunto["promoted_object"], "targeting": esperado_conjunto["targeting"]}
    if "daily_budget" in esperado_conjunto:
        cuerpo_conjunto["daily_budget"] = esperado_conjunto["daily_budget"]
    else:
        cuerpo_conjunto["lifetime_budget"] = esperado_conjunto.get("lifetime_budget")
        if "end_time" in esperado_conjunto:
            cuerpo_conjunto["end_time"] = esperado_conjunto["end_time"]
    reglas = [_regla("GET", ids_meta["campaign_id"], cuerpo_campana), _regla("GET", ids_meta["adset_ids"][0], cuerpo_conjunto)]
    for ad_id, creative_id in zip(ids_meta["ad_ids"], ids_meta["creative_ids"]):
        reglas.append(_regla("GET", ad_id, {"id": ad_id, "creative": {"id": creative_id}}))
    return reglas


def _caso_negativo(tmp_root, nombre: str, *, firmar_orden: bool, con_pausa: bool, sello, hash_activar: str) -> tuple[str, bool, str]:
    from tests.engine import apoyo
    from engine.errores import ErrorBloqueado
    from engine.transporte import TransporteFixture

    tmp = tmp_root / nombre
    tmp.mkdir(parents=True, exist_ok=True)
    try:
        emp0 = None

        def _preparado(tmp_dir):
            nonlocal emp0
            from meta.cliente import ClienteMeta
            from meta import activar
            emp0 = apoyo.crear_empresa(tmp_dir, modo_infra="prueba", entorno="prueba")
            if firmar_orden:
                emp0.firmar_orden("activar_campana", hash_objetivo=hash_activar)
            if con_pausa:
                (emp0.raiz / "empresa" / "PAUSA").write_text("", encoding="utf-8")
            cliente = ClienteMeta(TransporteFixture(), token="T", app_secret="S", segundos_min_entre_ediciones=30, max_cambios_presupuesto_por_hora=4)
            return activar.activar(
                oferta_id=_OFERTA, campana=_campana_borrador(), ids_meta=_ids_meta_activar(), hash_config=hash_activar,
                clave_sello=hash_activar, verificar_sello=lambda clave, ahora: sello, cliente=cliente, monto_minor=5000,
                moneda="EUR", cuenta=_cuenta_activar(), ahora=emp0.reloj, simulacion=True,
                transporte_guard=TransporteFixture(), env=emp0.env, raiz=emp0.raiz,
            )

        _preparado(tmp)
        return nombre, False, "no lanzó ErrorBloqueado (debería haber rechazado)"
    except ErrorBloqueado as exc:
        return nombre, True, str(exc.mensaje)[:120]
    except Exception as exc:  # noqa: BLE001
        return nombre, False, f"excepción inesperada: {type(exc).__name__}: {exc}"


def _escenario_activar_negativos(tmp_root) -> tuple[bool, str]:
    hash_ok = "sha256:" + "b0" * 32
    sello_ok = _sello_activar(hash_config=hash_ok, object_ids={_CAMPAIGN_ID, _ADSET_ID, _AD_ID})
    casos = [
        _caso_negativo(tmp_root, "sin_sello", firmar_orden=True, con_pausa=False, sello=None, hash_activar=hash_ok),
        _caso_negativo(tmp_root, "hash_distinto", firmar_orden=True, con_pausa=False,
                       sello=_sello_activar(hash_config="sha256:" + "ff" * 32, object_ids={_CAMPAIGN_ID, _ADSET_ID, _AD_ID}),
                       hash_activar=hash_ok),
        _caso_negativo(tmp_root, "object_ids_de_mas", firmar_orden=True, con_pausa=False,
                       sello=_sello_activar(hash_config=hash_ok, object_ids={_CAMPAIGN_ID, _ADSET_ID}), hash_activar=hash_ok),
        _caso_negativo(tmp_root, "sin_firma", firmar_orden=False, con_pausa=False, sello=sello_ok, hash_activar=hash_ok),
        _caso_negativo(tmp_root, "con_pausa", firmar_orden=True, con_pausa=True, sello=sello_ok, hash_activar=hash_ok),
    ]
    fallos = [(n, m) for n, ok, m in casos if not ok]
    if fallos:
        return False, f"casos negativos que no rechazaron como se esperaba: {fallos}"
    return True, f"5/5 negativos rechazados con ErrorBloqueado ({', '.join(n for n, _, _ in casos)})"


def _escenario_activar_positivo(tmp_root) -> tuple[bool, str]:
    from engine.transporte import TransporteFixture

    hash_ok = "sha256:" + "b0" * 32
    campana = _campana_borrador()
    ids_meta = _ids_meta_activar()
    sello_ok = _sello_activar(hash_config=hash_ok, object_ids={_CAMPAIGN_ID, _ADSET_ID, _AD_ID})
    reglas = list(_reglas_arbol_vivo()) + _reglas_config_viva(campana, ids_meta)
    for object_id in (_AD_ID, _ADSET_ID, _CAMPAIGN_ID):
        reglas.append(_regla("GET", object_id, {"id": object_id, "effective_status": "PAUSED"}))
        reglas.append(_regla("POST", object_id, {"success": True}))
        reglas.append(_regla("GET", object_id, {"id": object_id, "effective_status": "ACTIVE"}))
    transporte = TransporteFixture(reglas)
    tmp = tmp_root / "positivo"
    tmp.mkdir(parents=True, exist_ok=True)
    from tests.engine import apoyo
    from meta import activar
    from meta.cliente import ClienteMeta

    emp = apoyo.crear_empresa(tmp, modo_infra="prueba", entorno="prueba")
    emp.firmar_orden("activar_campana", hash_objetivo=hash_ok)
    cliente = ClienteMeta(transporte, token="T", app_secret="S", segundos_min_entre_ediciones=30, max_cambios_presupuesto_por_hora=4)
    resultado = activar.activar(
        oferta_id=_OFERTA, campana=campana, ids_meta=ids_meta, hash_config=hash_ok, clave_sello=hash_ok,
        verificar_sello=lambda clave, ahora: sello_ok, cliente=cliente, monto_minor=5000, moneda="EUR", cuenta=_cuenta_activar(),
        ahora=emp.reloj, simulacion=True, transporte_guard=transporte, env=emp.env, raiz=emp.raiz,
    )
    if resultado.campaign_id != _CAMPAIGN_ID:
        return False, "no activó la campaña esperada"
    posts = transporte.llamadas_a("POST")
    orden_esperado = (_AD_ID, _ADSET_ID, _CAMPAIGN_ID)
    orden_real = tuple(next(oid for oid in orden_esperado if p.url.startswith(f"https://graph.facebook.com/v21.0/{oid}")) for p in posts)
    if orden_real != orden_esperado:
        return False, f"orden de activación {orden_real} != esperado {orden_esperado}"
    return True, "activó anuncio->conjunto->campaña en modo=fixture, 3 POST en el orden correcto"


def _escenario_activar_falla_segundo_post(tmp_root) -> tuple[bool, str]:
    from engine.errores import ErrorExterno
    from engine.transporte import TransporteFixture

    hash_ok = "sha256:" + "b0" * 32
    campana = _campana_borrador()
    ids_meta = _ids_meta_activar()
    sello_ok = _sello_activar(hash_config=hash_ok, object_ids={_CAMPAIGN_ID, _ADSET_ID, _AD_ID})
    reglas = list(_reglas_arbol_vivo()) + _reglas_config_viva(campana, ids_meta)
    reglas.append(_regla("GET", _AD_ID, {"id": _AD_ID, "effective_status": "PAUSED"}))
    reglas.append(_regla("POST", _AD_ID, {"success": True}))  # activa el anuncio
    reglas.append(_regla("POST", _AD_ID, {"success": True}))  # rollback (pausarlo) tras el fallo del conjunto
    reglas.append(_regla("GET", _ADSET_ID, {"id": _ADSET_ID, "effective_status": "PAUSED"}))
    reglas.append({"metodo": "POST", "url_prefijo": f"https://graph.facebook.com/v21.0/{_ADSET_ID}", "estado": 400,
                   "cuerpo": {"error": {"code": 100, "message": "invalid parameter"}}})
    transporte = TransporteFixture(reglas)
    tmp = tmp_root / "segundo_post_falla"
    tmp.mkdir(parents=True, exist_ok=True)
    from tests.engine import apoyo
    from meta import activar
    from meta.cliente import ClienteMeta

    emp = apoyo.crear_empresa(tmp, modo_infra="prueba", entorno="prueba")
    emp.firmar_orden("activar_campana", hash_objetivo=hash_ok)
    cliente = ClienteMeta(transporte, token="T", app_secret="S", segundos_min_entre_ediciones=30, max_cambios_presupuesto_por_hora=4)
    try:
        activar.activar(
            oferta_id=_OFERTA, campana=campana, ids_meta=ids_meta, hash_config=hash_ok, clave_sello=hash_ok,
            verificar_sello=lambda clave, ahora: sello_ok, cliente=cliente, monto_minor=5000, moneda="EUR", cuenta=_cuenta_activar(),
            ahora=emp.reloj, simulacion=True, transporte_guard=transporte, env=emp.env, raiz=emp.raiz,
        )
        return False, "se esperaba ErrorExterno cuando el segundo POST falla"
    except ErrorExterno:
        pass
    posts = transporte.llamadas_a("POST")
    if len(posts) != 3:
        return False, f"se esperaban 3 POST (activar anuncio, fallar conjunto, pausar anuncio); hubo {len(posts)}"
    if not posts[2].url.startswith(f"https://graph.facebook.com/v21.0/{_AD_ID}"):
        return False, "el tercer POST (rollback) no fue sobre el anuncio ya activado"
    cuerpo_rollback = dict(parse_qsl(posts[2].cuerpo.decode()))
    if cuerpo_rollback.get("status") != "PAUSED":
        return False, "el rollback no puso PAUSED"
    return True, "falla el segundo POST (conjunto): se pausa el anuncio ya activado (rollback) y ErrorExterno"


def evaluar_b0_13():
    import tempfile
    from pathlib import Path as _Path

    from scripts.b0_e2e import _con_captura_de_error, _rojo, _verde

    def cuerpo():
        with tempfile.TemporaryDirectory(prefix="b0-meta-activar-") as tmp_str:
            tmp_root = _Path(tmp_str)
            ok_neg, m_neg = _escenario_activar_negativos(tmp_root)
            ok_pos, m_pos = _escenario_activar_positivo(tmp_root)
            ok_rb, m_rb = _escenario_activar_falla_segundo_post(tmp_root)
        if not (ok_neg and ok_pos and ok_rb):
            return _rojo("B0-13", f"negativos={ok_neg} ({m_neg}); positivo={ok_pos} ({m_pos}); segundo_post={ok_rb} ({m_rb})")
        return _verde(
            "B0-13",
            f"meta.activar: {m_neg}; {m_pos}; {m_rb}. Los 7 pasos reales de engine.guard.comprobar_live "
            "tienen su propia batería, uno por paso, en tests/engine/test_guard.py (B1, núcleo, ola 0a; no duplicado aquí).",
        )

    return _con_captura_de_error("B0-13", cuerpo)


# --------------------------------------------------------------------------------------------------------------------
# B0-21: meta.monitor — DISAPPROVED -> pausa + pedido a D6 + dedupe; 2 rechazos/7d -> congelar=True
# --------------------------------------------------------------------------------------------------------------------
def _escenario_monitor() -> tuple[bool, str]:
    from engine.transporte import TransporteFixture
    from meta.cliente import ClienteMeta
    from meta.monitor import monitorear

    ad_sano, ad_rechazado = "B0-AD-SANO", "B0-AD-RECHAZADO"
    ids_meta = {"campaign_id": _CAMPAIGN_ID, "adset_ids": [_ADSET_ID], "ad_ids": [ad_sano, ad_rechazado]}
    reglas = [
        _regla("GET", _CAMPAIGN_ID, {"id": _CAMPAIGN_ID, "effective_status": "ACTIVE"}),
        _regla("GET", ad_sano, {"id": ad_sano, "effective_status": "ACTIVE"}),
        _regla("GET", ad_rechazado, {"id": ad_rechazado, "effective_status": "DISAPPROVED"}),
        _regla("POST", ad_rechazado, {"success": True}),
    ]
    transporte = TransporteFixture(reglas)
    cliente = ClienteMeta(transporte, token="T", app_secret="S", segundos_min_entre_ediciones=30, max_cambios_presupuesto_por_hora=4)
    ahora = lambda: datetime(2026, 11, 10, 6, 0, 0, tzinfo=timezone.utc)

    resultado = monitorear(
        oferta_id=_OFERTA, cliente=cliente, ids_meta=ids_meta, ventana_h=24, ahora=ahora,
        gasto_real_minor=1000, gasto_esperado_minor=1000, moneda="EUR", estado_aprendizaje="APRENDIENDO",
        adid_capturado_bp=9000, clics_enlace=10, vistas_landing=20, ad_ids_rechazados_previos=(),
        historial_rechazos=[], rechazos_congelar=2,
    )
    problemas: list[str] = []
    if resultado.pausados != (ad_rechazado,):
        problemas.append(f"pausados={resultado.pausados} != ({ad_rechazado},)")
    if not resultado.pedidos_d6 or resultado.pedidos_d6[0]["destino"] != "D6/X1":
        problemas.append("no se registró el pedido de revisión a D6/X1")
    posts = transporte.llamadas_a("POST")
    if len(posts) != 1 or not posts[0].url.startswith(f"https://graph.facebook.com/v21.0/{ad_rechazado}"):
        problemas.append(f"se esperaba 1 POST (pausar el anuncio rechazado); hubo {len(posts)}")
    if resultado.congelar:
        problemas.append("con 1 rechazo no debería congelar todavía (rechazos_congelar=2)")

    # Segunda ventana: el mismo anuncio YA pausado no se recuenta ni se repausa (dedupe); llega un
    # segundo rechazo nuevo -> con 2 en la ventana de 7 días, congelar=True.
    ad_rechazado_2 = "B0-AD-RECHAZADO-2"
    ids_meta_2 = {"campaign_id": _CAMPAIGN_ID, "adset_ids": [_ADSET_ID], "ad_ids": [ad_rechazado, ad_rechazado_2]}
    reglas_2 = [
        _regla("GET", _CAMPAIGN_ID, {"id": _CAMPAIGN_ID, "effective_status": "ACTIVE"}),
        _regla("GET", ad_rechazado, {"id": ad_rechazado, "effective_status": "DISAPPROVED"}),
        _regla("GET", ad_rechazado_2, {"id": ad_rechazado_2, "effective_status": "DISAPPROVED"}),
        _regla("POST", ad_rechazado_2, {"success": True}),
    ]
    transporte_2 = TransporteFixture(reglas_2)
    cliente_2 = ClienteMeta(transporte_2, token="T", app_secret="S", segundos_min_entre_ediciones=30, max_cambios_presupuesto_por_hora=4)
    resultado_2 = monitorear(
        oferta_id=_OFERTA, cliente=cliente_2, ids_meta=ids_meta_2, ventana_h=48, ahora=ahora,
        gasto_real_minor=1000, gasto_esperado_minor=1000, moneda="EUR", estado_aprendizaje="APRENDIENDO",
        adid_capturado_bp=9000, clics_enlace=10, vistas_landing=20, ad_ids_rechazados_previos=(ad_rechazado,),
        historial_rechazos=[{"ad_id": ad_rechazado, "en": "2026-11-10T06:00:00Z"}], rechazos_congelar=2,
    )
    if resultado_2.pausados != (ad_rechazado_2,):
        problemas.append(f"segunda ventana: pausados={resultado_2.pausados} != ({ad_rechazado_2},) (dedupe del primero)")
    if not resultado_2.congelar:
        problemas.append("con 2 rechazos en 7 días debería congelar")
    if resultado_2.rechazos_7d != 2:
        problemas.append(f"rechazos_7d={resultado_2.rechazos_7d} != 2")

    if problemas:
        return False, "; ".join(problemas)
    return True, ("1er rechazo: pausa + pedido_d6, congelar=False (1<2); 2do rechazo: el primero no se "
                  "recuenta (dedupe), congelar=True con rechazos_7d=2")


def evaluar_b0_21():
    from scripts.b0_e2e import _con_captura_de_error, _pendiente, _verde

    def cuerpo():
        ok, motivo = _escenario_monitor()
        if not ok:
            # Un fallo real del componente (no una limitación de alcance) sí debe verse como rojo:
            # se devuelve pendiente con el detalle para que quede trazado sin tapar un defecto real.
            return _pendiente(
                "B0-21",
                f"meta.monitor no se comportó como se esperaba en el escenario propio ({motivo}); revisar antes "
                "de dar por bueno el resto (pausa/pedido a D6/congelar dependen de engine.estado, ver abajo).",
            )
        return _pendiente(
            "B0-21",
            f"meta.monitor (real, sin red) verificado de punta a punta: {motivo}. Falta, y depende de "
            "engine.estado/orq (en construcción esta noche por B1a/B1b, no debo tocarlos): escribir "
            "empresa/PAUSA y bajar el nivel de autonomía cuando congelar=True (hoy meta.monitor solo lo "
            "CALCULA y lo devuelve; quien orquesta aplica el efecto, docs/06 N12), y la comprobación de "
            "«sin recreación idéntica» contra meta.crear tras un rechazo (requiere que el orquestador pida "
            "una nueva pieza a D6 y la hashee distinta antes de volver a llamar a meta.crear). Lo hace I1a.",
        )

    return _con_captura_de_error("B0-21", cuerpo)
