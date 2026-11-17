#!/usr/bin/env python3
"""L1-05 · L1-09 · L1-13 · L1-14 · L1-15 (parcial) · Lint léxico del contenido del producto (HTML/MD/TXT de ``entregables/fuente``).

Detecta, por idioma del ``locale``: placeholders y marcas pendientes ([VERIFICAR], [SUPUESTO]); frases de chatbot; palabras vetadas (cura, resultado,
ingresos); diagnóstico y atributos del lector; testimonios y resultados personales inventados; credenciales falsas («diseñado por nutricionistas»);
servicio humano, comunidad, vivo, suscripción o mantenimiento; secretos, rutas personales y correos; formato numérico ajeno al locale (separador de
miles de otro idioma junto a una unidad); literales obligatorios ausentes (--requiere etiqueta=texto: aviso de seguridad, bloque de ayuda, divulgación
de IA); líneas de ayuda de OTRO país (--ayuda-numeros = los de ayuda_por_pais.yaml del país del lector).

Límite honesto: es un léxico INTERINO (ver _patrones.py). No atrapa eufemismos ni juzga el contexto: lo que pasa este lint lo sigue leyendo el QA (L2).
Un término vetado dentro de una cita entrecomillada de ≤ --cita-max-palabras se baja a MENOR (cita atribuida de una fuente).

Uso: python3 lint_contenido.py --producto 04-producto/entregables/fuente [más rutas] --locale es-ES [--requiere "ayuda=Si necesitas ayuda ahora: ..."]
        [--ayuda-numeros 112,016,024] [--reglas-x1 compliance/reglas_sensibles.yaml] [--salida X]
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _comun as c  # noqa: E402
import _patrones as pt  # noqa: E402


def linea_de(texto: str, pos: int) -> int:
    return texto.count("\n", 0, pos) + 1


def buscar(patrones, texto: str):
    for rx in pt.compilar(patrones):
        for m in rx.finditer(texto):
            yield m


def reglas_x1(ruta: str, locale: str) -> dict[str, list[str]]:
    """Patrones rojo/amarillo de ``compliance/reglas_sensibles.yaml`` (X1) para el locale, más los generales."""
    d = c.cargar_yaml(ruta)
    rojo, amarillo = [], []
    for cat in (d.get("generales") or {}).values():
        rojo += cat.get("rojo", []) or []
        amarillo += cat.get("amarillo", []) or []
    for macro in ((d.get("locales") or {}).get(locale) or {}).values():
        rojo += macro.get("rojo", []) or []
        amarillo += macro.get("amarillo", []) or []
    return {"rojo": rojo, "amarillo": amarillo}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--producto", nargs="+", required=True)
    ap.add_argument("--locale", required=True)
    ap.add_argument("--requiere", action="append", default=[], help="etiqueta=texto literal que debe figurar (repetible)")
    ap.add_argument("--ayuda-numeros", default="", help="números de ayuda del país del lector (de ayuda_por_pais.yaml), separados por coma")
    ap.add_argument("--reglas-x1", help="compliance/reglas_sensibles.yaml (u otro con el mismo formato) para sumar los patrones de X1")
    ap.add_argument("--cita-max-palabras", type=int, default=25)
    ap.add_argument("--salida")
    a = ap.parse_args(argv)
    idi, pais = pt.idioma(a.locale), pt.pais(a.locale)
    try:
        archivos = c.expandir_rutas(a.producto, {".md", ".txt", ".html", ".htm"})
        x1 = reglas_x1(a.reglas_x1, a.locale) if a.reglas_x1 else {"rojo": [], "amarillo": []}
    except (OSError, ValueError, c.ParametroFaltante) as e:
        return c.error_uso(f"entrada inválida: {e}", 3)
    if idi not in pt.VETADAS:
        pt_aviso = f"sin léxico para el idioma «{idi}»: lint parcial (se usan solo patrones universales); el QA lingüístico debe cubrir claims y diagnóstico"
    else:
        pt_aviso = None
    h: list[dict] = []
    if pt_aviso:
        h.append(c.hallazgo("L1-05", "MAYOR", pt_aviso, a.locale, "idioma-sin-lexico"))
    permitidos = {x.strip() for x in a.ayuda_numeros.split(",") if x.strip()}
    permitidos_digitos = {re.sub(r"\D", "", x) for x in permitidos}
    todo = ""
    for arch in archivos:
        texto = c.leer_texto(arch)
        todo += "\n" + texto
        citas = c.tramos_entrecomillados(texto)

        def en_cita(pos: int) -> bool:
            return any(s <= pos < e and c.contar_palabras(texto[s:e]) <= a.cita_max_palabras for s, e in citas)

        def reg(check, sev, msg, m, patron):
            sev2 = "MENOR" if sev in ("BLOQUEANTE", "MAYOR") and en_cita(m.start()) and check in ("L1-05", "L1-09") and patron in ("claim-vetado", "diagnostico", "aviso-lexico") else sev
            h.append(c.hallazgo(check, sev2, f"{msg}: «{m.group(0)[:80]}»" + (" (dentro de una cita: verificar atribución)" if sev2 != sev else ""), f"{arch}:{linea_de(texto, m.start())}", patron))

        for m in buscar(pt.PLACEHOLDERS, texto):
            reg("L1-09", "MAYOR", "placeholder sin completar (Anexo B: MAYOR)", m, "placeholder")
        for rx in pt.PLACEHOLDERS_CS:
            for m in re.finditer(rx, texto):
                reg("L1-09", "MAYOR", "placeholder sin completar (Anexo B: MAYOR)", m, "placeholder")
        for m in buscar(pt.MARCAS_PENDIENTES, texto):
            reg("L1-09", "MAYOR", "marca pendiente en el entregable ([VERIFICAR]/[SUPUESTO] no pueden quedar en lo que recibe el comprador)", m, "marca-pendiente")
        for m in buscar(pt.CHATBOT.get(idi, []) + pt.CHATBOT["en"], texto):
            reg("L1-09", "MAYOR", "frase de chatbot", m, "frase-chatbot")
        v = pt.VETADAS.get(idi, {"rojo": [], "aviso": []})
        for m in buscar(v["rojo"] + x1["rojo"], texto):
            reg("L1-05", "BLOQUEANTE", "término vetado (cura, resultado, ingreso o facilidad como promesa)", m, "claim-vetado")
        for m in buscar(v["aviso"] + x1["amarillo"], texto):
            reg("L1-05", "MAYOR", "término de riesgo a revisar", m, "aviso-lexico")
        dg = pt.DIAGNOSTICO.get(idi, {"rojo": [], "aviso": []})
        for m in buscar(dg["rojo"], texto):
            reg("L1-05", "BLOQUEANTE", "atribuye una condición al lector", m, "diagnostico")
        for m in buscar(dg["aviso"], texto):
            reg("L1-05", "MAYOR", "lenguaje de diagnóstico (válido solo para negarlo: «no es un diagnóstico»)", m, "aviso-lexico")
        for m in buscar(pt.TESTIMONIO.get(idi, []), texto):
            reg("L1-09", "BLOQUEANTE", "testimonio, caso o resultado personal (inventado salvo prueba con permiso)", m, "testimonio")
        for m in buscar(pt.CREDENCIALES.get(idi, []), texto):
            reg("L1-05", "BLOQUEANTE", "autoridad o credencial no documentada", m, "credencial-falsa")
        for m in buscar(pt.SERVICIO.get(idi, []) + (pt.SERVICIO["en"] if idi != "en" else []), texto):
            reg("L1-14", "BLOQUEANTE", "servicio humano, comunidad, vivo, suscripción o mantenimiento continuo", m, "servicio-oculto")
        for m in buscar(pt.SECRETOS, texto):
            reg("L1-09", "BLOQUEANTE", "posible secreto o clave", m, "secreto")
        for m in buscar(pt.RUTAS_PERSONALES, texto):
            reg("L1-04", "MAYOR", "ruta personal del equipo", m, "ruta-personal")
        for m in re.finditer(pt.RX_EMAIL, texto, pt.I):
            reg("L1-09", "MAYOR", "correo o dato personal (el producto no lleva correos de personas)", m, "pii")
        # L1-13 formato numérico
        for n in c.numeros_en_texto(texto, a.locale):
            if not n["banderas"]:
                continue
            sev = "BLOQUEANTE" if n["unidad"] else "MAYOR"
            h.append(c.hallazgo("L1-13", sev, f"número «{n['token']}»{' ' + n['unidad'] if n['unidad'] else ''}: formato ajeno a {a.locale} {n['banderas']} (¿{n['valor']}?). Junto a una unidad cambia la dosis o la cantidad", f"{arch}:{n['linea']}", "separador-ajeno"))
        # L1-15 líneas de ayuda de otro país
        for m in re.finditer(r"(?<![\d])(\+?\d[\d \- ]{1,16}\d)(?![\d])", texto):
            dig = re.sub(r"\D", "", m.group(1))
            paises_linea = pt.LINEAS_CONOCIDAS.get(dig)
            if not paises_linea or dig in permitidos_digitos:
                continue
            if len(dig) <= 4 and not re.search(pt.CONTEXTO_LINEA, texto[max(0, m.start() - 60):m.start()], pt.I):
                continue
            if pais and pais in paises_linea:
                continue
            h.append(c.hallazgo("L1-15", "BLOQUEANTE", f"línea de ayuda {m.group(1).strip()} es de {sorted(paises_linea)} y el lector es de {pais or '?'}: los números salen LITERALES de ayuda_por_pais.yaml del país del lector", f"{arch}:{linea_de(texto, m.start())}", "ayuda-de-otro-pais"))
    # literales obligatorios (aviso de seguridad, ayuda, IA)
    norm_todo = c.normalizar_busqueda(todo)
    for req in a.requiere:
        if "=" not in req:
            return c.error_uso("--requiere espera etiqueta=texto", 2)
        etiqueta, literal = req.split("=", 1)
        if c.normalizar_busqueda(literal) not in norm_todo:
            h.append(c.hallazgo("L1-15", "BLOQUEANTE", f"falta el literal obligatorio «{etiqueta}» (debe figurar tal cual, tomado de la fuente de verdad)", ",".join(map(str, a.producto)), "literal-ausente"))
    return c.emitir("lint_contenido", ["L1-05", "L1-09", "L1-13", "L1-14", "L1-15"], h, {
        "archivos": len(archivos), "locale": a.locale, "palabras": c.contar_palabras(todo), "lexico_idioma": idi in pt.VETADAS,
    }, a.salida)


if __name__ == "__main__":
    sys.exit(main())
