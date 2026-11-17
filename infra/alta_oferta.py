"""``infra.alta_oferta``: nodo N01b "D0 Alta de oferta" (docs/06 §2; docs/07 §3.4, §9.1).

Por cada oferta hay 11 pasos humanos (dominio, zona/Pages, dataset, token CAPI, verificación de
dominio, correo de envío, `Product`/`Price` de prueba y vivos, ruta `/api/sesion*`, secretos y
**recalcular y subir el `spend_cap`**) descritos en ``infra/plantillas/alta-oferta.yaml`` (quién, cómo
se comprueba, ítem de preflight). Ningún paso con dinero o 2FA lo hace un agente: el código **lista**
(dry-run, defecto), **verifica en solo lectura** con un :class:`engine.transporte.Transporte` inyectado
(sin injectar → "pendiente de verificar", NUNCA verde falso) y, solo con ``--ejecutar``, escribe
``ofertas/<id>/infra/alta.json`` (IDs, sin secretos).

Honesto sobre el alcance de esta entrega: no existe todavía un esquema propio en ``contratos/`` para
``alta.json`` (ver «Pedidos» del README); se escribe con ``schema_version`` propio y se valida solo la
forma mínima en este módulo, para no bloquear la construcción a la espera de CT.

**`spend_cap` paramétrico** (docs/07 §9.1, D0 §3.4): ``limite_gasto_cuenta_meta = gasto_acumulado +
min(capital_anuncios_restante, campana.spend_cap_factor × Σ topes_de_test_en_curso)`` — el factor
sale SIEMPRE de ``parametros.yaml`` (nunca el literal 1,10). Los tres agregados de cartera
(``gasto_acumulado``, ``capital_anuncios_restante``, ``Σ topes_de_test_en_curso``) no tienen hoy una
fuente propia (el portafolio vivo es de O0/B1, aún no existe): :func:`calcular_limite_gasto_cuenta_meta`
los recibe explícitos (inyectados), nunca los inventa.

CLI::

    python -m infra.alta_oferta listar --oferta OF-202611-01 [--json]
    python -m infra.alta_oferta verificar --oferta OF-202611-01 [--json]
    python -m infra.alta_oferta ejecutar --oferta OF-202611-01 --ejecutar [--raiz RUTA] [--ahora ISO] [--json]
    python -m infra.alta_oferta spend-cap --gasto-acumulado-minor N --capital-anuncios-restante-minor N \
        --suma-topes-test-en-curso-minor N [--raiz RUTA] [--json]

Salida (convenciones §8): 0 completo o dry-run · 2 uso · 3 esquema u oferta_id inválido ·
4 ``--ejecutar`` fuera de modo prueba (``FABRICA_ENTORNO=produccion``) · 5 falta ``spend_cap_factor``
en ``parametros.yaml``.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from engine import comun, parametros as parametros_mod
from engine.errores import ErrorBloqueado, ErrorUso, ErrorValidacion
from engine.transporte import Transporte

__all__ = [
    "PasoAlta", "ResultadoPaso", "calcular_limite_gasto_cuenta_meta", "cargar_plantilla", "ejecutar",
    "listar", "main", "ruta_alta", "ruta_plantilla", "verificar",
]

_RX_OFERTA_ID = re.compile(r"^OF-[0-9]{6}-[0-9]{2}$")
SCHEMA_VERSION_ALTA = "0.1.0"  # propio: sin contrato dedicado todavía (ver README "Pedidos")


def _exigir_oferta_id(oferta_id: str) -> str:
    if not isinstance(oferta_id, str) or not _RX_OFERTA_ID.fullmatch(oferta_id):
        raise ErrorValidacion("--oferta debe tener la forma OF-AAAAMM-NN")
    return oferta_id


# ----------------------------------------------------------------------------------------------
# Plantilla (11 pasos)
# ----------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class PasoAlta:
    """Un paso de ``infra/plantillas/alta-oferta.yaml``."""

    paso: int
    id: str
    que: str
    quien: str
    como_se_comprueba: str
    item_preflight: str


def ruta_plantilla(raiz: Path | None = None) -> Path:
    """Ruta de ``infra/plantillas/alta-oferta.yaml`` (siempre bajo el CÓDIGO, no ``FABRICA_RAIZ``)."""
    base = raiz if raiz is not None else Path(__file__).resolve().parents[1]
    return base / "infra" / "plantillas" / "alta-oferta.yaml"


def cargar_plantilla(ruta: Path | None = None) -> list[PasoAlta]:
    """Carga y valida la forma de la plantilla de 11 pasos. ``ErrorValidacion`` (3) si está mal formada."""
    destino = ruta if ruta is not None else ruta_plantilla()
    try:
        datos = comun.cargar_yaml(destino)
    except FileNotFoundError as exc:
        raise ErrorValidacion(f"falta la plantilla de alta de oferta: {destino}") from exc
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise ErrorValidacion(f"plantilla de alta de oferta ilegible: {exc}") from exc
    pasos = datos.get("pasos") if isinstance(datos, dict) else None
    if not isinstance(pasos, list) or not pasos:
        raise ErrorValidacion("alta-oferta.yaml: se esperaba una lista «pasos» no vacía")
    vistos: set[str] = set()
    resultado: list[PasoAlta] = []
    for crudo in pasos:
        if not isinstance(crudo, dict) or not crudo.get("id"):
            raise ErrorValidacion("alta-oferta.yaml: paso sin «id»")
        id_ = str(crudo["id"])
        if id_ in vistos:
            raise ErrorValidacion(f"alta-oferta.yaml: id repetido {id_!r}")
        vistos.add(id_)
        resultado.append(PasoAlta(
            paso=int(crudo.get("paso", 0)), id=id_, que=str(crudo.get("que", "")),
            quien=str(crudo.get("quien", "")), como_se_comprueba=str(crudo.get("como_se_comprueba", "")),
            item_preflight=str(crudo.get("item_preflight", "")),
        ))
    resultado.sort(key=lambda p: p.paso)
    return resultado


def listar(oferta_id: str, *, plantilla: Sequence[PasoAlta] | None = None) -> list[dict[str, Any]]:
    """Lista en seco los 11 pasos para ``oferta_id`` (nunca verifica ni escribe nada)."""
    _exigir_oferta_id(oferta_id)
    pasos = plantilla if plantilla is not None else cargar_plantilla()
    return [{"paso": p.paso, "id": p.id, "que": p.que, "quien": p.quien,
             "como_se_comprueba": p.como_se_comprueba, "item_preflight": p.item_preflight} for p in pasos]


# ----------------------------------------------------------------------------------------------
# Verificación de solo lectura (inyectable; sin injectar -> pendiente, nunca verde falso)
# ----------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class ResultadoPaso:
    """Resultado de verificar UN paso: ``estado`` ∈ {ok, falta, pendiente_verificacion}."""

    id: str
    estado: str
    mensaje: str
    evidencia: Mapping[str, Any]


Verificador = Callable[[], ResultadoPaso]

_ESTADOS_PASO = ("ok", "falta", "pendiente_verificacion")


def _pendiente(paso: PasoAlta) -> ResultadoPaso:
    return ResultadoPaso(paso.id, "pendiente_verificacion",
                         "sin verificador inyectado para este paso en este entorno de construcción", {})


def verificar(oferta_id: str, *, plantilla: Sequence[PasoAlta] | None = None,
             verificadores: Mapping[str, Verificador] | None = None) -> list[ResultadoPaso]:
    """Verifica en SOLO LECTURA cada paso con el verificador inyectado; sin uno, queda «pendiente».

    Nunca escribe ni compra nada. Un verificador que lanza ``ErrorExterno`` se informa como
    ``pendiente_verificacion`` (una sonda caída no es lo mismo que «falta»: no se sabe).
    """
    _exigir_oferta_id(oferta_id)
    pasos = plantilla if plantilla is not None else cargar_plantilla()
    verificadores = verificadores or {}
    resultados: list[ResultadoPaso] = []
    for paso in pasos:
        v = verificadores.get(paso.id)
        if v is None:
            resultados.append(_pendiente(paso))
            continue
        try:
            r = v()
        except Exception as exc:  # noqa: BLE001 - una sonda rota no debe tumbar el resto de la verificación
            r = ResultadoPaso(paso.id, "pendiente_verificacion", f"verificador con error: {exc}", {})
        if r.estado not in _ESTADOS_PASO:
            raise ErrorValidacion(f"verificador {paso.id}: estado desconocido {r.estado!r}")
        resultados.append(r)
    return resultados


# ----------------------------------------------------------------------------------------------
# spend_cap paramétrico (docs/07 §9.1, D0 §3.4)
# ----------------------------------------------------------------------------------------------
def calcular_limite_gasto_cuenta_meta(*, gasto_acumulado_minor: int, capital_anuncios_restante_minor: int,
                                      spend_cap_factor: str, suma_topes_test_en_curso_minor: int) -> int:
    """``gasto_acumulado + min(capital_anuncios_restante, spend_cap_factor × Σ topes_de_test_en_curso)``.

    Todo en la unidad menor de ``moneda_limites`` (enteros). ``spend_cap_factor`` es la cadena decimal
    de ``parametros.yaml`` (``campana.spend_cap_factor``; NUNCA el literal 1,10). Redondeo hacia abajo
    (igual criterio que ``total_test_max = floor(...)`` de la regla X10 del validador): el resultado
    nunca puede quedar por encima de lo que los tres agregados permiten.
    """
    gasto = comun.exigir_importe(gasto_acumulado_minor, "gasto_acumulado_minor")
    capital = comun.exigir_importe(capital_anuncios_restante_minor, "capital_anuncios_restante_minor")
    suma_topes = comun.exigir_importe(suma_topes_test_en_curso_minor, "suma_topes_test_en_curso_minor")
    try:
        factor = Decimal(str(spend_cap_factor))
    except InvalidOperation as exc:
        raise ErrorValidacion(f"spend_cap_factor inválido: {spend_cap_factor!r}") from exc
    if factor <= 0:
        raise ErrorValidacion("spend_cap_factor debe ser positivo")
    tope_por_test = (factor * Decimal(suma_topes)).to_integral_value(rounding="ROUND_FLOOR")
    minimo = min(Decimal(capital), tope_por_test)
    return gasto + int(minimo)


# ----------------------------------------------------------------------------------------------
# Escritura (solo con --ejecutar, en modo prueba sobre una raíz temporal/fixture)
# ----------------------------------------------------------------------------------------------
def ruta_alta(raiz: Path, oferta_id: str) -> Path:
    return raiz / "ofertas" / oferta_id / "infra" / "alta.json"


def ejecutar(oferta_id: str, *, raiz: Path, resultados: Sequence[ResultadoPaso],
            ahora: Callable[[], datetime] = comun.ahora_utc) -> dict[str, Any]:
    """Escribe ``ofertas/<id>/infra/alta.json`` con los resultados de :func:`verificar` (IDs, sin secretos).

    Solo la llama la CLI con ``--ejecutar``; esta función en sí no decide el modo, solo escribe.
    """
    _exigir_oferta_id(oferta_id)
    t = comun.instante(ahora)
    documento = {
        "schema_version": SCHEMA_VERSION_ALTA,
        "oferta_id": oferta_id,
        "generado_en": comun.iso_z(t),
        "pasos": [{"id": r.id, "estado": r.estado, "mensaje": r.mensaje[:300], "evidencia": dict(r.evidencia)}
                  for r in resultados],
        "completo": all(r.estado == "ok" for r in resultados),
    }
    comun.escribir_atomico(ruta_alta(raiz, oferta_id), comun.json_canonico(documento))
    return documento


# ----------------------------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------------------------
def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m infra.alta_oferta",
                                 description="N01b: alta de oferta, 11 pasos humanos (listar, verificar en solo lectura, escribir).")
    sub = ap.add_subparsers(dest="cmd", required=True)

    pl = sub.add_parser("listar")
    pl.add_argument("--oferta", required=True)
    pl.add_argument("--json", action="store_true")

    pv = sub.add_parser("verificar")
    pv.add_argument("--oferta", required=True)
    pv.add_argument("--json", action="store_true")

    pe = sub.add_parser("ejecutar")
    pe.add_argument("--oferta", required=True)
    pe.add_argument("--ejecutar", action="store_true", help="sin esto, solo imprime el plan (dry-run)")
    pe.add_argument("--raiz")
    pe.add_argument("--ahora")
    pe.add_argument("--json", action="store_true")

    ps = sub.add_parser("spend-cap")
    ps.add_argument("--gasto-acumulado-minor", type=int, required=True)
    ps.add_argument("--capital-anuncios-restante-minor", type=int, required=True)
    ps.add_argument("--suma-topes-test-en-curso-minor", type=int, required=True)
    ps.add_argument("--raiz")
    ps.add_argument("--json", action="store_true")

    try:
        args = ap.parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2

    def cuerpo() -> int:
        env = dict(os.environ)
        raiz_arg = getattr(args, "raiz", None)
        ahora_arg = getattr(args, "ahora", None)
        if (raiz_arg or ahora_arg) and comun.entorno(env) == "produccion":
            raise ErrorUso("--raiz y --ahora no existen con FABRICA_ENTORNO=produccion")
        raiz = Path(raiz_arg).resolve() if raiz_arg else comun.raiz(env)

        if args.cmd == "listar":
            datos = {"oferta_id": args.oferta, "pasos": listar(args.oferta)}
            codigo = 0
        elif args.cmd == "verificar":
            resultados = verificar(args.oferta)
            datos = {"oferta_id": args.oferta,
                     "pasos": [{"id": r.id, "estado": r.estado, "mensaje": r.mensaje} for r in resultados]}
            codigo = 0
        elif args.cmd == "ejecutar":
            resultados = verificar(args.oferta)
            if not args.ejecutar:
                datos = {"oferta_id": args.oferta, "modo": "dry_run",
                         "pasos": [{"id": r.id, "estado": r.estado} for r in resultados]}
                codigo = 0
            else:
                if comun.entorno(env) == "produccion":
                    raise ErrorBloqueado("--ejecutar solo corre en modo prueba, sobre una raíz temporal/fixture")
                reloj = (lambda: comun.parsear_z(args.ahora)) if args.ahora else comun.ahora_utc
                documento = ejecutar(args.oferta, raiz=raiz, resultados=resultados, ahora=reloj)
                datos = {"oferta_id": args.oferta, "ruta": str(ruta_alta(raiz, args.oferta)),
                         "completo": documento["completo"]}
                codigo = 0
        else:  # spend-cap
            par = parametros_mod.cargar_parametros(raiz / "empresa" / "parametros.yaml")
            factor = par.valor("campana.spend_cap_factor")
            limite = calcular_limite_gasto_cuenta_meta(
                gasto_acumulado_minor=args.gasto_acumulado_minor,
                capital_anuncios_restante_minor=args.capital_anuncios_restante_minor,
                spend_cap_factor=factor,
                suma_topes_test_en_curso_minor=args.suma_topes_test_en_curso_minor,
            )
            datos = {"limite_gasto_cuenta_meta_minor": limite, "spend_cap_factor": factor}
            codigo = 0

        if args.json:
            print(json.dumps({"ok": codigo == 0, "modo": "dry_run", "codigo": codigo, "datos": datos, "avisos": []},
                             sort_keys=True, ensure_ascii=False))
        else:
            print(json.dumps(datos, ensure_ascii=False, sort_keys=True))
        return codigo

    return comun.ejecutar_cli(cuerpo)


if __name__ == "__main__":
    sys.exit(main())
