---
oferta_id: OF-202611-01
version: v1
moneda: EUR
precio_lista: 2490
bump_precio: 990
garantia_dias: 14
veredicto: FACTIBLE
razon: "1.48"
riesgo_nivel: verde
paises: [ES]
peor_pais: ES
marca_propuesta:       # hasta 3 (L1-13); [SUPUESTO] dominios sin verificar disponibilidad; el dueño elige UNA en el gate H antes de comprar
  - {nombre: "Regreso Laboral Claro", dominio: "regresolaboralclaro.example"}
  - {nombre: "Mi Ruta Laboral", dominio: "mirutalaboral.example"}
  - {nombre: "Currículum en Orden", dominio: "curriculumenorden.example"}
---
# Currículum y Guion tras una Pausa Laboral — oferta v1 (borrador del Maker, pendiente del gate H)

## A. Para decidir
- **Veredicto de factibilidad: FACTIBLE** (razón 1,48 ≥ 1,3 en el peor país; razón_obj 0,89: sirve para testear, **no para escalar** hasta tener `razon_obj ≥ 1`).
- **Riesgo: VERDE** (P1 · C1 · E1 · N1). Sin claims de ingresos, empleo ni salud; el encuadre es de rol («tras una pausa laboral»), sin atributos.
- **Gasto autorizado: NINGUNO.** `limites.yaml` está en `null` (pérdida máxima por oferta, topes diarios, países y locales): la oferta se calcula, pero nada gasta ni se activa hasta que el dueño los fije y selle.
- Pérdida máxima del test (plan, sin costos fijos): 294,00 EUR = 7 días × 42,00 EUR. Evento de optimización: Purchase.

## B. Economía por mercado (salida de `engine.factibilidad`; nada calculado a mano)
| País | IVA (bp) | Meta (bp) | AOV | CPA be visto | CPA obj | CPA real central | razón | razón obj | veredicto | presup. test mín | días | pérdida máx. test |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ES (peor) | 2100 | 300 | 25,89 EUR | 17,22 EUR | 10,33 EUR | 11,67 EUR | 1.48 | 0.89 | FACTIBLE | 266,10 EUR | 7 | 294,00 EUR |

Entradas: precio 24,90 EUR con IVA incluido + bump 9,90 EUR (39,8 % del precio) con toma del 10 % (`economia.tasa_bump_bp`); escenarios de embudo y tasas de `parametros.yaml` sin override; tarjeta y billeteras (v1). Tarifas **[SUPUESTO]** (no existe `tarifas.json` de F1).

## C. Ciclos de palancas
Ninguno: el primer barrido de precios dio FACTIBLE en el escalón 24,90 EUR (14,90 → NO_FACTIBLE, 19,90 → AJUSTADA, 24,90 → FACTIBLE; los tres corridos por el motor en un solo ciclo de diseño).

## D. Riesgo
| Activo | P | C | E | N | Nota |
|---|---|---|---|---|---|
| Producto, nombre, marca, subtítulo | P1 | C1 | E1 | N1 | Sujeto = el entregable; verbos de la herramienta; medida de uso (90 min) |
| 4 bonus y bump | P1 | C1 | E0 | N1 | Sin servicio, comunidad ni mentoría; ninguno es requisito de la promesa |
| Ángulo recomendado «pausa-como-relato» | P1 | C1 | E1 | N1 | «Una pausa laboral no es un hueco…»: tercera persona, sin atributo |
Nivel = máximo de los cuatro ejes = VERDE. Reencuadre heredado de D1 (amarillo → verde): «para madres que vuelven tras la baja» → «tras una pausa laboral larga»; «conseguir trabajo» → «ordenar y presentar la experiencia». Categoría de Meta [VERIFICAR]: empleo (guía informativa sin listados).

## E. Supuestos y decisiones de alto impacto (para el gate H)
1. Precio 24,90 EUR: menor escalón con razón ≥ 1,3; ≈ 28,9 USD con EUR/USD 1,16 (dentro de `economia.precio_lista_rango`; con otro tipo de cambio podría salir del rango y pasaría a H).
2. CPM de práctica (2,10 EUR) **no es una estimación de mercado**: con un CPM de 4,50 EUR el mismo diseño daría NO_FACTIBLE.
3. IVA 21 % y recargo de Meta 3 % [VERIFICAR]; tipo de IVA del PDF según el contador.
4. Sin casos previos: la oferta no usa cifras de personas ni testimonios; la prueba es la muestra y la lógica del producto.
5. **Marca (gate H):** el dueño elige **una** de las 3 marcas neutras de la cabecera (`marca_propuesta[]`: sin claim, sin sufijos vedados, sin marcas conocidas; X1 las revisa) **antes** de comprar el dominio. D3 no compra dominio ni crea dataset; la elegida pasa a `marca` en `v<n+1>`.

## F. Declaraciones para D4, D5 y X1
- UE: la garantía comercial de 14 días **no sustituye** el derecho legal de desistimiento (14 días); el checkout debe llevar la casilla separada de consentimiento y reconocimiento (entrega inmediata) y la función de desistimiento en línea (D5/X1-J07 [VERIFICAR Directiva (UE) 2023/2673]).
- `mercado.consumo.boton_arrepentimiento = true`.
- Descargo de alcance: «Guía informativa; no garantiza resultados de empleo ni sustituye asesoramiento profesional».

---

## Ficha de la oferta (12 puntos)
1. **Nombre y subtítulo.** Currículum y Guion tras una Pausa Laboral. *Guía con plantilla editable: ordena la experiencia por competencias y prepara un guion de 30 segundos para explicar la pausa.*
2. **Concepto.** Un pack (guía en PDF + plantilla editable) con el método Puente de la Pausa: del inventario de lo hecho al guion hablado, en 5 pasos.
3. **Público.** Persona que vuelve a buscar trabajo tras una pausa larga y no sabe cómo presentarla en el currículum ni en la entrevista (rol en tercera persona, sin atributos).
4. **Problema y dolores.** «No sé cómo explicar tres años sin trabajar en el currículum»; las plantillas gratuitas dejan el hueco sin resolver; vergüenza al explicarlo.
5. **Resultado y promesa.** Un currículum por competencias y un guion de 30 segundos, listos en unos 90 minutos. No promete empleo, entrevistas ni sueldo.
6. **Contenido completo.** Guía de 5 pasos (inventario de la pausa, traducción a competencias, reordenación del currículum, guion de 30 segundos, ensayo) + plantilla editable.
7. **Módulos.** Inventario · Competencias · Currículum · Guion · Ensayo.
8. **Bonus (4).** Banco de 60 frases · Checklist del perfil en línea · 3 plantillas de correo de reconexión · Ficha de ensayo de entrevista.
9. **Beneficios.** Claridad al presentar la experiencia; un guion hablado que evita improvisar; plantilla lista para editar.
10. **Objeciones.** «¿Me va a conseguir trabajo?» (FAQ: no lo promete; ordena y presenta la experiencia) · «Ya hay plantillas gratis» (diferencial: inventario de la pausa + guion hablado).
11. **Precio y garantía.** 24,90 EUR (IVA incluido), pago único; bump «12 respuestas modelo para preguntas de entrevista» a 9,90 EUR. Reembolso incondicional durante 14 días.
12. **Llamado a la acción.** «Descargar la guía y la plantilla».
