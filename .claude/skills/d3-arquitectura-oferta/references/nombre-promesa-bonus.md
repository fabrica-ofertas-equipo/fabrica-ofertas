# Nombre, promesa, vehículo, entregables y bonus

Regla rectora: **lo prometido en anuncio y landing es contrato** (spec §1). Promesa y nombre **no pueden contradecir ni exagerar** la ficha MU/EU (backbone 5.11) ni el nivel de riesgo. Se localiza (no se traduce): ver `ejemplos-por-idioma.md`.

## 1. Cliente ideal
El de D1, en **tercera persona de rol o situación** (E0/E1): «persona que vuelve a buscar trabajo tras una pausa larga». Nunca «tú» + atributo, pregunta, edad numérica, estado familiar o civil, salud ni situación financiera vulnerable. «Madres» en tercera persona se prueba con una pieza pre-aprobada de X1 [VERIFICAR]; por defecto, rol sin atributo (reencuadre RE-08).

## 2. Promesa (`promesa`)
- **Sujeto = el entregable** (P0/P1). Verbos de la herramienta (registra, ordena, calcula, planifica, compara, incluye). Medida **de uso** («90 minutos para completarlo», «cinco cenas base»), nunca tiempo hasta un resultado ni dinero, salud o estado del lector.
- **Verificable por un novato cronometrado:** `tiempo_prometido_min` es la **única fuente** del tiempo (D4 la mide, no la cambia: la devuelve a D3). `vehiculo.tiempo_consumo_min = ⌈palabras_max / economia.lectura_wpm_diseno⌉ + minutos de ejecución` y `≤ economia.tiempo_diseno_max_factor × tiempo_prometido_min` (S2: un PDF largo «en 20 minutos» es MAYOR).
- Una cifra solo como **P2s** (suma del propio producto, rótulo «ilustrativo» en el mismo medio; `claims-por-macro-nicho.md`).
- `claims_permitidos[]`: cada uno con `claim_id` (kebab), `texto` y `evidencia_ref` (ruta de D4, `logica_del_producto` o `03-oferta/oferta.json#garantia`). Todo claim usado en un ángulo, anuncio o landing sale de aquí. `claims_prohibidos[]`: al menos los `claims_a_evitar` de D1 más los de este diseño.
- **No** prometer dinero, salud ni resultados; **no** «garantizamos»; **no** permitir «mencionar que se puede generar ingresos» aunque no lleve cifra (es P2n, nota 25 §2.2).

## 3. Nombre y subtítulo
- **Nombre (`promesa.titulo`) descriptivo en el idioma local** que explique de qué trata el producto; **sin** sufijos *Studio, Academy, Master, Pro, Lab, Creative*, sin verbo de cambio (baja, alivia, calma, equilibra, reinicia, limpia, activa, elimina, libra, multiplica), sin nombre de estado («Glucosa Estable», «Cero Deudas», «Sleep Reset»), sin «ganar» con el lector de beneficiario, sin «cura», sin marcas de terceros ni Venzio. En italiano no en inglés (S17).
- **Subtítulo (`promesa.subtitulo`) = promesa + diferencial (el MU)**, dentro de P0/P1.
- **Marca (`marca.nombre`) y dominio neutros**: sin condición, estado, resultado ni cifra; nace con la oferta. Los sufijos de marca (decisión 9 del backbone, «Clay Art Studio™») chocan con la regla de Fer: **sufijos solo en la marca si el dueño lo decide, nunca en el nombre del producto** (pregunta abierta n.º 6; por defecto, marca neutra sin sufijo).
- **`marca_propuesta[]`**: hasta 3 candidatos de marca **neutra**, cada uno `{nombre, dominio}` (dominio `[SUPUESTO]`, disponibilidad sin verificar), en la cabecera de `oferta.md` y en §E (el campo aún no está en `oferta.json`). Mismas reglas que el nombre: sin sufijos vedados, verbo de cambio, nombre de estado ni «ganar»; además sin claim de salud ni de dinero y sin imitar marcas conocidas. X1 las revisa; el dueño elige **una** en el gate H **antes** de comprar el dominio. **D3 nunca compra dominio ni crea dataset** (irreversibles).
- L1-13 (BLOQUEANTE; **detiene y decide una persona**) lo comprueba con `terminos_sensibles` de X1; `scripts/lint_d3.py` aplica una semilla local mientras no exista (nombre, subtítulo y cada `marca_propuesta[]`, que no pueden ser más de 3).

## 4. Mecanismo, vehículo y entregables
- `mecanismo`, `prueba_una_frase` y el entregable los **hereda de D1** (nombre del MU de 2-6 palabras; formato, alcance cerrado, estado A→B). **No re-elige el problema.** Si la causa raíz cambia o aparece un segundo mecanismo, o la prueba de una frase no se sostiene al escribirla en el idioma local: **devuelve a D1** (`parada.json` `devuelta_a_d1` + `devolucion_d1.json`) con el motivo canónico (`sin_mecanismo`, `multi_mecanismo`, `requiere_servicio`, …; `devoluciones-y-escalado.md`).
- `vehiculo.formato` ∈ {`guia_pdf`, `plantilla`, `biblioteca`, `hoja_de_calculo`, `checklist`, `minicurso_video_corto`, `pack`}. Un entregable **autocontenido**: sin servicio humano, comunidad, clases en vivo, suscripción ni mantenimiento continuo.
- `entregables[]`: `id` kebab, `tipo`, `cantidad` entera, `formato`.

## 5. Bonus (3 a 5)
- Fáciles de producir con IA, **ligados al resultado** y a la objeción n.º 1 (la de mayor severidad en `avatar.objeciones`).
- **Sin** comunidad, grupo privado, soporte, mentoría, sesión 1:1, clases en vivo, certificado, suscripción ni «actualizaciones de por vida». **Ninguno es requisito de la promesa** (S9). **Cada bonus hereda el riesgo**: uno rojo vuelve roja la oferta.
- Cada bonus es **un archivo o pack cerrado** que D4 puede producir con la misma licencia y las mismas fuentes que el entregable.

## 6. Mejoras de valor (las que el QA puede proponer)
Mecanismo con nombre propio; bonus barato contra la objeción n.º 1; precio mínimo con `razon ≥ razon_min`; muestra de 1 página; `precio_b` preaprobado (un segundo precio dentro de rango para el test de D7, sin cambiar la promesa); vocabulario por locale (`glosario`).

## 7. Auto-puntaje (`puntaje`)
Seis dimensiones con los pesos de la spec §6 `[HIPÓTESIS]` (puntaje 0-100): promesa 20 · confianza en el resultado 20 · tiempo hasta el avance 15 · facilidad de aplicar 15 · tranquilidad al comprar 15 · motivos para decidirse 15. `puntaje.total` (0-100) y `puntaje.dimension_min` (0-5: la dimensión más baja pasada a escala 0-5). **Topes** que el propio Maker aplica: sin prueba verificable, confianza ≤ 3; garantía condicionada, tranquilidad ≤ 3; tiempo descalzado, tiempo ≤ 2; `NO_FACTIBLE` ⇒ total ≤ 59; claim ROJO ⇒ 0. Umbrales: `economia.puntaje_min_oferta` (hoy 75) y `economia.puntaje_dim_min_oferta` (3). **Un 90 sin evidencia (S11) es un hallazgo MAYOR**: el QA puntúa a ciegas y vale el **menor**; una brecha > 10 = MAYOR. El auto-puntaje honesto es parte de la calidad de la skill.
