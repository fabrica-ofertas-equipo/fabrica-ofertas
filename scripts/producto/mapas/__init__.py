"""Pipeline de producción de los mapas de vocabulario de Słowomapa (D4, OF-202611-91).

Piezas (todas offline, sin red, sin gasto, sin claves; salvo Chrome/Swift/PDFKit locales para render y OCR):

- ``esquema``      esquema de un mapa (JSON) y validador propio.
- ``temario``      temario de 520 títulos (parser, validación, ``temario.json``).
- ``duplicados``   inventario de palabras y duplicados dentro y entre niveles.
- ``datos_qa``     listas de falsos amigos, marcas, promesas y palabras elementales.
- ``qa_idioma``    capas automáticas de QA de idioma (J11): ortografía, nivel, duplicados, listas, retraducción.
- ``revision_ciega`` paquete y validación del informe de la revisión ciega por un segundo agente.
- ``render``       HTML A4 (SVG de ramas) -> PDF/PNG con Chrome headless.
- ``ocr``          texto del PDF (PDFKit) y OCR (Vision) contra el JSON.
- ``paquete``      ``producto.json`` con sha256 por archivo (contrato ``producto.schema.json``).
- ``lote``         CLI que une todo.
"""
