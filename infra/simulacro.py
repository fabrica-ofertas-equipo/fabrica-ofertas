"""``infra.simulacro``: harness de las 12 pruebas de aceptación A-1…A-12 (docs/07-puesta-en-marcha.md
§9.3, tabla de kill switch) contra fixtures, en serie.

Honesto por diseño: cada prueba devuelve ``VERDE`` solo si el código REAL de este repositorio (nunca
una simulación propia del harness) se comportó como exige la tabla; ``ROJO`` si se comportó mal;
``PENDIENTE`` con un motivo explícito si la pieza que la prueba necesita no existe todavía en este
entorno de construcción (credenciales reales de Meta, el canal de alertas del Worker ``watchdog``,
el cron real de Cloudflare, el MCP de la Biblioteca de Anuncios). Nunca hay verde por omisión.

Qué SÍ ejercita de verdad (sin red, con :class:`engine.transporte.TransporteFixture`):
``engine.guard.comprobar_live`` (A-1, A-2), ``meta.pausar`` (A-3, A-4), ``meta.cliente.ClienteMeta``
ante un rechazo por permisos (A-8), ``infra.latido.evaluar_vencimiento`` + ``infra.preflight.sonda_c09_watchdog``
(A-10) y ``engine.orq.reanudar`` (A-12). A-5 es parcial: la decisión de pausar y la pausa de la
campaña vía fixture SÍ se ejercitan; el envío de alertas por los dos canales (lo hace el Worker
``watchdog`` en JavaScript, ``alertarDosCanales``) no tiene puente desde este harness de Python y
queda ``PENDIENTE``. A-6 (sin ruta de activación), A-7 (permiso real sobre ``spend_cap``), A-9
(publicar por MCP) y A-11 (cron real de Cloudflare) quedan ``PENDIENTE``: lo primero ya lo prueba
``node --test infra/workers/watchdog/test/`` (no se reimplementa aquí); el resto exige credenciales
o plataformas reales fuera del alcance de esta construcción nocturna (ola 3, docs/06 §7).

CLI::

    python -m infra.simulacro ejecutar [--raiz RUTA] [--ahora ISO] [--json]

Salida (convenciones §8): 0 ninguna prueba en ROJO (puede haber PENDIENTE) · 1 alguna prueba en ROJO.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from engine import comun, estado as motor_estado, guard
from engine import orq as motor_orq
from engine.errores import ErrorFabrica
from engine.transporte import TransporteFixture

__all__ = [
    "ESTADOS", "ResultadoAceptacion", "InformeSimulacro", "ejecutar_simulacro", "main",
]

ESTADOS = ("VERDE", "ROJO", "PENDIENTE")
_TOKEN_FICTICIO = "token-ficticio-no-real"  # no empieza con EAA/sk_/rk_/whsec_/cfut_: pasa el paso 6 en simulación


@dataclass(frozen=True)
class ResultadoAceptacion:
    """Resultado de UNA prueba A-n: ``estado`` ∈ :data:`ESTADOS`, motivo legible y evidencia estructurada."""

    id: str
    estado: str
    motivo: str
    evidencia: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class InformeSimulacro:
    generado_en: str
    resultados: tuple[ResultadoAceptacion, ...]

    @property
    def resumen(self) -> dict[str, int]:
        resumen = {e: 0 for e in ESTADOS}
        for r in self.resultados:
            resumen[r.estado] += 1
        return resumen

    @property
    def ok(self) -> bool:
        """Ninguna prueba en ROJO (PENDIENTE no bloquea el informe: es honestidad, no un fallo de código)."""
        return all(r.estado != "ROJO" for r in self.resultados)


@dataclass(frozen=True)
class _Contexto:
    raiz: Path
    env: dict[str, str]
    ahora: Callable[[], datetime]


def _env_simulacion(raiz: Path) -> dict[str, str]:
    """Entorno mínimo para ``comprobar_live(simulacion=True)``: entorno de prueba, credenciales ficticias."""
    return {
        "FABRICA_ENTORNO": "prueba", "FABRICA_RAIZ": str(raiz),
        "META_TOKEN_OPERADOR": _TOKEN_FICTICIO, "META_AD_ACCOUNT_ID": "act_100000000000001",
        "META_APP_SECRET": "app-secret-ficticio",
    }


def _resultado_de_excepcion(id_: str, exc: BaseException, *, esperado: str) -> ResultadoAceptacion:
    """Una excepción NO prevista por la prueba es ROJO (nunca se traga en silencio)."""
    return ResultadoAceptacion(id_, "ROJO", f"se esperaba {esperado}; ocurrió {type(exc).__name__}: {exc}", {})


# ----------------------------------------------------------------------------------------------
# A-1 / A-2: engine.guard.comprobar_live ante PAUSA puesta y quitada
# ----------------------------------------------------------------------------------------------
def _prueba_a1(ctx: _Contexto) -> ResultadoAceptacion:
    base = ctx.raiz / "A-1"
    motor_estado.fijar_pausa("simulacro A-1", raiz=base, ahora=ctx.ahora)
    try:
        transporte = TransporteFixture()
        try:
            guard.comprobar_live("gastar", oferta_id="OF-202611-01", monto_minor=100, moneda="EUR",
                                 ahora=ctx.ahora, simulacion=True, transporte=transporte,
                                 env=_env_simulacion(base), raiz=base)
        except ErrorFabrica as exc:
            paso = exc.detalle.get("paso")
            lectura_ok = guard.hay_pausa(base) is True  # la LECTURA sigue funcionando con PAUSA puesta
            if paso == "pausa" and lectura_ok:
                return ResultadoAceptacion("A-1", "VERDE",
                                           "con empresa/PAUSA puesto, comprobar_live(--live simulado) se detiene "
                                           "exactamente en el paso «pausa»; la lectura (hay_pausa) sigue funcionando",
                                           {"paso": paso})
            return ResultadoAceptacion("A-1", "ROJO", f"se bloqueó en el paso {paso!r}, no en «pausa»", {"paso": paso})
        return ResultadoAceptacion("A-1", "ROJO", "con empresa/PAUSA puesto, --live simulado NO se bloqueó", {})
    except Exception as exc:  # noqa: BLE001 - ver docstring del módulo: nunca se traga en silencio
        return _resultado_de_excepcion("A-1", exc, esperado="bloqueo en el paso «pausa»")
    finally:
        motor_estado.quitar_pausa(raiz=base, ahora=ctx.ahora)


def _prueba_a2(ctx: _Contexto) -> ResultadoAceptacion:
    base = ctx.raiz / "A-2"
    motor_estado.fijar_pausa("simulacro A-2", raiz=base, ahora=ctx.ahora)
    motor_estado.quitar_pausa(raiz=base, ahora=ctx.ahora)  # "borrar PAUSA" (docs/06 §5: borrar el archivo no reactiva nada)
    try:
        if guard.hay_pausa(base):
            return ResultadoAceptacion("A-2", "ROJO", "hay_pausa sigue True tras quitar_pausa", {})
        transporte = TransporteFixture()
        try:
            guard.comprobar_live("gastar", oferta_id="OF-202611-01", monto_minor=100, moneda="EUR",
                                 ahora=ctx.ahora, simulacion=True, transporte=transporte,
                                 env=_env_simulacion(base), raiz=base)
        except ErrorFabrica as exc:
            paso = exc.detalle.get("paso")
            if paso != "pausa":
                return ResultadoAceptacion("A-2", "VERDE",
                                           f"sin PAUSA, comprobar_live avanza más allá del paso «pausa» pero sigue "
                                           f"bloqueado en {paso!r} (sin infraestructura/aprobación nada se reactiva "
                                           "solo; el motor exige la orden humana de orq reanudar, probada en A-12)",
                                           {"paso": paso})
            return ResultadoAceptacion("A-2", "ROJO", "sin PAUSA, sigue bloqueado en «pausa» (no debería)", {"paso": paso})
        return ResultadoAceptacion("A-2", "ROJO", "sin PAUSA ni infraestructura, --live simulado pasó entero: no debería", {})
    except Exception as exc:  # noqa: BLE001
        return _resultado_de_excepcion("A-2", exc, esperado="bloqueo en un paso posterior a «pausa»")


# ----------------------------------------------------------------------------------------------
# A-3 / A-4: meta.pausar sobre un TransporteFixture (capa 2 del kill switch)
# ----------------------------------------------------------------------------------------------
def _cliente_meta_fixture(transporte: TransporteFixture):
    from meta.cliente import ClienteMeta
    return ClienteMeta(transporte=transporte, token="token-op-ficticio", app_secret="app-secret-ficticio",
                       segundos_min_entre_ediciones=0, max_cambios_presupuesto_por_hora=100,
                       base_url="https://meta.fixture.ejemplo", version="v0")


def _fixture_dos_activas_una_pausada() -> TransporteFixture:
    base = "https://meta.fixture.ejemplo/v0"
    return TransporteFixture([
        {"metodo": "GET", "url_prefijo": f"{base}/act_100000000000001/campaigns", "veces": 1,
         "cuerpo": {"data": [{"id": "c1", "effective_status": "ACTIVE"}, {"id": "c2", "effective_status": "ACTIVE"},
                             {"id": "c3", "effective_status": "PAUSED"}]}},
        {"metodo": "GET", "url_prefijo": f"{base}/c1", "veces": 1, "cuerpo": {"id": "c1", "effective_status": "ACTIVE"}},
        {"metodo": "POST", "url_prefijo": f"{base}/c1", "veces": 1, "cuerpo": {"success": True}},
        {"metodo": "GET", "url_prefijo": f"{base}/c1", "veces": 1, "cuerpo": {"id": "c1", "effective_status": "PAUSED"}},
        {"metodo": "GET", "url_prefijo": f"{base}/c2", "veces": 1, "cuerpo": {"id": "c2", "effective_status": "ACTIVE"}},
        {"metodo": "POST", "url_prefijo": f"{base}/c2", "veces": 1, "cuerpo": {"success": True}},
        {"metodo": "GET", "url_prefijo": f"{base}/c2", "veces": 1, "cuerpo": {"id": "c2", "effective_status": "PAUSED"}},
    ])


def _prueba_a3_a4(id_: str) -> ResultadoAceptacion:
    from meta.pausar import pausar_cuenta
    try:
        transporte = _fixture_dos_activas_una_pausada()
        cliente = _cliente_meta_fixture(transporte)
        pausadas = pausar_cuenta(cliente, "act_100000000000001")
        if set(pausadas) != {"c1", "c2"}:
            return ResultadoAceptacion(id_, "ROJO", f"se esperaba pausar exactamente {{c1, c2}}, se pausó {pausadas}", {})
        if transporte.pendientes():
            return ResultadoAceptacion(id_, "ROJO", "quedaron llamadas de la relectura sin consumir: la confirmación no ocurrió", {})
        return ResultadoAceptacion(id_, "VERDE",
                                   "meta.pausar.pausar_cuenta lista exactamente las 2 campañas ACTIVE y la relectura "
                                   "confirma PAUSED en ambas (idempotente: no toca la ya PAUSED)",
                                   {"pausadas": sorted(pausadas)})
    except Exception as exc:  # noqa: BLE001
        return _resultado_de_excepcion(id_, exc, esperado="pausar exactamente las 2 campañas ACTIVE con relectura")


# ----------------------------------------------------------------------------------------------
# A-5: latido detenido con 1 campaña ACTIVE -> decisión de pausar + pausa vía fixture (parcial: sin alerta)
# ----------------------------------------------------------------------------------------------
def _prueba_a5(ctx: _Contexto) -> ResultadoAceptacion:
    from infra.latido import evaluar_vencimiento
    from meta.pausar import pausar_cuenta
    try:
        t_ultimo = comun.instante(ctx.ahora)
        t_ahora = t_ultimo + timedelta(minutes=1)
        decision = evaluar_vencimiento(ultimo_latido=comun.iso_z(t_ultimo), ahora=t_ahora, latido_max_min=0)  # "detenido": 1 min sin latido ya es vencido con el margen en 0
        if not decision.debe_pausar:
            return ResultadoAceptacion("A-5", "ROJO", "evaluar_vencimiento no decidió pausar con el latido vencido", {})
        transporte = TransporteFixture([
            {"metodo": "GET", "url_prefijo": "https://meta.fixture.ejemplo/v0/act_100000000000001/campaigns", "veces": 1,
             "cuerpo": {"data": [{"id": "c1", "effective_status": "ACTIVE"}]}},
            {"metodo": "GET", "url_prefijo": "https://meta.fixture.ejemplo/v0/c1", "veces": 1, "cuerpo": {"id": "c1", "effective_status": "ACTIVE"}},
            {"metodo": "POST", "url_prefijo": "https://meta.fixture.ejemplo/v0/c1", "veces": 1, "cuerpo": {"success": True}},
            {"metodo": "GET", "url_prefijo": "https://meta.fixture.ejemplo/v0/c1", "veces": 1, "cuerpo": {"id": "c1", "effective_status": "PAUSED"}},
        ])
        cliente = _cliente_meta_fixture(transporte)
        pausadas = pausar_cuenta(cliente, "act_100000000000001")
        if pausadas != ("c1",):
            return ResultadoAceptacion("A-5", "ROJO", f"se esperaba pausar ('c1',), se pausó {pausadas}", {})
        return ResultadoAceptacion("A-5", "PENDIENTE",
                                   "verificado con fixtures: evaluar_vencimiento decide pausar y la campaña ACTIVE "
                                   "queda PAUSED; PENDIENTE el envío de la alerta por los DOS canales (lo hace "
                                   "infra/workers/watchdog/src/index.mjs::alertarDosCanales, en JavaScript, sin "
                                   "puente a este harness de Python; node --test no cubre el envío real tampoco, "
                                   "solo que se invoca cuando corresponde)",
                                   {"pausadas": list(pausadas)})
    except Exception as exc:  # noqa: BLE001
        return _resultado_de_excepcion("A-5", exc, esperado="decisión de pausar y pausa efectiva vía fixture")


# ----------------------------------------------------------------------------------------------
# A-6, A-7, A-9, A-11: fuera del alcance de este harness (ver docstring del módulo)
# ----------------------------------------------------------------------------------------------
def _prueba_pendiente(id_: str, motivo: str) -> ResultadoAceptacion:
    return ResultadoAceptacion(id_, "PENDIENTE", motivo, {})


# ----------------------------------------------------------------------------------------------
# A-8: un token sin permiso de escritura no se trata como éxito
# ----------------------------------------------------------------------------------------------
def _prueba_a8() -> ResultadoAceptacion:
    from engine.errores import ErrorExterno
    try:
        transporte = TransporteFixture([
            {"metodo": "GET", "url_prefijo": "https://meta.fixture.ejemplo/v0/c1", "veces": 1, "cuerpo": {"id": "c1", "effective_status": "ACTIVE"}},
            {"metodo": "POST", "url_prefijo": "https://meta.fixture.ejemplo/v0/c1", "veces": 1, "estado": 403,
             "cuerpo": {"error": {"message": "Permissions error (simulado)", "code": 200}}},
        ])
        cliente = _cliente_meta_fixture(transporte)
        try:
            from meta.pausar import pausar_campana
            pausar_campana(cliente, "c1")
        except ErrorExterno as exc:
            return ResultadoAceptacion("A-8", "VERDE",
                                       "un 403 de la plataforma se propaga como ErrorExterno, nunca se trata como "
                                       "éxito ni se reintenta como si fuera un 613; el alcance de la prueba real "
                                       "(que el TOKEN de solo lectura esté de verdad restringido en Meta/Stripe) "
                                       "exige la plataforma real (ola 3)",
                                       {"excepcion": str(exc)})
        return ResultadoAceptacion("A-8", "ROJO", "un 403 no produjo ErrorExterno: el código lo trató como éxito", {})
    except Exception as exc:  # noqa: BLE001
        return _resultado_de_excepcion("A-8", exc, esperado="ErrorExterno ante un 403")


# ----------------------------------------------------------------------------------------------
# A-10: motor detenido 35 min con 1 campaña ACTIVE -> pausa + preflight C-09 a ROJO
# ----------------------------------------------------------------------------------------------
def _prueba_a10(ctx: _Contexto) -> ResultadoAceptacion:
    from infra.latido import evaluar_vencimiento
    from infra.preflight import sonda_c09_watchdog
    try:
        t_ultimo = comun.instante(ctx.ahora)
        t_ahora = t_ultimo + timedelta(minutes=35)
        decision = evaluar_vencimiento(ultimo_latido=comun.iso_z(t_ultimo), ahora=t_ahora, latido_max_min=30)
        if not decision.debe_pausar:
            return ResultadoAceptacion("A-10", "ROJO", "35 min sin latido con latido_max_min=30 no decidió pausar", {})
        transporte = TransporteFixture([
            {"metodo": "GET", "url_prefijo": "https://watchdog.fixture.ejemplo/estado", "veces": 1,
             "cuerpo": {"visto_hace_min": 42, "latido_recibido_hace_min": 42, "pausa": False}},
        ])
        resultado_sonda = sonda_c09_watchdog(transporte, "https://watchdog.fixture.ejemplo")
        if resultado_sonda.estado != "ROJO":
            return ResultadoAceptacion("A-10", "ROJO", f"C-09 debía quedar ROJO con visto_hace_min=42, quedó {resultado_sonda.estado}", {})
        return ResultadoAceptacion("A-10", "VERDE",
                                   "con 35 min sin latido (latido_max_min=30), evaluar_vencimiento decide pausar y "
                                   "la sonda C-09 del preflight marca ROJO al ver al watchdog visto hace 42 min",
                                   {"motivo_vencimiento": decision.motivo, "sonda_c09": resultado_sonda.mensaje})
    except Exception as exc:  # noqa: BLE001
        return _resultado_de_excepcion("A-10", exc, esperado="pausa decidida y preflight C-09 en ROJO")


# ----------------------------------------------------------------------------------------------
# A-12: reanudar tras A-10, solo con orden firmada y preflight VERDE (ambos booleanos explícitos)
# ----------------------------------------------------------------------------------------------
def _prueba_a12(ctx: _Contexto) -> ResultadoAceptacion:
    base = ctx.raiz / "A-12"
    motor_estado.fijar_pausa("simulacro A-10->A-12", raiz=base, ahora=ctx.ahora)
    try:
        intentos: list[tuple[bool, bool, bool]] = []  # (firma, infra, se_bloqueo)
        for firma_verificada, infra_verde in ((False, False), (True, False), (False, True)):
            try:
                motor_orq.reanudar(raiz=base, ahora=ctx.ahora, firma_verificada=firma_verificada, infra_verde=infra_verde)
                intentos.append((firma_verificada, infra_verde, False))
            except ErrorFabrica:
                intentos.append((firma_verificada, infra_verde, True))
        if not all(bloqueo for _, _, bloqueo in intentos):
            return ResultadoAceptacion("A-12", "ROJO", f"algún intento incompleto NO se bloqueó: {intentos}", {})
        if not guard.hay_pausa(base):
            return ResultadoAceptacion("A-12", "ROJO", "PAUSA se quitó sin orden firmada ni preflight VERDE", {})
        motor_orq.reanudar(raiz=base, ahora=ctx.ahora, firma_verificada=True, infra_verde=True)
        if guard.hay_pausa(base):
            return ResultadoAceptacion("A-12", "ROJO", "con ambas condiciones cumplidas, reanudar no quitó PAUSA", {})
        return ResultadoAceptacion("A-12", "VERDE",
                                   "orq.reanudar exige firma_verificada E infra_verde; cualquier combinación "
                                   "incompleta se bloquea (ErrorBloqueado) y PAUSA sigue puesta; solo con ambas "
                                   "explícitas en True se quita PAUSA",
                                   {"intentos": intentos})
    except Exception as exc:  # noqa: BLE001
        return _resultado_de_excepcion("A-12", exc, esperado="bloqueo salvo con firma y preflight verificados")


# ----------------------------------------------------------------------------------------------
# Harness
# ----------------------------------------------------------------------------------------------
def ejecutar_simulacro(*, raiz: Path, ahora: Callable[[], datetime] = comun.ahora_utc) -> InformeSimulacro:
    """Corre A-1…A-12 EN SERIE, cada una en su propia subcarpeta de ``raiz`` (nunca toca ``empresa/`` real)."""
    ctx = _Contexto(raiz=raiz, env=_env_simulacion(raiz), ahora=ahora)
    resultados = (
        _prueba_a1(ctx),
        _prueba_a2(ctx),
        _prueba_a3_a4("A-3"),
        _prueba_a3_a4("A-4"),
        _prueba_a5(ctx),
        _prueba_pendiente("A-6", "cubierto por node --test infra/workers/watchdog/test/ (\"ninguna ruta activa "
                                 "nada\"); este harness de Python no reimplementa el Worker en JavaScript"),
        _prueba_pendiente("A-7", "exige el token real del operador contra la cuenta real de Meta con spend_cap "
                                 "apenas sobre amount_spent (ola 3, docs/06 §7); nuestro código solo LEE spend_cap "
                                 "a propósito, pero esta prueba es sobre el permiso de la PLATAFORMA, no del código"),
        _prueba_a8(),
        _prueba_pendiente("A-9", "exige publicar por la Biblioteca de Anuncios vía MCP en la sesión Code del "
                                 "dueño con credenciales reales de Meta (docs/06 §4.2 nota A5 H2); no disponible aquí"),
        _prueba_a10(ctx),
        _prueba_pendiente("A-11", "exige deshabilitar el cron real del Worker en Cloudflare y medir la alerta en "
                                  "<=15 min contra la plataforma real; no hay despliegue real en este entorno"),
        _prueba_a12(ctx),
    )
    return InformeSimulacro(generado_en=comun.iso_z(comun.instante(ahora)), resultados=resultados)


# ----------------------------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------------------------
def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m infra.simulacro", description="Harness de aceptación A-1…A-12 (docs/07 §9.3).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    pe = sub.add_parser("ejecutar")
    pe.add_argument("--raiz")
    pe.add_argument("--ahora")
    pe.add_argument("--json", action="store_true")
    try:
        args = ap.parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2

    def cuerpo() -> int:
        from engine.errores import ErrorUso
        env = dict(os.environ)
        if (args.raiz or args.ahora) and comun.entorno(env) == "produccion":
            raise ErrorUso("--raiz y --ahora no existen con FABRICA_ENTORNO=produccion")
        raiz = Path(args.raiz).resolve() if args.raiz else comun.raiz(env)
        reloj = (lambda: comun.parsear_z(args.ahora)) if args.ahora else comun.ahora_utc
        informe = ejecutar_simulacro(raiz=raiz, ahora=reloj)
        datos = {"generado_en": informe.generado_en, "resumen": informe.resumen,
                 "resultados": [{"id": r.id, "estado": r.estado, "motivo": r.motivo} for r in informe.resultados]}
        codigo = 0 if informe.ok else 1
        if args.json:
            print(json.dumps({"ok": informe.ok, "modo": "dry_run", "codigo": codigo, "datos": datos, "avisos": []},
                             sort_keys=True, ensure_ascii=False))
        else:
            print(json.dumps(datos, ensure_ascii=False, sort_keys=True))
        return codigo

    return comun.ejecutar_cli(cuerpo)


if __name__ == "__main__":
    sys.exit(main())
