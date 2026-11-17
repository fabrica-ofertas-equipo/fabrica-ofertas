# Locales: reglas de copy, formato y CTA por idioma

> v0.2 sin pulir (borrador generado desde la spec y revisado el 2026-11-07; no promover a 1.0.0 hasta cumplir el DoD y una corrida manual del dueño).
> La fuente de tono y glosario de cada idioma es `empresa/mercados/glosarios/<locale>.md` `[PENDIENTE: lo construye M1]`; la de precios, impuestos y métodos, `mercado.json`. Esta tabla es el **mínimo** que usa D5 mientras no existan, y cada fila se marca `[SUPUESTO]` y sin revisión nativa. Polonia e Italia son **hipótesis de arranque**, no un prior (decisión del dueño). Un problema hallado en un idioma no se asume válido en otro. Ejemplos de CTA y de nombres: orientativos, a revisar por un hablante nativo (`mercado.revision_linguistica`).

## 1. Reglas comunes a todo idioma
1. **Se redacta en el idioma**, no se traduce: mismas secciones, otro copy según cómo se dice y qué importa en ese mercado.
2. Una sola persona gramatical; tercera persona en el hero; sin atributo ni pregunta al lector en la primera pantalla.
3. Precios y garantía por placeholders; el generador aplica el formato del `locale`. Con monedas «dólar» distintas de USD (ARS, CAD, AUD, MXN…) se muestra el **código ISO** junto al importe (el `$` es ambiguo y `landing.validar` v0 lo trata como USD).
4. Glifos: la fuente debe cubrir los del idioma (`pl`: ł ą ę ś ć ń ó ź ż; `es`: ñ ¿ ¡ á é í ó ú ü; `it`: à è é ì ò ù; `fr`: é è à ç œ « »; `de`: ä ö ü ß; `ro`: ă â î ș ț). El lint avisa si un texto largo no tiene ninguno (`D5-COPY-GLIFOS`).
5. Cada idioma tiene **patrones rojos propios** además de los comunes (§3); **sin revisor nativo (J11, 2026-11-06: ya no es requisito, bloqueo ni gate)**: la calidad del idioma se asegura con la inmersión del mercado (J12), retraducción y segunda lectura con otro modelo (spec 5.10); `revision_linguistica.obligacion_legal_idioma` sin revisor nativo es solo el aviso P-06c del prechequeo (la regla `X32_REVISOR` de `scripts/validar_esquemas.py` queda por retirar: pedido a S-A/S-B).
6. Fechas, números y separadores por locale; símbolos de moneda según la tabla.

## 2. Tabla por idioma
| Locale | Tratamiento | Formato de precio | Plural/otros cuidados | Ejemplos de CTA (hero · compra · cierre) |
|---|---|---|---|---|
| `es-ES` | tú | `19,90 €` | «guion» sin tilde; ¿ ? ¡ ! | «Quiero la guía» · «Comprar la guía por {precio}» · «Quiero mi currículum puente» |
| `es-AR` | vos (voseo) | `19.990 ARS` | evitar peninsularismos; el `$` solo con código | «Quiero la planilla» · «Comprar la planilla por {precio}» · «Quiero armar mis costos» |
| `it-IT` | tu | `14,90 €` | «prezzo finale»; evitar «senza dieta» y plazos | «Voglio il planner» · «Acquista il planner a {precio}» · «Inizio con una settimana» |
| `pl-PL` | ty | `49,00 zł` | casos y plural de «dni»/«kart»; documentación en polaco | «Chcę zestaw kart» · «Kup zestaw za {precio}» · «Zaczynam od jednego pytania» |
| `en-US` | you | `$19.90` | sin BNPL ni PayPal | «Get the planner» · «Buy the planner for {precio}» · «Start with one week» |
| `en-CA` | you | `19.90 CAD` | CAD con código; ortografía canadiense `[SUPUESTO]` | ídem |
| `fr-FR` | vous (o tu según glosario) | `19,90 €` (espacio fino antes de €) | « » y espacios antes de ? ! : ; | «Je veux le guide» · «Acheter le guide pour {precio}» · «Je commence» |
| `de-DE` / `de-AT` | Sie (o du según glosario) | `19,90 €` | compuestos largos: +20 % de holgura en límites | «Ich möchte den Planer» · «Planer für {precio} kaufen» · «Jetzt anfangen» (evitar «jetzt» como urgencia) |
| `ro-RO` | tu | `49,00 lei` | sin ayuda de crisis verificada hoy (nota 25 §8) | a definir con glosario |

## 3. Patrones rojos propios del idioma (nota 25 §4)
| Idioma | Evitar |
|---|---|
| es | el RD 1907/1996 solo aplica con «pretendida finalidad sanitaria»; sin «¿Estás endeudado?», «tu ex», cifras de ahorro |
| it | «senza dieta», plazos («in 30 giorni»): patrón sancionado por la AGCM |
| pl | «cud», «leczy», plazos «w 7 dni»; sin «randki» (facilitación de citas, LM-04) |
| ro | propiedades de prevención o curación (Ley 56/2021, art. 7(2)) |
| fr | lenguaje terapéutico (CSP L5122-2) |
| de | «gegen» + dolencia (HWG §3: eficacia terapéutica); «Kurs mit Betreuung» invita a FernUSG |
| en | «cure», «heal», «lose N lbs», «make money», «passive income»; la ASA/FTC miran precio, urgencia y endosos |

## 4. Nombre de oferta descriptivo
Formato + objeto en el idioma local («Biblioteca de patrones», «Karty do rozmów dla par», «Weekly Meal-Prep Planner»); sin sufijos de marca (Studio, Academy, Master, Pro, Lab, Creative) ni nombres de estado o resultado. La **marca** es otra cosa: nace neutra, corta, sin condición, estado, resultado ni cifra. El nombre lo fija D3; D5 solo verifica.

## 5. Qué hacer cuando el idioma no tiene glosario ni revisor
Marcar `tono.nota` con `[SUPUESTO]`; elegir tratamiento informal salvo que el mercado sea formal por defecto; pedir **retraducción** (al español, para que el dueño la lea) y segunda lectura con otro modelo; no inventar giros idiomáticos; dejar en `brief.md` la lista de frases dudosas para el revisor humano por muestreo; si `obligacion_legal_idioma` aplica y no hay revisor nativo, **no continuar** (P-06).
