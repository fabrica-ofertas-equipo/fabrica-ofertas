# scripts/producto/mapas — fábrica de los mapas de Słowomapa (D4, OF-202611-91)

Pipeline reproducible para producir los 520 mapas de vocabulario con control automático. Todo offline (sin red, sin gasto, sin claves); usa Chrome sin pantalla y herramientas de macOS (PDFKit, Vision, NSSpellChecker, `swiftc`). Piloto con 12 mapas reales: `ofertas/OF-202611-91/04-producto/`. Procedimiento para agentes por lotes: `04-producto/procedimiento-lotes.md`. Pruebas: `.venv/bin/python -m unittest discover -s tests/producto_mapas -t . -p "test_*.py"` (97 pruebas, 14 s; las que usan Chrome o Swift se omiten si no están).

| Módulo | Qué hace |
|---|---|
| `esquema.py` | Esquema de un mapa (JSON) y validador propio (forma, longitudes, cobertura de palabras en frases, artículo a/an en los huecos, presupuesto de ≤ 450 palabras, contra el temario) |
| `temario.py` + `temario_fuente.txt` | Temario de 520 títulos (70/80/90/100/90/90): parser, validación, `temario.json` con `mapa_id` y la ruta («siguiente») |
| `duplicados.py` | Inventario de palabras; duplicados dentro del nivel (BLOQUEANTE), entre niveles (informativo) y frases repetidas; lista de palabras ya usadas para el siguiente lote |
| `datos_qa.py` | Listas interinas: falsos amigos PL↔EN, marcas, sensibles, promesas, jerga, palabras elementales, longitudes de frase por nivel |
| `qa_idioma.py` | Capas de QA de idioma (J11): ortografía (corrector del sistema), nivel, duplicados, listas, retraducción ciega |
| `revision_ciega.py` | Paquete de la revisión ciega por un segundo agente, rúbrica E1-E8, validación del informe y **decisión por código** |
| `prompts.py` + `plantillas/` | Encargo del escritor por lote y prompts del revisor ciego y del retraductor |
| `render.py` + `plantilla.css` | Hoja A4 (HTML + SVG de ramas por código), PDF y PNG con Chrome, **medición de maquetación** (¿cabe?) con densidades automáticas d0/d1/d2, miniaturas de la landing |
| `ocr.py` + `ocr_pdf.swift` + `ortografia.swift` | Texto del PDF (capa de texto y OCR de Vision) contra el JSON; corrector ortográfico |
| `paquete.py` | `producto.json` con sha256 por archivo (reutiliza `scripts.producto.empaquetar`; valida el contrato) |
| `lote.py` | CLI: `validar`, `qa`, `render`, `ocr`, `muestra`, `estado` |

## Receta (los 12 del piloto; para los 520 cambia la carpeta)
```bash
B=ofertas/OF-202611-91/04-producto; M=$B/entregables/fuente/mapas; T=$B/temario.json
.venv/bin/python -m scripts.producto.mapas.temario generar --sobrescribir
.venv/bin/python -m scripts.producto.mapas.lote validar --mapas $M --temario $T          # esquema + duplicados + temario
.venv/bin/python -m scripts.producto.mapas.lote qa --mapas $M --excepciones $B/excepciones_ortografia.json --salida $B/qa/qa-automatico.json
.venv/bin/python -m scripts.producto.mapas.lote render --mapas $M --temario $T --salida $B/entregables --por-mapa --indice --borrador --sobrescribir
.venv/bin/python -m scripts.producto.mapas.lote ocr --mapas $M --salida $B/entregables --reporte $B/qa/ocr-pdf.json
.venv/bin/python -m scripts.producto.mapas.lote muestra --mapas $M --temario $T --salida $B/muestra --principal a1-001-food,b2-001-technology-and-the-internet,c1-001-argument-and-debate
.venv/bin/python -m scripts.producto.mapas.lote estado --mapas $M --temario $T --qa-dir $B/qa --salida $B/qa/estado_mapas.json --reporte $B/qa/ocr-pdf.json
.venv/bin/python -m scripts.producto.mapas.paquete --base $B --prometido-min 10 --salida $B/producto.json
.venv/bin/python -m scripts.producto.mapas.prompts --nivel B1 --desde 3 --hasta 12 --mapas $M --temario $T      # encargo del escritor
```
`render` SIN `--borrador` solo funciona si están escritos los 520 (el índice no anuncia lo que no hay: «lo anunciado = lo entregado»).

## Criterio de aceptación por mapa (`lote estado`)
1. Esquema: 0 BLOQUEANTE y 0 MAYOR (con el temario). 2. QA automático: ortografía, nivel, duplicados del nivel y listas sin BLOQUEANTE/MAYOR (la ortografía NO ejecutada no cuenta como pasada). 3. Revisión ciega por un segundo agente: 0 defectos de severidad alta, ≤ 2 de media, media E1-E8 ≥ 4,5 y E1, E2, E3, E5 ≥ 4 (`revision_ciega.decidir`). 4. (opcional) OCR/capa de texto del PDF del nivel.

## Límites honestos
- Ninguna capa certifica un idioma: el corrector no ve una palabra bien escrita pero equivocada (recall medido ≈ 85 % con errores sintéticos); las listas son cortas; la retraducción y la revisión ciega las hace un modelo de la misma familia (errores correlacionados posibles). No hay lista CEFR offline: el nivel lo juzga el revisor.
- macOS: `swiftc`, PDFKit, Vision y el diccionario polaco del sistema son requisitos de las capas de ortografía y OCR; sin ellos esas capas se declaran NO EJECUTADAS (nunca pasadas).
- Chrome 156 sale con código 2 si `HOME` es un directorio temporal: `render.py` usa el HOME real con perfil temporal (`--user-data-dir`).
