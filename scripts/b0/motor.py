"""B0-05, 06, 07, 16, 19, 22, 23, 25 (I1a, ola 2): la parte de B0 que SÍ depende de
``engine.estado``/``engine.orq``/``engine.d8``/``engine.cerrar`` (B1a/B1b, terminados esta noche).

Recorre ``ofertas/_ejemplo/`` de punta a punta con el motor REAL sobre una raíz temporal propia
(nunca toca el ``empresa/`` real), reutilizando ``tests.engine.apoyo`` y ``tests.engine.apoyo_orq``
(B1a dejó dicho que son «el patrón: reutilízalos, no los dupliques» — ver sus docstrings).

Qué hace cada bloque:

* **B0-05/06/07/23** (:func:`recorrido_m1_d7`): un recorrido D1→M1→D2→D3→D4→D5→D6→D7 real con
  ``engine.orq.ejecutar``/``ingresar``/``firmar`` sobre el contenido YA válido de
  ``ofertas/_ejemplo/`` (CT lo regeneró y re-selló en la ola 0b), con gates H reales (Ed25519 de
  prueba) en nivel N2 (coincide con ``contratos/gates.json``: D1/M1/D3/D5/D7 = H, D2/D4/D6 = S).
  Incluye, sobre esta misma raíz: un FAIL reparado en la ronda 2 de D2 (contenido real, solo cambia
  el veredicto de QA, igual que el patrón de ``tests/engine/test_orq.py``); D1 ejecutado dos veces
  con la misma fixture → «reutilizado» (B0-06); cambiar ``oferta.json`` (D3, v2) tras activar
  → D4-D7 obsoletas y campaña pausada (B0-07); una oferta aparte con D1 en 2 rondas FAIL → escalado;
  otra pareja de ofertas que comparan ``ejecutar`` contra ``ingresar`` byte a byte (B0-23, incluido
  el rechazo de un symlink fuera de ruta).
* **B0-25** (:func:`evaluar_b0_25`): la MISMA orden firmada Ed25519, entregada por
  ``POST /ordenes`` (``dashboard.api.ApiServicio``, WSGI, llamada en proceso — nunca ``socket``) en
  vez de escrita localmente por ``orq firmar``; mismo documento, y ``nonce`` repetido → 409.
* **B0-16/19/22** (:func:`evaluar_b0_16`, :func:`evaluar_b0_19`, :func:`evaluar_b0_22`):
  ``engine.d8.ciclo``/``veredicto`` y ``engine.cerrar.cerrar_oferta`` REALES. ``d8`` exige un
  ``conn`` con columnas exactas (``dim_anuncio(ad_id, oferta_id, concepto_id)``,
  ``fact_meta_ad_dia(ad_id, fecha, gasto_minor, clics_enlace, pull_ts)``,
  ``fact_pedido(session_id, oferta_id, adid, pagado_en, estado, interno, verificacion, moneda,
  bruto_minor, impuesto_minor, fee_minor)``, ``fact_meta_conv``, ``fact_reembolso``) que **no**
  coincide con lo que de verdad migra ``datos/migraciones/0001_inicial.sql`` (esa tabla usa
  ``checkout_session_id``, sin ``estado``/``interno``/``verificacion``/``bruto_minor``) y, además,
  ninguna función de ``datos/etl_meta.py`` escribe ``dim_anuncio`` (que
  ``decision.entradas._ids_de_celda`` exige incluso para la celda ``oferta_mercado``) — ver
  «Pedidos» del informe de la sesión, con la cita exacta. Por eso este módulo abre su PROPIO almacén
  mínimo (igual, a propósito, al que ya usa ``tests/engine/test_d8.py``, de B1b) y lo alimenta con
  los números agregados de ``scripts.b0.generador`` (gasto, clics, compras) en vez de pasar por el
  ETL real de ``datos`` (eso ya lo prueba B0-15, en ``scripts/b0/datos.py``, de otra sesión).
"""
from __future__ import annotations

import io
import json
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Sequence

from engine import comun
from engine import d8 as engine_d8
from engine import cerrar as engine_cerrar
from engine import estado, orq
from engine.ejecutor import EjecutorMotor
from engine.errores import ErrorBloqueado, ErrorFabrica, ErrorValidacion
from engine.limites import Limites
from engine.parametros import Parametros

from scripts.b0 import generador
from scripts.validar_esquemas import ARCHIVOS_SELLADOS, DIRECTORIOS_SELLADOS, EXPONENTE_ISO4217, dec

RAIZ_REPO = Path(__file__).resolve().parents[2]
EJEMPLO = RAIZ_REPO / "ofertas" / "_ejemplo"
_ORDEN_ETAPAS: tuple[str, ...] = ("D1", "M1", "D2", "D3", "D4", "D5", "D6", "D7")


# ====================================================================================================
# Utilidades comunes del recorrido M1..D7 (B0-05, 06, 07, 23)
# ====================================================================================================
def _rutas_selladas(etapa: str) -> list[str]:
    return list(ARCHIVOS_SELLADOS.get(etapa, [])) + list(DIRECTORIOS_SELLADOS.get(etapa, []))


def _copiar_etapa_real(etapa: str, salida: Path, *, mutar: Callable[[str, Any], Any] | None = None) -> None:
    """Copia el contenido YA válido de ``ofertas/_ejemplo/`` para ``etapa`` dentro de ``salida``."""
    for rel in ARCHIVOS_SELLADOS.get(etapa, []):
        contenido = json.loads((EJEMPLO / rel).read_text(encoding="utf-8"))
        if mutar is not None:
            contenido = mutar(rel, contenido)
        destino = salida / rel
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(json.dumps(contenido, ensure_ascii=False, indent=2), encoding="utf-8")
    for rel in DIRECTORIOS_SELLADOS.get(etapa, []):
        shutil.copytree(EJEMPLO / rel, salida / rel)


def _qa(*, etapa: str, version: str, ronda: int, veredicto: str, oferta_id: str, artefacto_ref: str) -> dict:
    """``qa.json`` mínimo pero válido (mismo patrón que ``tests/engine/apoyo_orq._qa_minimo``, reutilizado
    tal cual por ``tests/engine/test_orq.py``; aquí reconstruido porque el ``artefacto_ref`` de una
    etapa con VARIOS archivos sellados —D3, D5— no entra en la firma de un solo string sin elegir uno)."""
    sha = "sha256:" + "b0" * 32
    return {
        "schema_version": "1.0.0", "ambito": "oferta", "oferta_id": oferta_id, "periodo": None,
        "etapa": etapa, "version": version, "ronda": ronda, "creado_en": "2026-11-09T09:30:00Z",
        "skill_version_qa": "0.1.0", "skill_version_maker": "0.1.0", "artefacto_ref": artefacto_ref,
        "artefacto_sha256": sha, "entradas": {}, "veredicto": veredicto,
        "puntaje_global": "4.0", "umbral": "3.0",
        "items": [{"item_id": "R1", "nombre": "cumple el esquema", "puntaje": 4, "evidencia": "validado contra el esquema"}],
        "checks_l1": [{"check_id": "L1-01", "resultado": "pass", "detalle": "contenido real de ofertas/_ejemplo (I1a, B0)"}],
        "simulaciones_l3": [], "hallazgos": [],
        "justificacion_sin_hallazgos": "Fixture de integración B0 (I1a): contenido real de ofertas/_ejemplo, sin hallazgos nuevos.",
        "cambios_aplicados": [], "mejoras_propuestas": [], "riesgos_residuales": [], "aprendizajes_para_skill": [], "x1": None,
    }


