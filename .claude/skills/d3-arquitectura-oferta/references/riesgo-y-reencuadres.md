# Riesgo por candidato, activo y mercado: ejes P·C·E·N, niveles y reencuadres

Fuente primaria: `docs/_investigacion/25-marco-salud-relaciones-dinero.md` (§2 ejes y tabla, §3.3 líneas rojas, §4 reencuadres, §5 ángulos, §7 contenido, §8 mercados, §11 calibración). Aquí solo se destila lo que D3 aplica; ante duda, manda la nota. **El riesgo se evalúa por promesa, contenido, encuadre y categoría de negocio, nunca por tema** (decisión 13).

## 1. Qué hace D3 con el riesgo
1. **Hereda** `riesgo` de D1 y lo **re-verifica** sobre cada activo de la oferta (D3 puede subir el nivel sin permiso; solo lo baja aplicando un reencuadre verificable, y X1 aprueba toda bajada desde ROJO o AMARILLO-B).
2. Activos que cuentan (el nivel de la oferta es el **máximo** entre todos): nombre del producto, del método y de la marca; dominio; título y subtítulo; cada bonus; el bump; el ángulo recomendado (`angulos[]`); `claims_permitidos`; la garantía; la prueba. **Un bonus o un bump pertenecen al candidato**: si por sí solos serían ROJO, la oferta es ROJO hasta quitarlos.
3. Propone los **ejes** (códigos de §2); el **nivel lo calcula el código**: `.venv/bin/python -m scripts.nivel_riesgo --P <código> --C <código> --E <código> --N <código> --json` (única implementación ejes → nivel; `nivel` en minúscula, `subnivel` aparte, `colores`, `veredicto_riesgo`, `version_tabla`; `nivel` es `null` fuera de macro-nicho; N0 en macro se rechaza). Si un snapshot trae solo colores, ≥ 2 amarillos = B [SUPUESTO]. El modelo no baja un nivel que un lint subió (`compliance.lint_claims`, X13 de `validar_esquemas`).
4. Escribe `oferta.riesgo{P, C, E, N, nivel, reencuadre_aplicado, fuentes, categoria, claims_a_evitar, angulo_seguro}`: P/C/E/N en **colores** (`verde|amarillo|rojo`: P0-P1, C0-C1, E0-E1, N0-N1 = verde; P2s, C2, N1s = amarillo; P2n-P3, C3, E2-E3, N2-N3 = rojo), `nivel` = máximo de los cuatro. Los **códigos** de eje (P1, C2…) van en `oferta.md` §D (el contrato aún no los guarda: `dependencias.md`).
5. Un riesgo ROJO no avanza: **reencuadre** (máx. 2 intentos) o `parada.json` `riesgo_rojo_sin_reencuadre` / devolución a D1.

