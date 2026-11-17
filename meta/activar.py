"""``meta.activar``: N12, la activación de una campaña de test (docs/06 N11-N12, departamentos/08 §4).

Orden exacto (docs/06 N12): (1) sello de X1 vigente sobre ``hash_config`` y con los ``object_ids``
EXACTOS de ``ids_meta.json`` (``scripts.validar_esquemas.problemas_uso_sello``, la comprobación
TOCTOU justo antes de usar un sello); (2) los 7 pasos de ``engine.guard.comprobar_live("activar", …,
sello=hash_config)`` (entorno, PAUSA, infra, límites + agregados, credenciales y la **orden firmada**
que aprueba ``hash_config``); (3) relectura del árbol vivo en Meta y comparación exacta de IDs contra
``ids_meta.json``; **(3b, A5)** re-lectura del ESTADO VIVO de cada campo que importa (presupuesto,
``spend_cap``, evento de optimización, targeting, creativo, enlace, textos y ``special_ad_categories``
como proxy de DSA mientras ``campana.economia.dsa`` no exista, ver README «Pedidos») y comparación
contra lo que ``campana.json`` (la configuración sellada) declara: cualquier diferencia bloquea con
``ErrorBloqueado`` y nombra el campo (``diferencias_config_viva``); (4) activación **anuncios →
conjunto → campaña** (la campaña al final: nunca hay entrega a medias), saltando lo que ya está
``ACTIVE`` (no-op idempotente); (5) relectura final de ``effective_status``: si algo no quedó
``ACTIVE`` o algo imprevisto SÍ quedó ``ACTIVE``, se pausa todo lo que este módulo activó y sale con
``ErrorExterno``. Si un ``POST`` de activación falla a mitad de la secuencia, también se pausa lo ya
activado antes de relanzar el error (nunca una campaña a medio activar sin que alguien lo sepa).

El sello de X1 (``compliance.verificar_sello``) todavía no existe (B6 lo construye en paralelo): este
módulo recibe la función como parámetro (``verificar_sello``); las pruebas usan una función falsa —
«fake de verificar_sello», ola 1 de B5 en docs/06 §8.
"""
from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from engine import comun, guard, limites as motor_limites
from engine.errores import ErrorBloqueado, ErrorExterno, ErrorFabrica, ErrorUso
from engine.guard import EstadoCuenta
from engine.limites import CampanaActiva
from engine.transporte import Transporte
from meta import _cli_comun, payloads
from meta.cliente import ClienteMeta
from scripts.validar_esquemas import problemas_uso_sello

__all__ = [
    "ResultadoActivar", "activar", "diferencias_config_viva", "ids_de", "leer_estado_vivo", "main",
]

_CAMPOS_EFFECTIVE_STATUS = ("id", "effective_status")
_CAMPOS_CAMPANA_VIVA = ("id", "spend_cap", "special_ad_categories")
_CAMPOS_CONJUNTO_VIVO = ("id", "daily_budget", "lifetime_budget", "optimization_goal", "targeting", "end_time", "promoted_object")
_CAMPOS_ANUNCIO_VIVO = ("id", "creative")
_CAMPOS_CREATIVO_VIVO = ("id", "object_story_spec")
_CAMPOS_TEXTO_LINK_DATA = ("message", "name", "description")


def ids_de(ids_meta: Mapping[str, Any]) -> set[str]:
    """Conjunto de IDs que ``activar`` enciende: campaña + conjuntos + anuncios (no creativos, que no se activan)."""
    return {ids_meta["campaign_id"], *ids_meta["adset_ids"], *ids_meta["ad_ids"]}


