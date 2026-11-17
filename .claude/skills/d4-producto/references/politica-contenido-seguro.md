# Política de contenido seguro (§4.3 de la spec; notas 25 §7 y 22f)

> Principio: **herramienta y criterio atribuido a fuentes, no consejo individual.** El producto no diagnostica, no prescribe, no calcula «su» dosis ni «su» inversión, no promete un efecto y no sustituye a un profesional. El riesgo se evalúa **por promesa, contenido, encuadre y modelo de negocio — nunca por tema**: D4 re-verifica el eje **C** (contenido) sobre el producto real y **solo puede subir** el nivel. Solo X1 lo baja desde rojo o amarillo-b (decisión 13). Sin abogado como requisito (decisión 14): lo verificable lo automatiza X1; esto describe obligaciones y riesgos.

## 1. Qué se produce y qué se niega (por macro-nicho)

| | Se produce (con fuentes, aviso y revisión según nivel) | D4 **se niega** (rojo; D1/D3 reencuadran o descartan) |
|---|---|---|
| **Salud** | Recetarios con tabla pública; menús para adultos sin condición; conservación con fuente T1; rutinas con cuestionario de aptitud y reglas de parada; hábitos y sueño; planners sin metas | Diagnóstico, tratamiento o cura; dosis y suplementos; kcal objetivo; ayuno prolongado; dieta o ejercicio **prescritos** a embarazadas, lactantes o menores; interpretar análisis o IMC; prácticas de riesgo físico agudo (hiperventilación, agua fría, sauna) |
| **Relaciones** | Guiones y límites; conversaciones difíciles; coparentalidad logística; ruptura y duelo con recursos; agendas | Planes de seguridad o «cómo salir»; terapia, apego, trauma; diagnóstico de terceros; manipulación; espionaje; contenido sexual |
| **Dinero** | Presupuesto, sobres; deuda propia como técnica; calculadoras con supuestos visibles; calendarios fiscales con casos dorados; CV; costeo | Recomendar activos o cripto; «ingresos pasivos»; negociar, liquidar o consolidar deudas; reparar crédito; elusión; hipotecas |

Un candidato que llega en la columna derecha **no se produce**: `verificacion.json` con `resultado: devuelve` y motivo `linea_roja_de_contenido_o_negocio` (o el canónico que corresponda), a D3/D1. Pasos de reencuadre: catálogo de `docs/_investigacion/25-…md §4` (lo aplica D1/D3, no D4).

## 2. Niveles y qué exigen de D4

| Nivel | D4 exige |
|---|---|
| Verde | Lints L1 y muestreo de X1; aviso de alcance; en conflicto de pareja o familia (también verde): «Si temes por tu seguridad, no uses este material» + línea de violencia del país |
| Amarillo-A | Cada hecho en `afirmaciones.jsonl` (T1/T2); aviso por tipo de producto; **RHS** (`templates/rhs_lista.md`) en el primer lanzamiento de cada hoja × idioma |
| Amarillo-B | Además texto fiel a fuente T1 o revisión profesional; bloque «Si necesitas ayuda ahora»; decisión **H** del dueño; sin ayuda verificada del país, no sale en ese país |
| Rojo | No se produce |

## 3. Reglas de contenido

1. **Hechos:** de `respaldo/` (§ `respaldo-y-fuentes-de-hechos.md`). Causalidad solo T1/T2 y atribuida; si no, se reformula a descripción («las guías oficiales recomiendan…»).
2. **Lenguaje:** segunda persona solo para pasos del método («anota», «elige»); nunca atributos del lector («si tienes diabetes», «si estás endeudado»); sin verbos de eficacia («elimina», «cura», «acelera el metabolismo», «garantiza», «sin esfuerzo»); condicionales atribuidos; ejemplos con «ejemplo ilustrativo con supuestos X, Y».
3. **Cuándo parar:** disparadores **concretos** (mareo, dolor, miedo a tu pareja, no poder pagar los mínimos), no «consulta a tu médico» repetido en cada página.
4. **Pisos duros** (ingesta, ayuno, carga, horas de ayuno): los de fuentes T1; ningún plan por debajo; ninguna meta de peso ni plazo. Valores en `parametros.yaml` cuando existan [PENDIENTE: `piso_kcal` etc.].
5. **Sin testimonios, casos o resultados personales** (ni «antes y después»); personajes de ejemplo = «ejemplo ficticio» sin cifras de resultado. Sin reseñas con cifras.
6. **Calculadoras y hojas:** supuestos visibles, casos dorados y segundo cálculo; ninguna proyección de inversión ni «rendimiento histórico» como expectativa; ninguna hoja que puntúe salud o deuda.
7. **Sin afiliados ni enlaces de seguimiento** (UTM y atribución son de D5/D7); sin enlace a bancos, exchanges o comparadores.

