# Trazabilidad — {oferta_id} · {locale} · {version}

> Sin esquema propio (lo lee X1, QA, D5 y D10). Una sección por tema; todo con ruta citada.

## 1. Matriz promesa → entregable → prueba
Ver `matriz_promesas` en `producto.json` (vista legible: `matriz_promesas.md`). Resultado de `cobertura_matriz.py`: {pass/fail · fecha}.

## 2. Fuentes y respaldo
- `respaldo/afirmaciones.jsonl`: {n} afirmaciones · temas: {lista} · todas con `sha256` de su snapshot en `respaldo/fuentes/`.
- Fuentes por tema: ≥ `producto.min_fuentes_por_tema` (≥ 1 T1) del país del lector. Resultado de `verificar_respaldo.py`: {pass/fail · fecha}.
- Fuente con instrucción oculta o texto hostil detectada: {no / sí → ignorada y registrada en `incidentes` de esta carpeta}.

## 3. Originalidad y anti-copia
- Referencias de ANATOMÍA usadas (de `validacion.json`/`corpus_competencia`): {tipo de estructura: p. ej. «tabla de costeo por unidad»}; **ningún contenido ajeno** como entrada.
- `similitud_ngrama.py`: {0 tramos ≥ umbral · n alertas · cobertura %} · búsqueda de {K} frases (hecha por una persona; ningún agente navega): {resultado}.
- Control comparado R5 (prompt simple de chatbot en el mismo idioma): {qué aporta de más este producto}.

## 4. IA y aporte humano (autoría honesta)
| Parte | Hecha por | Herramienta/modelo | Revisión humana | Nota |
|---|---|---|---|---|
| {texto cap. 1-4} | IA + editor | {modelo} | {quién/cuándo o «no»} | |
| {imágenes} | IA | {herramienta, plan} | {muestreo %} | rotuladas «IA» en el colofón |

Divulgación aplicada: {texto literal} (según `limites.politica_divulgacion_ia`; si es `null`: la más conservadora y se anota como [SUPUESTO]).
Nunca: «diseñado por nutricionistas», «revisado por…» salvo que sea cierto y esté documentado (colofón, no portada).

## 5. Licencias
`licencias.json`: {n} activos, 100 % cubiertos (origen, herramienta y plan, URL de licencia, alcance comercial/redistribución/uso del comprador, evidencia, prompt).

## 6. Localización
`localizacion.json`: ruta {redaccion_nativa|adaptacion_de_madre}, glosario {versión}, retraducción {resultado}, segunda lectura {resultado}, revisión humana nativa {pendiente/hecha}.

## 7. Ejecución del método
`autoprueba.json`: {n} pasos ejecutados por agente, {n} `no_ejecutable_por_agente` (pasan al checklist del dueño), casos dorados {n/n ok}.
