"""``meta.monitor``: vigilancia T+1/6/24/48/72 h tras activar y traspaso a D8 (docs/06 N12, B0-21).

Lee el árbol vivo (campaña y cada anuncio) y produce ``traspaso.json`` (``contratos/traspaso.schema.json``).
Un anuncio con ``effective_status == "DISAPPROVED"`` se **pausa** de inmediato (con ``forzar=True``:
pausar nunca espera, ``contratos/gates.json`` ``accion:pausar``), cuenta en ``rechazos_7d`` y abre un
pedido de revisión a D6/X1; nunca se vuelve a contar el MISMO anuncio (los creativos son inmutables:
"rollback" es pausar y crear otro ``ad_id``, nunca reenviar el mismo). Con ``rechazos_7d >=
compliance.rechazos_congelar`` el resultado marca ``congelar=True`` (quien orquesta escribe
``empresa/PAUSA`` y baja el nivel de autonomía; este módulo no lo hace: solo lee y pausa el anuncio).
"""
from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from engine import comun, limites as motor_limites, parametros as motor_parametros
from engine.errores import ErrorUso
from meta import _cli_comun
from meta.cliente import ClienteMeta

__all__ = ["ResultadoMonitor", "VENTANAS_H", "main", "monitorear"]

VENTANAS_H = (1, 6, 24, 48, 72)
_ESTADO_RECHAZADO = "DISAPPROVED"
_CAMPOS = ("id", "effective_status")


@dataclass(frozen=True)
class ResultadoMonitor:
    """Resultado de una corrida de ``monitorear``: el ``traspaso.json`` y los efectos que produjo."""

    traspaso: dict[str, Any]
    pausados: tuple[str, ...]
    nuevos_rechazos: tuple[str, ...]
    rechazos_7d: int
    congelar: bool
    pedidos_d6: tuple[dict[str, Any], ...]


def monitorear(*, oferta_id: str, cliente: ClienteMeta, ids_meta: Mapping[str, Any], ventana_h: int,
               ahora: Callable[[], datetime] = comun.ahora_utc, gasto_real_minor: int, gasto_esperado_minor: int,
               moneda: str, estado_aprendizaje: str, adid_capturado_bp: int | None, clics_enlace: int, vistas_landing: int,
               ad_ids_rechazados_previos: Sequence[str] = (), historial_rechazos: Sequence[Mapping[str, Any]] = (),
               rechazos_congelar: int) -> ResultadoMonitor:
    """Una corrida de monitoreo (una ventana ``T+Nh``); no escribe archivos, solo lee Meta y pausa lo rechazado.

    ``historial_rechazos`` son los rechazos YA registrados (``[{"ad_id":…, "en": "...Z"}]``, de corridas
    anteriores, lo persiste quien llama); se usa para contar ``rechazos_7d`` sin volver a contar el mismo
    anuncio dos veces. ``ad_ids_rechazados_previos`` son los ``ad_id`` ya pausados por rechazo (de
    cualquier antigüedad): un anuncio ahí nunca se vuelve a pausar ni a contar ni a pedir revisión otra vez.
    """
    if ventana_h not in VENTANAS_H:
        raise ValueError(f"ventana_h inválida: {ventana_h!r} (se espera uno de {VENTANAS_H})")
    t = comun.instante(ahora)

    campana_leida = cliente.leer(ids_meta["campaign_id"], campos=_CAMPOS)
    anuncios_leidos = [cliente.leer(ad_id, campos=_CAMPOS) for ad_id in ids_meta["ad_ids"]]

    pausados: list[str] = []
    nuevos_rechazos: list[str] = []
    pedidos_d6: list[dict[str, Any]] = []
    anuncios_traspaso: list[dict[str, Any]] = []
    previos = set(ad_ids_rechazados_previos)
    for anuncio in anuncios_leidos:
        ad_id, estado = str(anuncio["id"]), str(anuncio["effective_status"])
        rechazado = estado == _ESTADO_RECHAZADO
        if rechazado and ad_id not in previos:
            cliente.cambiar_estado(ad_id, "PAUSED", forzar=True)
            pausados.append(ad_id)
            nuevos_rechazos.append(ad_id)
            pedidos_d6.append({
                "tipo": "revision_creativo", "destino": "D6/X1", "oferta_id": oferta_id, "ad_id": ad_id,
                "motivo": _ESTADO_RECHAZADO, "ts": comun.iso_z(t),
            })
        anuncios_traspaso.append({"ad_id": ad_id, "effective_status": estado, "rechazado": rechazado})

    ventana_7d = [r for r in historial_rechazos if t - comun.parsear_z(r["en"]) <= timedelta(days=7)]
    rechazados_en_7d = {str(r["ad_id"]) for r in ventana_7d} | set(nuevos_rechazos)
    rechazos_7d = len(rechazados_en_7d)
    congelar = rechazos_7d >= rechazos_congelar

    anomalias: list[str] = []
    if gasto_real_minor > gasto_esperado_minor:
        anomalias.append("gasto-sobre-esperado")
    if any(a["rechazado"] for a in anuncios_traspaso):
        anomalias.append("anuncio-rechazado")

    lanzamiento_estable = ventana_h == 72 and not anomalias and rechazos_7d == 0
    traspaso = {
        "schema_version": "1.1.0", "oferta_id": oferta_id, "ventana_h": ventana_h, "medido_en": comun.iso_z(t),
        "campana": {"campaign_id": str(campana_leida["id"]), "effective_status": str(campana_leida["effective_status"])},
        "anuncios": anuncios_traspaso, "gasto": {"real": {"monto": gasto_real_minor, "moneda": moneda},
                                                  "esperado": {"monto": gasto_esperado_minor, "moneda": moneda}},
        "estado_aprendizaje": estado_aprendizaje, "rechazos_7d": rechazos_7d, "adid_capturado_bp": adid_capturado_bp,
        "clics_enlace": clics_enlace, "vistas_landing": vistas_landing, "anomalias": anomalias,
        "lanzamiento_estable": lanzamiento_estable,
    }
    return ResultadoMonitor(
        traspaso=traspaso, pausados=tuple(pausados), nuevos_rechazos=tuple(nuevos_rechazos), rechazos_7d=rechazos_7d,
        congelar=congelar, pedidos_d6=tuple(pedidos_d6),
    )


