# Guía de lenguaje del panel — «que lo entienda cualquiera»

> Para quien escribe o cambia textos del panel (pantallas, botones, avisos, ayudas). Decisión del dueño (2026-11-06): *todo término técnico o palabra confusa se explica en simple; el panel tiene que ser amigable y fácil para ejecutar y ver todas las tareas del negocio.* **Ordenar y traducir, no recortar:** la información técnica sigue existiendo, pero un clic más allá («Detalle técnico»), nunca en el primer renglón.

## 1. A quién le hablas
A una persona que decide el negocio y **no** es programadora ni experta en marketing digital. Si una frase la tendría que googlear, está mal escrita.

## 2. Reglas
1. **Primero qué pasa y qué hacer.** Cada pantalla y cada aviso responde: *¿qué es esto? ¿está bien o mal? ¿qué hago ahora?* El dato técnico va después.
2. **Frases cortas, palabras de todos los días.** Un solo mensaje por frase. Evita la voz pasiva y los infinitivos largos.
3. **Los botones y títulos de acción empiezan con un verbo:** «Ver cómo firmarlo», «Copiar el comando», «Elegir el idioma». Nada de «Gestión de…», «Configuración de…».
4. **Cero siglas sin explicar.** Si una sigla es inevitable (IVA, ROAS), la primera vez lleva una ayuda corta (`ui.termino`) y el texto principal usa la palabra simple.
5. **Nada de nombres internos en el primer renglón:** ni rutas de archivos, ni ids, ni hashes, ni nombres de funciones o claves de configuración. Van en «Detalle técnico».
6. **Los estados se dicen con palabras y un icono, nunca solo con color:** «Listo», «Falta algo», «Espera tu firma», «Bloqueado», «Sin datos todavía».
7. **Números con su unidad y su sentido:** «12 ventas», «27 USD por venta», «hace 3 horas». Si una cifra no se puede medir todavía, dilo («todavía no hay datos»); nunca inventes.
8. **Los comandos nunca se esconden pero tampoco encabezan:** se muestran copiables (`ui.comando`) dentro de «Cómo hacerlo», con una frase que dice qué hace.
9. **Tono:** cercano y directo (tú), sin infantilizar ni exagerar. Se puede ser preciso sin ser técnico.
10. **No cambies identificadores:** rutas (`#/pulido`), claves de datos, nombres de archivos, `data-*`, ids de glosario. Solo cambia el texto que ve la persona.

## 3. Reemplazos (jerga → palabra simple)

