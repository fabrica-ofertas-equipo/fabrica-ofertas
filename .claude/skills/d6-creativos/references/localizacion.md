# Localización: crear en el idioma, no traducir

Fuentes: spec §4 «Localización», `docs/_investigacion/11-playbook-anuncios-creativos.md` §6, backbone §5.10, `departamentos/16-mercados-localizacion.md` §4 y las decisiones **J11** (sin revisor nativo), **J12** (inmersión del mercado) y **J13** (derechos) del dueño (`inmersion-y-derechos.md`). **Ningún país es prior**: Polonia e Italia son hipótesis a decidir con datos propios; los creadores no aportan datos creativos de ninguno de los dos. La unidad de lanzamiento es el idioma/mercado (`oferta_id`).

## 1. Reglas

1. **Reescribir desde la motivación local.** No se traduce el guion ni el anuncio de **un tercero** (traducir un guion ajeno es copia, J13). Se parte de `voz_cliente` del `locale` (con fuente y país), del **dossier de voz del cliente** del país (J12), del glosario y de la ficha de formato local. **Excepción:** un **ganador propio** puede llevarse a otro idioma con la variante «ganador traducido» (traducción fiel + 5 capas + X1 por `locale`: `formatos-que-miden-bien.md` §3); sigue siendo una hipótesis en el idioma nuevo.
2. **Voz IA nativa** (`voice_type: preset` filtrado por idioma con `list_voices`), nunca clonada. Pronunciación de números, precios y términos del oficio comprobada con la transcripción de `whisper-cli` (`qc6.py`, audio = guion) y, en N0-N2, con la escucha del dueño; sin revisor nativo (J11). Se anota en `linguistico.json`.
3. **Precios y números del país:** moneda de `mercado.moneda_cobro`, separadores y posición del símbolo del `locale` (§3). Nada de «dólares» en un anuncio en euros o zlotys.
4. **Manos, hogares, objetos y materiales del país**; evitar etiquetas o textos de otro idioma en un fotograma.
5. **Sin métodos de pago locales** en el anuncio (BLIK, Bizum, Satispay…): el test usa tarjeta y billeteras; se mencionan solo en landing/checkout si Stripe los habilita.
6. **Sin «link en la bio» ni Instagram**: la identidad es la fan page; las piezas 9:16, 4:5 y 1:1 sirven Feed, Reels y Stories.
7. **Un hook ganador en otro idioma es hipótesis**, no un activo exportable: nueva `oferta_id`, texto rehecho (o traducción fiel de un ganador **propio**, regla 1), X1 revalida los claims por jurisdicción, no se reutilizan PNG con texto (se re-renderizan) ni dataset.
8. **Familias:** la oferta hermana hereda estructura y matriz; el texto se rehace por `locale`.
9. **Sin revisor nativo (J11, «saca lo de revisores nativos»).** La revisión humana por un hablante nativo ya no es requisito, bloqueo ni gate, tampoco con `obligacion_legal_idioma` (PL, FR, Quebec): esa obligación se cumple **escribiendo en el idioma**. La calidad se asegura con las cinco capas automáticas de abajo. Si el dueño pide un revisor, queda como dato **opcional** en `linguistico.json`. Hasta que S-A retire `X32_REVISOR` de `scripts/validar_esquemas.py` y de la spec 07/16 (`PEDIDOS.md` #5), un validador de otra etapa puede seguir dando error por esto: **no es un criterio de D6**, y el Maker lo anota en el brief en vez de pedir un revisor.

## 2. QA lingüístico por capas (`linguistico.json`, sin revisor nativo)

Las cinco capas de QM-14 (`docs/_historial/modelado-piloto/proceso-de-modelado.md` §5.9). Todas automáticas; ninguna puede decir `no_aplica` sin una justificación escrita.

| Capa | Quién | Qué | Evidencia |
|---|---|---|---|
| 1. Glosario y dossier | M1 + inmersión del mercado (J12) | `empresa/mercados/glosarios/<locale>.md` (registro tú/vos/Ty/Lei…, términos del oficio y del macro-nicho, términos prohibidos de X1, moneda, decimales, plurales, género) y el dossier de voz del cliente | Ruta del glosario y del dossier y su versión. **[PENDIENTE: el glosario no existe]**: hasta entonces `[SUPUESTO]` anotado |
| 2. Lint determinista | `compliance.lint_claims` + `scripts/qc6.py` (palabras de claims rojos, formatos, otro idioma) + `scripts/mercados/lint_locale.py` **[PENDIENTE: S-B, SB-13]** | glosario obligatorio/prohibido, formatos, diacríticos, otro idioma, longitud, moneda coherente, claims rojos | Salida de cada script |
| 3. Retraducción | Otro proceso/modelo | Retraduce `copies.json` y guiones al español del dueño **sin ver el original**; se compara el sentido | `retraduccion[]` con diferencias |
| 4. Segunda lectura | **Otro modelo**, contexto aparte (auditor de IA del idioma) | Naturalidad, registro, calco del español o del inglés, falsos amigos, plurales, números | `segunda_lectura[]` |
| 5. Cobertura cruzada contra el dossier | El Maker con el dossier abierto, y el QA por muestreo | Cuántos giros y términos del dossier usa cada pieza, ninguno de sus «qué evitar», calcos bajo el umbral (`inmersion.calcos_max`, **[PENDIENTE: S-A]**). **Reemplaza al muestreo humano nativo** | `cobertura_dossier{terminos_del_dossier_usados, que_evitar_presentes, calcos}` |

El hogar único del dato `revisor_nativo` es `mercado.json#revision_linguistica` y ahora es **opcional** (J11); no hay una clave de `parametros.yaml` para esto en D6 y esta skill no la define. Sin revisor, **nada se bloquea ni se pone en ROJO**: el riesgo de un matiz torpe es del dueño (decisión J11) y se mide con el KPI «% de piezas con calcos o correcciones del dueño, por idioma».

## 3. Formato de precio, moneda y números por `locale` (verificar con el glosario y el dossier)

| Locale | Ejemplo de 19,90 | Notas |
|---|---|---|
| es-ES | `19,90 €` | coma decimal; símbolo detrás con espacio |
| es-AR / es-MX | según moneda de cobro (ARS/MXN/USD) | Rioplatense: voseo (`tenés`) solo si `es-AR` y el glosario lo fija |
| it-IT | `19,90 €` | coma decimal; «Più informazioni» como texto de apoyo, no como CTA del enum |
| pl-PL | `19,90 zł` (o `19 zł` si es redondo) | plurales polacos 2–4 vs 5+; género gramatical del hablante (*robiłeś/robiłaś*): evitar la segunda persona con género |
| en-US | `$19.90` | punto decimal; símbolo delante |
| en-GB | `£19.90` | |
| fr-FR | `19,90 €` | espacio fino antes de `?`, `!`, `:` `[VERIFICAR]` |
| de-DE | `19,90 €` | |
| ro-RO | `19,90 lei` | |

El precio del anuncio, normalizado (símbolo y separadores), debe **coincidir** con `oferta.precio.lista` y con lo que muestra la landing (`data-precio-minor` + `data-decimales` en el ejemplo de D5). Caracteres obligatorios intactos: ñ, á, é, í, ó, ú, ü, ¿ ¡ (es); à è é ì ò ù (it); ą ć ę ł ń ó ś ź ż (pl); ă â î ș ț (ro); é è ê ç œ (fr); ä ö ü ß (de).

## 4. Notas por idioma (de la nota 25 §4 y la spec; no exhaustivas)

- **pl:** sin «cud», «leczy», «płynnie», «sekret poliglotów» ni plazos «w 7 dni»; atención al truncado de titulares con palabras largas; la información al consumidor debe estar en polaco: se cumple escribiéndola en polaco (sin revisor, J11). Vision lee la `ż`/`Ż` como `z` (ver `control-de-calidad-6-puntos.md` §3). Ejemplos de voz local: `docs/_historial/modelado-piloto/inmersion/pl-voz-del-cliente.md` (tuteo «ty»; el humor y la jerga de Wykop no se imitan).
- **it:** «senza dieta» y los plazos son el patrón sancionado por la AGCM; «Planner settimanale dei pasti» y «Modello Excel per costi, prezzo e margine» son los dorados.
- **de:** «gegen» + dolencia es eficacia terapéutica (HWG §3); «Kurs mit Betreuung» invita a FernUSG: producto como `Arbeitsmappe als PDF` sin soporte.
- **fr:** sin lenguaje terapéutico (CSP L5122-2); sin revisor obligatorio (J11); Quebec va fuera del clúster `en-CA`.
- **ro:** sin propiedades de prevención ni curación (Ley 56/2021 art. 7(2)).
- **es:** el RD 1907/1996 solo aplica con «pretendida finalidad sanitaria»; en ES y DE de salud, los términos de su art. 4 (insomnio, diabetes, adelgazante…) no se usan referidos al producto.
- **en:** «Lose weight», «treatment», «guaranteed income» son rojo; el inglés de EE. UU., Reino Unido y Canadá no es el mismo registro: una oferta `en-GB` no hereda una `en-US` sin rehacer ortografía, moneda y ejemplos.

## 5. Qué se entrega por idioma

Mismos archivos que en cualquier idioma, con `idioma` = `locale` en cada copy. `linguistico.json` queda con las cinco capas aunque alguna diga `no_aplica` con justificación; ningún idioma se aprueba «porque sí».

## 6. Inmersión y derechos

Qué se lee del mercado (J12), cómo se usa y qué no se copia nunca (J13/J17/J18): `inmersion-y-derechos.md`. Formatos que se llevan de un idioma a otro: `formatos-que-miden-bien.md` §3.