def leer_estado_vivo(cliente: ClienteMeta, ids_meta: Mapping[str, Any], *, incluir_creativo: bool = False) -> dict[str, Any]:
    """Relee de Meta (o del fixture) los campos de configuración que :func:`diferencias_config_viva` compara.

    Solo el primer conjunto (``adset_ids[0]``): D7 arma ``CBO_1AS``, un conjunto por campaña
    (departamentos/08 §3.2); si algún día hay más de uno, releer cada uno es tarea de quien agregue
    esa estructura. ``incluir_creativo=True`` además relee ``object_story_spec`` de cada creativo (para
    comparar ``enlace``/``textos``); solo tiene sentido si quien llama tiene los payloads esperados.
    """
    campana_leida = cliente.leer(ids_meta["campaign_id"], campos=_CAMPOS_CAMPANA_VIVA)
    conjunto_leido = cliente.leer(ids_meta["adset_ids"][0], campos=_CAMPOS_CONJUNTO_VIVO)
    anuncios_leidos = [cliente.leer(ad_id, campos=_CAMPOS_ANUNCIO_VIVO) for ad_id in ids_meta["ad_ids"]]
    vivo: dict[str, Any] = {"campana": campana_leida, "conjunto": conjunto_leido, "anuncios": anuncios_leidos}
    if incluir_creativo:
        vivo["creativos"] = [cliente.leer(cid, campos=_CAMPOS_CREATIVO_VIVO) for cid in (ids_meta.get("creative_ids") or ())]
    return vivo


