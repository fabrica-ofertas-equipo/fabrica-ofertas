# Localización: redacción nativa, no traducción

> Spec §3.2 (`ruta_localizacion`), §4 paso 3 y 6, §6.3.4; backbone 5.10. Salida: `04-producto/localizacion.json` (`templates/localizacion.ejemplo.json`). Datos: `ofertas/<id>/mercado.json` (M1) y `empresa/mercados/glosarios/<locale>.md` (M1).

## 1. Reglas duras

1. **Sin glosario no se produce** (fail-closed): preflight del paso 0. El glosario trae registro (tuteo/voseo/Sie/Lei), términos obligatorios y prohibidos (incluye `terminos_sensibles`), unidades, moneda, separadores, fechas, funciones de hoja, autoridades y fuentes oficiales por macro-nicho, fórmulas de aviso/IA/ayuda, falsos amigos e idioma obligatorio de la información precontractual (Polonia, Francia, Quebec: [VERIFICAR]). Hoy **no existe** la carpeta `empresa/mercados/` [PENDIENTE M1].
2. **Nunca** traducir el archivo de otro idioma y publicarlo. Una oferta hija (`variante_de`) hereda la **estructura** de la madre (matriz, esquema, fichas MU/EU); el **producto se produce de nuevo** en su locale: contenido, fuentes del país, ejemplos, unidades, avisos y ayuda locales. No se reutilizan archivos ni hashes de la madre.
3. D4 **no decide** idioma ni mercado (M1/D9): `oferta.locale` manda; el `idioma` de cada ítem = `oferta.locale` (L1-01).

## 2. Ruta de localización (decisión)

| Ruta | Cuándo | Cómo |
|---|---|---|
| **(a) Redacción nativa desde el brief local** (por defecto) | Todo producto, y siempre que la madre sea de otra familia lingüística o el contenido dependa de normas/fuentes locales | Brief local = `oferta.json` + `voz_cliente` + glosario; fuentes T1 del país; el Maker escribe en el idioma sin mirar texto de la madre |
| **(b) Adaptación de la madre** | Solo si la madre existe y está aprobada | Misma estructura (matriz, esquema, fichas), **contenido regenerado** con fuentes locales; nada de pegar párrafos traducidos. Se anota `madre_de_la_que_hereda_estructura` |

## 3. Qué se localiza (y se verifica)

Unidades (cucharada/cucharadita, g/ml, mg/kcal = fuente), moneda y formato (símbolo y posición), separadores de número y fecha, trámites e instituciones locales, fuentes T1 del país, ayuda del país (literal), aviso de alcance e IA (del glosario), tuteo/voseo, ejemplos (nombres, importes y costumbres plausibles del país, rotulados «ejemplo ficticio»), funciones y configuración regional de las hojas. L1-13 (`lint_contenido.py`, `verificar_respaldo.py`) lo comprueba.

## 4. QA lingüístico (paso 6; backbone 5.10; idiomas sin revisor nativo)

| Control | Quién | Alcance |
|---|---|---|
| **(a) Retraducción** al español por un contexto limpio | Agente distinto del Maker (proceso separado, contexto limpio) | **100 %** de avisos, ayuda, cifras, unidades y pasos; `linguistica_retraduccion_pct_resto` del resto [propuesto]. Las **discrepancias de sentido son hallazgos** (un aviso con sentido invertido = BLOQUEANTE) |
| **(b) Segunda lectura con otro modelo** | Otro modelo | Registro, falsos amigos, unidades, modismos, glosario |
| **(c) Muestreo humano nativo** | Revisor nativo pagado por hora [DUEÑO] | **Primer lanzamiento de cada idioma** (glosario, avisos, ayuda, partes críticas); luego 1 de cada 5 (`linguistica_muestreo_nativo_posterior` [propuesto]). Con `mercado.revision_linguistica.revisor_nativo = false` es **H obligatorio** en el primer producto del idioma; con `obligacion_legal_idioma = true` y sin revisor nativo, X1 da ROJO y no se lanza |

Los pasos (a) y (b) los ejecuta el orquestador con agentes separados; el Maker deja los textos y el QA recibe los resultados en `localizacion.json`. **Un LLM no puede declarar `revision_humana.hecha_por`**: solo una persona real, con fecha.

## 5. Ejemplos de falla que la skill debe atrapar

- `1,500 g` (separador inglés) en it-IT → L1-13 BLOQUEANTE (se lee 1,5 g).
- `cucchiaio` por `cucchiaino` → BLOQUEANTE (unidad distinta a la fuente).
- Línea 988 (EE. UU.) en un producto it-IT → BLOQUEANTE (ayuda de otro país; usar 1522 desde `ayuda_por_pais.yaml`).
- «Calco» del español: sintaxis y falsos amigos → R12 ≤ 2.
- Umbral fiscal del país equivocado → BLOQUEANTE (fuente de otro país para un `umbral`).
