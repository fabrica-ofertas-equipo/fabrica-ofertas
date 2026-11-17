# Límites de inferencia: qué se puede y qué NO se puede decir con la Biblioteca

> Base: `docs/_investigacion/02-conectores.md` (c.3, c.6), `docs/_investigacion/04-meta-ads.md` §1, `18d` §0 y §4, spec D2 §2 y §3.4. Regla madre: **la Biblioteca mide oferta publicitaria persistente (intento sostenido), no ventas, no gasto, no demanda y no rentabilidad.** «Oferta validada» es solo la de backbone 5.9 (compras netas en Stripe, cohorte madura, CPA ≤ objetivo), que mide el test pago de D7/D8. «Con una venta ya está validado» no es criterio del sistema.

## 1. Lo que la Biblioteca NO dice
Gasto, impresiones, alcance, conversiones, ROAS, CTR · texto principal del anuncio (el conector da solo el *título del enlace*, a menudo genérico) · fecha de fin y duración de los inactivos · estado (se deduce comparando `ACTIVE` contra sin filtro) · URL de destino, precio, oferta, formato, idioma, plataformas · cuántas personas vieron o compraron. Su `ad_delivery_start_time` es la fecha **deseada** de inicio, no la primera impresión.

## 2. Tabla de inferencias
| Se observa | NO se concluye | Se puede decir (forma segura) |
|---|---|---|
| 160 anuncios de un anunciante | «gana mucho dinero» / «está validado» | «1 operador, 1 concepto estimado, 60 días; sin datos de gasto». El volumen bruto pesa 0 en SS_a (vector 0,233) |
| `estimated_total_count` alto | «mucha demanda» / «mercado grande» | «el conector estima N anuncios para este término y país (contexto, no suma entre países)» |
| `estimated_total_count` bajo o 0 | «no hay mercado» / «hueco» | «poca oferta que use este término; puede ser hueco o falta de demanda; solo el test pago lo distingue» |
| Anuncio activo hace > 45 días | «rentable» | «el anunciante sostiene este concepto; intento sostenido, no ganancia» |
| Muchas variantes del mismo creativo | «escala» / «gana» | «producción masiva de variantes o tests; sesgo de supervivencia» |
| Mismo embudo traducido en varios idiomas (cuentas en BRL/USD/CRC) | «ventas probadas» | «operador translocal: apuesta a que ya funcionó; se cuenta **1 operador**, no N páginas» |
| Moneda de la cuenta (`currency`) | país objetivo, idioma o precio | «moneda de la cuenta publicitaria; el precio y su moneda salen del snapshot o la landing (`moneda_precio`)» |
| Orden por creación descendente y límite 50 | «esto es todo lo que hay» | «muestra de los 50 más recientes: **piso**; los anuncios viejos (la mejor señal) quedan enterrados» |
| Término en el idioma A devuelve 0 | «no existe» | «0 en ese formato/término; se probó el nativo y la jerga regional (eval ro-RO): 0 en un formato no es NO_GO» |
| Un solo concepto muy repetido | «hay demanda» | «monocultivo; ver `saturacion` y la bandera de la sonda» |
| Competidor promete ingresos/curas/plazos | «podemos prometerlo» o «NO_GO» | «dato de mercado + `prohibido_copiar`; el riesgo está en **nuestro** ángulo» |
| Búsqueda sin resultados | «mercado inexistente» | «búsqueda fallida ≠ mercado inexistente: con confianza baja, GO_CONDICIONAL» |

## 3. Reglas de redacción (aplican a `validacion.json`, `informe.md`, handoff)
1. Toda afirmación que mueva el veredicto lleva `evidencia_id` (URL https + fecha); sin ellos **se rechaza** (`metricas.py` sale con código 3).
2. Prohibido el lenguaje de rentabilidad ajena: «gana mucha plata», «factura X/mes», «le va bien», «es un negocio rentable», «está validado». Si aparece citado de un competidor, va como dato etiquetado (`prohibido_copiar`), nunca como conclusión.
3. Informa siempre «N operadores sostenidos, M conceptos, sin datos de gasto», y marca `[VERIFICAR]` el hecho externo sin fuente.
4. Cada campo de un competidor es `observado` (lo viste en snapshot, landing o texto crudo), `inferido` (de otro dato; di de cuál) o `no_disponible`. Sin snapshot leído, los campos de texto son `no_disponible`.
5. `no_inferible[]` de `validacion.json` lista siempre lo de §1 que pesa en esta decisión; `veredicto.evidencia_faltante[]` lista lo que **sí** se podría conseguir y cómo (accionable: «leer 3 snapshots más de op-02», «re-lectura a +7 días»).
6. «Qué la refutaría»: el informe dice qué observación cambiaría el veredicto.
7. Un conteo de una muestra truncada es un **piso**: se escribe «≥ N» o «al menos N» y `truncado = true`; nunca se compara con un umbral como si fuera un total.
8. El **antídoto de convergencia**: si el ángulo que recomendamos lo usa la mayoría de los sostenidos y no hay diferenciador sustentado, `convergencia = alta` (no GO). Un diferenciador exige ≥ `hueco_min_frases` frases y ausencia en ≥ `umbral_hueco_ausencia` de los sostenidos.
9. Cuándo el veredicto es `provisional`: sin lectura de snapshots (`pendiente_humano`) o con datos de una sola foto. La re-lectura a +7 días y el historial son los que suben la confianza (criterio 5).

## 4. Qué distingue «hueco» de «falta de demanda»
Ninguna lectura de la Biblioteca lo distingue. Lo que sí aporta D2: ausencia **medida** del mecanismo en los sostenidos, ≥ 5 frases de ≥ 3 fuentes que piden eso (voz del cliente), y el sustituto gratis. Lo demás es hipótesis para D7 (`hipotesis_para_d7`), incluida la de que el ángulo seguro puede rendir menos que el agresivo de los competidores.