def diferencias_config_viva(*, campana: Mapping[str, Any], ids_meta: Mapping[str, Any], vivo: Mapping[str, Any],
                            payloads_creativo: Mapping[str, Mapping[str, Any]] | None = None) -> list[str]:
    """Campos donde el estado VIVO (``vivo``, de :func:`leer_estado_vivo`) difiere de lo sellado en ``campana``.

    Lista vacía = coincide. Cada entrada nombra el campo y los valores vivo/esperado (docs/06 N12, A5):
    ``presupuesto.spend_cap`` o ``presupuesto.diario``/``candado_alternativo.lifetime_budget``,
    ``evento_optimizacion``, ``targeting``, ``dsa.special_ad_categories`` (proxy de DSA: ``campana.json``
    todavía no tiene un campo ``dsa`` propio, pedido a CT) y, por anuncio, ``creativo`` (que el
    ``creative_id`` en vivo sea el mismo que ``ids_meta.creative_ids`` registró: los creativos son
    inmutables, así que un cambio ahí es un reemplazo silencioso). ``enlace`` y ``textos`` (dentro de
    ``object_story_spec.link_data`` del creativo) solo se comprueban si se pasa ``payloads_creativo``
    (el mismo ``{ad_name: payload}`` de ``meta.crear``): sin él no hay forma de derivar el valor
    esperado desde los contratos actuales.
    """
    diffs: list[str] = []

    esperado_campana = payloads.payload_campana(campana)
    spend_cap_vivo = vivo["campana"].get("spend_cap")
    spend_cap_esperado = esperado_campana.get("spend_cap")
    if spend_cap_esperado is not None:
        if spend_cap_vivo is None or int(spend_cap_vivo) != int(spend_cap_esperado):
            diffs.append(f"presupuesto.spend_cap: vivo={spend_cap_vivo!r} esperado={spend_cap_esperado!r}")
    elif spend_cap_vivo is not None:
        diffs.append(f"presupuesto.spend_cap: vivo={spend_cap_vivo!r} esperado=None (candado_alternativo)")

    cats_vivo = sorted(vivo["campana"].get("special_ad_categories") or [])
    cats_esperado = sorted(campana.get("special_ad_categories") or [])
    if cats_vivo != cats_esperado:
        diffs.append(f"dsa.special_ad_categories: vivo={cats_vivo} esperado={cats_esperado}")

    esperado_conjunto = payloads.payload_conjunto(campana, campaign_id=str(ids_meta["campaign_id"]), pixel_id="_")
    if vivo["conjunto"].get("optimization_goal") != esperado_conjunto.get("optimization_goal"):
        diffs.append(f"evento_optimizacion.optimization_goal: vivo={vivo['conjunto'].get('optimization_goal')!r} esperado={esperado_conjunto.get('optimization_goal')!r}")
    # optimization_goal es el mismo para PURCHASE e INITIATE_CHECKOUT (payloads._EVENTO_OPTIMIZACION_META):
    # lo que de verdad distingue el evento es promoted_object.custom_event_type, independiente del pixel_id.
    evento_vivo = (vivo["conjunto"].get("promoted_object") or {}).get("custom_event_type")
    if evento_vivo != campana.get("evento_optimizacion"):
        diffs.append(f"evento_optimizacion: vivo={evento_vivo!r} esperado={campana.get('evento_optimizacion')!r}")
    if vivo["conjunto"].get("targeting") != esperado_conjunto.get("targeting"):
        diffs.append(f"targeting: vivo={vivo['conjunto'].get('targeting')!r} esperado={esperado_conjunto.get('targeting')!r}")
    if "daily_budget" in esperado_conjunto:
        if vivo["conjunto"].get("daily_budget") != esperado_conjunto.get("daily_budget"):
            diffs.append(f"presupuesto.diario: vivo={vivo['conjunto'].get('daily_budget')!r} esperado={esperado_conjunto.get('daily_budget')!r}")
    else:
        if vivo["conjunto"].get("lifetime_budget") != esperado_conjunto.get("lifetime_budget"):
            diffs.append(f"presupuesto.candado_alternativo.lifetime_budget: vivo={vivo['conjunto'].get('lifetime_budget')!r} esperado={esperado_conjunto.get('lifetime_budget')!r}")

    creative_ids_esperados = list(ids_meta.get("creative_ids") or ())
    for indice, anuncio in enumerate(vivo["anuncios"]):
        if indice >= len(creative_ids_esperados):
            continue
        creative_vivo = (anuncio.get("creative") or {}).get("id")
        creative_esperado = creative_ids_esperados[indice]
        if str(creative_vivo) != str(creative_esperado):
            diffs.append(f"creativo[{anuncio.get('id')}]: vivo={creative_vivo!r} esperado={creative_esperado!r}")

    if payloads_creativo is not None:
        creativos_vivos = {str(c.get("id")): c for c in (vivo.get("creativos") or [])}
        for indice, anuncio_campana in enumerate(campana.get("anuncios") or []):
            if indice >= len(creative_ids_esperados):
                continue
            creativo_vivo = creativos_vivos.get(str(creative_ids_esperados[indice]))
            payload_esperado = payloads_creativo.get(anuncio_campana["ad_name"])
            if creativo_vivo is None or payload_esperado is None:
                continue
            spec_vivo = (creativo_vivo.get("object_story_spec") or {}).get("link_data") or {}
            spec_esperado = (payload_esperado.get("object_story_spec") or {}).get("link_data") or {}
            if spec_esperado.get("link") is not None and spec_vivo.get("link") != spec_esperado.get("link"):
                diffs.append(f"enlace[{anuncio_campana['ad_name']}]: vivo={spec_vivo.get('link')!r} esperado={spec_esperado.get('link')!r}")
            for campo in _CAMPOS_TEXTO_LINK_DATA:
                if spec_esperado.get(campo) is not None and spec_vivo.get(campo) != spec_esperado.get(campo):
                    diffs.append(f"textos.{campo}[{anuncio_campana['ad_name']}]: vivo={spec_vivo.get(campo)!r} esperado={spec_esperado.get(campo)!r}")

    return diffs


@dataclass(frozen=True)
class ResultadoActivar:
    """Resultado de una activación exitosa."""

    campaign_id: str
    adset_ids: tuple[str, ...]
    ad_ids: tuple[str, ...]
    clave_idempotencia: str
    pasos_guard: tuple[str, ...]
    avisos: tuple[str, ...] = ()


def _sello_vigente(*, verificar_sello: Callable[[str, datetime], Mapping[str, Any] | None], clave_sello: str,
                   hash_config: str, object_ids: set[str], ahora: datetime) -> Mapping[str, Any]:
    sello = verificar_sello(clave_sello, ahora)
    if sello is None:
        raise ErrorBloqueado("sin sello de X1 vigente: meta.activar no activa nada sin el veto de X1 resuelto a favor")
    problemas = problemas_uso_sello(sello, artefacto_sha256=hash_config, object_ids=object_ids, ahora=ahora)
    if problemas:
        detalle = "; ".join(f"{codigo}: {mensaje}" for codigo, mensaje in problemas)
        raise ErrorBloqueado(f"sello de X1 inválido para esta activación: {detalle}")
    return sello


