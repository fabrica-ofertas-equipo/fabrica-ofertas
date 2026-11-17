---
# Cabecera legible por máquina: scripts/lint_d3.py (L1-02) la compara con oferta.json y economia.json. Importes en UNIDAD MENOR (centavos), sin separadores;
# `razon` entre comillas (cadena de 2 decimales, tal cual la imprime el motor). Borra estos comentarios al rellenar.
oferta_id: OF-AAAAMM-NN
version: v1
moneda: EUR                 # = oferta.json.moneda = economia.json entradas_usadas.moneda
precio_lista: 0             # = oferta.json precio.lista.monto
bump_precio: 0              # = oferta.json bump.precio.monto (0 si bump = null)
garantia_dias: 14           # = oferta.json garantia.dias
veredicto: FACTIBLE         # = economia.json veredicto (FACTIBLE | AJUSTADA | NO_FACTIBLE)
razon: "0.00"               # = economia.json razon
riesgo_nivel: verde         # = oferta.json riesgo.nivel
paises: [XX]                # = oferta.json paises_segmentacion
peor_pais: XX               # el país cuyo economia.json se guardó
marca_propuesta:            # hasta 3 candidatos de marca NEUTRA (L1-13); oferta.json aún no tiene el campo. Dominio = [SUPUESTO] sin verificar; no se compra
  - {nombre: "", dominio: ""}
---
# <promesa.titulo> — oferta v<n> (borrador del Maker, pendiente del gate H)

<!-- SECCIONES A-F: para el DUEÑO, en español. La ficha (debajo de «## Ficha») va en el IDIOMA DE LA OFERTA: es lo que lee el «cliente frío» del QA (L3-1) y lo que lintea L1-03. -->

## A. Para decidir
- **Veredicto de factibilidad: <FACTIBLE|AJUSTADA|NO_FACTIBLE>** (razón <x,xx> frente a `economia.razon_min_factible`; razón_obj <x,xx>: ≥ 1 para ESCALAR, no solo para testear). Si hubo ciclos de palancas, cuántos.
- **Riesgo: <VERDE|AMARILLO-A|AMARILLO-B|ROJO reencuadrado>** (P · C · E · N) y qué lo sostiene.
- **Gasto autorizado:** <«NINGUNO: limites.yaml en null (…)» | el tope que sí está fijado>. La oferta se calcula, pero nada gasta ni se activa sin los límites sellados por el dueño.
- Pérdida máxima del test (plan, más costos fijos), días y evento de optimización (Purchase | InitiateCheckout) tal como los da el motor.
- Pendientes de idioma o de cumplimiento: revisor nativo, reglas de X1 para el locale, ayuda del país.

## B. Economía por mercado (salida de `engine.factibilidad`; nada calculado a mano)
<!-- Pega aquí la tabla de scripts/economia_por_pais.py (una fila por país del clúster; el peor país va marcado). Después, una línea con las entradas: precio, bump y su toma, escenarios (de parametros.yaml o override con fuente D2/M1), método de pago (v1: tarjeta y billeteras), y qué es [SUPUESTO]. -->

## C. Ciclos de palancas
<!-- Solo si hubo NO_FACTIBLE o AJUSTADA. Una fila por corrida del motor: ciclo (0 = propuesta inicial, 1, 2), palanca (precio | bump | mercado | …), precio, bump, razón del peor país, veredicto. «Ninguno» si el primer barrido ya dio FACTIBLE. -->

## D. Riesgo
<!-- Tabla por ACTIVO (producto/nombre/marca/subtítulo, cada bonus y el bump, ángulo recomendado) con P, C, E, N (códigos de la nota 25 §2.2) y nota. Nivel = máximo. Reencuadre aplicado (RE-xx) y qué deseo conserva. claims_prohibidos. Descargos y ayuda del macro-nicho. Mercado/matriz de X1 [PENDIENTE si no existe]. -->

## E. Supuestos y decisiones de alto impacto (para el gate H)
<!-- Lista numerada, cada ítem = una decisión que el dueño puede cambiar: precio elegido y por qué, CPM y tarifas de práctica, IVA y recargos [VERIFICAR], mercado, garantía, ausencia de casos previos, revisión nativa. Último ítem: «Marca (gate H)»: las marca_propuesta[] de la cabecera (hasta 3, neutras: sin claim, sin sufijos vedados, sin marcas conocidas); el dueño elige UNA antes de comprar el dominio; D3 no compra dominio ni crea dataset. -->

## F. Declaraciones para D4, D5 y X1
<!-- UE/UK: garantía comercial ≠ desistimiento legal; casilla separada y función de desistimiento en línea (D5/X1-J07). boton_arrepentimiento. Descargos y bloque de ayuda del país. Qué NO debe prometer ninguna pieza. -->

## G. Modelado (referente → nuestra oferta; mejoras pequeñas; palancas y dónde se ven; tarjeta antes/después; expresión no tocada)
<!-- SOLO en modo `modelado`; si no, borra esta sección. Forma de referencia: `ofertas/OF-202611-91/03-oferta/oferta.md` §G. Tabla «pieza · referente (visto) · nuestra oferta · igual / mejora / propio»; bloque `modelado` (`palancas[]` con `donde_se_ve` e `hipotesis_test`); tarjeta de 12 dimensiones de `modelado/antes_despues.json`; lista de la expresión del referente que NO se tocó. Skill `modelado-oferta` (MOD-5/MOD-6). -->

---

## Ficha de la oferta (12 puntos) — EN EL IDIOMA DE LA OFERTA
<!-- El encabezado puede ir localizado («## Karta oferty (12 punktów)») si conserva el «(12 …)»: lint_d3 lo reconoce para lintear la ficha. -->
1. **Nombre y subtítulo.** <promesa.titulo>. *<promesa.subtitulo>*
2. **Concepto.** <qué es, en una frase: el entregable y su método con nombre>
3. **Público.** <rol o situación en tercera persona; sin «tú» + atributo, sin pregunta>
4. **Problema y dolores.** <citas literales de voz_cliente.json, entre comillas>
5. **Resultado y promesa.** <el entregable y la medida de USO (tiempo para completarlo); nunca dinero, salud ni estado del lector>
6. **Contenido completo.** <lista exacta de lo que se entrega>
7. **Categorías o módulos.** <…>
8. **Bonus (3-5).** <uno por línea; ninguno es requisito de la promesa>
9. **Beneficios.** <de uso, con verbos de la herramienta>
10. **Objeciones.** <cada una con su respuesta: faq | diferencial | garantía | muestra>
11. **Precio y garantía.** <precio con IVA incluido y moneda; pago único; bump; reembolso incondicional de N días>
12. **Llamado a la acción.** <una línea, sin urgencia falsa>
