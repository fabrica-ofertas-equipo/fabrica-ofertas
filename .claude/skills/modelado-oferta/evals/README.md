# Evals de la skill de modelado (mínimos, v0.1)

| Carpeta o archivo | Contenido | Cómo se usa |
|---|---|---|
| `dorados/casos.yaml` | tres casos: **C1** el piloto de Polonia (oferta A, J18/J19) paso a paso con entradas y salidas esperadas resumidas; **C2** el script contra los dos HTML reales; **C3** contenido hostil | el Maker corre C1 y el QA debe dar PASS o PASS_CON_NOTAS; C2 y C3 los comprueba `tests/modelado/` |
| `dorados/01-pl-mapas-ingles/salida_esperada.json` | cifras y decisiones del piloto que un buen modelado debe reproducir (bloques, palancas, antes/después, riesgos) | comparación con tolerancia; no es un «resultado único» |
| `sembrados.yaml` | 10 defectos sembrados con la mutación y lo que el QA debe detectar | meta: ≥ 90 % de los bloqueantes |

## Pruebas del script (sin red)
```
.venv/bin/python -m unittest discover -s tests/modelado -t . -p "test_*.py"
```
Comprueban el esqueleto y el mapa de ranuras (secciones y orden, CTA, `<details>`, fijos, tokens, terceros, ids no filtrados), el contenido hostil, los límites de tamaño, de nodos, de profundidad y de tiempo, los frenos de red y la comparación con los HTML reales de `docs/_historial/modelado-piloto/referentes/html/` (se omite si no están).

## Qué NO prueban
Que una oferta modelada venda, que Meta apruebe un anuncio ni que el texto en polaco sea nativo (J11: sin revisor humano). Un PASS prueba que el modelado cumple la rúbrica; la validación de mercado es D7/D8. Las pruebas del script prueban su comportamiento sobre dos páginas y sobre cadenas de ejemplo, no que cualquier página del mundo se segmente bien.

## Orden de corrida recomendado
1. Pruebas del script (verdes). 2. C1 con el Maker sobre el material del piloto (`docs/_historial/modelado-piloto/`). 3. QA sobre C1 (PASS) y sobre los sembrados (≥ 90 %). 4. Cuando exista otro referente, repetir con él **sin editar la skill** entre uno y otro: si obliga a editarla, el hallazgo va a la bitácora `Pulido` del panel.
