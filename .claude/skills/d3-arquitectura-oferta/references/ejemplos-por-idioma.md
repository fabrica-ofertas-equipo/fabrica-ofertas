# Ejemplos por idioma (es-ES, it-IT, pl-PL): se localiza, no se traduce

Todo es `[SUPUESTO]` y **sin revisión nativa** (backbone 5.10: sin revisor, retraducción + segunda lectura con otro modelo; revisor nativo obligatorio donde la ley del idioma lo exige, según M1 para el idioma del primer mercado; los tres idiomas de los dorados son ejemplos de la skill, no un par de arranque). Las tres ofertas completas están en `evals/dorados/` (cada una con sus entradas, `oferta.json`, `economia.json` y `oferta.md`). Otro idioma = otra `oferta_id` de la familia con `variante_de`; **se rehacen economía, riesgo, ángulos y vocabulario**, no se traduce el texto.

| | es-ES · dinero | it-IT · salud | pl-PL · relaciones |
|---|---|---|---|
| Oferta dorada | `01-es-es-reinsercion` | `02-it-it-planner-pasti` | `03-pl-pl-karty-rozmow` |
| Nombre (descriptivo, sin sufijo) | Currículum y Guion tras una Pausa Laboral | Planner Settimanale dei Pasti con Lista della Spesa | Karty Rozmów dla Par |
| Mecanismo (2-6 palabras) | Puente de la Pausa | Pasti a Blocchi | Rytuał Jednego Pytania |
| Subtítulo = promesa + diferencial | Guía con plantilla editable: ordena la experiencia por competencias y prepara un guion de 30 segundos para explicar la pausa | Cinque cene base a blocchi intercambiabili e una lista della spesa settimanale da compilare in circa 20 minuti | 50 kart z pytaniami do wydruku, w trzech poziomach, i zasada rozmowy na zmianę na wieczór we dwoje |
| Medida de uso (no resultado) | 90 min | 20 min | 15 min |
| Garantía visible | «Si no te sirve, te devolvemos el importe durante 14 días. Sin preguntas.» | «Se non ti serve, puoi chiedere il rimborso entro 14 giorni. Senza domande.» | «Jeśli to nie dla Ciebie, zwrócimy pieniądze w ciągu 14 dni. Bez pytań.» |
| Precio con IVA (escalón local) | 24,90 EUR | 24,90 EUR | 89 zł |
| Encuadre del público (E1, 3.ª persona) | «persona que vuelve a buscar trabajo tras una pausa larga» | «chi non sa cosa cucinare ogni sera» | «pary, które mieszkają razem» |
| Qué se evita | «conseguirás trabajo», cifras de sueldo, «madres» como atributo | kilos, plazos, «senza dieta», «dimagrire», valores nutricionales | «randki», terapia, promesas sobre la relación |
| Descargo / ayuda | «Guía informativa; no garantiza resultados de empleo» | «Strumento di organizzazione; non fornisce consigli nutrizionali» | aviso de seguridad + línea de violencia en la pareja de PL (800 120 002, `[VERIFICAR]` por X1-J02) |
| Lint de X1 (L1-03) | hay reglas (es-ES) | hay reglas (it-IT) **sin revisión nativa** [HIPÓTESIS] | hay reglas (pl-PL) **sin revisión nativa** [HIPÓTESIS] |

## Cómo localizar (reglas)
1. **Nombre**: el que diría el cliente en su idioma; no un anglicismo (it: no «Weekly Meal Planner Pro»; S17); sin la jerga del marketing local.
2. **Vocabulario**: de `voz_cliente.json` y del glosario del locale (`empresa/mercados/glosarios/<locale>.md`, M1; no existe hoy: `dependencias.md` A5); las citas del avatar en el idioma original, literales.
3. **Formato de precio y moneda**: coma decimal en es/it/pl (`24,90 €`, `89 zł`); la moneda del mercado (nunca EUR en un mercado que cobra en PLN con un método local, S20).
4. **Persona gramatical**: segunda persona de cortesía según el locale (it «ti», pl «Ci»/«Państwo», es «te») **solo con verbo de acción neutro**; nunca con atributo ni pregunta sobre el lector.
5. **Trampas del idioma** (`claims-por-macro-nicho.md`): pl «w 7 dni» y «cud/leczy»; it «senza dieta»; de «gegen»; es RD 1907/1996.
6. **Idiomas sin ejemplo todavía** (en, fr, de, ro, pt): `[PENDIENTE]`; se pulen al forjar una oferta en cada uno. Los casos de la suite de frontera cubren es 85, en 57, it 32, pl 16, fr 15, ro 12, de 8, pt 5.
7. **Segunda lectura nativa** (L3-6) de título, subtítulo y ángulos: que «suene a su idioma» y no a traducción.