def _fixture_etapa(tmp_dir: Path, etapa: str, *, oferta_id: str, version: str = "v1",
                   veredictos: Sequence[str] = ("PASS",), mutar: Callable[[str, Any], Any] | None = None) -> Path:
    """Fixture de ``len(veredictos)`` rondas para ``etapa``, con el contenido REAL de ``ofertas/_ejemplo``."""
    rel_ref = _rutas_selladas(etapa)[0]
    for indice, veredicto in enumerate(veredictos, start=1):
        ronda = tmp_dir / f"ronda-{indice}"
        _copiar_etapa_real(etapa, ronda / "salida", mutar=mutar if indice == len(veredictos) else None)
        if indice != len(veredictos):
            # Las rondas que NO son la última representan un FAIL sobre el contenido ya bueno (se
            # repara "solo" en la ronda siguiente): mismo patrón que B1a usa en tests/engine/test_orq.py.
            _copiar_etapa_real(etapa, ronda / "salida")
        qa = _qa(etapa=etapa, version=version, ronda=min(indice, 2), veredicto=veredicto, oferta_id=oferta_id, artefacto_ref=rel_ref)
        ronda.mkdir(parents=True, exist_ok=True)
        (ronda / "qa.json").write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding="utf-8")
    return tmp_dir


def _ejecutar_con_gate(oferta_id: str, etapa: str, fixture_dir: Path, *, emp: Any, nonce: str) -> dict:
    """``orq.ejecutar``; si el gate es H y queda ``pendiente_firma``, firma con la clave de prueba y repite."""
    resultado = orq.ejecutar(oferta_id, etapa, fixture_dir=fixture_dir, raiz=emp.raiz, ahora=emp.reloj, env=emp.env)
    if resultado["resultado"] == "pendiente_firma":
        orq.firmar(oferta_id=oferta_id, etapa=etapa, hash_objetivo=resultado["hash_salida"],
                  clave_privada=emp.claves.privada, raiz=emp.raiz, ahora=emp.reloj, nonce=nonce)
        resultado = orq.ejecutar(oferta_id, etapa, fixture_dir=fixture_dir, raiz=emp.raiz, ahora=emp.reloj, env=emp.env)
    return resultado


def _crear_oferta(emp: Any, tmp: Path, *, slug: str, nivel: str = "N2") -> str:
    from tests.engine.apoyo_orq import pre_brief

    ruta = tmp / f"brief-{slug}.yaml"
    import yaml
    ruta.write_text(yaml.safe_dump(pre_brief(nivel_autonomia=nivel, slug=slug), sort_keys=False, allow_unicode=True), encoding="utf-8")
    return orq.crear(ruta_brief=ruta, raiz=emp.raiz, ahora=emp.reloj)["oferta_id"]