def _leer_estado(cliente: ClienteMeta, object_id: str) -> str:
    return str(cliente.leer(object_id, campos=_CAMPOS_EFFECTIVE_STATUS).get("effective_status"))


def _activar_si_falta(cliente: ClienteMeta, object_id: str) -> bool:
    """Activa ``object_id`` si no está ya ``ACTIVE`` (no-op idempotente); devuelve si este módulo lo activó."""
    if _leer_estado(cliente, object_id) == "ACTIVE":
        return False
    cliente.cambiar_estado(object_id, "ACTIVE")
    return True


def _pausar_lo_activado(cliente: ClienteMeta, activados: Sequence[str]) -> None:
    for object_id in reversed(activados):
        try:
            cliente.cambiar_estado(object_id, "PAUSED", forzar=True)
        except ErrorFabrica:
            pass  # mejor esfuerzo: ya estamos reportando un error más arriba; no lo oculta otro


def activar(*, oferta_id: str, campana: Mapping[str, Any], ids_meta: Mapping[str, Any], hash_config: str,
           clave_sello: str, verificar_sello: Callable[[str, datetime], Mapping[str, Any] | None],
           cliente: ClienteMeta, monto_minor: int, moneda: str, cuenta: EstadoCuenta,
           ahora: Callable[[], datetime] = comun.ahora_utc, simulacion: bool = False,
           transporte_guard: Transporte | None = None, env: Mapping[str, str] | None = None, raiz: Any = None,
           payloads_creativo: Mapping[str, Mapping[str, Any]] | None = None) -> ResultadoActivar:
    """Activa la campaña de ``ids_meta`` tras comprobar el sello de X1, los 7 pasos de ``guard`` y que el
    estado VIVO de Meta siga coincidiendo con ``campana.json`` (la configuración sellada, A5).

    ``campana`` es el ``campana.json`` ya validado y sellado (de ahí sale ``hash_config``): lo usa
    :func:`diferencias_config_viva` para derivar lo que la Marketing API DEBERÍA tener. ``monto_minor``/
    ``moneda``/``cuenta`` son el peor caso del efecto y el estado de la cuenta que ``engine.guard``
    necesita para los topes agregados (M05): ``cuenta.nueva`` debe ser la campaña que se activa, con
    ``oferta_id`` y ``max_teorico_diario_minor`` iguales a ``oferta_id``/``monto_minor``.
    ``payloads_creativo`` (opcional, el mismo ``{ad_name: payload}`` de ``meta.crear``) permite además
    comparar ``enlace`` y ``textos``; sin él, esas dos comprobaciones no corren (aviso en el resultado,
    nunca ``ErrorBloqueado`` por su ausencia: no son parte del esquema de ``campana.json`` todavía).
    ``simulacion=True`` es el modo fixture de B0 (exige ``transporte_guard`` de tipo
    :class:`~engine.transporte.TransporteFixture`; el ``ClienteMeta`` corre sobre su PROPIO transporte,
    normalmente el mismo objeto).

    Errores: ``ErrorBloqueado`` si el sello, el árbol de IDs o cualquier campo de la configuración viva
    no coincide (dice cuál); ``ErrorExterno`` si tras activar algo no quedó ``ACTIVE``.
    """
    t = comun.instante(ahora)
    object_ids = ids_de(ids_meta)
    _sello_vigente(verificar_sello=verificar_sello, clave_sello=clave_sello, hash_config=hash_config, object_ids=object_ids, ahora=t)

    ctx = guard.comprobar_live(
        "activar", oferta_id=oferta_id, monto_minor=monto_minor, moneda=moneda, sello=hash_config, ahora=ahora,
        simulacion=simulacion, transporte=transporte_guard, env=env, raiz=raiz, cuenta=cuenta,
    )

    arbol_vivo = {
        cliente.leer(ids_meta["campaign_id"], campos=("id",))["id"],
        *(o["id"] for o in cliente.listar(f"{ids_meta['campaign_id']}/adsets", campos=("id",))),
        *(o["id"] for o in cliente.listar(f"{ids_meta['campaign_id']}/ads", campos=("id",))),
    }
    if arbol_vivo != object_ids:
        extra, falta = arbol_vivo - object_ids, object_ids - arbol_vivo
        raise ErrorBloqueado(f"el árbol vivo de Meta no coincide con ids_meta.json (extra={sorted(extra)}, falta={sorted(falta)})")

    avisos: list[str] = []
    vivo = leer_estado_vivo(cliente, ids_meta, incluir_creativo=payloads_creativo is not None)
    diffs = diferencias_config_viva(campana=campana, ids_meta=ids_meta, vivo=vivo, payloads_creativo=payloads_creativo)
    if diffs:
        raise ErrorBloqueado(f"la configuración viva de Meta no coincide con campana.json sellado: {'; '.join(diffs)}")
    if payloads_creativo is None:
        avisos.append("sin --creativos: no se comprobaron enlace ni textos del creativo vivo (A5 parcial)")

    activados: list[str] = []
    try:
        for ad_id in ids_meta["ad_ids"]:
            if _activar_si_falta(cliente, ad_id):
                activados.append(ad_id)
        for adset_id in ids_meta["adset_ids"]:
            if _activar_si_falta(cliente, adset_id):
                activados.append(adset_id)
        if _activar_si_falta(cliente, ids_meta["campaign_id"]):
            activados.append(ids_meta["campaign_id"])
    except ErrorFabrica:
        _pausar_lo_activado(cliente, activados)
        raise

    estados_finales = {oid: _leer_estado(cliente, oid) for oid in object_ids}
    inesperados = {oid: estado for oid, estado in estados_finales.items() if estado != "ACTIVE"}
    if inesperados:
        _pausar_lo_activado(cliente, activados)
        raise ErrorExterno(f"tras activar, algún objeto no quedó ACTIVE: {inesperados}")

    return ResultadoActivar(
        campaign_id=ids_meta["campaign_id"], adset_ids=tuple(ids_meta["adset_ids"]), ad_ids=tuple(ids_meta["ad_ids"]),
        clave_idempotencia=ctx.clave_idempotencia, pasos_guard=ctx.pasos, avisos=tuple(avisos),
    )


