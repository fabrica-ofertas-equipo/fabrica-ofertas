#!/usr/bin/env python3
"""tanda — ayudas deterministas del modo «tanda» manual de D6 (B1-16): armar el encargo y la bandeja «por aprobar». Sin red, sin gasto.

  plan     reparte las piezas de una tanda entre relevos, ángulos nuevos y traducciones (prioridad de la fuente: primero lo que se cansa,
           después ángulos nuevos y traducciones) sin pasar del máximo ni inventar pedidos que no existen.
  bandeja  une la matriz, el informe de `qc6.py lote` y el régimen de aprobación en `por-aprobar.json`.

Régimen de aprobación (lo decide el dueño; NO lo decide este script): `total` (el dueño ve cada pieza) o `muestreo` (el dueño ve las que
`qc6` marca y una muestra; las demás quedan «lista_para_sello_x1» y solo el sello vigente de X1 por plantilla, verificado por el motor,
permite activarlas). `muestreo` sin `--confirmado-por-dueno` se rechaza. Este script nunca aprueba nada ni verifica una firma.

Códigos: 0 ok · 3 entrada o régimen inválido · 2 uso.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any, Mapping, Sequence

VERSION = "0.1.0"
# [SUPUESTO] (la fuente no da piezas por tanda; B1-14): 5 candidatos por idioma por día como mínimo, 10 como máximo. Ver references/modo-tanda.md §6.
MIN_DEFECTO, MAX_DEFECTO = 5, 10
MUESTRA_PCT_DEFECTO = 20  # [SUPUESTO]
REGIMENES = ("total", "muestreo")


class ErrorEntrada(Exception):
    """Entrada inválida (código 3)."""


class ErrorUso(Exception):
    """Uso incorrecto (código 2)."""


def repartir(objetivo: int, relevos: int, angulos: int, traducciones: int, *, minimo: int = MIN_DEFECTO, maximo: int = MAX_DEFECTO) -> dict[str, Any]:
    """Composición de una tanda. Relevos primero; el resto se alterna entre ángulos nuevos y traducciones (empieza por ángulos).
    Si no hay pedidos suficientes la tanda queda más corta y se dice (``faltan``); nunca se rellena con piezas sin motivo."""
    if min(objetivo, relevos, angulos, traducciones, minimo) < 0 or maximo < minimo:
        raise ErrorEntrada("cantidades negativas o máximo < mínimo")
    objetivo_efectivo = max(minimo, min(objetivo, maximo))
    r = min(relevos, objetivo_efectivo)
    a = t = 0
    resto = objetivo_efectivo - r
    turno = "a"
    while resto > 0 and (a < angulos or t < traducciones):
        if turno == "a" and a < angulos:
            a += 1
            resto -= 1
        elif turno == "t" and t < traducciones:
            t += 1
            resto -= 1
        turno = "t" if turno == "a" else "a"
    produce = r + a + t
    avisos = []
    if objetivo != objetivo_efectivo:
        avisos.append(f"objetivo {objetivo} ajustado a {objetivo_efectivo} por los límites [{minimo}, {maximo}]")
    if produce < minimo:
        avisos.append(f"solo hay pedidos para {produce} pieza(s), menos del mínimo {minimo}: no se rellena con piezas sin motivo")
    if relevos > objetivo_efectivo:
        avisos.append(f"{relevos - objetivo_efectivo} relevo(s) quedan para la tanda siguiente (la fatiga no espera: subir el máximo es decisión de S-A/dueño)")
    return {"objetivo": objetivo, "objetivo_efectivo": objetivo_efectivo, "produce": produce, "faltan": objetivo_efectivo - produce,
            "composicion": {"relevos": r, "angulos_nuevos": a, "traducciones": t}, "avisos": avisos}


def cmd_plan(a: argparse.Namespace) -> int:
    rep = repartir(a.objetivo, a.relevos, a.angulos_nuevos, a.traducciones, minimo=a.minimo, maximo=a.maximo)
    encargo = {
        "schema_version": "0.1.0", "tipo": "tanda", "modo": "manual", "oferta_id": a.oferta_id, "locale": a.locale, "fecha": a.fecha or date.today().isoformat(),
        **rep, "prioridad": ["relevos", "angulos_nuevos", "traducciones"], "ruta": "A (HTML a PNG, 0 créditos)",
        "limites": {"minimo": a.minimo, "maximo": a.maximo, "estado": "[SUPUESTO] pendiente de parametros.yaml (PEDIDOS.md #1)"},
        "reglas": ["una variable por vez (SKILL §5.8)", "cada gancho pasa por ganchos.py rechazar antes de redactarse", "qc6 lote antes de dejar la tanda en «por aprobar»",
                   "de noche se produce y a la tarde se carga: la tanda no sube nada a Meta"],
    }
    texto = json.dumps(encargo, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if a.salida:
        a.salida.parent.mkdir(parents=True, exist_ok=True)
        a.salida.write_text(texto, encoding="utf-8")
    print(json.dumps(encargo, ensure_ascii=False, sort_keys=True) if a.json else
          f"tanda {encargo['locale']} {encargo['fecha']}: {rep['produce']} pieza(s) = relevos {rep['composicion']['relevos']} + ángulos nuevos "
          f"{rep['composicion']['angulos_nuevos']} + traducciones {rep['composicion']['traducciones']}" + ("".join(f"\n  aviso: {x}" for x in rep["avisos"])))
    return 0


def _cargar(ruta: Path) -> Any:
    try:
        return json.loads(Path(ruta).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ErrorEntrada(f"no se pudo leer {ruta}: {exc}") from exc


def en_muestra(sha256: str, pct: int) -> bool:
    """Muestra determinista: una pieza entra si su hash cae en el primer ``pct`` % (misma pieza, misma decisión)."""
    return int(hashlib.sha256(sha256.encode("utf-8")).hexdigest()[:8], 16) % 100 < pct


def sello_vigente(sellos: Mapping[str, Any], plantilla_id: str, fecha: str) -> bool:
    """El sello figura y no venció. NO verifica la firma criptográfica: eso lo hace el motor (compliance.sellar / engine.guard)."""
    s = sellos.get(plantilla_id)
    return bool(isinstance(s, Mapping) and s.get("sello_ref") and str(s.get("vigente_hasta", "")) >= fecha)


def armar_bandeja(matriz: Mapping[str, Any], qc6: Mapping[str, Any], *, regimen: str, confirmado: bool, muestra_pct: int, sellos: Mapping[str, Any], fecha: str) -> dict[str, Any]:
    if regimen not in REGIMENES:
        raise ErrorEntrada(f"régimen {regimen!r} fuera de {REGIMENES}")
    if regimen == "muestreo" and not confirmado:
        raise ErrorEntrada("el régimen «muestreo» exige --confirmado-por-dueno: lo elige el dueño, no el Maker (PEDIDOS.md #2). Mientras tanto, «total».")
    if not 0 <= muestra_pct <= 100:
        raise ErrorEntrada("muestra_pct fuera de 0..100")
    filas = {x.get("ad_name"): x for x in (matriz.get("anuncios") or []) if isinstance(x, Mapping)}
    piezas = []
    for p in qc6.get("piezas", []):
        base = str(p["pieza"]).split("@")[0]
        fila = filas.get(base, {})
        plantilla = fila.get("plantilla_id") or fila.get("variante_formato") or "estatico-html"
        estado, sha = p["estado"], p.get("sha256") or ""
        if estado == "falla":
            accion, motivo = "corregir_o_descartar", "qc6 falla: " + "; ".join(f"{x['id']}" for x in p["puntos"] if x["estado"] == "falla")
        elif regimen == "total":
            accion, motivo = "aprobar_dueno", "régimen total"
        elif estado == "revisar":
            accion, motivo = "aprobar_dueno", "qc6 marcó revisar"
        elif not sello_vigente(sellos, plantilla, fecha):
            accion, motivo = "aprobar_dueno", f"la plantilla «{plantilla}» no tiene sello de X1 vigente"
        elif en_muestra(sha, muestra_pct):
            accion, motivo = "aprobar_dueno", f"muestra del {muestra_pct} %"
        else:
            accion, motivo = "lista_para_sello_x1", "qc6 ok, plantilla con sello vigente, fuera de la muestra: no se activa sin la verificación del motor"
        piezas.append({"ad_name": p["pieza"], "archivo": p.get("archivo"), "sha256": sha or None, "plantilla_id": plantilla, "hook_tipo": fila.get("hook_tipo"),
                       "qc6": estado, "accion": accion, "motivo": motivo})
    cuentas = {a: sum(1 for x in piezas if x["accion"] == a) for a in ("aprobar_dueno", "lista_para_sello_x1", "corregir_o_descartar")}
    return {"schema_version": "0.1.0", "tipo": "por-aprobar", "fecha": fecha, "regimen": regimen, "regimen_confirmado_por_dueno": confirmado,
            "muestra_pct": muestra_pct if regimen == "muestreo" else None, "total": len(piezas), **cuentas, "piezas": piezas,
            "aviso": "Nada de esto aprueba ni activa una pieza: la aprobación es del dueño (gate) y la activación, del motor con el sello vigente de X1."}


def cmd_bandeja(a: argparse.Namespace) -> int:
    d: Path = a.tanda_dir
    matriz = _cargar(a.matriz or d / "matriz.json")
    qc6 = _cargar(a.qc6 or d / "qc6.json")
    sellos = _cargar(a.sellos) if a.sellos else {}
    if qc6.get("modo") == "simulado":
        raise ErrorEntrada("qc6.json es de una corrida simulada: no es evidencia, hay que correr qc6 lote en real")
    b = armar_bandeja(matriz, qc6, regimen=a.regimen, confirmado=a.confirmado_por_dueno, muestra_pct=a.muestra_pct, sellos=sellos, fecha=a.fecha or date.today().isoformat())
    salida = a.salida or d / "por-aprobar.json"
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(json.dumps(b, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(b, ensure_ascii=False, sort_keys=True) if a.json else
          f"por-aprobar: {b['total']} pieza(s) · dueño {b['aprobar_dueno']} · lista para sello {b['lista_para_sello_x1']} · corregir {b['corregir_o_descartar']} → {salida}")
    return 0


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="tanda.py", description="Modo tanda manual de D6: encargo y bandeja «por aprobar».")
    sub = p.add_subparsers(dest="cmd", required=True)
    pl = sub.add_parser("plan")
    pl.add_argument("--locale", required=True)
    pl.add_argument("--oferta-id", dest="oferta_id")
    pl.add_argument("--fecha")
    pl.add_argument("--objetivo", type=int, required=True)
    pl.add_argument("--relevos", type=int, default=0, help="creativos cansados con pedido de relevo")
    pl.add_argument("--angulos-nuevos", dest="angulos_nuevos", type=int, default=0, help="ángulos permitidos de oferta.angulos[] aún sin probar")
    pl.add_argument("--traducciones", type=int, default=0, help="ganadores de otro idioma por traducir")
    pl.add_argument("--minimo", type=int, default=MIN_DEFECTO)
    pl.add_argument("--maximo", type=int, default=MAX_DEFECTO)
    pl.add_argument("--salida", type=Path)
    pl.add_argument("--json", action="store_true")
    pl.set_defaults(func=cmd_plan)
    ba = sub.add_parser("bandeja")
    ba.add_argument("--tanda-dir", type=Path, required=True, dest="tanda_dir")
    ba.add_argument("--matriz", type=Path)
    ba.add_argument("--qc6", type=Path, help="informe de `qc6.py lote --salida` (default <tanda>/qc6.json)")
    ba.add_argument("--regimen", choices=REGIMENES, required=True, help="sin default: lo elige el dueño")
    ba.add_argument("--confirmado-por-dueno", action="store_true", dest="confirmado_por_dueno")
    ba.add_argument("--muestra-pct", type=int, default=MUESTRA_PCT_DEFECTO, dest="muestra_pct")
    ba.add_argument("--sellos", type=Path, help='JSON {"<plantilla_id>": {"sello_ref": "...", "vigente_hasta": "AAAA-MM-DD"}}')
    ba.add_argument("--fecha")
    ba.add_argument("--salida", type=Path)
    ba.add_argument("--json", action="store_true")
    ba.set_defaults(func=cmd_bandeja)
    return p


def main(argv: Sequence[str] | None = None) -> int:
    try:
        a = _parser().parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2
    try:
        return int(a.func(a))
    except ErrorEntrada as exc:
        print(f"entrada inválida: {exc}", file=sys.stderr)
        return 3
    except ErrorUso as exc:
        print(f"error de uso: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
