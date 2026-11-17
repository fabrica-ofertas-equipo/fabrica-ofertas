"""Genera el encargo para el agente ESCRITOR de un lote de mapas (plantilla ``plantillas/prompt_escritor.md``).

El encargo lleva: los mapas del lote con su título y su «siguiente» (del temario), las palabras YA usadas en el nivel (para no repetirlas),
la guía del nivel, los falsos amigos conocidos y un mapa de ejemplo ya aceptado. El validador y el QA automático son los de este paquete.

    .venv/bin/python -m scripts.producto.mapas.prompts --nivel B1 --desde 3 --hasta 12 --mapas DIR --temario T [--destino DIR] [--ejemplo RUTA]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from string import Template
from typing import Any, Mapping

from scripts.producto.mapas import datos_qa as D
from scripts.producto.mapas import duplicados
from scripts.producto.mapas.lote import cargar_mapas

PLANTILLA = Path(__file__).with_name("plantillas") / "prompt_escritor.md"
GUIA_NIVEL = {
    "A1": "Palabras concretas y muy frecuentes (≤ 10 letras casi siempre); frases en presente simple de ≤ 9 palabras; sin phrasal verbs ni modismos; las pistas usan palabras A1.",
    "A2": "Vocabulario cotidiano ampliado; frases de ≤ 12 palabras (pasado simple y comparativos permitidos); pocos phrasal verbs muy comunes; pistas de nivel A1-A2.",
    "B1": "Vocabulario de temas generales y de trabajo/estudio; frases de ≤ 16 palabras; colocaciones habituales y phrasal verbs frecuentes; pistas de nivel A2-B1.",
    "B2": "Vocabulario abstracto y de temas especializados cotidianos; frases de ≤ 20 palabras; colocaciones y phrasal verbs; evita palabras de B1 (si la palabra es de B1 o inferior, no sirve en B2).",
    "C1": "Vocabulario formal, académico y matizado; frases de ≤ 26 palabras; colocaciones precisas; evita palabras de B2 o inferiores.",
    "C2": "Vocabulario poco frecuente y de matices finos (casi-sinónimos con diferencias de registro o connotación); frases de ≤ 30 palabras; evita palabras de C1 o inferiores; cuida el equivalente polaco: que sea natural, no un calco.",
}


def construir(nivel: str, desde: int, hasta: int, mapas: list[Mapping[str, Any]], temario: Mapping[str, Any], *, destino: str, ejemplo: str, ruta_temario: str) -> str:
    lote = [m for m in temario["mapas"] if m["nivel"] == nivel and desde <= m["numero"] <= hasta]
    if not lote:
        raise ValueError(f"no hay mapas {nivel} {desde}-{hasta} en el temario")
    lista = "\n".join(f"- `{m['mapa_id']}` · {m['tema']['en']} · {m['tema']['pl']} · siguiente: `{m['siguiente']}`" for m in lote)
    fa = "\n".join(f"- {e['en']} ≠ {', '.join(e['falso'])} (correcto: {', '.join(e['correcto'])})" for e in D.FALSOS_AMIGOS)
    usadas = duplicados.ya_usadas(mapas, nivel)
    return Template(PLANTILLA.read_text(encoding="utf-8")).substitute(
        nivel=nivel, desde=desde, hasta=hasta, destino=destino, temario=ruta_temario, ejemplo=ejemplo, guia_nivel=GUIA_NIVEL[nivel], lista_mapas=lista,
        falsos_amigos=fa, ya_usadas=(", ".join(usadas) if usadas else "(ninguna todavía)"))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m scripts.producto.mapas.prompts")
    ap.add_argument("--nivel", required=True)
    ap.add_argument("--desde", type=int, required=True)
    ap.add_argument("--hasta", type=int, required=True)
    ap.add_argument("--mapas", required=True, help="carpeta con los mapas ya aceptados (para la lista de palabras usadas)")
    ap.add_argument("--temario", required=True)
    ap.add_argument("--destino", default="ofertas/OF-202611-91/04-producto/.staging/lote")
    ap.add_argument("--ejemplo", default="ofertas/OF-202611-91/04-producto/entregables/fuente/mapas/B1/b1-002-health.json")
    a = ap.parse_args(argv)
    tem = json.loads(Path(a.temario).read_text(encoding="utf-8"))
    print(construir(a.nivel, a.desde, a.hasta, cargar_mapas(a.mapas), tem, destino=a.destino, ejemplo=a.ejemplo, ruta_temario=a.temario))
    return 0


if __name__ == "__main__":
    sys.exit(main())