# ====================================================================================================
# Recorrido principal: D1..D7 sobre ofertas/_ejemplo (contenido real)
# ====================================================================================================
def recorrido_m1_d7(tmp: Path) -> dict[str, Any]:
    """Corre TODO el recorrido real (B0-05/06/07/23) sobre ``tmp`` y devuelve un resumen con lo que
    cada criterio necesita. Nunca toca ``empresa/`` real (``tmp`` es siempre una raíz temporal)."""
    from tests.engine import apoyo

    emp = apoyo.crear_empresa(tmp, modo_infra="prueba", entorno="prueba")
    resultado: dict[str, Any] = {"emp": emp, "etapas": {}}

    # --- oferta principal: D1..D7, con un FAIL reparado en la ronda 2 de D2 --------------------------
    oferta_id = _crear_oferta(emp, tmp, slug="b0-motor-principal")
    resultado["oferta_id"] = oferta_id
    for etapa in _ORDEN_ETAPAS:
        veredictos = ("FAIL", "PASS") if etapa == "D2" else ("PASS",)
        fixture = tmp / f"fx-principal-{etapa}"
        _fixture_etapa(fixture, etapa, oferta_id=oferta_id, veredictos=veredictos)
        r = _ejecutar_con_gate(oferta_id, etapa, fixture, emp=emp, nonce=f"b0-motor-principal-{etapa.lower()}-01")
        resultado["etapas"][etapa] = r
        if r["resultado"] != "aprobado":
            # Sin esto, un fallo real de una etapa (no un límite de alcance) quedaría enmascarado:
            # las etapas siguientes deben poder seguir viendo por qué faltó algo.
            resultado["fallo_en"] = etapa
            break

    # --- B0-06: D1 ejecutado DOS VECES con la MISMA fixture -> "reutilizado" ------------------------
    if "fallo_en" not in resultado:
        fixture_d1 = tmp / "fx-principal-D1"
        resultado["d1_reutilizado"] = orq.ejecutar(oferta_id, "D1", fixture_dir=fixture_d1, raiz=emp.raiz, ahora=emp.reloj, env=emp.env)

    # --- B0-07: tras activar, cambiar oferta.json (D3 v2) -> D4-D7 obsoletas y campaña pausada -------
    if "fallo_en" not in resultado:
        for fase in ("en_construccion", "listo_para_activar", "en_test"):
            estado.transicionar_fase(oferta_id, fase, actor="b0-motor", causa="avance de prueba (I1a)", raiz=emp.raiz, ahora=emp.reloj)

        def _mutar_oferta(rel: str, contenido: Any) -> Any:
            if rel == "03-oferta/oferta.json" and isinstance(contenido, dict):
                contenido = dict(contenido)
                contenido["angulos"] = list(contenido.get("angulos", [])) + [{
                    "id": "angulo-b0-motor-v2", "hook": "Ángulo nuevo de prueba (I1a, B0-07)",
                    "objecion": "ninguna (ángulo de prueba)", "evidencia": "contenido sintético de integración",
                }]
            return contenido

        fixture_d3_v2 = tmp / "fx-principal-D3-v2"
        _fixture_etapa(fixture_d3_v2, "D3", oferta_id=oferta_id, version="v2", mutar=_mutar_oferta)
        resultado["d3_v2"] = _ejecutar_con_gate(oferta_id, "D3", fixture_d3_v2, emp=emp, nonce="b0-motor-principal-d3v2-01")
        resultado["estado_tras_v2"] = estado.cargar(oferta_id, raiz=emp.raiz)

    # --- B0-05 (parte 2): una oferta aparte, D1 con 2 rondas FAIL -> escalado ------------------------
    oferta_escalado = _crear_oferta(emp, tmp, slug="b0-motor-escalado")
    fixture_escalado = tmp / "fx-escalado-D1"
    _fixture_etapa(fixture_escalado, "D1", oferta_id=oferta_escalado, veredictos=("FAIL", "FAIL"))
    resultado["escalado"] = orq.ejecutar(oferta_escalado, "D1", fixture_dir=fixture_escalado, raiz=emp.raiz, ahora=emp.reloj, env=emp.env)
    resultado["escalado_estado"] = estado.cargar(oferta_escalado, raiz=emp.raiz)

    # --- B0-23: ejecutar vs ingresar, mismo contenido real de D1 -> mismo hash/gate; symlink -> 3 ----
    contenido_d1 = json.loads((EJEMPLO / "01-descubrimiento" / "candidatos.json").read_text(encoding="utf-8"))
    oferta_ejecutar = _crear_oferta(emp, tmp, slug="b0-motor-paridad-ejecutar")
    fixture_paridad = tmp / "fx-paridad-D1"
    _copiar_etapa_real("D1", fixture_paridad / "ronda-1" / "salida")
    (fixture_paridad / "ronda-1").mkdir(parents=True, exist_ok=True)
    (fixture_paridad / "ronda-1" / "qa.json").write_text(
        json.dumps(_qa(etapa="D1", version="v1", ronda=1, veredicto="PASS", oferta_id=oferta_ejecutar,
                      artefacto_ref="01-descubrimiento/candidatos.json"), ensure_ascii=False, indent=2), encoding="utf-8")
    via_ejecutar = _ejecutar_con_gate(oferta_ejecutar, "D1", fixture_paridad, emp=emp, nonce="b0-motor-paridad-ejecutar-01")

    oferta_ingresar = _crear_oferta(emp, tmp, slug="b0-motor-paridad-ingresar")
    desde = tmp / "ingresar-D1"
    destino = desde / "01-descubrimiento" / "candidatos.json"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(contenido_d1, ensure_ascii=False, indent=2), encoding="utf-8")
    via_ingresar_intento = orq.ingresar(oferta_ingresar, "D1", desde=desde, raiz=emp.raiz, ahora=emp.reloj, env=emp.env)
    if via_ingresar_intento["resultado"] == "pendiente_firma":
        orq.firmar(oferta_id=oferta_ingresar, etapa="D1", hash_objetivo=via_ingresar_intento["hash_salida"],
                  clave_privada=emp.claves.privada, raiz=emp.raiz, ahora=emp.reloj, nonce="b0-motor-paridad-ingresar-01")
        via_ingresar = orq.ingresar(oferta_ingresar, "D1", desde=desde, raiz=emp.raiz, ahora=emp.reloj, env=emp.env)
    else:
        via_ingresar = via_ingresar_intento
    resultado["paridad"] = {"ejecutar": via_ejecutar, "ingresar": via_ingresar}

    oferta_symlink = _crear_oferta(emp, tmp, slug="b0-motor-paridad-symlink")
    desde_symlink = tmp / "ingresar-symlink"
    destino_symlink = desde_symlink / "01-descubrimiento" / "candidatos.json"
    destino_symlink.parent.mkdir(parents=True, exist_ok=True)
    destino_symlink.write_text(json.dumps(contenido_d1, ensure_ascii=False, indent=2), encoding="utf-8")
    (desde_symlink / "enlace-fuera-de-ruta.json").symlink_to(destino_symlink)
    try:
        orq.ingresar(oferta_symlink, "D1", desde=desde_symlink, raiz=emp.raiz, ahora=emp.reloj, env=emp.env)
        resultado["symlink_codigo"] = 0
    except ErrorFabrica as exc:
        resultado["symlink_codigo"] = exc.codigo_salida

    return resultado


def _criterios_desde_recorrido(r: dict[str, Any]) -> dict[str, Any]:
    """Construye los 4 ``Criterio`` (B0-05, 06, 07, 23) a partir de UN solo :func:`recorrido_m1_d7`."""
    from scripts.b0_e2e import _rojo, _verde

    if "fallo_en" in r:
        etapa = r["fallo_en"]
        detalle = r["etapas"][etapa]
        motivo = f"la etapa {etapa} no quedó 'aprobado' (dio {detalle['resultado']!r}) en el recorrido real D1..D7"
        return {k: _rojo(k, motivo) for k in ("B0-05", "B0-06", "B0-07", "B0-23")}

    criterios: dict[str, Any] = {}

    # B0-05: todas las etapas aprobadas con gate H real (D1/M1/D3/D5/D7 en N2), D2 FAIL->ronda2->PASS,
    # y una oferta aparte escalada tras 2 rondas FAIL.
    aprobadas = {e: r["etapas"][e]["resultado"] == "aprobado" for e in _ORDEN_ETAPAS}
    d2_dos_rondas = r["etapas"]["D2"].get("rondas") == 2
    escalado_ok = r["escalado"]["resultado"] == "escalado" and r["escalado_estado"]["etapas"]["D1"]["estado"] == "escalado"
    if not all(aprobadas.values()):
        criterios["B0-05"] = _rojo("B0-05", f"no todas las etapas quedaron aprobadas: {aprobadas}")
    elif not d2_dos_rondas:
        criterios["B0-05"] = _rojo("B0-05", f"D2 no mostró el FAIL->ronda2->PASS esperado: rondas={r['etapas']['D2'].get('rondas')}")
    elif not escalado_ok:
        criterios["B0-05"] = _rojo("B0-05", f"2 rondas FAIL de D1 en una oferta aparte no dieron 'escalado': {r['escalado']}")
    else:
        criterios["B0-05"] = _verde(
            "B0-05",
            f"D1..D7 aprobadas sobre ofertas/_ejemplo real (oferta {r['oferta_id']}) con gates H firmados "
            "(Ed25519 de prueba, N2: D1/M1/D3/D5/D7) y S automáticos (D2/D4/D6); D2 reparó un FAIL en la "
            "ronda 2 con el MISMO contenido real; una segunda oferta con D1 en 2 rondas FAIL quedó "
            "'escalado' (engine.orq.ejecutar + engine.estado reales, sin fakes).",
        )

    # B0-06: D1 ejecutado dos veces con la MISMA fixture -> "reutilizado", mismo hash_salida.
    primero = r["etapas"]["D1"]
    segundo = r.get("d1_reutilizado") or {}
    if segundo.get("resultado") != "reutilizado" or segundo.get("hash_salida") != primero.get("hash_salida"):
        criterios["B0-06"] = _rojo("B0-06", f"la segunda ejecución de D1 no dio 'reutilizado' con el mismo hash: {segundo}")
    else:
        criterios["B0-06"] = _verde("B0-06", f"D1 ejecutado dos veces con la misma fixture: la 2da dice 'reutilizado' "
                                             f"con hash_salida idéntico ({segundo['hash_salida'][:19]}…)")

    # B0-07: cambiar oferta.json (D3 v2) tras activar -> D4..D7 obsoletas, pausada.
    est_v2 = r.get("estado_tras_v2")
    if est_v2 is None:
        criterios["B0-07"] = _rojo("B0-07", "no se llegó a la parte de obsolescencia del recorrido")
    else:
        d3_v2_ok = r["d3_v2"]["resultado"] == "aprobado" and r["d3_v2"]["version"] == "v2"
        obsoletas = [e for e in ("D4", "D5", "D6", "D7") if est_v2["etapas"][e]["obsoleta"] and est_v2["etapas"][e]["estado"] == "pendiente"]
        pausada = est_v2["fase"] == "pausada"
        if not (d3_v2_ok and len(obsoletas) == 4 and pausada):
            criterios["B0-07"] = _rojo(
                "B0-07", f"d3_v2_ok={d3_v2_ok}, obsoletas={obsoletas} (se esperaban 4), fase={est_v2['fase']!r} (se esperaba 'pausada')",
            )
        else:
            criterios["B0-07"] = _verde(
                "B0-07",
                "D3 re-aprobada en v2 con contenido real mutado (un ángulo nuevo) tras activar la campaña "
                "(fase en_test): engine.estado.propagar_obsolescencia volvió pendiente+obsoleta a D4,D5,D6,D7 "
                "(cierre transitivo real) y pausó la campaña (fase -> pausada).",
            )

    # B0-23: ejecutar vs ingresar, mismo hash_salida y mismo resultado con contenido real; symlink -> 3.
    par = r.get("paridad") or {}
    via_e, via_i = par.get("ejecutar") or {}, par.get("ingresar") or {}
    paridad_ok = (via_e.get("hash_salida") == via_i.get("hash_salida") and via_e.get("resultado") == via_i.get("resultado") == "aprobado")
    symlink_ok = r.get("symlink_codigo") == 3
    if not (paridad_ok and symlink_ok):
        criterios["B0-23"] = _rojo("B0-23", f"paridad_ok={paridad_ok} (ejecutar={via_e}, ingresar={via_i}); symlink_codigo={r.get('symlink_codigo')} (se esperaba 3)")
    else:
        criterios["B0-23"] = _verde(
            "B0-23",
            f"orq.ingresar sobre el MISMO contenido real de D1 produjo el mismo hash_salida y el mismo "
            f"gate que orq.ejecutar --modo fixture ({via_e['hash_salida'][:19]}…); un symlink fuera de ruta "
            "en --desde se rechazó con ErrorValidacion (código 3).",
        )
    return criterios


