#!/usr/bin/env python3
"""L1-17 (parte XLSX) · Lint de hojas de cálculo (.xlsx/.xlsm) SIN abrirlas en una aplicación: inspecciona el ZIP/XML.

Detecta: macros (.xlsm o ``vbaProject.bin``), enlaces externos (``externalLinks``, ``connections.xml``, fórmulas con ``HYPERLINK/WEBSERVICE/IMPORTXML/
IMPORTDATA/IMPORTHTML/INDIRECT``), hojas ocultas («hidden»/«veryHidden»), filas o columnas ocultas, objetos incrustados, metadatos personales
(``creator``/``lastModifiedBy``) y fórmulas que DEVUELVEN UN ESTADO sobre el comprador (IF/IFS/SWITCH/CHOOSE con un literal tipo «obeso», «riesgo alto»,
«depresión», «deuda crítica»: «hoja que puntúa salud o deuda» = BLOQUEANTE).

NO calcula las fórmulas: los casos dorados de una calculadora los verifica `scripts/producto/calc_hoja` [PENDIENTE] o, mientras tanto, una persona
en la aplicación (references/humano-vs-agente.md). Una hoja de Google Sheets se exporta a .xlsx para linted y se revisa también en la interfaz.

Uso: python3 lint_hoja.py --hoja 04-producto/entregables/plantilla-vN.xlsx [más] [--permitir-autor "Marca Editorial"] [--salida X]
"""
from __future__ import annotations

import argparse
import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _comun as c  # noqa: E402
import _patrones as pt  # noqa: E402

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
FUNCIONES_EXTERNAS = re.compile(r"\b(?:HYPERLINK|WEBSERVICE|IMPORTXML|IMPORTDATA|IMPORTHTML|IMPORTRANGE|INDIRECT|CALL|REGISTER\.ID|EXEC)\s*\(", re.I)
RX_CONDICIONAL = re.compile(r"\b(?:IF|IFS|SWITCH|CHOOSE|SI|SI\.CONJUNTO|SEGÚN|WENN)\s*\(", re.I)
RX_LITERAL = re.compile(r'"([^"]{2,80})"')


def inspeccionar(ruta: Path, permitir_autor: set[str]) -> tuple[list[dict], dict]:
    h: list[dict] = []
    resumen = {"archivo": str(ruta), "hojas": [], "formulas": 0}
    if not zipfile.is_zipfile(ruta):
        h.append(c.hallazgo("L1-17", "BLOQUEANTE", "no es un .xlsx válido (ZIP)", str(ruta)))
        return h, resumen
    with zipfile.ZipFile(ruta) as z:
        nombres = z.namelist()
        if ruta.suffix.lower() == ".xlsm" or any(n.endswith("vbaProject.bin") for n in nombres):
            h.append(c.hallazgo("L1-17", "BLOQUEANTE", "contiene macros (VBA): el producto no lleva código ejecutable", str(ruta), "macros"))
        if any(n.startswith("xl/externalLinks/") for n in nombres) or "xl/connections.xml" in nombres:
            h.append(c.hallazgo("L1-17", "BLOQUEANTE", "enlaces externos o conexiones de datos: la hoja no puede llamar a nada fuera del archivo", str(ruta), "enlaces-externos"))
        if any(n.startswith(("xl/embeddings/", "xl/activeX/")) for n in nombres):
            h.append(c.hallazgo("L1-17", "BLOQUEANTE", "objetos incrustados o controles ActiveX", str(ruta), "incrustados"))
        try:
            wb = ET.fromstring(z.read("xl/workbook.xml"))
        except (KeyError, ET.ParseError):
            h.append(c.hallazgo("L1-17", "BLOQUEANTE", "falta o es ilegible xl/workbook.xml", str(ruta)))
            return h, resumen
        for s in wb.findall("m:sheets/m:sheet", NS):
            nombre, estado = s.get("name"), s.get("state", "visible")
            resumen["hojas"].append({"nombre": nombre, "estado": estado})
            if estado in ("hidden", "veryHidden"):
                h.append(c.hallazgo("L1-17", "BLOQUEANTE", f"hoja oculta «{nombre}» ({estado}): nada oculto en el producto", str(ruta), "hoja-oculta"))
        for dn in wb.findall("m:definedNames/m:definedName", NS):
            if dn.get("hidden") == "1":
                h.append(c.hallazgo("L1-17", "MAYOR", f"nombre definido oculto «{dn.get('name')}»", str(ruta), "nombre-oculto"))
        for n in sorted(x for x in nombres if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", x)):
            try:
                ws = ET.fromstring(z.read(n))
            except ET.ParseError:
                h.append(c.hallazgo("L1-17", "BLOQUEANTE", f"{n} ilegible", str(ruta)))
                continue
            ocultas = len([r for r in ws.iter("{%s}row" % NS["m"]) if r.get("hidden") == "1"]) + len([x for x in ws.iter("{%s}col" % NS["m"]) if x.get("hidden") == "1"])
            if ocultas:
                h.append(c.hallazgo("L1-17", "MAYOR", f"{ocultas} fila(s)/columna(s) ocultas en {n}: mostrar o eliminar", str(ruta), "filas-ocultas"))
            for f in ws.iter("{%s}f" % NS["m"]):
                formula = f.text or ""
                resumen["formulas"] += 1
                if FUNCIONES_EXTERNAS.search(formula):
                    h.append(c.hallazgo("L1-17", "BLOQUEANTE", f"fórmula con función externa o indirecta: {formula[:80]}", f"{ruta}:{n}", "formula-externa"))
                if RX_CONDICIONAL.search(formula):
                    for lit in RX_LITERAL.findall(formula):
                        if any(re.search(p, lit, re.I) for p in pt.ESTADOS_HOJA):
                            h.append(c.hallazgo("L1-17", "BLOQUEANTE", f"la hoja puntúa o etiqueta un estado del comprador («{lit}»): una calculadora devuelve números con supuestos visibles, nunca un estado de salud o deuda", f"{ruta}:{n}", "hoja-puntua-estado"))
        try:
            core = ET.fromstring(z.read("docProps/core.xml"))
            for tag in ("creator", "lastModifiedBy"):
                el = core.find(".//{http://purl.org/dc/elements/1.1/}creator") if tag == "creator" else core.find(".//{http://schemas.openxmlformats.org/package/2006/metadata/core-properties}lastModifiedBy")
                val = (el.text or "").strip() if el is not None else ""
                if val and val not in permitir_autor and val.lower() not in {"openpyxl", "microsoft office user", "libreoffice"}:
                    h.append(c.hallazgo("L1-17", "MAYOR", f"metadato «{tag}» = «{val}»: sin autor personal por defecto (usar la marca o vaciarlo)", f"{ruta}:docProps/core.xml", "metadato-personal"))
        except (KeyError, ET.ParseError):
            pass
    return h, resumen


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--hoja", nargs="+", required=True)
    ap.add_argument("--permitir-autor", action="append", default=[])
    ap.add_argument("--salida")
    a = ap.parse_args(argv)
    h: list[dict] = []
    res = []
    for r in a.hoja:
        p = Path(r)
        if not p.is_file():
            return c.error_uso(f"no existe {r}", 3)
        hh, rr = inspeccionar(p, set(a.permitir_autor))
        h += hh
        res.append(rr)
    return c.emitir("lint_hoja", ["L1-17"], h, {"hojas_revisadas": res}, a.salida)


if __name__ == "__main__":
    sys.exit(main())