| Término técnico | En el texto principal di… | Ayuda corta (qué es) |
|---|---|---|
| gate (A/S/H) | «punto de control» · «espera tu firma» · «aprobación» | un paso donde el sistema se frena a esperar que alguien lo apruebe |
| preflight | «chequeo antes de lanzar» | revisa de una vez que todo esté listo (pagos, páginas, medición) antes de gastar un peso |
| hash / sha256 | «huella» | una marca única del archivo: si alguien lo toca, la huella cambia |
| sello / sellado | «visto bueno firmado» · «aprobado y firmado» | la aprobación de cumplimiento quedó firmada sobre esa versión exacta |
| QA | «revisión de calidad» | un revisor independiente que mira el trabajo sin conocer cómo se hizo |
| Maker | «quien lo prepara» · «la IA que lo prepara» | |
| skill | «guía de trabajo» (la primera vez: «guía de trabajo (skill)») | las instrucciones que sigue cada IA para hacer su tarea |
| motor | «el sistema» · «el sistema automático» | el programa que mueve cada oferta de un paso al siguiente |
| borrador | se mantiene | |
| CBO | «campaña con presupuesto compartido» | Meta reparte el presupuesto entre los anuncios de la campaña |
| CPA | «costo por venta» | cuánto se gasta en anuncios por cada venta |
| ROAS | «retorno por dólar invertido» | por cada dólar en anuncios, cuántos vuelven en ventas |
| CTR | «% que hace clic» | |
| CPM | «costo por mil vistas» | |
| UTM | «etiqueta del anuncio» | dice de qué anuncio vino cada venta |
| píxel / dataset | «medidor de Meta» | avisa a Meta cuando alguien compra, para que sus anuncios aprendan |
| payload | «los datos que se envían» | |
| checkout | «pantalla de pago» | |
| bump | «oferta extra al pagar» | una casilla para sumar un producto en el mismo pago |
| upsell | «oferta después de pagar» | |
| break-even / BE | «punto de equilibrio» | lo máximo que puedes pagar por una venta sin perder plata |
| ledger | «libro de movimientos» | |
| N0…N4 | «nivel de autonomía 0 a 4» | cuánto hace el sistema solo: nivel 0 = todo lo apruebas tú; más alto = más lo hace solo |
| dry-run / simulación | «simulacro» | ejecuta todo pero **no cambia nada** |
| JSON / YAML | «archivo de datos» | |
| latido | «última señal de vida» | |
| locale | «idioma y país» | |
| schema / esquema / contrato | «formato esperado» | |
| fail-closed | «por seguridad, si falta un dato no se hace nada» | |
| API / endpoint / SSE / token | **no aparecen** en el texto principal | |
| DoD | «criterios para darla por terminada» | |
| snapshot | «foto del momento» | |
| PAUSA | «PAUSA (freno de emergencia)» | detiene todo el gasto hasta que una persona la levanta |
| freno de captura | «freno de la captura de anuncios» | el sistema lo puso solo cuando Meta bloqueó una visita; solo lo levanta el dueño |
| madre / hija (oferta) | «oferta original» / «versión en otro idioma» | |
| OSS (IVA UE) | «régimen de IVA de la UE (OSS)» | |
| idempotente, hook, runner, parser, ETL, TTL, PII | no aparecen; describe lo que hacen | |

## 4. Estructura de una pantalla
- **Título** claro (sustantivo o pregunta simple) y **una frase de para qué sirve** debajo.
- **«Qué hacer ahora»** arriba si hay algo pendiente (`ui.atencion`), con un botón de verbo.
- Números grandes con su explicación en una línea.
- Todo lo técnico (rutas, hashes, JSON, comandos largos) dentro de «Detalle técnico».
- Estados vacíos: decir **qué falta, quién lo produce y cómo** (`ui.vacioConPasos`).

## 5. Nombres de las pantallas (los que ve la persona)
Se cambió solo el nombre visible: las rutas (`#/landing`…), los atajos `g`+letra y los iconos siguen igual. Quien escriba el nombre viejo en el buscador (Ctrl/⌘+K) igual la encuentra.

| Ruta | Antes | Ahora |
|---|---|---|
| `#/landing` | Landing | **Página de venta** |
| `#/skills` | Skills | **Guías de trabajo** |
| `#/pulido` | Pulido | **Mejoras pendientes** |
| `#/registro` | Registro | **Historial** |
| `#/descubrimiento` | Descubrimiento | **Radar de ofertas** |
| `#/operacion` | Operación | **Resultados** |
| `#/agentes` | Agentes | **Equipo de IA** |
| `#/parametros` | Parámetros y límites | **Límites y reglas** |
| `#/sistema` | Sistema | **Salud del sistema** |
| `#/poscompra` | Poscompra | **Después de la venta** |

Los nombres de las etapas de una oferta también se dicen en palabras simples: «Página de venta y pago» (D5), «Anuncios» (D6) y «Después de la venta» (D10). Si un texto nombra una pantalla, usa el nombre de esta tabla.

## 6. Prueba antes de dar por terminado un texto
- ¿Lo entiende alguien que nunca programó ni hizo publicidad en internet?
- ¿Dice qué pasa **y** qué hacer?
- ¿Quedó alguna sigla o palabra rara en el primer renglón? Si sí: reemplázala o explícala.
- ¿Cambiaste algún identificador? Si sí: reviértelo.
- ¿Las pruebas siguen en verde (`node --test 'tests/dashboard/'*.mjs`, Python de `tests/dashboard`)? Si una prueba comprobaba el texto viejo, actualiza la prueba al texto nuevo.