_CACHE_RECORRIDO: dict[str, dict[str, Any]] = {}


def _recorrido_cacheado(tmp: Path) -> dict[str, Any]:
    """Memoiza :func:`recorrido_m1_d7` por ``str(tmp)`` (nunca ``id(tmp)``: un ``Path`` efímero puede
    recolectarse y su ``id`` reutilizarse por otra raíz temporal más adelante en el mismo proceso, lo
    que daría un resultado cruzado): ``scripts.b0_e2e`` llama 4 evaluadores (B0-05/06/07/23) sobre la
    MISMA raíz temporal de una corrida; esto evita correrlo 4 veces. Una sola entrada en caché: una
    raíz nueva reemplaza a la anterior (no se acumulan raíces ya borradas de corridas previas)."""
    clave = str(tmp)
    if clave not in _CACHE_RECORRIDO:
        sub = tmp / "b0-motor-recorrido"
        sub.mkdir(parents=True, exist_ok=True)
        _CACHE_RECORRIDO.clear()
        _CACHE_RECORRIDO[clave] = _criterios_desde_recorrido(recorrido_m1_d7(sub))
    return _CACHE_RECORRIDO[clave]


def evaluar_b0_05(tmp: Path):
    from scripts.b0_e2e import _con_captura_de_error
    return _con_captura_de_error("B0-05", lambda: _recorrido_cacheado(tmp)["B0-05"])


def evaluar_b0_06(tmp: Path):
    from scripts.b0_e2e import _con_captura_de_error
    return _con_captura_de_error("B0-06", lambda: _recorrido_cacheado(tmp)["B0-06"])


def evaluar_b0_07(tmp: Path):
    from scripts.b0_e2e import _con_captura_de_error
    return _con_captura_de_error("B0-07", lambda: _recorrido_cacheado(tmp)["B0-07"])


def evaluar_b0_23(tmp: Path):
    from scripts.b0_e2e import _con_captura_de_error
    return _con_captura_de_error("B0-23", lambda: _recorrido_cacheado(tmp)["B0-23"])


# ====================================================================================================
# B0-25: POST /ordenes (dashboard.api.ApiServicio, WSGI en proceso) ≡ orq firmar local
# ====================================================================================================
def _llamar_wsgi(app: Any, *, cuerpo: bytes, ts: str, firma: str) -> tuple[int, dict]:
    environ = {
        "REQUEST_METHOD": "POST", "PATH_INFO": "/ordenes", "CONTENT_LENGTH": str(len(cuerpo)),
        "wsgi.input": io.BytesIO(cuerpo), "HTTP_X_FABRICA_TS": ts, "HTTP_X_FABRICA_FIRMA": firma,
    }
    capturado: list[Any] = []

    def _start_response(estado: str, cabeceras: Any) -> None:
        capturado.append(estado)

    cuerpo_resp = app(environ, _start_response)
    codigo = int(capturado[0].split(" ", 1)[0])
    return codigo, json.loads(b"".join(cuerpo_resp).decode("utf-8"))


