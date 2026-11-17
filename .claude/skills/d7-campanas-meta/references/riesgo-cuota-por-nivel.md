# Riesgo, cuota y ritmo por nivel (D7 solo lee; no clasifica ni rebaja)

El nivel lo calculan D1/D3/X1 **por candidato** (promesa, contenido, encuadre, categoría de negocio; nunca por tema) con `python -m scripts.nivel_riesgo --P … --C … --E … --N …` (devuelve `nivel` en minúscula, `subnivel` A|B aparte, `colores`, `veredicto_riesgo`; `ejes_codigo` y `version_tabla` en `riesgo_de_candidato`; `nivel` es `None` fuera de macro-nicho) y viene en `oferta.json.riesgo`. D7 no lo calcula, no lo baja y no emite veredicto de riesgo: lo comprueba. Marco: `docs/_investigacion/25-marco-salud-relaciones-dinero.md` §2.3–2.6, §5.3, §10.1.

## 1. Qué hace D7 según el nivel (v0.1)

| Nivel | D7 | Cómo se determina |
|---|---|---|
| verde | arma; lint L1 de X1 y muestreo; gate H de activación | `riesgo.nivel = verde` (con `nivel_max_lanzable = null` es el único nivel que se arma) |
| amarillo-a | arma **solo si** `limites` trae las claves de riesgo (abajo) **y** hay RHS registrada en `lanzamiento.log`; gate H; pre-aprobación `compliance.anticipacion_preaprobacion_h` | `nivel = amarillo` con **un** eje amarillo entre P, C, N (E no es amarillo: E2/E3 son rojo) |
| amarillo-b | **no se arma** en v0.1 (necesita decisión H por envío, ayuda verificada del país y texto fiel a fuente T1) → escala | **dos o más** ejes amarillos entre P, C, N |
| rojo | **no se arma**, ni en borrador | `nivel = rojo` |

`candidatos.schema.json#/$defs/riesgo` (`additionalProperties: false`) todavía no admite `subnivel`, `ejes_codigo` ni `version_tabla` `[PENDIENTE: CT-3, LT-04/LT-20]`: mientras tanto un `oferta.json` válido no los trae y `d7.py lint` usa el `subnivel` del snapshot si existe o, si no, lo deriva de los colores de los ejes (**≥ 2 amarillos entre P, C, N = B**) `[SUPUESTO]`. No existe ninguna regla «todo amarillo = B». D7 no importa `scripts.nivel_riesgo` ni lo reimplementa: lee el resultado (tres implementaciones independientes por diseño). RHS = revisión humana de seguridad (una persona recorre la lista L3 de 22f §4.7 en 30–60 min; no acredita exactitud clínica): obligatoria en el primer lanzamiento de cada hoja × idioma y mientras una bandera L1/L2 siga abierta.

## 2. Claves de `limites.yaml` que D7 necesita para amarillos (25 §10.1; ya en `limites.schema` 1.3.0, todas en `null` hasta que el dueño las fije)

`nivel_max_lanzable` (por macro-nicho) · `hojas_pausadas[]` · `cuota_gasto_amarillo_max_pct` y `cuota_gasto_amarillo_b_max_pct` · `envios_amarillo_a_semana` · `envios_amarillo_b_mes` · `dias_limpios_para_subir_cuota` · `edad_minima_audiencia`. **Con `null` D7 lanza solo verde** (`nivel_max_lanzable: null` = SOLO VERDE, fail-closed; el lint da BLOQ `amarillo_sin_claves_de_riesgo`); `edad_minima_audiencia: null` = 18. Valores iniciales de la nota 25 (30 %/10 %, 3 por semana, 1 por mes, 60 días limpios) son `[HIPÓTESIS]` del dueño: se citan por clave, no se copian.

## 3. Reglas de cuota y congelación

- **Cuota de gasto** (amarillo-a ≤ cuota del gasto diario; 50 % tras `dias_limpios_para_subir_cuota`): es un agregado de cuenta; `engine.guard` hoy agrega gasto, no cuota por nivel ni envíos por semana `[PENDIENTE: SB-12]`. La tarjeta debe mostrar la cuota consumida.
- **Congelación** (`parametros.compliance.rechazos_congelar` rechazos en `compliance.rechazos_ventana_dias` días): rechazo de **producto o contenido** (ejes C, N) congela la hoja; de **pieza** (ejes P, E) revertido congela el ángulo (un rechazo revertido en revisión no cuenta, HC 1210227555661027); dos en 7 días congelan la cuenta. En amarillos, pausa del ángulo al primer rechazo.
- D7 no calcula reembolsos ni disputas (`salud_operativa`), pero **no lanza** si la oferta, la hoja o el macro-nicho están en pausa naranja/roja; la tarjeta muestra el escalón (amarillos, un escalón más bajo).
- Mercado: `paises ⊆ limites.paises_permitidos` y matriz país × nivel (J01; no existe en código `[PENDIENTE: SB-12]`; PX3 de `meta.preflight.items_px` da ROJO informativo mientras `riesgo_matriz_pais_nivel_ok` sea `None`). Italia, Francia, España, Alemania: gate H del dueño **una vez** por país × macro-nicho × nivel (amarillo-a). Sin intereses sensibles ni lookalike de compradores amarillos en UE/UK.
- Prioridad de datos: URL, UTM y eventos sin salud, ciclo, deuda, ruptura, ingresos ni impuestos.

## 4. Quién sube o baja un nivel

D3, D5, D6 y D4 pueden **subir** el nivel de su activo; solo bajan aplicando un reencuadre verificable. X1 veta y aprueba toda bajada desde rojo y amarillo-b. El dueño decide líneas rojas y tolerancia, **no** el nivel de un candidato. D7 jamás reencuadra ni «rebaja» para poder armar.