## 2. Ejes y códigos (resumen operativo de la nota 25 §2.2)
| Eje | Código | Criterio |
|---|---|---|
| **P** promesa (qué afirman producto, nombre, marca, anuncio, landing) | P0 | El sujeto es el archivo, plan, tabla o calendario; cifras solo del entregable |
| | P1 | Beneficio de **uso** con verbos de la herramienta (registra, ordena, calcula, planifica, compara). El producto/método/marca no es causa de un cambio en el cuerpo, el ánimo, el dinero o la deuda del lector, con o sin cifra |
| | **P2s** | Cifra reproducible por el lector, con supuestos visibles y rótulo «ilustrativo» **en el mismo medio** (suma de la tabla del propio producto; nunca peso, salud, ingresos ganados ni estados de otra persona) |
| | **P2n** | Resultado atribuido al lector (corporal, emocional, económico o de facilidad), **con o sin cifra y con o sin plazo**: verbos de cambio con el lector de beneficiario, nombres de estado («Glucosa Estable», «Cero Deudas»), facilidad sobre el resultado («sin experiencia», «sin inversión»), reseñas con cifras |
| | P3 | Cura o diagnóstico; ingreso garantizado; control de un tercero; testimonio sintético, antes/después, escasez o precio ficticios; claim fisiológico; camuflaje anuncio-producto |
| **C** contenido (qué instruye, qué daño podría causar; lo mide sobre todo D4) | C0-C1 | Plantillas, calendarios, listas, métodos con ejemplo, recetas con tabla pública |
| | C2 | Progresión de carga, criterio nutricional, seguridad alimentaria con cifras, calendarios de plazos y cálculo con tasas, lectura de contratos, guion sobre ruptura/duelo/separación con hijos, deuda propia, registro de medicación indicada, población vulnerable |
| | C3 | Dosis, diagnóstico, tratamiento, kcal objetivo, ayuno prolongado, planes de seguridad, vigilancia, recomendar instrumentos, documentos legales personalizados, dieta/ejercicio/suplementos **prescritos** a menores, embarazo o lactancia, riesgo físico agudo |
| **E** encuadre (cómo se dirige al espectador; lo fija cada pieza) | E0-E1 | Habla del producto, o rol/situación en **tercera persona** sin «tú» + atributo ni pregunta («quien vuelve a trabajar tras una pausa») |
| | E2 | Afirma, implica o **pregunta** un atributo del lector (edad, sexo, estado familiar o civil, salud, situación financiera vulnerable, «tu ex») o juzga su valor, cuerpo o aspecto («inútil», «deja de sentirte…») |
| | E3 | Habla a menores, usa su imagen o los exhorta a comprar |
| **N** negocio (Meta, Stripe, consumo, salud, finanzas) | N1 | Vigilada: nutrición y fitness generales, hábitos, pareja, crianza, presupuesto, empleo, impuestos y deuda propia (**todo candidato en macro es al menos N1**; N0 solo existe para `fuera_de_macro_nicho`) |
| | N1s | Vigilada **por función**: el entregable mide o registra el cuerpo del comprador, o este carga datos sensibles en un formulario, quiz o calculadora web. Los temas (embarazo, ruptura, deuda, impuestos…) **no** son N1s |
| | N2 | Exige autorización o conecta personas: citas (incluida la facilitación), telemedicina, inversión, crédito, hipotecas, afiliado financiero, servicio humano, bolsa de vacantes o colocación garantizada, certificación profesional, reventa de trámites oficiales |
| | N3 | Prohibida: multinivel, get-rich-quick, CFD, binarias, reparación de crédito, consejería de deuda, contenido sexual |

**Tabla ejes → nivel** (única; en este orden): ROJO si P ∈ {P2n, P3} o C = C3 o E ∈ {E2, E3} o N ∈ {N2, N3}; AMARILLO si no es rojo y (P = P2s o C = C2 o N = N1s), subnivel **B** con dos o más de esos tres y **A** con uno; VERDE en otro caso. `fuera_de_macro_nicho` no tiene nivel (se rechaza antes de calcular).
**Anclas** (para clasificar por analogía): costeo, márgenes y tarifas = N1; sueño, hábitos y pausas = N1 en macro; registro o calendario sin consejo = C1; guion sobre separación, duelo o ruptura = C2; logística de coparentalidad = C1; registro de medicación = C2; caminar y movilidad suave = C1; tabla de conservación o temperaturas = C2; un tema vigilado es una **etiqueta**, no un eje.
**Prueba del espectador ajeno** (E): la frase debe ser verdadera y neutra para cualquiera que la lea; si solo tiene sentido para quien padece X, afirma X.