# ----------------------------------------------------------------------------------------------
# CLI (envoltorio en scripts/meta_activar.py)
# ----------------------------------------------------------------------------------------------
def _verificar_sello_de_archivo(ruta: Path | None) -> Callable[[str, datetime], Mapping[str, Any] | None]:
    """El sello de X1 lo lee de ``ruta`` (``empresa/compliance/sellos/<hash>.json``); ``compliance.verificar_sello`` todavía no existe."""

    def _fn(clave_sello: str, ahora: datetime) -> Mapping[str, Any] | None:
        if ruta is None or not ruta.is_file():
            return None
        try:
            return comun.cargar_json(ruta)
        except (OSError, ValueError, UnicodeDecodeError):
            return None

    return _fn


def _cuenta_desde_archivo(ruta: Path) -> EstadoCuenta:
    datos = comun.cargar_json(ruta)
    nueva = datos.get("nueva")
    return EstadoCuenta(
        activas=tuple(datos.get("activas") or ()), gasto_vitalicio_minor=datos.get("gasto_vitalicio_minor"),
        nueva=CampanaActiva.desde(nueva) if nueva is not None else None,
        ediciones_recientes=tuple(datos.get("ediciones_recientes") or ()), ultimo_aumento=datos.get("ultimo_aumento"),
    )


