# Las 30 líneas rojas (promesas, contenidos y modelos de negocio): PROPUESTA, SIN APROBAR

**Estado:** `empresa/limites.yaml` tiene `lineas_rojas: []` (el dueño aún no las aprueba) y `subnichos_prohibidos: []` **por diseño** (ningún tema se excluye). Estas 30 son la propuesta de la nota 25 §3.3 (9 de promesa, 10 de contenido, 11 de modelo de negocio), la que `docs/00-decisiones-y-tareas-del-dueno.md` §0.B.5 pide aprobar («Recomiendo: aprobar»). Hasta que el dueño las apruebe y las cargue en `limites.yaml` (`[PENDIENTE: lo hace el dueño]`, `dependencias.md` D-05), **X1 las aplica como criterio de dictamen** pero no hay bloqueo por `limites` en el motor: el sello solo exige lint sin ROJO + QA PASS.

**Dónde viven los datos:** texto completo y todas las URL en `docs/_historial/hwr-semillas/casos-frontera.yaml` (campo `lineas_rojas`, ids en minúscula) y en la nota 25 §3.3. Aquí solo el resumen operativo. `base`: **global** = texto oficial leído que rige en todos los mercados; **local** = texto oficial de un mercado o resumen; **prudencia** = decisión propia de diseño **sin** texto oficial que la prohíba (no atribuirla a Meta ni a Stripe). Un rojo por prudencia se mantiene porque el daño posible es real y su salida es barata (reencuadre o derivación).

**Forma en `limites.yaml`** (esquema `contratos/limites.schema.json`): `lineas_rojas[] = {id (kebab), tipo (promesa|contenido|modelo_negocio), descripcion (≥ 5 caracteres)}`. El Maker entrega `limites.propuesta.yaml` (`templates/limites.propuesta.yaml`); nunca escribe `limites.yaml`.