# ----------------------------------------------------------------------------------------------
# CLI (A3, ola 2 B5b): envoltorio en scripts/ no existe aún (pedido); se corre con -m directo.
# ----------------------------------------------------------------------------------------------
def main(argv: Sequence[str] | None = None) -> int:
    """``python -m meta.monitor --oferta OF-… --ids-meta ids_meta.json --ventana-h {1,6,24,48,72} …``.

    Solo mide y pausa lo ``DISAPPROVED`` (nunca reactiva ni recrea, ver docstring del módulo); el
    traspaso estable a D8 lo decide quien orqueste, no este CLI. Salidas: 0 correcto · 2 uso ·
    3 validación (``--ventana-h`` fuera de :data:`VENTANAS_H`) · 4 bloqueado (``--modo live``) ·
    5 límite/parámetro faltante · 6 externo (error de la Marketing API).
    """
    ap = argparse.ArgumentParser(prog="python -m meta.monitor", description="Vigilancia T+1/6/24/48/72 h tras activar (docs/06 N12, B0-21).")
    ap.add_argument("--ids-meta", required=True, dest="ids_meta_ruta")
    ap.add_argument("--ventana-h", required=True, type=int, dest="ventana_h", choices=VENTANAS_H)
    ap.add_argument("--gasto-real", required=True, type=int, dest="gasto_real_minor")
    ap.add_argument("--gasto-esperado", required=True, type=int, dest="gasto_esperado_minor")
    ap.add_argument("--moneda", required=True)
    ap.add_argument("--estado-aprendizaje", required=True, dest="estado_aprendizaje")
    ap.add_argument("--adid-capturado-bp", type=int, dest="adid_capturado_bp")
    ap.add_argument("--clics-enlace", required=True, type=int, dest="clics_enlace")
    ap.add_argument("--vistas-landing", required=True, type=int, dest="vistas_landing")
    ap.add_argument("--historial", dest="historial_ruta", help="JSON {historial_rechazos: [...], ad_ids_rechazados_previos: [...]}")
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
        ids_meta = comun.cargar_json(Path(args.ids_meta_ruta))
        historial = comun.cargar_json(Path(args.historial_ruta)) if args.historial_ruta else {}

        if args.modo == "dry-run":
            plan = {"oferta_id": args.oferta, "ventana_h": args.ventana_h, "object_ids": sorted({
                ids_meta["campaign_id"], *ids_meta["ad_ids"],
            })}
            _cli_comun.imprimir(ok=True, modo="dry_run", codigo=0, datos=plan, avisos=["dry-run: no se llama a Meta ni se pausa nada"], as_json=args.json)
            return 0

        lim = motor_limites.cargar_limites((raiz or comun.raiz(env)) / "empresa" / "limites.yaml", env=env)
        par = motor_parametros.cargar_parametros((raiz or comun.raiz(env)) / "empresa" / "parametros.yaml")
        cliente, _ = _cli_comun.construir_cliente(
            args, env, segundos_min_entre_ediciones=lim.valor("segundos_min_entre_ediciones"),
            max_cambios_presupuesto_por_hora=lim.valor("max_cambios_presupuesto_por_hora_por_conjunto"),
        )
        resultado = monitorear(
            oferta_id=args.oferta, cliente=cliente, ids_meta=ids_meta, ventana_h=args.ventana_h, ahora=reloj,
            gasto_real_minor=args.gasto_real_minor, gasto_esperado_minor=args.gasto_esperado_minor, moneda=args.moneda,
            estado_aprendizaje=args.estado_aprendizaje, adid_capturado_bp=args.adid_capturado_bp,
            clics_enlace=args.clics_enlace, vistas_landing=args.vistas_landing,
            ad_ids_rechazados_previos=tuple(historial.get("ad_ids_rechazados_previos") or ()),
            historial_rechazos=tuple(historial.get("historial_rechazos") or ()),
            rechazos_congelar=int(par.valor("compliance.rechazos_congelar")),
        )
        datos = {
            "traspaso": resultado.traspaso, "pausados": list(resultado.pausados), "nuevos_rechazos": list(resultado.nuevos_rechazos),
            "rechazos_7d": resultado.rechazos_7d, "congelar": resultado.congelar, "pedidos_d6": list(resultado.pedidos_d6),
        }
        _cli_comun.imprimir(ok=True, modo=args.modo, codigo=0, datos=datos, avisos=[], as_json=args.json)
        return 0

    return comun.ejecutar_cli(cuerpo)


if __name__ == "__main__":
    sys.exit(main())