## 3. Qué exige cada nivel (nota 25 §2.4)
| | VERDE | AMARILLO-A | AMARILLO-B | ROJO |
|---|---|---|---|---|
| Ángulos | patrones seguros (`claims-por-macro-nicho.md`) | producto, criterio o herramienta; sin condición | igual, sin gancho de ruptura, duelo, abuso ni deuda en el creativo | ninguno hasta reencuadrar |
| Fuentes | cifras y reglas atribuidas | cada hecho con fuente T1/T2 (D4) | igual, texto fiel a la fuente | — |
| Descargo y ayuda | aviso de alcance; **todo producto de conflicto de pareja o familia (también verde): «Si temes por tu seguridad, no uses este material» + línea de ayuda por violencia del país** | aviso por tipo de producto | aviso reforzado y bloque «Si necesitas ayuda ahora» con números de `ayuda_por_pais.yaml` | no corrigen un claim |
| Gate de D3 | autonomía N0-N2: **H siempre** (`contratos/gates.json`); autonomía N3: S solo con VERDE, 0 amarillos abiertos y `razon ≥ 1,5` (ver `devoluciones-y-escalado.md`) | `requiere_gate_humano_legal = true` | `true` + decisión H + ayuda verificada del país | no se lanza |
| Cuota | sin tope | `limites.cuota_gasto_amarillo_max_pct` (clave de `limites` 1.3.0; `null` = solo verde) | `limites.cuota_gasto_amarillo_b_max_pct` (≤ la anterior; `null` = sin amarillo-b) | — |
`requiere_gate_humano_legal` es un nombre heredado del contrato: significa **gate H del dueño**, no consulta a abogado (decisión 14). Con AMARILLO es `true`; con VERDE, `false`.

## 4. Mercado (X1 manda; el overlay solo sube)
La matriz país × nivel vive en `empresa/compliance/matriz_pais_nivel.yaml` (X1) [PENDIENTE: no existe hoy]. Hasta que exista, D3 aplica la tabla de la nota 25 §8.1 como `[HIPÓTESIS]` y la declara en `supuestos[]`: exposición V (bajo) hasta amarillo-b con ayuda verificada; A (medio) amarillo-a, B con gate H, ayuda y revisión; A+ (medio-alto: IT, FR, ES, DE en dinero y salud según el caso) amarillo-a **solo con gate H del dueño por país × macro-nicho × nivel**; R (alto) verde de hogar sin cifra de ahorro, instrumento ni ingreso. Sin ayuda verificada de la categoría central (duelo, ruptura, abuso, salud mental, peso con seguimiento), **el producto no sale en ese país** (`parada.json` `fuera_de_mercado_permitido`/`detenida_por_dato_faltante`). Un nivel mayor que `limites.nivel_max_lanzable[macro_nicho]` (objeto por macro con `verde`, `amarillo-a` o `amarillo-b`; **`null` = SOLO VERDE**, fail-closed: no es un dato faltante ni «sin gasto») o macro/país fuera de `limites.*_permitidos` tampoco sale.

