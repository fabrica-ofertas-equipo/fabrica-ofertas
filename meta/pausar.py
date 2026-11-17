"""``meta.pausar``: capa 2 del kill switch (docs/06 §5, `orquestador.pausa_global_max_min`).

``PAUSED`` idempotente, con relectura para confirmar: una campaña ya ``PAUSED`` es un no-op; tras
pausar se vuelve a leer y, si Meta no lo reflejó, es ``ErrorExterno`` (nunca se asume que un ``POST``
exitoso significa que el objeto ya está pausado). Pausar siempre usa ``forzar=True``
(``contratos/gates.json`` ``accion:pausar``: nunca espera al ritmo ni a un humano).
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Sequence

from engine import comun, limites as motor_limites
from engine.errores import ErrorExterno, ErrorUso
from meta import _cli_comun
from meta.cliente import ClienteMeta

__all__ = ["main", "pausar_campana", "pausar_cuenta", "pausar_cuentas"]

_CAMPOS = ("id", "effective_status")


def pausar_campana(cliente: ClienteMeta, campaign_id: str) -> bool:
    """Pausa ``campaign_id`` si está ``ACTIVE``; relee para confirmar. ``True`` solo si hizo algo (idempotente)."""
    estado = str(cliente.leer(campaign_id, campos=_CAMPOS).get("effective_status"))
    if estado != "ACTIVE":
        return False
    cliente.cambiar_estado(campaign_id, "PAUSED", forzar=True)
    confirmado = str(cliente.leer(campaign_id, campos=_CAMPOS).get("effective_status"))
    if confirmado == "ACTIVE":
        raise ErrorExterno(f"meta.pausar: {campaign_id} sigue ACTIVE después de pausar (relectura)")
    return True


def pausar_cuenta(cliente: ClienteMeta, ad_account_id: str) -> tuple[str, ...]:
    """Pausa TODAS las campañas ``ACTIVE`` de ``ad_account_id`` (kill switch de cuenta); devuelve las pausadas."""
    campanas = cliente.listar(f"{ad_account_id}/campaigns", campos=_CAMPOS)
    pausadas: list[str] = []
    for campana in campanas:
        if campana.get("effective_status") == "ACTIVE" and pausar_campana(cliente, str(campana["id"])):
            pausadas.append(str(campana["id"]))
    return tuple(pausadas)


def pausar_cuentas(cliente: ClienteMeta, ad_account_ids: Sequence[str]) -> dict[str, tuple[str, ...]]:
    """Pausa todas las cuentas de ``cuentas_permitidas``; mapa ``ad_account_id -> campañas pausadas``."""
    return {ad_account_id: pausar_cuenta(cliente, ad_account_id) for ad_account_id in ad_account_ids}


# ----------------------------------------------------------------------------------------------
# CLI (envoltorio en scripts/pausar.py): capa 2 del kill switch (docs/06 §5)
# ----------------------------------------------------------------------------------------------
def main(argv: Sequence[str] | None = None) -> int:
    """``python -m meta.pausar [--campana-id ID] [--ad-account act_… | todas las de limites.cuentas_permitidas]``."""
    ap = argparse.ArgumentParser(prog="python -m meta.pausar", description="PAUSED idempotente, con relectura (capa 2 del kill switch).")
    ap.add_argument("--ad-account", dest="ad_account", help="una cuenta; si se omite, todas las de limites.cuentas_permitidas")
    ap.add_argument("--campana-id", dest="campana_id", help="si se da, pausa solo esta campaña (no toda la cuenta)")
    _cli_comun.agregar_argumentos_comunes(ap, con_oferta=False)
    try:
        args = ap.parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2

    def cuerpo() -> int:
        env = dict(os.environ)
        if args.raiz and comun.entorno(env) == "produccion":
            raise ErrorUso("--raiz no existe con FABRICA_ENTORNO=produccion")
        raiz = Path(args.raiz).resolve() if args.raiz else comun.raiz(env)

        if args.modo == "dry-run":
            _cli_comun.imprimir(ok=True, modo="dry_run", codigo=0,
                               datos={"campana_id": args.campana_id, "ad_account": args.ad_account}, avisos=[], as_json=args.json)
            return 0

        lim = motor_limites.cargar_limites(raiz / "empresa" / "limites.yaml", env=env)
        cliente, _ = _cli_comun.construir_cliente(
            args, env, segundos_min_entre_ediciones=lim.valor("segundos_min_entre_ediciones"),
            max_cambios_presupuesto_por_hora=lim.valor("max_cambios_presupuesto_por_hora_por_conjunto"),
        )
        if args.campana_id:
            pausada = pausar_campana(cliente, args.campana_id)
            datos = {args.campana_id: pausada}
        elif args.ad_account:
            datos = {args.ad_account: list(pausar_cuenta(cliente, args.ad_account))}
        else:
            datos = {cuenta: list(pausadas) for cuenta, pausadas in pausar_cuentas(cliente, lim.valor("cuentas_permitidas")).items()}
        _cli_comun.imprimir(ok=True, modo=args.modo, codigo=0, datos=datos, avisos=[], as_json=args.json)
        return 0

    return comun.ejecutar_cli(cuerpo)


if __name__ == "__main__":
    sys.exit(main())
