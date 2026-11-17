<!-- Plantilla de brief-creativo.md (ofertas/<oferta_id>/06-creativos/). En el idioma del dueño (español); los textos del anuncio, en el locale. -->
# Brief creativo — {{oferta_id}} · v{{n}} · locale {{locale}}

## 0. Entradas y estado
| Entrada | Ruta | Estado (`ok` · `falta` · `[SUPUESTO]` · `origen: dueño`) |
|---|---|---|
| mercado | `mercado.json` | |
| oferta (+ riesgo) | `03-oferta/oferta.json` | |
| economía | `03-oferta/economia.json` | |
| validación / voz del cliente / competencia | `02-validacion/…` | |
| landing | `05-landing/…` (hash {{landing_hash}}) | |
| límites y parámetros | `empresa/limites.yaml`, `empresa/parametros.yaml` | |
| glosario / términos sensibles / ayuda por país | `empresa/mercados/…`, `empresa/compliance/…` | |
| **inmersión del mercado (J12):** `voz_cliente.json` + dossier de voz del cliente del país | `02-validacion/voz_cliente.json`, dossier | |
| biblioteca de ganchos | `datos/ganchos.jsonl` (`ganchos.py estadisticas`) | |
| pedido (loop) | `pedidos_creativos.json#{{pedido_id}}` | |

Preguntas bloqueantes enviadas al dueño (una sola lista): {{…}}

## 1. Oferta, claims y prohibiciones
- Macro-nicho: {{salud | relaciones | dinero}} · nivel de la oferta: {{verde | amarillo-a | amarillo-b | rojo}} (ejes P/C/E/N: {{…}})
- `claims_permitidos`: {{claim_id → texto}} · `claims_prohibidos`: {{…}} · `claims_a_evitar`: {{…}} · `angulo_seguro`: {{…}}
- Mecanismo único (procedimiento nombrado, no claim de salud ni de ingresos): {{nombre}}
- `categoria_especial_posible` (empleo / productos financieros, para X1 y D7): {{sí/no/[VERIFICAR]}}

## 2. Dimensionado y matriz
- `n_anuncios_max` = {{n}} (salida de `validar_d6.py nmax`: por presupuesto {{…}}, `creativos.n_anuncios_max` {{…}}, `campana.n_anuncios_tope` {{…}}). Si < `campana.n_anuncios_min`: **no se genera** y se pide {{subir gasto_test_plan | bajar cpa_obj | rediseñar}}.
- Conceptos ({{c}}) × hooks: {{tabla: concepto_id · angulo_id · nivel · hook_id · hook_tipo · formato · ruta · variable_cambiada}}
- Reserva ({{r}} conceptos): {{…}}
- Riesgo por pieza: {{ejes_codigo por anuncio y salida de `python -m scripts.nivel_riesgo`; `repite_promesa_central`; declarado vs recalculado vs oferta}}

## 3. Fuentes, derechos y anti-copia (J13/J17/J18)
{{resumen de fuentes_inspiracion.json: por fuente, qué se hereda (estructura), qué se transforma, qué es expresión protegida; n-gramas revisados; `ganchos.py rechazar` por gancho}}
- Datos inventados: ninguno (sin testimonios, cifras de alumnos, avisos de compra ni urgencias falsas): {{confirmado}}

## 4. Localización (sin revisor nativo, J11)
{{registro, glosario y dossier, términos a evitar, formato de precio, voz elegida (`voice_id`); las 5 capas de `linguistico.json`: estado de cada una}}

## 4b. Control de calidad de 6 puntos (`qc6.py`)
{{resumen de `qc6.json`: piezas ok · revisar · falla y qué se corrigió; motores que faltaron}}

## 4c. Modo tanda (solo si aplica)
{{carpeta de la tanda, composición (relevos · ángulos nuevos · traducciones), régimen de aprobación elegido por el dueño}}

## 5. Costos y ruta
| Pieza | Ruta | Herramienta · modelo | Cotizado | Con margen | Real |
|---|---|---|---|---|---|
- Total cotizado: {{…}} ≤ `creditos_max_oferta` ({{…}}); aprobado por el dueño: {{sí/no, fecha, mensaje}}
- Costo real por tipo de pieza (para fijar `creditos_max_pieza` al pulir): {{…}}

## 6. Método consultado
{{archivos de `anthropic-skills:creativos-ads` usados, si alguno; choques con reglas de D6 y cómo se resolvieron}}

## 7. `[SUPUESTO]`, decisiones y preguntas abiertas (≤15 líneas)
{{…}}

## 8. Autorrevisión (L1 y L2 de `rubric.md`; ≥3 hallazgos o justificación con evidencia)
| # | Hallazgo | Severidad | Evidencia (archivo:línea o ad_name) | Estado |
|---|---|---|---|---|