def main(argv: Sequence[str] | None = None) -> int:
    """``python -m meta.activar --oferta OF-… --campana campana.json --ids-meta ids_meta.json --sello sello.json --cuenta cuenta.json --monto … --moneda …``."""
    ap = argparse.ArgumentParser(prog="python -m meta.activar", description="Activación N12: sello de X1 + 7 pasos de guard + Meta.")
    ap.add_argument("--campana", required=True, dest="campana_ruta", help="ruta a campana.json (la configuración sellada, A5)")
    ap.add_argument("--ids-meta", required=True, dest="ids_meta_ruta", help="ruta a ids_meta.json")
    ap.add_argument("--hash-config", required=True, dest="hash_config")
    ap.add_argument("--sello", dest="sello_ruta", help="ruta al sello de X1 (empresa/compliance/sellos/<hash>.json)")
    ap.add_argument("--cuenta", required=True, dest="cuenta_ruta", help="JSON con activas, gasto_vitalicio_minor y nueva (la campaña del efecto)")
    ap.add_argument("--monto", type=int, required=True, help="peor caso del efecto en la unidad menor (max_teorico_diario)")
    ap.add_argument("--moneda", required=True)
    ap.add_argument("--creativos", dest="creativos_ruta", help="JSON {ad_name: payload de adcreatives} usado por meta.crear; habilita comprobar enlace y textos (A5)")
    _cli_comun.agregar_argumentos_comunes(ap)
    try:
        args = ap.parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2

    def cuerpo() -> int:
        env = dict(os.environ)
        if (args.raiz or args.ahora) and comun.entorno(env) == "produccion":
            raise ErrorUso("--raiz y --ahora no existen con FABRICA_ENTORNO=produccion")
        raiz = Path(args.raiz).resolve() if args.raiz else None
        reloj = (lambda: comun.parsear_z(args.ahora)) if args.ahora else comun.ahora_utc
        campana = comun.cargar_json(Path(args.campana_ruta))
        ids_meta = comun.cargar_json(Path(args.ids_meta_ruta))
        cuenta = _cuenta_desde_archivo(Path(args.cuenta_ruta))
        if campana.get("oferta_id") != args.oferta:
            raise ErrorUso(f"--oferta {args.oferta!r} no coincide con campana.oferta_id {campana.get('oferta_id')!r}")
        if campana.get("hash_config") and campana["hash_config"] != args.hash_config:
            raise ErrorUso(f"--hash-config {args.hash_config!r} no coincide con campana.hash_config {campana['hash_config']!r}")
        payloads_creativo = comun.cargar_json(Path(args.creativos_ruta)) if args.creativos_ruta else None

        if args.modo == "dry-run":
            plan = {"object_ids": sorted(ids_de(ids_meta)), "hash_config": args.hash_config, "oferta_id": args.oferta}
            _cli_comun.imprimir(ok=True, modo="dry_run", codigo=0, datos=plan, avisos=["dry-run: no se llama a Meta ni a guard"], as_json=args.json)
            return 0

        lim = motor_limites.cargar_limites((raiz or comun.raiz(env)) / "empresa" / "limites.yaml", env=env)
        cliente, transporte = _cli_comun.construir_cliente(
            args, env, segundos_min_entre_ediciones=lim.valor("segundos_min_entre_ediciones"),
            max_cambios_presupuesto_por_hora=lim.valor("max_cambios_presupuesto_por_hora_por_conjunto"),
        )
        resultado = activar(
            oferta_id=args.oferta, campana=campana, ids_meta=ids_meta, hash_config=args.hash_config, clave_sello=args.hash_config,
            verificar_sello=_verificar_sello_de_archivo(Path(args.sello_ruta) if args.sello_ruta else None),
            cliente=cliente, monto_minor=args.monto, moneda=args.moneda, cuenta=cuenta, ahora=reloj,
            simulacion=(args.modo == "fixture"), transporte_guard=transporte, env=env, raiz=raiz,
            payloads_creativo=payloads_creativo,
        )
        datos = {"campaign_id": resultado.campaign_id, "adset_ids": list(resultado.adset_ids), "ad_ids": list(resultado.ad_ids),
                 "clave_idempotencia": resultado.clave_idempotencia, "pasos_guard": list(resultado.pasos_guard)}
        _cli_comun.imprimir(ok=True, modo=args.modo, codigo=0, datos=datos, avisos=list(resultado.avisos), as_json=args.json)
        return 0

    return comun.ejecutar_cli(cuerpo)


if __name__ == "__main__":
    sys.exit(main())
