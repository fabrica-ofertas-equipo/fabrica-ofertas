# Preguntas abiertas y supuestos

> El §10.1 de la spec pide «preguntas bloqueantes primero (máx. 8)». Esta v0.1 se forjó sin poder preguntar: cada una avanza con un `[SUPUESTO]` que el dueño confirma o corrige al pulir. Las del §11 de la spec siguen abiertas.

## A. Bloqueantes de una corrida real (máx. 8) y el supuesto con que se avanzó
| # | Pregunta al dueño | `[SUPUESTO]` de esta v0.1 |
|---|---|---|
| 1 | ¿Cuál es la `oferta_id` y el `locale` de la primera corrida a mano? | Regresión con `ofertas/_ejemplo` (es-ES, dinero, verde) y los casos de `evals/dorados/` (entre ellos «Tetto per Categoria» en it-IT como variante); ninguna oferta real aprobada todavía |
| 2 | ¿Ruta de render PDF? | **A:** Chrome sin pantalla (disponible y probado). WeasyPrint y veraPDF no se instalan sin tu OK |
| 3 | ¿Quién hace el checklist de 10 min, el cold run cronometrado y el RHS; hay revisor nativo pagado por hora para el primer producto de cada idioma (recomendado en cada idioma que M1 proponga; p. ej. italiano o polaco si salen de los datos)? | Tú haces checklist y cronometrado; RHS en el primer amarillo-a; revisor nativo por hora en el primer producto de cada idioma `[DUEÑO]` |
| 4 | ¿Se agrega a D4 la generación de imágenes (hoy **sin Higgsfield en D4**; las de ambiente las produce D6) y con qué topes (`creditos_max_pieza`, `creditos_max_oferta`, `costo_max_producto`)? | **No** y todos `null` ⇒ el producto va **solo con texto** (portada tipográfica) |
| 5 | ¿Política de divulgación de IA (`limites.politica_divulgacion_ia`)? | Divulgar en el colofón y en `ia_divulgacion` (la más conservadora); «revisión editorial de [LLC]» solo si es cierto |
| 6 | ¿Pie con ID de pedido (estampa por comprador)? | **Apagada** en temas sensibles |
| 7 | ¿Se ofrece además un enlace «hacer una copia» de Google Sheets? | **No**: el maestro es el `.xlsx` con hash; Sheets sería un paso humano (GUI) |
| 8 | ~~¿El QA debe ser de «otra familia de modelo»?~~ **Resuelta** (D4-05; spec 05:132): no. La independencia la dan el contexto limpio, la lectura sola, los L1 por código y la calibración con sembrados; el runner usa un solo modelo (`parametros.agentes.modelo`) y un modelo de QA propio sería `agentes.modelo_qa` (clase S) | Sin acción |

## B. Otros supuestos
- Sin `disable-model-invocation`: D4 no mueve dinero, no publica ni activa; el gasto de créditos exige cotización, permiso y los hooks (`pretooluse_gasto`).
- `minicurso_video_corto` queda fuera de v0.1.
- `lectura_wpm` sin factor por locale (factor 1 hasta que exista el parámetro).
- Los léxicos de `scripts/_patrones.py` y las líneas de ayuda conocidas son **interinos** hasta que X1 entregue `terminos_sensibles` y `ayuda_por_pais.yaml`.
- Formato de `afirmaciones.jsonl`, `licencias.json`, `localizacion.json`, `verificacion.json`, `autoprueba.json`: contrato provisional (sin esquema).

## C. Abiertas de la spec §11 (siguen en pie)
1. [DUEÑO] Aprobar las 30 líneas rojas (`lineas_rojas` vacío) y `nivel_max_lanzable`: sin ellas el preflight no cierra en producción.
2. [DUEÑO] Marca visual por oferta: «marca y dominio por oferta» es un **[SUPUESTO]** hasta que el dueño lo confirme (backbone decisión 9; respondió «no aplica creo»); la marca la aprueba el dueño en D3 (gate H) antes de comprar dominio; paleta y tipografías OFL (verificar cada `OFL.txt`).
3. [DUEÑO] `costo_max_producto`, `creditos_max_pieza`, `creditos_max_oferta` (los `creditos_*` solo importan si el dueño agrega imágenes generadas a D4; hoy sin Higgsfield en D4) — Decisión DD, se fija con D6.
4. [DUEÑO] Política de actualizaciones (recomendado: gratuitas para correcciones y cambios de fuente, sin contenido nuevo) y de divulgación de IA.
5. [DUEÑO] Quién hace checklist, cold run humano y RHS; revisor nativo; pie con ID de pedido; unidades de una biblioteca que verifica un humano.
6. [VERIFICAR] Chromium en Railway (p. ej. con Playwright); PDF/UA con veraPDF; categoría fiscal de PDFs y plantillas; máximo de URL prefirmadas de R2; plazo transitorio del art. 50(2) del Reglamento de IA.
7. Pedidos: CT-3 `producto.schema.json` MINOR, reglas cruzadas y claves del Anexo A (LT-26, LT-27, LT-46, LT-47); CT-4 esquemas de apoyo. `scripts/nivel_riesgo.py` ya existe. Pendientes: X1 (`empresa/compliance/*`) y M1 (glosarios). Detalle en `dependencias.md`.
