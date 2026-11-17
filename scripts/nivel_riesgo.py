"""Nivel de riesgo POR CANDIDATO a partir de los ejes P, C, E, N: tabla única (nota 25 §2.3, D-01, C-24).

Es la ÚNICA implementación de ejes → nivel (el LLM no calcula el nivel). Promueve a ``scripts/`` el
sustituto probado ``.claude/skills/x1-compliance/scripts/nivel_ejes.py`` (230 casos de la suite
``docs/_historial/hwr-semillas/casos-frontera.yaml`` sin discrepancias), con tres diferencias:
  * los errores son ``ErrorFabrica`` tipados (convenciones §8: dato inválido → 3, nunca un fallo interno);
  * ``riesgo_de_candidato`` devuelve el bloque ``riesgo`` completo con ``version_tabla`` y ``ejes_codigo``;
  * falla CERRADO ante cualquier código de eje desconocido, ausente o inconsistente.

El riesgo se mide por la PROMESA, el contenido, el encuadre y la categoría de negocio del candidato,
nunca por el tema (decisión 13 corregida por el dueño): este módulo solo ve los cuatro ejes ya
asignados, no el tema.

Uso::

    python -m scripts.nivel_riesgo --P P2n --C C1 --E E0 --N N1 [--zona-gris] [--reencuadre] [--json]
    python -m scripts.nivel_riesgo --suite docs/_historial/hwr-semillas/casos-frontera.yaml

Sin red, sin escritura, sin secretos. Salida (convenciones §8): 0 ok · 1 interno · 2 uso · 3 dato
inválido o discrepancias de la suite.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

from engine.comun import ejecutar_cli
from engine.errores import ErrorUso, ErrorValidacion

#: Versión de la tabla de la nota 25 §2.3 (se graba en cada ``riesgo`` para poder re-evaluar si cambia).
VERSION_TABLA = "nota25-2.3-v1"

ESCALA: dict[str, tuple[str, ...]] = {
    "P": ("P0", "P1", "P2s", "P2n", "P3"),
    "C": ("C0", "C1", "C2", "C3"),
    "E": ("E0", "E1", "E2", "E3"),
    "N": ("N0", "N1", "N1s", "N2", "N3"),
}

#: código → color por eje (nota 25 §2.3, «equivalencia código → color»).
COLOR: dict[str, str] = {
    "P0": "verde", "P1": "verde", "P2s": "amarillo", "P2n": "rojo", "P3": "rojo",
    "C0": "verde", "C1": "verde", "C2": "amarillo", "C3": "rojo",
    "E0": "verde", "E1": "verde", "E2": "rojo", "E3": "rojo",
    "N0": "verde", "N1": "verde", "N1s": "amarillo", "N2": "rojo", "N3": "rojo",
}
ORDEN: dict[str, int] = {"verde": 0, "amarillo": 1, "rojo": 2}
EJES: tuple[str, ...] = ("P", "C", "E", "N")


def _validar_ejes(ejes: Mapping[str, Any]) -> dict[str, str]:
    """Copia validada de ``ejes``: los cuatro presentes y dentro de su escala (falla cerrado)."""
    if not isinstance(ejes, Mapping):
        raise ErrorValidacion("los ejes deben ser un objeto {P, C, E, N}")
    extra = sorted(set(ejes) - set(EJES))
    if extra:
        raise ErrorValidacion(f"ejes desconocidos: {', '.join(map(str, extra))}")
    limpio: dict[str, str] = {}
    for eje, escala in ESCALA.items():
        valor = ejes.get(eje)
        if valor not in escala:
            raise ErrorValidacion(f"eje {eje} inválido: {valor!r}; admitidos: {', '.join(escala)}")
        limpio[eje] = valor
    return limpio


def calcular(ejes: Mapping[str, Any], *, fuera_de_macro: bool = False, zona_gris: bool = False,
             hay_reencuadre: bool = False) -> dict[str, Any]:
    """``{nivel, subnivel, colores, veredicto_riesgo}`` para los ejes dados.

    ``fuera_de_macro`` (diagnóstico de lo que no cae en salud/relaciones/dinero) devuelve ``nivel=None``
    y ``veredicto_riesgo='bloquea'``: nunca puede lanzarse. ``zona_gris`` (cerrada por el dueño) pasa un
    amarillo-A a ``pasa_con_gate``; ``hay_reencuadre`` (existe un reencuadre que conserva el deseo y baja
    a amarillo o menos) convierte un rojo en ``reformular``. Errores: ``ErrorValidacion`` (3).
    """
    e = _validar_ejes(ejes)
    colores = {eje: COLOR[e[eje]] for eje in EJES}
    if fuera_de_macro:
        return {"nivel": None, "subnivel": None, "colores": colores, "veredicto_riesgo": "bloquea"}
    if e["N"] == "N0":
        raise ErrorValidacion("N0 solo existe fuera de macro-nicho (nota 25 §2.2): todo candidato en macro es al menos N1")
    peor = max(colores.values(), key=ORDEN.__getitem__)
    if peor == "rojo":
        return {"nivel": "rojo", "subnivel": None, "colores": colores,
                "veredicto_riesgo": "reformular" if hay_reencuadre else "bloquea"}
    if peor == "amarillo":
        amarillos = sum(1 for c in colores.values() if c == "amarillo")
        sub = "B" if amarillos >= 2 else "A"
        veredicto = "pasa_con_gate" if (sub == "B" or zona_gris) else "pasa_con_revision"
        return {"nivel": "amarillo", "subnivel": sub, "colores": colores, "veredicto_riesgo": veredicto}
    return {"nivel": "verde", "subnivel": None, "colores": colores, "veredicto_riesgo": "pasa"}


def riesgo_de_candidato(ejes: Mapping[str, Any], *, zona_gris: bool = False, hay_reencuadre: bool = False,
                        **extras: Any) -> dict[str, Any]:
    """Bloque ``riesgo`` de un candidato EN macro-nicho: ejes, colores, nivel, subnivel, veredicto y versión.

    ``extras`` (categoría, claims, ángulo, fuentes, reencuadre…) los aporta quien arma el candidato y se
    copian tal cual al resultado SIN influir en el nivel (el nivel sale solo de los cuatro ejes). Un
    resultado ``rojo`` o con ``veredicto_riesgo`` que no empieza por ``pasa`` NO es lanzable: la puerta de
    entrada de D1 (§3.8.1 regla 4) decide con ``nivel`` y ``subnivel``.
    """
    r = calcular(ejes, zona_gris=zona_gris, hay_reencuadre=hay_reencuadre)
    salida: dict[str, Any] = dict(extras)
    salida.update({
        "ejes_codigo": _validar_ejes(ejes),
        "colores": r["colores"],
        "nivel": r["nivel"],
        "subnivel": r["subnivel"],
        "veredicto_riesgo": r["veredicto_riesgo"],
        "version_tabla": VERSION_TABLA,
    })
    return salida


def _cargar_yaml(ruta: Path) -> Any:
    import yaml  # PyYAML está en el .venv del proyecto

    try:
        return yaml.safe_load(ruta.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ErrorUso(f"no se pudo leer la suite {ruta}: {exc.strerror}") from exc


def verificar_suite(ruta: Path) -> list[str]:
    """Compara nivel, subnivel y veredicto calculados con los de cada caso de la suite; devuelve las discrepancias."""
    datos = _cargar_yaml(ruta)
    if not isinstance(datos, Mapping) or not isinstance(datos.get("casos"), list):
        raise ErrorValidacion("la suite no tiene la forma {casos: [...]}")
    errores: list[str] = []
    for caso in datos["casos"]:
        fuera = caso["macro_nicho_esperado"] == "fuera_de_macro_nicho"
        try:
            r = calcular(caso["ejes"], fuera_de_macro=fuera, zona_gris=bool(caso.get("zona_gris")),
                         hay_reencuadre=caso["veredicto_esperado"] == "reformular")
        except ErrorValidacion as exc:
            if fuera:  # los fuera de macro llevan N0 «solo diagnóstico»: no se calcula nivel
                continue
            errores.append(f"{caso['id']}: {exc.mensaje}")
            continue
        esperado = (None if fuera else str(caso["nivel_esperado"]).lower(), caso.get("subnivel"), caso["veredicto_esperado"])
        obtenido = (r["nivel"], r["subnivel"], r["veredicto_riesgo"])
        if esperado != obtenido:
            errores.append(f"{caso['id']}: esperado {esperado} != calculado {obtenido}")
    return errores


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m scripts.nivel_riesgo", description="Nivel de riesgo por ejes P/C/E/N (nota 25 §2.3)")
    for eje in EJES:
        p.add_argument(f"--{eje}", choices=ESCALA[eje])
    p.add_argument("--zona-gris", action="store_true", help="zona gris cerrada por el dueño (amarillo-A pasa a pasa_con_gate)")
    p.add_argument("--reencuadre", action="store_true", help="existe un reencuadre que conserva el deseo y baja a <= amarillo")
    p.add_argument("--fuera-de-macro", action="store_true")
    p.add_argument("--suite", type=Path, help="casos-frontera.yaml: verifica la aritmética de toda la suite")
    p.add_argument("--json", action="store_true")
    return p


def _principal(argv: list[str] | None) -> int:
    try:
        a = _parser().parse_args(argv)
    except SystemExit as exc:
        if exc.code in (0, None):
            return 0
        raise ErrorUso("argumentos inválidos (ver --help)") from None
    if a.suite:
        errores = verificar_suite(a.suite)
        print("\n".join(errores) if errores else "suite: 0 discrepancias")
        return 3 if errores else 0
    if not all((a.P, a.C, a.E, a.N)):
        raise ErrorUso("faltan ejes: --P --C --E --N (o --suite)")
    r = calcular({"P": a.P, "C": a.C, "E": a.E, "N": a.N}, fuera_de_macro=a.fuera_de_macro,
                 zona_gris=a.zona_gris, hay_reencuadre=a.reencuadre)
    print(json.dumps(r, ensure_ascii=False, sort_keys=True) if a.json
          else f"nivel={r['nivel']} subnivel={r['subnivel']} veredicto={r['veredicto_riesgo']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    return ejecutar_cli(lambda: _principal(argv))


if __name__ == "__main__":
    raise SystemExit(main())