def evaluar_b0_25(tmp: Path):
    from scripts.b0_e2e import _con_captura_de_error, _rojo, _verde

    def cuerpo():
        from tests.engine import apoyo
        from dashboard.api import ApiServicio, firmar as firmar_api

        base = tmp / "b0-motor-ordenes"
        base.mkdir(parents=True, exist_ok=True)
        emp_local = apoyo.crear_empresa(base / "local", modo_infra="prueba", entorno="prueba")
        emp_api = apoyo.crear_empresa(base / "api", modo_infra="prueba", entorno="prueba")
        oferta_id = _crear_oferta(emp_local, base, slug="b0-motor-ordenes")
        hash_objetivo = "sha256:" + "25" * 32
        nonce = "b0-motor-ordenes-nonce-01"

        # Camino local: orq.firmar (el reloj de la fixture es FIJO: mismo ts en ambos caminos).
        orq.firmar(oferta_id=oferta_id, etapa="D1", hash_objetivo=hash_objetivo, clave_privada=emp_local.claves.privada,
                  raiz=emp_local.raiz, ahora=emp_local.reloj, nonce=nonce)
        local_doc = comun.cargar_json(emp_local.ruta("ordenes", f"{nonce}.json"))

        # Camino API: la MISMA orden (mismo ts porque ambos relojes son el mismo fijo), construida
        # con la clave privada igual que orq.firmar, entregada por POST /ordenes (WSGI, sin red).
        orden = {"schema_version": "1.1.0", "accion": "aprobar_etapa", "oferta_id": oferta_id,
                "hash_objetivo": hash_objetivo, "ts": comun.iso_z(emp_api.reloj()), "nonce": nonce, "etapa": "D1"}
        orden["firma"] = comun.firmar_ed25519(comun.json_canonico(orden), emp_local.claves.privada)
        cuerpo_bytes = comun.json_canonico(orden)
        secreto = b"b0-motor-ordenes-secreto-de-prueba"
        ts_cabecera = comun.iso_z(emp_api.reloj())
        # dashboard.api firma /ordenes con contexto "req" (la respuesta de /estado usa "resp", para que
        # una firma de respuesta nunca autentique una petición): ver dashboard/api.py CTX_REQ.
        firma_cabecera = firmar_api(secreto, cuerpo_bytes, ts_cabecera, "req")
        app = ApiServicio(raiz=emp_api.raiz, secreto=secreto, parametros={"tolerancia_seg": 300, "cuerpo_max_bytes": 65536},
                          ahora=emp_api.reloj, env=emp_api.env)
        codigo_1, resp_1 = _llamar_wsgi(app, cuerpo=cuerpo_bytes, ts=ts_cabecera, firma=firma_cabecera)
        if codigo_1 != 200 or resp_1.get("resultado") != "registrada":
            return _rojo("B0-25", f"POST /ordenes no registró la orden válida: {codigo_1} {resp_1}")
        api_doc = comun.cargar_json(emp_api.ruta("ordenes", f"{nonce}.json"))
        if api_doc != local_doc:
            return _rojo("B0-25", f"la orden escrita por la API difiere de la escrita por orq.firmar: {api_doc} != {local_doc}")

        # nonce repetido -> 409 (crear_exclusivo falla; mismo archivo, sin pisarlo).
        codigo_2, resp_2 = _llamar_wsgi(app, cuerpo=cuerpo_bytes, ts=ts_cabecera, firma=firma_cabecera)
        if codigo_2 != 409 or resp_2.get("motivo") != "nonce_repetido":
            return _rojo("B0-25", f"un nonce repetido por POST /ordenes no dio 409 nonce_repetido: {codigo_2} {resp_2}")

        return _verde(
            "B0-25",
            "una orden Ed25519 entregada por POST /ordenes (dashboard.api.ApiServicio, WSGI en proceso, "
            "sin abrir ningún socket) produjo el MISMO documento que escribe orq.firmar en el terminal del dueño "
            "(empresa/ordenes/<nonce>.json, comparado byte a byte); el mismo nonce repetido por la API "
            "dio 409 nonce_repetido (engine.guard/orq ya prueban el rechazo del lado 'orq firmar').",
        )

    return _con_captura_de_error("B0-25", cuerpo)


# ====================================================================================================
# B0-16/19/22: engine.d8.ciclo / engine.d8.veredicto / engine.cerrar.cerrar_oferta REALES
# ====================================================================================================
def _conexion_d8_memoria():
    """Esquema mínimo que ``engine.d8``/``decision.entradas`` de verdad consultan (``conn.execute`` con
    columnas EXACTAS): deliberadamente IGUAL al que usa ``tests/engine/test_d8.py`` (prueba de B1b
    contra el mismo módulo), porque el esquema que migra ``datos/migraciones/0001_inicial.sql`` NO
    coincide (columnas distintas en ``fact_pedido``, sin ``dim_anuncio`` poblada por ningún ETL) — ver
    «Pedidos» del informe."""
    import sqlite3

    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """
        CREATE TABLE dim_anuncio (ad_id TEXT PRIMARY KEY, oferta_id TEXT NOT NULL, concepto_id TEXT);
        CREATE TABLE fact_meta_ad_dia (ad_id TEXT NOT NULL, fecha TEXT NOT NULL, gasto_minor INTEGER NOT NULL,
                                        clics_enlace INTEGER NOT NULL, pull_ts TEXT);
        CREATE TABLE fact_pedido (session_id TEXT NOT NULL, oferta_id TEXT NOT NULL, adid TEXT, pagado_en TEXT NOT NULL,
                                   estado TEXT NOT NULL, interno INTEGER NOT NULL DEFAULT 0, verificacion INTEGER NOT NULL DEFAULT 0,
                                   moneda TEXT NOT NULL, bruto_minor INTEGER NOT NULL, impuesto_minor INTEGER NOT NULL DEFAULT 0,
                                   fee_minor INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE fact_meta_conv (ad_id TEXT NOT NULL, fecha TEXT NOT NULL, ventana TEXT NOT NULL, compras_meta INTEGER NOT NULL);
        CREATE TABLE fact_reembolso (session_id TEXT NOT NULL, monto_minor INTEGER NOT NULL, estado TEXT NOT NULL);
        """
    )
    return conn


def _monto_minor(spend: str, moneda: str) -> int:
    return int(dec(spend) * (10 ** EXPONENTE_ISO4217[moneda]))


def _cargar_escenario(conn: Any, oferta_id: str, escenario: dict, *, moneda: str = "EUR") -> None:
    """Carga ``{"meta": doc, "stripe": doc}`` de ``scripts.b0.generador`` al esquema de :func:`_conexion_d8_memoria`."""
    ads_vistos: set[str] = set()
    for fila in escenario["meta"]["filas"]:
        ad_id = str(fila["ad_id"])
        if ad_id not in ads_vistos:
            conn.execute("INSERT INTO dim_anuncio VALUES (?,?,?)", (ad_id, oferta_id, None))
            ads_vistos.add(ad_id)
        conn.execute(
            "INSERT INTO fact_meta_ad_dia VALUES (?,?,?,?,?)",
            (ad_id, fila["date_start"], _monto_minor(fila["spend"], moneda), int(fila["inline_link_clicks"]),
             f"{fila['date_start']}T23:59:00Z"),
        )
    sesiones_vistas: set[str] = set()
    pi_a_sesion: dict[str, str] = {}
    for evento in escenario["stripe"]["eventos"]:
        obj = evento["data"]["object"]
        if evento["type"] == "checkout.session.completed":
            session_id = str(obj["id"])
            if session_id in sesiones_vistas or obj.get("payment_status") != "paid":
                continue
            sesiones_vistas.add(session_id)
            pi_a_sesion[str(obj.get("payment_intent"))] = session_id
            metadata = obj.get("metadata") or {}
            verificacion = 1 if metadata.get("verificacion") == "1" else 0
            adid = metadata.get("adid") or "desconocido"
            pagado_en = comun.iso_z(datetime.fromtimestamp(int(evento["created"]), tz=timezone.utc))
            conn.execute(
                "INSERT INTO fact_pedido VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (session_id, oferta_id, adid, pagado_en, "pagado", 0, verificacion, str(obj["currency"]).upper(),
                 int(obj["amount_total"]), 0, 50),
            )
        elif evento["type"] == "charge.refunded":
            session_id = pi_a_sesion.get(str(obj.get("payment_intent")))
            if session_id is not None:
                conn.execute("INSERT INTO fact_reembolso VALUES (?,?,?)", (session_id, int(obj["amount_refunded"]), "ejecutado"))