| Id | Tipo | Base | Resumen (nota 25 §3.3) |
|---|---|---|---|
| LP-01 | promesa | global | Curar, sanar, eliminar, revertir o prevenir una enfermedad; en particular diabetes, herpes, tiroides, psoriasis, ébola, cáncer, autismo, alzhéimer, párkinson, ELA y VIH, aunque lo diga un profesional. Solo «manejo de síntomas» queda fuera de la lista de Meta; nuestro lint es más estricto y se declara política propia |
| LP-02 | promesa | local | Cifra, ritmo o plazo de pérdida de peso («8 kg en 30 días») |
| LP-03 | promesa | global | Ingreso, ahorro o retorno prometido, con o sin cifra, con o sin plazo, garantizado o no; promesas de facilidad sobre dinero («sin inversión», «sin experiencia», «fácil», «rápido», «con poco esfuerzo»); «ingresos pasivos», «libertad financiera», «renunciá a tu trabajo»; rendimiento pasado como expectativa. Meta admite estas […] |
| LP-04 | promesa | global | Controlar o recuperar la voluntad de un tercero (ex, pareja) con plazo o garantía; esoterismo de resultado (rituales, amarres); garantía de reembolso atada a un resultado sobre otra persona |
| LP-05 | promesa | global | Testimonios falsos o sintéticos, antes/después, capturas de resultados, reseñas generadas, escasez o precio de referencia ficticios, venta de alta presión |
| LP-06 | promesa | global | Afirmar o insinuar un atributo del espectador (condición física o mental, deuda o situación financiera vulnerable, estado familiar, edad, orientación), también como pregunta |
| LP-07 | promesa | local | Claims fisiológicos sin evidencia competente (metabolismo, hormonas, cortisol, nervio vago, detox, «activa tu…») |
| LP-08 | promesa | local | Aval o credencial sanitaria o financiera falsa o aparente (bata, logos de organismos, «avalado por médicos», avatar «asesor») |
| LP-09 | promesa | global | Incoherencia anuncio-landing-producto-descriptor (camuflaje): el producto real promete algo que el anuncio no dice |
| LC-01 | contenido | global | Dosis, suplementos, medicación, fármacos para bajar de peso; interpretar análisis o IMC con umbrales diagnósticos |
| LC-02 | contenido | global | Conductas alimentarias extremas o de trastorno alimentario, ayuno prolongado, dietas muy bajas en calorías, detox con ayuno |
| LC-03 | contenido | global | Diagnóstico a distancia (del lector o de terceros), terapia, EMDR o trauma, cuestionarios clínicos |
| LC-04 | contenido | prudencia | Planes de salida o seguridad ante abuso; confrontación del abusador o de quien ejerce control; contacto con quien pidió no ser contactado; abuso como gancho. (La preparación de conversaciones difíciles NO es esta línea.) |
| LC-05 | contenido | prudencia | Vigilancia o monitoreo de pareja o hijos sin consentimiento |
| LC-06 | contenido | local | Asesoramiento personalizado de inversión; recomendar instrumentos, emisores o cripto; documentos legales «listos para firmar». En Alemania, además, ayuda fiscal personalizada (veto, StBerG §5). En el resto, una hoja o calculadora fiscal que reproduce una fórmula u hoja de trabajo oficial publicada, con los datos del propio […] |
| LC-07 | contenido | global | Contenido sexual para gratificación (incluida IA) y productos de excitación |
| LC-08 | contenido | prudencia | Dieta, ejercicio o suplementos PRESCRITOS (qué comer, cuánto, qué ejercicio hacer, qué dar al bebé) en embarazo, posparto, lactancia, menores o salud infantil clínica. Los registros que el comprador completa con lo que indica su médico o pediatra, las listas de compras y la reproducción literal, con fecha y enlace, de una […] |
| LC-09 | contenido | global | Datos de salud, ciclo, deuda, ruptura, ingresos o impuestos en píxel, API de Conversiones, audiencias, URL, UTM, nombres de evento, quizzes con puntaje que infieren un estado, listas de compradores subidas a cualquier plataforma, etiquetas o segmentos del proveedor de correo, ítem del recibo, asunto y remitente de los correos |
| LC-10 | contenido | prudencia | Prácticas con riesgo físico agudo: hiperventilación o retención del aliento, apnea, inmersión en agua fría o caliente, sauna, ayuno de más de 24 h, carga máxima sin supervisión, calor o frío extremos |
| LM-01 | modelo_negocio | global | Multinivel, pirámide, comisión por reclutar o por referidos de referidos, reventa del pack, «oportunidad de negocio» con clientes o ubicaciones |
| LM-02 | modelo_negocio | global | Reparación de crédito, liquidación, negociación o consolidación de deudas, asesoría de deuda, agencias de cobro; contenido que promueve servicios de consolidación, perdón o refinanciación de préstamos estudiantiles (Meta, HC 1695974997209192, según la crítica red team; para guías informativas es política prudencial) |
| LM-03 | modelo_negocio | global | Inversión y corretaje, CFD y binarias, ICO, funded prop trading, señales; exchanges y afiliados cripto; crédito, hipoteca o seguro sin autorización; comisiones por derivar a proveedores |
| LM-04 | modelo_negocio | global | Servicios que conectan personas (citas, matchmaking, clubes de solteros), agencias matrimoniales; facilitación de citas (perfiles, biografías y mensajes de apertura para aplicaciones de citas). La literatura o el entretenimiento sobre relaciones y las tarjetas para una cita en persona no lo son (HC 765622867361201, leído hoy ✔) |
| LM-05 | modelo_negocio | prudencia | Servicio humano personalizado (coaching 1:1, consultas por mensaje, telemedicina) o comunidad en vivo |
| LM-06 | modelo_negocio | global | Tratamiento de adicciones, recetados y telemedicina (LegitScript y permiso) |
| LM-07 | modelo_negocio | global | Menores como destinatarios o uso de su imagen; exhortación directa a niños |
| LM-08 | modelo_negocio | global | Elusión de la aplicación: cuentas o páginas paralelas, cloaking, re-subir texto rechazado con cambios cosméticos |
| LM-09 | modelo_negocio | global | Cobrar con Stripe productos no declarados en la solicitud, o repartir ventas entre descriptores para esconder disputas |
| LM-10 | modelo_negocio | global | Empaquetar o revender información, trámites, formularios o ayudas oficiales gratuitos sin valor añadido demostrable por el propio producto, o tramitarlos en nombre del cliente |
| LM-11 | modelo_negocio | global | Guías, calculadoras o asesoría hipotecaria: «Mortgage consulting» está restringido en general y prohibido en EE. UU. y Canadá; qué entiende Stripe por «consulting» es [VERIFICAR]: hasta tener respuesta escrita de Stripe es N2 y no sale |

## Cómo se usan en un dictamen

- Cada hallazgo ROJO cita **la línea roja** (`lp-03`…) y la **frase literal** que la activa; nunca «por el tema».
- Cada caso ROJO activa al menos una línea roja (el verificador de la suite lo exige).
- Las zonas grises (astrología, señales de relación dañina, ayuno, dejar de fumar, inversión conceptual, cripto de custodia) **no** son líneas rojas: se resuelven con el dueño (`preguntas-abiertas.md` P-06) y, cerradas, pasan como `pasa_con_gate`.
- Las líneas con `base: prudencia` (LC-04, LC-05, LC-08, LC-10, LM-05) no se citan como política de plataforma.
- LM-08 (elusión: cuentas paralelas, cloaking, re-subir texto rechazado con cambios cosméticos) bloquea siempre; **prohibido rotar cuentas o clonar embudos**.
- Un cambio de línea roja la propone el Maker en `limites.propuesta.yaml`; la aprueba el dueño con firma; **relajarla** exige aprobación explícita (spec 14 §4 paso 10).