## 4. Autoría e IA (honestidad)

- **Nunca** «diseñado por nutricionistas/médicos/expertos», «avalado por», logos de organismos o de editores, **salvo que sea cierto y esté documentado** (credencial, consentimiento escrito, fecha). En **es-ES y de-DE** la credencial real va en el **colofón**, no en el anuncio ni en la cabecera de la landing.
- **Divulgación de IA** según `limites.politica_divulgacion_ia` (hoy `null` → usar la más conservadora: divulgar en el colofón y en `producto.json#ia_divulgacion`, anotado `[SUPUESTO]`) y art. 50 del Reglamento de IA (aplica desde 2026-08-02; el plazo transitorio del 50(2) es `[VERIFICAR]`). Texto base por idioma: plantilla C de la nota 22f §7.2, **siempre revisada por el glosario del locale**; «con revisión editorial de [LLC]» solo si es cierto.
- La IA no es la autoridad («la IA recomienda»): la autoridad es la fuente citada. **No eliminar C2PA** de imágenes de IA; registrar herramienta y fecha por activo (`licencias.json`).
- Imágenes de IA: nunca avatares como clientes/expertos/profesionales (bata, uniforme, título); nunca foto «real» de un resultado; presentador sintético solo etiquetado.

## 5. Avisos (plantillas de la nota 22f §7.2; el texto definitivo sale del glosario del locale)

- **Aviso de alcance** (portada interior y pie): «Esta guía es educativa. No constituye consejo médico, financiero ni legal ni reemplaza a un profesional cualificado. Los datos provienen de las fuentes citadas al final (última revisión: [fecha]).» Define alcance, **no confiesa defectos** («puede ser peligrosa»: no), **no contiene claims ni cifras**, no excluye responsabilidad por lesiones, y no corrige un claim contradictorio.
- Reembolso desvinculado del resultado («por cualquier motivo»), lo fija D3.
- **Cuándo parar:** patrón por tema con disparadores concretos.
- **Ayuda:** bloque «Si necesitas ayuda ahora» **al inicio y al final**, con números **literales** de `empresa/compliance/ayuda_por_pais.yaml` (verificación ≤ 180 días; «24 h» solo si la fuente lo dice), obligatorio cuando el tema central es **duelo, ruptura, abuso, salud mental o peso con seguimiento**. En estrés cotidiano, sueño y deuda: enlace a los recursos oficiales del país, sin teléfono de crisis. **D4 nunca escribe un número a mano ni usa uno de otro país**; **sin ayuda verificada del país de la categoría central, el producto no sale en ese país** (excepto 112/911). El archivo aún no existe [PENDIENTE X1]; los números ya verificados en 22f/25 figuran en `scripts/_patrones.py` solo para **detectar** números ajenos, no para imprimir.

## 6. Lector vulnerable y RHS

L3 (un LLM interpreta, no sustituye a una persona): trastorno alimentario ante un recetario; relación controladora ante un guion; deuda ante un plan. El RHS humano (`templates/rhs_lista.md`) no acredita exactitud clínica. El QA (contexto limpio, solo lectura) detecta incoherencias contra la fuente: **no certifica** exactitud clínica, fiscal ni legal.

## 7. Actualización y retiro

Versión y fechas visibles; `revisar_antes_de` = el menor entre la volatilidad (`parametros.yaml#producto.volatilidad_revision_dias`) y la revisión por nivel/macro (6 meses en salud sensible y dinero, 12 en verde [propuesto]). **En 72 h** ante cambio de guía oficial o ley citada, alerta regulatoria, reporte de daño, cambio de política de Meta/Stripe, enlace roto o cambio de modelo/plantilla de D4 (el QA se reinicia). Si la fuente cambia y contradice al producto: retiro, v2 gratuita y nota de corrección. Tres reportes de daño en 30 días o una lesión grave = retiro (D10/X1). Nunca se reactiva sin gate H.