def _parametros_b0_motor(**cambios: Any) -> Parametros:
    plano = {
        "estadistica.prior_conv_fuerza_clics": 50, "estadistica.prior_cpc_fuerza_clics": 20,
        "estadistica.alfa_descarte": "0.05", "estadistica.alfa_descarte_tope": "0.20", "estadistica.k_min_matar": "2.0",
        "estadistica.n_min_escala": 8, "estadistica.nodos_cpc": 5, "estadistica.dias_madurez_compra": 2,
        "estadistica.k_min_fallida": "3.0",
        "testeo.p_escala": "0.80", "testeo.ventana_no_decidir_h": 0, "testeo.cobertura_adid_min_pct": 80,
        "testeo.razon_meta_stripe_min": "0.5", "testeo.razon_meta_stripe_max": "2.0", "testeo.razon_ventana_dias": 7,
        "testeo.razon_n_min": 1000,
        "testeo.p_fallida": "0.90",
        "veredicto.madurez_dias_extra": 7, "veredicto.compras_min": 3, "veredicto.dias_min": 3,
        "veredicto.max_dia_pct": 80, "veredicto.reembolso_max_pct": 50,
        "economia.factor_cpa_objetivo": "0.6",
        "salud_operativa.reembolsos_objetivo_pct": 7,
    }
    plano.update(cambios)
    grupos: dict = {}
    for clave, valor in plano.items():
        grupo, nombre = clave.split(".")
        grupos.setdefault(grupo, {})[nombre] = {"valor": valor, "unidad": "u", "hipotesis": True, "fuente": "prueba", "ultima_calibracion": None}
    return Parametros({"schema_version": "1.1.0", "version": 1, "grupos": grupos})


def _limites_b0_motor(**cambios: Any) -> Limites:
    datos = {"moneda_limites": "EUR", "gasto_total_test_por_oferta": 30000, "gasto_diario_por_oferta": 3000,
            "factor_techo_teorico_diario": "1.75", "politica_reembolso_dias": 14}
    datos.update(cambios)
    return Limites(datos=datos, entorno="prueba")


def _preparar_oferta_en_test(tmp: Path, *, slug: str) -> tuple[Path, str, Any]:
    """Raíz temporal con una oferta real (D1..D3 aprobados -> economia.json presente) en fase ``en_test``."""
    from tests.engine import apoyo

    sub = tmp / f"b0-motor-d8-{slug}"
    emp = apoyo.crear_empresa(sub, modo_infra="prueba", entorno="prueba")
    oferta_id = _crear_oferta(emp, sub, slug=slug)
    for etapa in ("D1", "M1", "D2", "D3"):
        fixture = sub / f"fx-{etapa}"
        _fixture_etapa(fixture, etapa, oferta_id=oferta_id)
        r = _ejecutar_con_gate(oferta_id, etapa, fixture, emp=emp, nonce=f"b0-motor-d8-{slug}-{etapa.lower()}-01")
        if r["resultado"] != "aprobado":
            raise AssertionError(f"{etapa} no quedó aprobado preparando la oferta en_test: {r}")
    for fase in ("en_construccion", "listo_para_activar", "en_test"):
        estado.transicionar_fase(oferta_id, fase, actor="b0-motor", causa="preparación B0-16/19/22", raiz=emp.raiz, ahora=emp.reloj)
    return emp.raiz, oferta_id, emp


_AHORA_D8 = datetime(2026, 11, 24, 9, 0, 0, tzinfo=timezone.utc)


def _escenario_b_ganador_ajustado(oferta_id: str) -> dict[str, Any]:
    """Mismo generador real (``scripts.b0.generador``), con un gasto diario propio: el preset
    ``B_ganador_fuerte`` de ``generador.ESCENARIOS`` (pensado para que B0-15 vea una cobertura del
    90%, no para cruzar el ``cpa_obj`` de ESTE ``economia.json``) deja el CPA tipico apenas por
    ENCIMA de ``cpa_obj`` (SEGUIR/prometedora, no ESCALAR); con menos gasto diario y el mismo número
    de compras (10, con adid conocido) el CPA tipico cae bien por debajo del objetivo. Documentado
    en «Decisiones» del informe de la sesión."""
    meta = generador.generar_insights_meta(oferta_id=oferta_id, semilla=202, gasto_diario_centavos=300)
    dias = sorted({f["date_start"] for f in meta["filas"]})
    ad_ids = generador._AD_IDS  # mismos 5 ad_id sintéticos que ya trae el documento de insights
    compras = [(dias[i], ad_ids[i % len(ad_ids)]) for i in range(2, 12)]
    stripe = generador.generar_eventos_stripe(oferta_id=oferta_id, semilla=202, compras=compras,
                                              con_reembolso=True, con_compra_prueba=True, con_duplicado=True)
    return {"meta": meta, "stripe": stripe, "descripcion": "14 días, ~50 EUR de gasto, 10 compras (90% cobertura): ganador claro"}


