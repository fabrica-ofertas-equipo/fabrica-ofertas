"""Hito B0 «caminante» (ola 2, I1b): recorrido de punta a punta sobre ``ofertas/_ejemplo/``.

Qué hace HOY (ola 2, parte que no depende del motor de estados)
-----------------------------------------------------------------
Copia ``ofertas/_ejemplo/`` a una raíz temporal (nunca toca el ``empresa/`` real, comprobado por
hash: criterio B0-04) y evalúa los 25 criterios de docs/06 §6.2 llamando a los módulos REALES de
cada componente (``agentes``, ``tracking`` por ``node`` subproceso, ``postcompra`` incl. el Worker
``fulfill``, ``landing``, ``meta``, ``infra/workers/watchdog`` por ``node``, ``datos`` con un
generador determinista propio de 14 días), cada uno en ``scripts/b0/<componente>.py``. Nunca
simula con un bloque que finja pasar: donde el componente real no alcanza a cubrir toda la cláusula
del criterio (porque depende de ``engine.estado``/``engine.orq``/``engine.d8``, que **B1a/B1b**
están escribiendo activamente esta misma noche y que esta sesión tiene prohibido tocar o depender
de ellos) el criterio queda **pendiente** con el motivo exacto de qué cláusula sí se cubrió y cuál
falta (ver ``_MOTIVOS_PENDIENTES`` y las «Decisiones»/«Pedidos» del informe final de la sesión).

Reutiliza ``tests/engine/apoyo.py`` (B1 lo dejó explícitamente «reutilizable por I1 para B0»): el
fixture ``tests/fixtures/engine/empresa_prueba/`` con límites sellados y firmados con una clave
Ed25519 de prueba, generada al vuelo con ``ssh-keygen`` (nunca una clave real).

CLI
---
::

    .venv/bin/python -m scripts.b0_e2e                  # resumen humano
    .venv/bin/python -m scripts.b0_e2e --criterios       # tabla de los 25 con VERDE/ROJO/pendiente
    .venv/bin/python -m scripts.b0_e2e --json            # una línea JSON (convenciones §9)

Nunca usa ``--live`` ni red; siempre corre como si ``FABRICA_ENTORNO=prueba`` (nunca toca el
``os.environ`` real: cada paso recibe su propio diccionario ``env``). Salida: 0 si ningún criterio
quedó en ROJO (los PENDIENTES no cuentan como error, son el estado esperado de este esqueleto);
3 si algún criterio demostrable falló de verdad.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from dataclasses import asdict, dataclass
from datetime import timedelta
from pathlib import Path
from typing import Callable
from unittest import mock

from engine import comun
from engine.errores import ErrorFabrica

from scripts.b0 import agentes as b0_agentes
from scripts.b0 import datos as b0_datos
from scripts.b0 import infra as b0_infra
from scripts.b0 import landing as b0_landing
from scripts.b0 import meta as b0_meta
from scripts.b0 import motor as b0_motor
from scripts.b0 import postcompra as b0_postcompra
from scripts.b0 import tracking as b0_tracking

__all__ = ["CRITERIOS", "Criterio", "ejecutar", "main"]

RAIZ_REAL = comun.raiz()

# Orden e identificador de los 25 criterios de docs/06 §6.2 (tabla de aceptación del hito B0).
CRITERIOS: dict[str, str] = {
    "B0-01": "test_all.sh y lint.sh salen 0; ninguna prueba abre un socket",
    "B0-02": "validar_esquemas 0 con _ejemplo re-sellado; factibilidad reproduce economia.json",
    "B0-03": "límites null→5; PAUSA→4; estado 7h→4; modo≠vivo→4; --live fuera de producción→4; dry-run→0 y árbol intacto",
    "B0-04": "el empresa/ real queda intacto (hash antes/después)",
    "B0-05": "M1→D7 aprobado con gates H firmados; FAIL→ronda 2→PASS; 2 rondas fallidas→escalado",
    "B0-06": "etapa ejecutada dos veces→mismos hashes y «reutilizado»",
    "B0-07": "cambiar oferta.json vuelve obsoletas D4-D7 y pausa la campaña activa",
    "B0-08": "10 casos del runner; sonda de hooks 100% exit 2; entorno sin claves",
    "B0-09": "sesión con metadata completa; firma falsa→400; duplicado→una entrega; event_id correcto en CAPI",
    "B0-10": "pago simulado→entregado, correo en outbox, enlace con vencimiento y cuota; sin reenvío",
    "B0-11": "landing.validar pasa el ejemplo y falla el 100% de las 12 mutaciones (8 base + 4 complementarias)",
    "B0-12": "meta.crear idempotente; cada P rojo del preflight detectado",
    "B0-13": "meta.activar: 5 negativos, 1 positivo, 7 pasos reales por separado; «falla el segundo POST»",
    "B0-14": "latido detenido→pausa simulada y alerta por ambos canales; watchdog sin ruta de activación",
    "B0-15": "ETL de 14 días dos veces→tablas idénticas; cobertura≥mínimo; Stripe↔ledger=0",
    "B0-16": "tres escenarios (incl. 95%+retraso) con tasas dentro de docs/08 §5.3; «CPM alto» no mata",
    "B0-17": "dashboard = cifras de la base, escapado, cifras viejas tachadas",
    "B0-18": "verificar_cadena sin roturas; costos = suma de corridas; 0 datos personales en registros",
    "B0-19": "senal_pausa por reembolsos→D8 pausa, consumida_por",
    "B0-20": "disputa abierta rechaza reembolso automático; evidencia; dos disputas→pausa",
    "B0-21": "anuncio DISAPPROVED→pausa, registro, pedido a D6, sin recreación idéntica",
    "B0-22": "tras cerrar la campaña: gasto 0, ETL/veredicto siguen, VALIDADA no antes de espera_madurez.hasta",
    "B0-23": "orq ingresar ≡ ejecutar --modo fixture; archivo fuera de ruta→3",
    "B0-24": "parsers de datos y meta pasan con fixtures de forma real capturadas",
    "B0-25": "orden firmada por POST /ordenes ≡ orq firmar local; nonce repetido rechazado",
}
ORDEN_CRITERIOS: tuple[str, ...] = tuple(f"B0-{n:02d}" for n in range(1, 26))


@dataclass(frozen=True)
class Criterio:
    """Resultado de evaluar un criterio de B0: ``estado`` en {"verde", "rojo", "pendiente"}."""

    id: str
    nombre: str
    estado: str
    motivo: str

    def a_dict(self) -> dict[str, str]:
        return asdict(self)


def _verde(id_: str, motivo: str) -> Criterio:
    return Criterio(id_, CRITERIOS[id_], "verde", motivo)


def _rojo(id_: str, motivo: str) -> Criterio:
    return Criterio(id_, CRITERIOS[id_], "rojo", motivo)


def _pendiente(id_: str, motivo: str) -> Criterio:
    return Criterio(id_, CRITERIOS[id_], "pendiente", f"pendiente: {motivo}")


def _con_captura_de_error(id_: str, cuerpo: Callable[[], Criterio]) -> Criterio:
    """Corre ``cuerpo`` y, ante cualquier excepción no prevista, lo informa como ROJO (nunca revienta la corrida)."""
    try:
        return cuerpo()
    except Exception as exc:  # noqa: BLE001 - frontera del escenario: un error inesperado es un hallazgo, no un crash
        return _rojo(id_, f"error inesperado evaluando el criterio: {type(exc).__name__}: {exc}")


# --------------------------------------------------------------------------------------------------------------------
# B0-02: validar_esquemas + engine.factibilidad sobre la COPIA temporal de ofertas/_ejemplo
# --------------------------------------------------------------------------------------------------------------------
def _eval_b0_02(dir_ejemplo: Path) -> Criterio:
    def cuerpo() -> Criterio:
        from scripts.validar_esquemas import DIR_EJEMPLOS, CLAVE_DE_PRUEBA, cargar_json, cargar_yaml, limites_de_prueba, validar_oferta
        from engine import factibilidad

        lim = limites_de_prueba()
        par = cargar_yaml(DIR_EJEMPLOS / "parametros.valido.yaml")
        aut = cargar_yaml(DIR_EJEMPLOS / "autonomia.valido.yaml")
        informe = validar_oferta(dir_ejemplo, limites=lim, parametros=par, autonomia=aut, clave_firma=CLAVE_DE_PRUEBA)
        if informe.codigo_salida != 0:
            primeros = "; ".join(str(h) for h in informe.errores[:3])
            return _rojo("B0-02", f"validar_oferta código {informe.codigo_salida} ({len(informe.errores)} error(es)): {primeros}")
        economia = cargar_json(dir_ejemplo / "03-oferta" / "economia.json")
        diferencias = factibilidad.verificar(economia, par, lim)
        if diferencias:
            return _rojo("B0-02", f"engine.factibilidad.verificar encontró {len(diferencias)} diferencia(s): {diferencias[0]}")
        return _verde("B0-02", f"validar_oferta 0 ({informe.verificados} verificaciones) y economia.json reproducible por engine.factibilidad.verificar")

    return _con_captura_de_error("B0-02", cuerpo)


# --------------------------------------------------------------------------------------------------------------------
# B0-03: los 7 pasos de engine.guard.comprobar_live (5 negativos + 1 positivo, fixture B1 ya construido)
# --------------------------------------------------------------------------------------------------------------------
def _eval_b0_03(tmp: Path) -> Criterio:
    def cuerpo() -> Criterio:
        from tests.engine import apoyo
        from engine import guard
        from engine import limites as motor_limites
        from engine.transporte import TransporteFixture

        casos: list[tuple[str, bool, str]] = []

        # 1) límites en null (la plantilla de B1) -> ErrorLimite (5): sin dato de límites no se gasta ni se activa.
        lim_nulo = motor_limites.cargar_limites(apoyo.FIXTURES / "limites_plantilla.yaml")
        try:
            motor_limites.exigir_operacion(lim_nulo, "gastar")
            casos.append(("limites_en_null", False, "no lanzó ErrorLimite"))
        except ErrorFabrica as exc:
            casos.append(("limites_en_null", exc.codigo_salida == 5, f"código {exc.codigo_salida}"))

        # 2) --live fuera de producción -> ErrorBloqueado (4), paso «entorno».
        try:
            guard.comprobar_live("gastar", simulacion=False, entorno="desarrollo", env={}, raiz=tmp)
            casos.append(("live_fuera_de_produccion", False, "no lanzó ErrorBloqueado"))
        except ErrorFabrica as exc:
            casos.append(("live_fuera_de_produccion", exc.codigo_salida == 4, f"código {exc.codigo_salida}"))

        # 3) empresa/PAUSA presente -> ErrorBloqueado (4), paso «pausa».
        d_pausa = tmp / "caso_pausa"
        emp = apoyo.crear_empresa(d_pausa, modo_infra="vivo", entorno="produccion")
        (d_pausa / "empresa" / "PAUSA").write_text("", encoding="utf-8")
        try:
            guard.comprobar_live("gastar", oferta_id=apoyo.OFERTA, monto_minor=1000, moneda="EUR",
                                 ahora=emp.reloj, env=emp.env, raiz=emp.raiz)
            casos.append(("pausa_presente", False, "no lanzó ErrorBloqueado"))
        except ErrorFabrica as exc:
            casos.append(("pausa_presente", exc.codigo_salida == 4, f"código {exc.codigo_salida}"))

        # 4) estado.json de infra vencido (generado hace 7 h, válido_hasta en el pasado) -> ErrorBloqueado (4).
        d_vieja = tmp / "caso_infra_vencida"
        emp2 = apoyo.crear_empresa(d_vieja, modo_infra="vivo", entorno="produccion")
        emp2.reescribir_estado(
            generado_en=comun.iso_z(apoyo.AHORA_BASE - timedelta(hours=7)),
            valido_hasta=comun.iso_z(apoyo.AHORA_BASE - timedelta(hours=1)),
        )
        try:
            guard.comprobar_live("gastar", oferta_id=apoyo.OFERTA, monto_minor=1000, moneda="EUR",
                                 ahora=emp2.reloj, env=emp2.env, raiz=emp2.raiz)
            casos.append(("infra_vencida", False, "no lanzó ErrorBloqueado"))
        except ErrorFabrica as exc:
            casos.append(("infra_vencida", exc.codigo_salida == 4, f"código {exc.codigo_salida}"))

        # 5) infra_estado.modo != vivo (es «prueba») fuera de simulación -> ErrorBloqueado (4).
        d_modo = tmp / "caso_modo_no_vivo"
        emp3 = apoyo.crear_empresa(d_modo, modo_infra="prueba", entorno="produccion")
        try:
            guard.comprobar_live("gastar", oferta_id=apoyo.OFERTA, monto_minor=1000, moneda="EUR",
                                 ahora=emp3.reloj, env=emp3.env, raiz=emp3.raiz)
            casos.append(("modo_no_vivo", False, "no lanzó ErrorBloqueado"))
        except ErrorFabrica as exc:
            casos.append(("modo_no_vivo", exc.codigo_salida == 4, f"código {exc.codigo_salida}"))

        # 6) positivo: modo fixture (simulacion=True), árbol intacto antes/después.
        d_ok = tmp / "caso_fixture_ok"
        emp4 = apoyo.crear_empresa(d_ok, modo_infra="prueba", entorno="prueba")
        hash_antes = comun.hash_directorio(d_ok)
        ctx = guard.comprobar_live(
            "gastar", oferta_id=apoyo.OFERTA, monto_minor=1000, moneda="EUR", ahora=emp4.reloj,
            simulacion=True, transporte=TransporteFixture(), entorno="prueba", env=emp4.env, raiz=emp4.raiz,
        )
        hash_despues = comun.hash_directorio(d_ok)
        casos.append(("dry_run_positivo", ctx.modo == "fixture" and hash_antes == hash_despues,
                      f"modo={ctx.modo}, árbol intacto={hash_antes == hash_despues}"))

        fallos = [(n, m) for n, ok, m in casos if not ok]
        if fallos:
            return _rojo("B0-03", "; ".join(f"{n}: {m}" for n, m in fallos))
        return _verde("B0-03", "6/6 casos sobre engine.guard.comprobar_live (5 negativos + 1 positivo fixture), "
                               "con tests/fixtures/engine/empresa_prueba vía tests/engine/apoyo.crear_empresa")

    return _con_captura_de_error("B0-03", cuerpo)


# --------------------------------------------------------------------------------------------------------------------
# B0-04: empresa/ real intacto
# --------------------------------------------------------------------------------------------------------------------
def _eval_b0_04(hash_antes: str | None, hash_despues: str | None) -> Criterio:
    if hash_antes is None:
        return _rojo("B0-04", "no se pudo calcular el hash de empresa/ real antes de correr (¿no existe la carpeta?)")
    if hash_antes != hash_despues:
        return _rojo("B0-04", "el hash de empresa/ real cambió durante la corrida de b0_e2e: algo escribió fuera de la raíz temporal")
    return _verde("B0-04", f"empresa/ real sin cambios (hash {hash_antes[:19]}…)")


# --------------------------------------------------------------------------------------------------------------------
# B0-18: cadena del registro y suma de costos (núcleo real de engine.registro)
# --------------------------------------------------------------------------------------------------------------------
def _eval_b0_18(tmp: Path) -> Criterio:
    def cuerpo() -> Criterio:
        from tests.engine import apoyo
        from engine import registro as motor_registro

        carpeta = tmp / "registro_prueba"
        ruta_registro = carpeta / "registro.jsonl"
        ruta_costos = carpeta / "costos.jsonl"
        reloj = lambda: apoyo.AHORA_BASE
        base_evento = {
            "ejecucion_id": "b0-escenario-01", "oferta_id": apoyo.OFERTA, "etapa": "O0", "agente": "motor:b0",
            "herramienta": "scripts.b0_e2e", "entrada_resumen": "paso de demostración del escenario B0 (sin datos personales)",
            "resultado": {"estado": "ok", "codigo": 0}, "costo_estimado": {"monto": 0, "moneda": "EUR"}, "modo": "dry_run",
        }
        motor_registro.registrar({**base_evento, "evento": "accion"}, ruta=ruta_registro, ahora=reloj)
        motor_registro.registrar({**base_evento, "evento": "llamada_herramienta"}, ruta=ruta_registro, ahora=reloj)
        problemas = motor_registro.verificar_cadena(ruta_registro)
        if problemas:
            return _rojo("B0-18", f"verificar_cadena encontró {len(problemas)} problema(s): {problemas[0]}")

        c1 = motor_registro.costo(apoyo.OFERTA, "ia", 500, "EUR", ruta=ruta_costos, ahora=reloj,
                                  etapa="O0", ejecucion_id="b0-escenario-01", concepto="demostracion-b0")
        c2 = motor_registro.costo(apoyo.OFERTA, "ia", 300, "EUR", ruta=ruta_costos, ahora=reloj,
                                  etapa="O0", ejecucion_id="b0-escenario-01", concepto="demostracion-b0")
        total = sum(c["monto"]["monto"] for c in comun.leer_jsonl(ruta_costos))
        esperado = c1["monto"]["monto"] + c2["monto"]["monto"]
        if total != esperado:
            return _rojo("B0-18", f"la suma de costos.jsonl ({total}) no coincide con la suma de las corridas ({esperado})")
        return _verde("B0-18", "cadena del registro sana tras 2 eventos; costos.jsonl = suma de las 2 corridas (800 céntimos EUR)")

    return _con_captura_de_error("B0-18", cuerpo)


# --------------------------------------------------------------------------------------------------------------------
# B0-01: ninguna prueba del escenario abre un socket (se evalúa al final, sobre el resto de los resultados)
# --------------------------------------------------------------------------------------------------------------------
def _eval_b0_01(resto: dict[str, Criterio]) -> Criterio:
    # Solo un criterio ROJO cuyo motivo mencione "socket" es señal real de un intento bloqueado; un
    # criterio VERDE o PENDIENTE puede mencionar la palabra en prosa (p. ej. "llamada WSGI sin
    # socket") sin que eso sea un hallazgo (I1a: antes esto daba un falso positivo en B0-25).
    sospechosos = [c.id for c in resto.values() if c.estado == "rojo" and "socket" in c.motivo.lower()]
    if sospechosos:
        return _rojo("B0-01", f"se detectó un intento de abrir un socket durante: {', '.join(sospechosos)}")
    return _verde(
        "B0-01",
        "los criterios B0-02, B0-03, B0-04, B0-08…B0-15 y B0-18…B0-21 corrieron completos con "
        "socket.socket bloqueado en ESTE proceso Python (AssertionError si algo intenta abrir red) y "
        "ninguno lo disparó; los subprocesos `node` que lanzan agentes/tracking/infra/postcompra no "
        "abren un socket desde Python (exec de un proceso nuevo) y sus arneses .mjs nunca llaman a un "
        "host real (fetch reemplazado o transporte/almacén en memoria inyectado). test_all.sh y lint.sh "
        "COMPLETOS (todo el árbol, todas las sesiones) solo los confirma la propia CI al correrlos (no "
        "se puede repetir aquí sin recursión).",
    )


# --------------------------------------------------------------------------------------------------------------------
# Los criterios que de verdad quedan pendientes esta noche (ver scripts/b0/motor.py para B0-05, 06, 07,
# 16, 19, 22, 23, 25, que I1a ya cerró sobre engine.estado/orq/d8/cerrar reales).
# --------------------------------------------------------------------------------------------------------------------
_MOTIVOS_PENDIENTES: dict[str, str] = {
    "B0-17": "dashboard/ lo reconstruye otra sesión (panel con sidebar, API propia); el criterio se re-mapea a su "
             "contrato cuando termine.",
    "B0-24": "no hay capturas reales de Meta/Stripe (tests/fixtures/{meta,datos}/reales/): exigen la sesión Code "
             "con el MCP de Meta y el sandbox de Stripe, y esta noche no hay red ni credenciales; no se marca "
             "verde con fixtures sintéticos.",
}


# --------------------------------------------------------------------------------------------------------------------
# Orquestación completa
# --------------------------------------------------------------------------------------------------------------------
def ejecutar(raiz_tmp: Path | None = None) -> dict[str, Criterio]:
    """Corre el escenario de B0 (ola 2) sobre una raíz temporal y devuelve los 25 resultados, en orden.

    ``raiz_tmp``: si se pasa, se usa (y se crea) en vez de una carpeta temporal efímera; solo pensado
    para que las pruebas de ``tests/integracion/`` reutilicen la misma corrida sin pagarla 25 veces.
    Nunca toca ``os.environ`` ni la raíz real del repositorio salvo para LEER ``empresa/`` (B0-04).
    """
    ruta_empresa_real = RAIZ_REAL / "empresa"
    hash_antes = comun.hash_directorio(ruta_empresa_real) if ruta_empresa_real.is_dir() else None

    def _correr(tmp: Path) -> dict[str, Criterio]:
        tmp_ofertas = tmp / "ofertas" / "_ejemplo"
        shutil.copytree(RAIZ_REAL / "ofertas" / "_ejemplo", tmp_ofertas)

        resultados: dict[str, Criterio] = {}
        # El bloqueo de socket.socket cubre ESTE proceso Python; los módulos de scripts/b0/ que
        # lanzan `node` por subproceso (agentes/tracking/infra/postcompra) no abren un socket desde
        # aquí (exec de un proceso nuevo, no socket.socket) y sus arneses .mjs nunca llaman a un
        # host real (fetch global reemplazado o transporte/almacén en memoria inyectado).
        parche = mock.patch("socket.socket", side_effect=AssertionError("b0_e2e: socket.socket bloqueado (escenario sin red)"))
        parche.start()
        try:
            resultados["B0-02"] = _eval_b0_02(tmp_ofertas)
            resultados["B0-03"] = _eval_b0_03(tmp)
            resultados["B0-18"] = _eval_b0_18(tmp)
            resultados["B0-05"] = b0_motor.evaluar_b0_05(tmp)
            resultados["B0-06"] = b0_motor.evaluar_b0_06(tmp)
            resultados["B0-07"] = b0_motor.evaluar_b0_07(tmp)
            resultados["B0-23"] = b0_motor.evaluar_b0_23(tmp)
            resultados["B0-25"] = b0_motor.evaluar_b0_25(tmp)
            resultados["B0-08"] = b0_agentes.evaluar_b0_08()
            resultados["B0-09"] = b0_tracking.evaluar_b0_09()
            resultados["B0-10"] = b0_postcompra.evaluar_b0_10()
            resultados["B0-11"] = b0_landing.evaluar_b0_11()
            resultados["B0-12"] = b0_meta.evaluar_b0_12()
            resultados["B0-13"] = b0_meta.evaluar_b0_13()
            resultados["B0-14"] = b0_infra.evaluar_b0_14()
            resultados["B0-15"] = b0_datos.evaluar_b0_15()
            resultados["B0-16"] = b0_motor.evaluar_b0_16()
            resultados["B0-19"] = b0_motor.evaluar_b0_19()
            resultados["B0-20"] = b0_postcompra.evaluar_b0_20()
            resultados["B0-21"] = b0_meta.evaluar_b0_21()
            resultados["B0-22"] = b0_motor.evaluar_b0_22()
        finally:
            parche.stop()

        hash_despues = comun.hash_directorio(ruta_empresa_real) if ruta_empresa_real.is_dir() else None
        resultados["B0-04"] = _eval_b0_04(hash_antes, hash_despues)
        resultados["B0-01"] = _eval_b0_01(resultados)
        for id_, motivo in _MOTIVOS_PENDIENTES.items():
            resultados[id_] = _pendiente(id_, motivo)
        return resultados

    if raiz_tmp is not None:
        raiz_tmp.mkdir(parents=True, exist_ok=True)
        resultados = _correr(raiz_tmp)
    else:
        with tempfile.TemporaryDirectory(prefix="fabrica-b0-") as tmp_str:
            resultados = _correr(Path(tmp_str))

    return {id_: resultados[id_] for id_ in ORDEN_CRITERIOS}


# --------------------------------------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------------------------------------
def _tabla(resultados: dict[str, Criterio]) -> str:
    lineas = [f"{'ID':6} {'ESTADO':10} MOTIVO"]
    for id_, c in resultados.items():
        estado = c.estado.upper() if c.estado != "pendiente" else "pendiente"
        lineas.append(f"{id_:6} {estado:10} {c.motivo}")
    verdes = sum(1 for c in resultados.values() if c.estado == "verde")
    rojos = sum(1 for c in resultados.values() if c.estado == "rojo")
    pendientes = sum(1 for c in resultados.values() if c.estado == "pendiente")
    lineas.append(f"\nTOTAL {len(resultados)}: {verdes} verde(s), {rojos} rojo(s), {pendientes} pendiente(s)")
    return "\n".join(lineas)


def _parsear_argumentos(argv: list[str] | None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        prog="python -m scripts.b0_e2e",
        description="Esqueleto del hito B0: recorre ofertas/_ejemplo en una raíz temporal y evalúa los 25 criterios.",
    )
    ap.add_argument("--criterios", action="store_true", help="imprime la tabla de los 25 criterios con VERDE/ROJO/pendiente")
    ap.add_argument("--json", action="store_true", help="imprime una única línea JSON (convenciones §9)")
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    def _principal() -> int:
        args = _parsear_argumentos(argv)
        resultados = ejecutar()
        rojos = [c for c in resultados.values() if c.estado == "rojo"]
        if args.json:
            datos = {"criterios": [c.a_dict() for c in resultados.values()]}
            avisos = [f"{c.id}: {c.motivo}" for c in rojos]
            print(json.dumps(
                {"ok": not rojos, "modo": "fixture", "codigo": 0 if not rojos else 3, "datos": datos, "avisos": avisos},
                sort_keys=True, ensure_ascii=False, separators=(",", ":"),
            ))
        elif args.criterios:
            print(_tabla(resultados))
        else:
            verdes = sum(1 for c in resultados.values() if c.estado == "verde")
            pendientes = sum(1 for c in resultados.values() if c.estado == "pendiente")
            print(f"B0 (ola 2): {verdes} verde(s), {len(rojos)} rojo(s), {pendientes} pendiente(s) de 25. "
                  f"Usa --criterios para el detalle.")
        return 0 if not rojos else 3

    return comun.ejecutar_cli(_principal)


if __name__ == "__main__":
    sys.exit(main())