## 5. Reencuadres seguros RE-01…RE-15 (nota 25 §4)
Válido si: (1) **conserva problema y deseo central**, (2) el nivel baja a ≤ amarillo, (3) anuncio = landing = producto = descriptor (si no, es camuflaje, LP-09). **Máximo 2 intentos**; cambiar solo palabras es elusión (LM-08) y el registro de rechazos es por claim. `deseo_conservado`: **total** (el comprador reconocería la misma métrica de éxito) o **parcial** (se estrecha o desplaza B; vale solo si D1 aporta una cita E3 del B reencuadrado; si no, **bloquea** y lo adyacente entra como otro candidato).
| Id | Transformación | Ejemplo |
|---|---|---|
| RE-01 | de la condición al método | «¿Estás endeudado?» → método de 4 pasos en una hoja |
| RE-02 | de la cifra a la herramienta | «Perdi 8 kg in 30 giorni» → planner settimanale dei pasti con lista della spesa |
| RE-03 | del diagnóstico a la organización | quiz de ansiedad → registro para la consulta |
| RE-04 | de los ingresos a la plantilla de costos | «Ganá USD 500 con velas» → costeo por gramo de cera |
| RE-05 | de la cura al criterio medible | «Antiinflamatoria» → legumbres con fibra por porción |
| RE-06 | del control del otro a la preparación propia | «Recupera a tu ex en 7 días» → 10 preguntas antes de decidir |
| RE-07 | del plazo del efecto al del formato | «Dormí en 7 días» → planificador nocturno de 14 días |
| RE-08 | de la 2.ª persona con atributo al rol en 3.ª | «Si ganás poco…» → presupuesto por día de cobro |
| RE-09 | de la prueba inventada al producto | antes/después → vista previa del PDF |
| RE-10 | del servicio al archivo | club de solteros → 50 tarjetas |
| RE-11 | del dato sensible al evento genérico | `deuda_alta` → `checkout_iniciado` |
| RE-12 | de la recomendación al marco impersonal | «Invertí en estas 5 acciones» → glosario con tres tasas rotuladas |
| RE-13 | del menor al adulto responsable | guía para adolescentes → guion para el adulto |
| RE-14 | de la garantía de resultado al precio único | «Ahorrás o te devolvemos» → 14 días incondicionales |
| RE-15 | de la vigilancia al acuerdo | «Revisá su celular» → acuerdo de privacidad entre los dos |
**Sin reencuadre** (se bloquea y se abre otro candidato): curar una enfermedad, ingreso pasivo, reconquista garantizada, dosis, plan de salida de un abuso, trading, adicciones, dieta infantil, contenido sexual.
En `oferta.riesgo.reencuadre_aplicado`: `aplicado: true`, `nivel_original` (> `nivel`) y `descripcion` (qué se cambió en promesa, contenido, encuadre o negocio). Si lo hizo D1, se **hereda**; si D3 aplica uno nuevo, se suma y se explica en oferta.md §D.

## 6. Líneas rojas (30; promesas, contenidos y modelos de negocio; ids de `casos-frontera.yaml`)
Promesa: **LP-01** curar/sanar/revertir/prevenir una enfermedad · **LP-02** cifra, ritmo o plazo de pérdida de peso · **LP-03** ingreso, ahorro o retorno prometido (con o sin cifra), facilidad sobre dinero, «ingresos pasivos» · **LP-04** controlar la voluntad de un tercero; esoterismo de resultado · **LP-05** testimonios sintéticos, antes/después, escasez o precio ficticios · **LP-06** atributo del espectador, también como pregunta · **LP-07** claims fisiológicos sin evidencia · **LP-08** aval o credencial falsa o aparente · **LP-09** camuflaje.
Contenido: **LC-01** dosis, suplementos, medicación · **LC-02** conducta alimentaria extrema · **LC-03** diagnóstico a distancia, terapia · **LC-04** planes de salida ante abuso; confrontar al abusador · **LC-05** vigilancia de pareja o hijos · **LC-06** asesoría personalizada de inversión, documentos legales «listos para firmar» (Alemania: ayuda fiscal personalizada) · **LC-07** contenido sexual · **LC-08** dieta/ejercicio/suplementos prescritos en embarazo, posparto, lactancia o menores · **LC-09** datos sensibles en píxel, URL, UTM, listas o recibos · **LC-10** riesgo físico agudo.
Modelo de negocio: **LM-01** multinivel · **LM-02** reparación de crédito, consejería de deuda · **LM-03** inversión, corretaje, CFD, cripto · **LM-04** conectar personas, facilitación de citas · **LM-05** servicio humano o comunidad en vivo · **LM-06** adicciones · **LM-07** menores · **LM-08** elusión (cuentas paralelas, cloaking, re-subir texto rechazado) · **LM-09** cobrar productos no declarados · **LM-10** reventa de trámites oficiales gratuitos · **LM-11** asesoría hipotecaria.
Texto completo, fuente y base (oficial vs prudencia) en `casos-frontera.yaml` → `lineas_rojas[]`. `empresa/limites.yaml` → `lineas_rojas[]` es la lista que **aprueba el dueño** (hoy vacía: [PENDIENTE]); D3 aplica las 30 de la nota mientras tanto y lo declara.