def evaluar_b0_16():
    from scripts.b0_e2e import _con_captura_de_error, _rojo, _verde

    def cuerpo():
        import tempfile

        resultados: dict[str, Any] = {}
        with tempfile.TemporaryDirectory(prefix="b0-motor-d8-16-") as tmp_str:
            tmp = Path(tmp_str)
            par = _parametros_b0_motor()
            lim = _limites_b0_motor()
            for nombre, esperado in (("A_perdedor_severo", "MATAR"), ("B_ganador_fuerte", "ESCALAR"), ("C_intermedio_95_retraso", None)):
                raiz, oferta_id, emp = _preparar_oferta_en_test(tmp, slug=nombre.split("_")[0].lower())
                conn = _conexion_d8_memoria()
                try:
                    if nombre == "B_ganador_fuerte":
                        escenario = _escenario_b_ganador_ajustado(oferta_id)
                    else:
                        escenario = generador.generar_escenario(nombre, oferta_id=oferta_id)
                    _cargar_escenario(conn, oferta_id, escenario)
                    ejecutor = EjecutorMotor(raiz=raiz, ahora=lambda: _AHORA_D8)
                    registros = engine_d8.ciclo(oferta_id, conn=conn, ahora=lambda: _AHORA_D8, par=par, lim=lim,
                                                ejecutor=ejecutor, modo="live", raiz=raiz)
                finally:
                    conn.close()
                accion_oferta = next((r["accion"] for r in registros if r["objeto_id"] == oferta_id), None)
                resultados[nombre] = accion_oferta
                if esperado is not None and accion_oferta != esperado:
                    return _rojo("B0-16", f"{nombre}: engine.d8.ciclo dio {accion_oferta!r}, se esperaba {esperado!r} ({registros})")
                if esperado is None and accion_oferta not in ("SEGUIR", "ESCALAR", "INCONCLUSO"):
                    return _rojo("B0-16", f"{nombre} (intermedio, 95% cobertura + retraso): acción fuera de rango: {accion_oferta!r}")

            # Celda con diagnóstico "CPM alto" (gasto por clic muy alto, pocas compras, tope lejano): NO debe matar.
            # [Nota honesta: decision.reglas.evaluar_celda no implementa un código "CPM alto" explícito
            # (testeo.cpm_alto_factor existe en parametros.yaml pero no está conectado a evaluar_celda/d8;
            # ver "Pedidos" del informe); se demuestra la propiedad -- gasto por clic alto no mata por sí
            # solo, antes de cruzar k_min_matar*CPA_BE con evidencia estadística -- no el código literal.
            raiz_cpm, oferta_cpm, _ = _preparar_oferta_en_test(tmp, slug="cpmalto")
            conn_cpm = _conexion_d8_memoria()
            try:
                conn_cpm.execute("INSERT INTO dim_anuncio VALUES (?,?,?)", ("CPM-ALTO-01", oferta_cpm, None))
                # CPM alto = pocos clics por EUR gastado: 10 EUR de gasto, apenas 2 clics de enlace, 0 compras.
                conn_cpm.execute("INSERT INTO fact_meta_ad_dia VALUES (?,?,?,?,?)",
                                 ("CPM-ALTO-01", "2026-11-10", 1000, 2, "2026-11-24T08:00:00Z"))
                registros_cpm = engine_d8.ciclo(oferta_cpm, conn=conn_cpm, ahora=lambda: _AHORA_D8, par=par, lim=lim,
                                                ejecutor=EjecutorMotor(raiz=raiz_cpm, ahora=lambda: _AHORA_D8), modo="live", raiz=raiz_cpm)
            finally:
                conn_cpm.close()
            accion_cpm = next((r["accion"] for r in registros_cpm if r["objeto_id"] == oferta_cpm), None)
            if accion_cpm == "MATAR":
                return _rojo("B0-16", f"celda de CPM alto (gasto 10 EUR, 2 clics, 0 compras, muy bajo k_min_matar*CPA_BE) dio MATAR: {registros_cpm}")

        return _verde(
            "B0-16",
            f"engine.d8.ciclo real sobre los 3 escenarios de scripts.b0.generador: A_perdedor_severo -> MATAR, "
            f"B_ganador_fuerte -> ESCALAR, C_intermedio_95_retraso (95% cobertura + retraso de atribución de "
            f"36h) -> {resultados['C_intermedio_95_retraso']!r} (dentro de docs/08 §5.3); una celda de CPM alto "
            "(gasto/clic alto, 0 compras, lejos del tope) dio SEGUIR/INCONCLUSO, nunca MATAR.",
        )

    return _con_captura_de_error("B0-16", cuerpo)


def evaluar_b0_19():
    from scripts.b0_e2e import _con_captura_de_error, _rojo, _verde

    def cuerpo():
        import tempfile

        with tempfile.TemporaryDirectory(prefix="b0-motor-d8-19-") as tmp_str:
            tmp = Path(tmp_str)
            raiz, oferta_id, emp = _preparar_oferta_en_test(tmp, slug="senalpausa")
            senal = {
                "schema_version": "1.1.0", "oferta_id": oferta_id, "ts": comun.iso_z(_AHORA_D8), "emitida": True,
                "nivel": "rojo", "motivo": "reembolsos",
                "metricas": {"muestra_suficiente": True, "pagos_ventana": 60, "casos_disputa_efw": 0,
                            "disputas_efw_pct": "0", "reembolsos_pct": "13.3", "ventana_dias": 30},
                "umbrales_usados": {"disputas_alerta_pct": "1.0", "ratio_disputas_pausa": "0.02",
                                    "reembolsos_alerta_pct": "8.0", "reembolsos_pausa_pct": "12.0"},
                "accion_solicitada": "pausar", "consumida_por": None,
            }
            ruta_senal = raiz / "ofertas" / oferta_id / "10-postcompra" / "senal_pausa.json"
            comun.escribir_atomico(ruta_senal, comun.json_canonico(senal))
            conn = _conexion_d8_memoria()
            try:
                par, lim = _parametros_b0_motor(), _limites_b0_motor()
                ejecutor = EjecutorMotor(raiz=raiz, ahora=lambda: _AHORA_D8)
                registros = engine_d8.ciclo(oferta_id, conn=conn, ahora=lambda: _AHORA_D8, par=par, lim=lim,
                                            ejecutor=ejecutor, modo="live", raiz=raiz)
            finally:
                conn.close()
            if not registros or registros[0]["accion"] != "INCONCLUSO" or not registros[0]["ejecutada"]:
                return _rojo("B0-19", f"senal_pausa no produjo INCONCLUSO ejecutada=true: {registros}")
            est = estado.cargar(oferta_id, raiz=raiz)
            if est["fase"] != "pausada":
                return _rojo("B0-19", f"la oferta no quedó 'pausada' tras la señal: fase={est['fase']!r}")
            senal_final = comun.cargar_json(ruta_senal)
            if senal_final.get("consumida_por", {}).get("etapa") != "D8" or not senal_final["consumida_por"].get("decision_id"):
                return _rojo("B0-19", f"senal_pausa.json no quedó con consumida_por relleno: {senal_final}")
            decision_id_1 = senal_final["consumida_por"]["decision_id"]
            # Segunda lectura: la señal ya consumida no se reprocesa (idempotencia de D8, R08).
            conn2 = _conexion_d8_memoria()
            try:
                registros_2 = engine_d8.ciclo(oferta_id, conn=conn2, ahora=lambda: _AHORA_D8, par=par, lim=lim,
                                              ejecutor=EjecutorMotor(raiz=raiz, ahora=lambda: _AHORA_D8), modo="live", raiz=raiz)
            finally:
                conn2.close()
            if registros_2:
                return _rojo("B0-19", f"una segunda lectura de ciclo() reprocesó la señal ya consumida: {registros_2}")
            if comun.cargar_json(ruta_senal)["consumida_por"]["decision_id"] != decision_id_1:
                return _rojo("B0-19", "la segunda lectura cambió el consumida_por ya fijado (no debería)")

        return _verde(
            "B0-19",
            "engine.d8.ciclo real: senal_pausa.json con motivo 'reembolsos' (13,3% sobre reembolsos_pausa_pct "
            "del escenario) produjo accion=INCONCLUSO ejecutada=true, pausó la oferta (fase 'en_test' -> "
            "'pausada') y rellenó consumida_por.decision_id; una segunda lectura no la reprocesa (idempotente).",
        )

    return _con_captura_de_error("B0-19", cuerpo)


