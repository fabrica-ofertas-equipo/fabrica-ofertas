# Ángulos, avatar e hipótesis de test

## 1. Niveles de conciencia (`nivel_conciencia`, N1-N5 del contrato; distintos de los niveles de autonomía N0-N4)
Pirámide de Schwartz `[SUPUESTO: lectura estándar; D6 §3.2 los usa así]`: **N1** inconsciente del problema · **N2** consciente del problema · **N3** consciente de la solución · **N4** consciente del producto · **N5** más consciente (listo para comprar). D6 testea en frío N2-N3 sobre todo; N1 es apuesta; N4 con comparables; **N5 no existe en el test**. D3 entrega **≥ 5 ángulos (el contrato exige ≥ 3), ≥ 3 niveles distintos**.

## 2. Cada ángulo (`angulos[]`)
| Campo | Regla |
|---|---|
| `angulo_id` | kebab **sin `_`** (alimenta los nombres de Meta, backbone 5.2); único; la medición se une por `oferta_id` + `adid` (5.3), nunca por nombre |
| `nivel_conciencia` | N1-N5 |
| `hook` | **patrón seguro** del macro-nicho (`claims-por-macro-nicho.md`): sin atributo ni pregunta sobre el lector, sin verbo de cambio con el lector de beneficiario, sin cifra ni plazo de resultado; el nivel de riesgo del ángulo ≤ el de la oferta |
| `objecion` | la objeción que el ángulo desactiva (de `avatar.objeciones` / D2 `objeciones_top`) |
| `prueba` | lo que lo sostiene: muestra, lógica del producto, garantía visible |
| `claims_ref` | **no vacío**, ⊂ `promesa.claims_permitidos[].claim_id` |
| `cita_voz_ref` | referencia a la cita que lo origina: `EV-nn` (evidencia E3 de `candidatos.json`) o `voz_cliente.json#<frase_id>`; `null` solo si el ángulo no nace de una cita (anótalo) |
Ángulos de **mecanismo** («Puente de la Pausa»), de **objeción**, de **tiempo de uso** y de **garantía visible** funcionan sin prometer resultado. **No** copies titulares de la competencia (`prohibido_copiar` de D2; L1-09: ≥ `compliance.ngrama_copia_palabras` palabras iguales = MAYOR, entre `ngrama_alerta_temprana_palabras` y esa cifra = alerta).

## 3. Avatar (`avatar`)
`quiere[]`, `cree[]`, `siente[]`, `lo_dice[]`, `objeciones[{texto, respuesta_en, severidad}]`, `vocabulario[]`.
- **`lo_dice[]` son citas TEXTUALES** de `voz_cliente.json` (`texto_literal`) o de la evidencia E3 del candidato, **en el idioma de la oferta**; nunca «mejoradas», parafraseadas ni traducidas (S8). Sin nombres, @handles ni datos personales.
- `objeciones[].respuesta_en`: dónde se responde (`faq`, `diferencial`, `garantia`, `muestra`, `bump`…); toda objeción tiene respuesta.
- `vocabulario[]`: el léxico del cliente del locale (de D2 y del glosario de M1).

## 4. Hipótesis de test (`hipotesis_test[]`)
Cada una con una **métrica distinguible con el volumen del test**: con ~`testeo.n_dec` (15) compras no se comparan ángulos por compras; se comparan por **CTR de enlace** y **costo por checkout iniciado**. Una hipótesis por línea; incluye la del bump (toma real vs `tasa_bump_bp`) y, si aplica, la de `precio_b`. Sin promesa de resultado: son para D7/D8.

## 5. Localización de los ángulos
Un ángulo se **escribe en el idioma local** (no se traduce el de otro mercado): otra `oferta_id` de la familia = ángulos, riesgo, economía y vocabulario rehechos. Segunda lectura nativa de título, subtítulo y ángulos (5.10): sin revisor nativo, retraducción + segunda lectura con otro modelo, declarado en `supuestos[]`.
