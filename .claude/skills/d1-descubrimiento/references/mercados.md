# Mercados, idioma y moneda en D1

> Dueño de la ficha de país: **M1** (`departamentos/16-mercados-localizacion.md`, skill `.claude/skills/m1-mercados-localizacion`; contrato de D1 en su `.claude/skills/m1-mercados-localizacion/references/interfaz-d1.md`). D1 **lee** la ficha, no la reconstruye. Decisión del dueño: **mercado global por idioma/locale; ningún país es prior** (Polonia e Italia son **hipótesis** de partida; las cifras de los creadores también). Stripe es de una **LLC de EE. UU.** (decisión resuelta); Meta con una cuenta y un píxel por oferta, sin Instagram.

## 1. Unidad de trabajo
- **Una corrida de snapshot = un locale** (`es-MX`, `pl-PL`…; BCP-47 con región). El barrido puede cubrir varios (`barridos/*.json#locales[]` en el diseño del banco `[PENDIENTE: CT-4]`). `mercado.paises` = países de segmentación (ISO-2).
- **La evidencia es por locale.** Lo hallado en `es` no se asume válido en `es-AR`, `pl` ni `it`: el traslado exige barrido local (backbone §3.2). Una evidencia de un locale presentada como válida en otro sin barrido local es el defecto S15.
- Idioma + país no bastan para fijar el locale (`es` + `MX` → `es-MX`): lo resuelve M1 (`locales_activos.yaml#paises`).

## 2. De dónde salen las entradas (hoy)
| Entrada | Fuente | Estado |
|---|---|---|
| locales permitidos y países | `empresa/limites.yaml` (`locales_permitidos`, `paises_permitidos`) | **vacíos**: ningún locale permitido → preflight bloquea |
| locales activos, prioridad, presupuesto de exploración | `empresa/mercados/locales_activos.yaml` | no existe `[PENDIENTE: M1]` |
| términos de búsqueda por locale (`dolor[]`, `sustitutos[]`, `sitios_site[]`, `fuente_id_candidatos[]`) | `empresa/mercados/terminos_busqueda/<locale>.yaml` | no existe `[PENDIENTE: M1]`; un término sin revisión nativa va `[VERIFICAR]` y no entra a un barrido programado |
| ficha de país (poder adquisitivo, medios de pago, métodos locales) | `empresa/mercados/paises/<ISO>.json` y `ofertas/<id>/mercado.json` | atlas por construir `[PENDIENTE: M1]`; `mercado.json` siempre `estado_decision = hipotesis` |
Mientras M1 no publique esas piezas, **el locale y los países salen del brief y los confirma el dueño en el encargo**; lo registras `[SUPUESTO]`. Los términos del Maker son `[VERIFICAR]` hasta una segunda lectura nativa (otro modelo o una persona); `scripts/modelado/barrido/frases_forma.yaml` ya trae las frases estructurales en 8 idiomas (es, en, pt, it, fr, de, pl, ro) con sus países.

## 3. Dinero: reglas que no se rompen
- **Importes = entero en unidad menor + ISO 4217** (`comunes#dinero_no_negativo`: `{"monto": 900, "moneda": "USD"}`); decimales como **cadena**; nunca `float`. No hay `moneda` suelta.
- `precio_plausible.min/max` van en la **moneda de cobro** del brief (la que cobra la LLC). **Sin cotización registrada no se convierte** a moneda local ni se inventa un tipo de cambio; el precio local visible y los medios de pago los fija M1/D3. La `currency` de la Biblioteca es la de la **cuenta del anunciante**, no la del mercado, ni la del precio de su landing: nunca la uses como precio.
- **Poder adquisitivo:** en mercados de poder adquisitivo bajo el ticket baja y el CPA sin backend suele salir inviable: ajusta `precio_plausible` y `viabilidad_cpa` y dilo (eval 5). La comisión fija pesa en tickets de pocos dólares (`03-stripe.md`).
- **Medios de pago viables por país** salen de M1 (`mercado.json#metodos_pago`, fase de pagos): un método local que la fase de pagos no habilita no sirve; «USD sin conversión ni medio de pago viable» es el defecto 8.
- **CPM del país del público.** Rangos de terceros (`04-meta-ads.md` §8.2, `[VERIFICAR]`): LatAm USD 2-6, España 5-10, EE. UU. 10-20; CTR y CVR **sin fuente** `[HIPÓTESIS]`. Un CPM de EE. UU. para público de México es el defecto S17.

## 4. Transferencia entre locales (Modo D y cualquier idea «traída» de otro idioma)
Un candidato `oferta_primero` nace de una oferta que corre en un país **origen** y se lleva a un **destino**. Reglas:
1. **Hipótesis de transferencia, siempre:** la ausencia de rivales en el destino (E2) es evidencia de **oferta**, no de demanda ni de dolor en ese locale. Todo candidato lleva `requiere_barrido_local = true` (en `modelado.json#transferencia`) y una hipótesis para D2 que lo diga.
2. **Paridad de evidencia en el destino:** ≥ `evidencia_min_fuentes` fuentes y ≥ `evidencia_min_tipos` tipos **en ese locale**, con **≥ 1 E3** del locale destino y una E1 o E2. Sin la E3 del destino no hay candidato: el par queda `incompleta`.
3. **Países fuente para buscar ofertas** (hipótesis de orden, no prior): EE. UU. primero (el mejor lugar para encontrar, según los mentores), luego BR, MX, ES, IT, CO; los términos van en el **idioma del país**. **Mercados destino** = los de M1 (`locales_activos`) y las decisiones del dueño; para cada oferta se mide en cuáles no corre el original ni nadie con una oferta equivalente (matriz página × país).
4. `hipotesis_transferencia` (nombre fijado por M1): `{problema_id, locale_origen, locale_destino, mecanismo_traducible ∈ si·parcial·no, macro_nicho, banderas, riesgo_nivel, senal_ids_origen[], via}` en `empresa/descubrimiento/transferencias/AAAA-MM-DD.jsonl` (append-only, D1) `[PENDIENTE: CT-4/S-B]`. M1 responde `{viable, bloqueos[], barrido_local_solicitado, requisitos[]}`; con `barrido_local_solicitado = true` D1 abre un barrido **dirigido** al locale destino con paridad de evidencia.
5. Un hueco de **localización** (hay rivales del mismo concepto en el país de referencia pero pocos en el local) es hipótesis para D7, nunca candidato fuerte.

## 5. Presupuesto de exploración por locale
M1 **reparte, sin ampliar**, los topes globales (`max_busquedas_por_barrido`, `max_costo_por_barrido`, `modelado_max_consultas_por_corrida`, `limites.max_consultas_biblioteca`): `cuota_l = tope_global · w_l / Σw`, mínimo 1 barrido mensual por locale activo y ≤ 20 % para locales sin ficha completa. D1 gasta dentro de la cuota; `max_barridos_por_semana` sigue siendo global. Con un tope en `null`, la cuota es `null` y **no se consulta**.

## 6. Qué haces tú
Pedir en las preguntas bloqueantes: locale, países de segmentación, moneda de cobro, rango de precio y si el dueño autoriza un tope de sesión. Citar la ficha de país de M1 cuando exista; si no, declararlo. Nunca asumir un país por impresión del dueño o de un creador (D-09: coherencia de moneda, precio y medios de pago; R-8 de la rúbrica).