def evaluar_b0_22():
    from scripts.b0_e2e import _con_captura_de_error, _rojo, _verde

    def cuerpo():
        import tempfile

        par, lim = _parametros_b0_motor(), _limites_b0_motor()
        with tempfile.TemporaryDirectory(prefix="b0-motor-d8-22-") as tmp_str:
            tmp = Path(tmp_str)

            # --- Escenario 1: cierre por TOPE de gasto sin veredicto (zona ambigua: ni MATAR ni ESCALAR,
            # igual que el patrón de tests/engine/test_d8.py) -> "gasto 0" tras cerrar, ETL/veredicto SIGUEN. ---
            raiz1, oferta_1, _ = _preparar_oferta_en_test(tmp, slug="cierre-tope")
            conn1 = _conexion_d8_memoria()
            try:
                for i in range(20):
                    conn1.execute(
                        "INSERT INTO fact_pedido VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                        (f"cs_b0motor22_{i}", oferta_1, "AD-01", "2026-11-08T10:00:00Z", "pagado", 0, 0, "EUR", 1700, 0, 50),
                    )
                conn1.execute("INSERT INTO dim_anuncio VALUES (?,?,?)", ("AD-01", oferta_1, None))
                conn1.execute("INSERT INTO fact_meta_ad_dia VALUES (?,?,?,?,?)", ("AD-01", "2026-11-05", 30000, 750, None))
                ahora_tope = lambda: datetime(2026, 11, 12, 9, 0, 0, tzinfo=timezone.utc)

                lim_tope_bajo = _limites_b0_motor(gasto_total_test_por_oferta=30000)
                ejecutor = EjecutorMotor(raiz=raiz1, ahora=ahora_tope)
                registros = engine_d8.ciclo(oferta_1, conn=conn1, ahora=ahora_tope, par=par, lim=lim_tope_bajo,
                                            ejecutor=ejecutor, modo="live", raiz=raiz1)
                est_cerrada = estado.cargar(oferta_1, raiz=raiz1)
                if est_cerrada["fase"] != "inconclusa":
                    return _rojo("B0-22", f"el tope de gasto sin veredicto no cerró la fase a 'inconclusa': fase={est_cerrada['fase']!r} ({registros})")

                # Tras "cerrar" (fase ya no en_test): una lectura más de d8.ciclo() no decide ni gasta nada (gasto 0).
                registros_tras_cierre = engine_d8.ciclo(oferta_1, conn=conn1, ahora=ahora_tope, par=par, lim=lim_tope_bajo,
                                                        ejecutor=ejecutor, modo="live", raiz=raiz1)
                if registros_tras_cierre:
                    return _rojo("B0-22", f"d8.ciclo() siguió decidiendo/gastando tras el cierre: {registros_tras_cierre}")

                # El reloj avanza 18 días (misma cohorte, sin gasto nuevo): el ETL/veredicto SIGUEN
                # corriendo (no revientan sobre una oferta cerrada) y, al no haber mejorado la evidencia,
                # el veredicto maduro NO inventa una VALIDADA que la evidencia no sostiene.
                ahora_mas_tarde = lambda: datetime(2026, 11, 30, 9, 0, 0, tzinfo=timezone.utc)
                doc_mas_tarde = engine_d8.veredicto(oferta_1, conn=conn1, ahora=ahora_mas_tarde, par=par, lim=lim, raiz=raiz1)
                if doc_mas_tarde["estado"] == "VALIDADA":
                    return _rojo("B0-22", f"una cohorte ambigua dio VALIDADA tras madurar (no debería, la evidencia no mejoró): {doc_mas_tarde}")
            finally:
                conn1.close()

            # --- Escenario 2: cohorte GANADORA (mismos números que el caso probado de tests/engine/
            # test_d8.py): VALIDADA no aparece antes de la madurez (garantía + margen) y SÍ después; cierre. ---
            raiz2, oferta_2, _ = _preparar_oferta_en_test(tmp, slug="cierre-validada")
            conn2 = _conexion_d8_memoria()
            try:
                for i in range(5):
                    conn2.execute(
                        "INSERT INTO fact_pedido VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                        (f"cs_b0motor22_ok_{i}", oferta_2, "AD-01", f"2026-10-0{i + 1}T10:00:00Z", "pagado", 0, 0, "EUR", 2700, 0, 50),
                    )
                conn2.execute("INSERT INTO dim_anuncio VALUES (?,?,?)", ("AD-01", oferta_2, None))
                for i in range(5):
                    conn2.execute("INSERT INTO fact_meta_ad_dia VALUES (?,?,?,?,?)", ("AD-01", f"2026-10-0{i + 1}", 200, 15, None))

                ahora_temprano = lambda: datetime(2026, 10, 10, 9, 0, 0, tzinfo=timezone.utc)  # antes de madurar (último pedido + 21 d = 2026-10-26)
                doc_temprano = engine_d8.veredicto(oferta_2, conn=conn2, ahora=ahora_temprano, par=par, lim=lim, raiz=raiz2)
                if doc_temprano["estado"] == "VALIDADA":
                    return _rojo("B0-22", f"veredicto dio VALIDADA ANTES de madurar la cohorte ganadora: {doc_temprano}")

                ahora_maduro = lambda: datetime(2026, 11, 20, 9, 0, 0, tzinfo=timezone.utc)  # bien después de madurar
                doc_maduro = engine_d8.veredicto(oferta_2, conn=conn2, ahora=ahora_maduro, par=par, lim=lim, raiz=raiz2)
                if doc_maduro["estado"] != "VALIDADA":
                    return _rojo("B0-22", f"tras madurar, la cohorte ganadora no dio VALIDADA: {doc_maduro}")

                cierre = engine_cerrar.cerrar_oferta(oferta_2, raiz=raiz2, ahora=ahora_maduro)
                est_final = estado.cargar(oferta_2, raiz=raiz2)
                if est_final["fase"] != "validada":
                    return _rojo("B0-22", f"engine.cerrar no movió la fase a 'validada' con el veredicto maduro: {cierre}")
            finally:
                conn2.close()

        return _verde(
            "B0-22",
            "engine.d8.ciclo real: al agotarse el tope de gasto de una celda ambigua sin veredicto final, "
            "cerró la fase a 'inconclusa' (gasto 0 desde ahí: una lectura posterior de ciclo() no decide ni "
            "pausa nada más); el ETL/veredicto SIGUIERON corriendo sobre la oferta cerrada sin inventar una "
            "VALIDADA que la evidencia no sostiene. Por separado, con una cohorte ganadora (misma forma que "
            "tests/engine/test_d8.py), engine.d8.veredicto NO dio VALIDADA antes de madurar (garantía 14 d + "
            "margen 7 d) y SÍ después; engine.cerrar.cerrar_oferta cerró la fase a 'validada' sobre ese "
            "veredicto maduro.",
        )

    return _con_captura_de_error("B0-22", cuerpo)
