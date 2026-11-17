# Localización como servicio transversal (SOP paso 16)

> Fuente: `departamentos/16` §4.2; backbone §5.10. M1 **no escribe** en carpetas ajenas: entrega glosarios y reglas, y cada Maker (D3-D6, D10) transcrea con ellos. Lo que M1 NO hace: fijar precio, clasificar riesgo, redactar claims o anuncios.

## 1. Las 6 etapas
| # | Etapa | Actor | Qué se hace | Medible |
|---|---|---|---|---|
| 1 | Glosario y reglas | M1 Maker + revisor nativo | `empresa/mercados/glosarios/<locale>.md` (plantilla `templates/glosario.md`) y `reglas/<locale>.yaml` (`templates/reglas-locale.yaml`): registro (tú/Lei/Ty), términos del oficio **y de cada macro-nicho**, términos prohibidos (**vienen de X1** `terminos_sensibles/<locale>.yaml`, no se inventan), formato de moneda, decimales, fechas, unidades/papel, género y plurales (en polaco 2-4 vs 5+; «robiłeś/robiłaś»), ejemplos buenos/malos | glosario con las 8 secciones y ≥ 3 ejemplos buenos y malos |
| 2 | Traducir + adaptar | Maker de cada departamento con el glosario | **Transcreación** (voz, humor, ritmo, ejemplos locales), no traducción literal | — |
| 3 | Lint determinista | `scripts/lint_locale.py` | términos prohibidos/obligatorios, moneda coherente con `moneda_cobro`, formato decimal, alfabeto ajeno, diacríticos, plurales (heurística), calcos, longitud | 0 bloqueantes |
| 4 | Retraducción | segundo modelo | traduce de vuelta al idioma fuente; un juez compara **significado y promesa**; discrepancia en promesa, precio o legal = MAYOR | — |
| 5 | Segunda lectura | otro modelo | naturalidad, calcos del inglés/español, concordancias | — |
| 6 | Muestreo humano | nativo | **primer lanzamiento de un idioma:** 100 % de legales, checkout y landing + muestreo de piezas de anuncio y del producto (`mercados.muestreo_nativo_primer_lanzamiento`); después `producto.linguistica_muestreo_nativo_posterior` (hogar único en el grupo `producto`, 20 %, alineado a D4; no existe `mercados.muestreo_nativo_posterior_pct`, C-05). Con `obligacion_legal_idioma`: 100 % y **sin revisor no se lanza** (R5) | `revision_linguistica.revisor_nativo` |

`mercado.json#revision_linguistica.metodos` declara cuáles de `retraduccion`, `segunda_lectura_otro_modelo`, `revision_humana_muestreo` se planifican. **El lint no demuestra buena traducción**: un texto limpio en el lint sigue pasando por 4-6.

## 2. Qué lleva el glosario (mínimos)
1. Tono y registro con ejemplo bueno y malo. 2. Formatos (`49 zł`, `9,90 €`; separador decimal y de miles; coherente con `moneda_cobro`). 3. Gramática que rompe traducciones (género del lector, plurales por rangos, casos). 4. Términos del oficio. 5. **Términos por macro-nicho** (salud · relaciones · dinero): obligatorios (avisos de alcance, «ilustrativo» del idioma, descargo de ayuda) y prohibidos (fuente X1) con alternativa segura. 6. **Nombre del producto**: marca neutra, sin connotación local rara (lista de descartados y por qué). 7. Ejemplos buenos/malos. 8. **Qué NO sabe este glosario.**
Estado del revisor en cada glosario: `ninguno | contratado (alias, fecha)`. Sin revisor, los términos del locale y las listas de búsqueda son `[VERIFICAR]` y no entran a producción.

## 3. Handoffs (qué recibe cada etapa)
- **D3**: moneda, rango de precio de referencia (no el precio) y glosario del nombre del producto.
- **D4**: idioma, unidades, formato de papel (A4/Letter) y fuentes con diacríticos.
- **D5**: plantillas legales en el idioma, casillas de renuncia al desistimiento, CMP, **métodos por moneda** y formatos.
- **D6**: voz del locale y lista de términos sensibles (de X1).
- **D10**: plantillas fijas de soporte en el idioma y horarios.
Sin abogado (decisión 14): las páginas legales y el banner son plantilla generada; M1 no pide revisión legal humana: pide **revisor nativo de idioma** y los checks automáticos de X1.

## 4. Casos que M1 debe saber rechazar
Idioma sin glosario aprobado ⇒ no entra a `locales_activos.yaml` como `activo`. Idioma con obligación legal sin revisor ⇒ R5. `pt-PT` y `pt-BR` son **locales distintos**. Quebec en francés es otro proyecto (idioma y régimen propios), no una variante de `en-CA`.
