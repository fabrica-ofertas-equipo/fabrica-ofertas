# Nichos: la propuesta de árbol (pendiente de aprobación) y cómo se usa

> **Estado: PROPUESTA, no aprobada.** `docs/_historial/d1-v2-semillas/nichos.yaml` (v1.1; 92 hojas: 32 salud, 28 relaciones, 32 dinero; 18 nichos; 17 `semillas_fuera_de_marco`) deriva de `docs/_historial/hwr-semillas/nichos-hwr.yaml` v2 (86 hojas) y de las notas 20a/20b/23/24a/24b/25. **La aprobación del dueño está pendiente** (y también la de `fuentes.yaml`): la skill **cita** estos archivos como propuesta y **nunca los copia a `empresa/descubrimiento/`**. Si necesitas una hoja que no existe, la propones en `informe.md` (y, vía el dueño, en `empresa/propuestas/`); el candidato queda condicionado a su aprobación.

## 1. Estructura
`macro_nicho → nicho_id → microsegmento (hoja)`; ids en kebab ASCII (`comunes#kebab`). Por hoja: `id`, `etiqueta`, `macro_secundario`, `prior_riesgo{nivel, rango[], riesgo_alto, encuadre_que_sube, reencuadres[]}`, `tanda`, `dsp{demanda, seguridad, producibilidad, puntaje}` o `null`, `idiomas[]`, `formatos[]`, `estacionalidad`, `origen`, `confianza`, `estado`.

| Macro | Nichos (propuesta) |
|---|---|
| **salud** | alimentacion-y-cocina · control-de-peso · alimentacion-y-condiciones · movimiento-y-ejercicio · sueno-estres-y-bienestar-emocional · ciclo-de-vida-y-salud-reproductiva · sustancias-y-remedios · consulta-y-registros-de-salud |
| **relaciones** | pareja-comunicacion · pareja-crisis-y-separacion · crianza-y-familia · familia-y-cuidado · habilidades-sociales-y-amistad |
| **dinero** | presupuesto-y-ahorro-del-hogar · deuda-credito-e-impuestos · inversion-y-cripto · empleo-e-ingresos-propios · proteccion-y-educacion-financiera |
Hojas que usan los casos dorados: `reinsercion-laboral-tras-pausa`, `vender-manualidades-costeo`, `presupuesto-por-cobro`, `tarjetas-conversacion-citas-casa`, `pantallas-reglas-familia`, `anti-estafas-checklist`.

## 2. Semántica fija (decisión 13)
- **El prior y la `tanda` son prioridad de EXPLORACIÓN, nunca veto ni filtro por tema.** El nivel real de un candidato sale de sus ejes P, C, E, N (`riesgo-por-candidato.md`). Ninguna hoja está excluida: las de prior rojo se exploran solo vía reencuadre y con decisión del dueño.
- `tanda 1` = 21 hojas verdes (las de `dsp` alto, ≥ `tanda1_dsp_min`) + 6 amarillas elegidas por la nota 25 §3.1 (incluye el caso del dueño); `tanda1_dsp_min` se aplica solo a las verdes. **El orden de lanzamiento lo fija el candidato** por su nivel, no por la hoja: una hoja de tanda ≥ 3 con un candidato verde sube a la tanda que le toca por su nivel.
- `formatos[]` es texto libre de exploración; el `entregable.formato` lo fijas tú del enum de `candidatos` (`guia_pdf`, `plantilla`, `biblioteca`, `hoja_de_calculo`, `checklist`, `minicurso_video_corto`, `pack`).
- `nicho_id` y `microsegmento` de un candidato **deben ser una hoja existente** (puerta de entrada regla 3). Un `tema_slug` del barrido **nunca** se copia como `nicho_id`.
- Ninguna hoja de tanda 1 se siembra sin una **cita E3** que fije su macro (Q6): p. ej. la conversión de recetas a freidora de aire es «fuera» salvo cita de «comer más sano» (con la cita, salud).

## 3. Semillas fuera de marco (registradas, **no sembradas**)
Crochet y patrones, costura, planos y manuales de oficios (carpintería, electricidad, plomería, steel framing), fichas para psicólogos, recetarios, etc.: la mayoría de los ~27 nichos que nombran los mentores (`20a nichos_semilla`) cae **fuera del marco** (el deseo es tejer, construir o ejercer una profesión) y está en `nichos.yaml#semillas_fuera_de_marco` con su `motivo_macro` (`hobby`, `estetica`, `deseo_del_comprador_es_profesional`). **Con la opción A del dueño se busca y se puntúa en todos los temas y se etiqueta cuáles caen en salud, relaciones o dinero**; lo de fuera se cuenta en M-06 y no se lanza. Entran al marco solo por su reencuadre (p. ej. crochet → `vender-manualidades-costeo` si hay cita E3 de «no sé qué precio poner»; planos → `presupuesto-oficios-cotizacion`).

## 4. Cómo la usas en cada modo
- **Modo B** (dado un nicho): el dueño da una hoja o un nicho; buscas ≥ 5 fuentes con profundidad en ese nicho, sin quedarte en los términos de los mentores.
- **Modo A** (radar abierto): partes de las hojas de tanda 1 **y** de formas estructurales (Modo D), con cuota mínima por macro (`cuota_min_exploracion_por_macro_nicho_pct`) y ≥ `min_explore` hojas ausentes de la memoria de ofertas. Nunca bajas un macro de la cuota de exploración por un mal rendimiento (X2 informa con `n` suficiente).
- **Modo D**: las hojas × modificadores de formato (ebook, guía, plantilla, pack, kit, «descarga inmediata») alimentan las frases de búsqueda por idioma; el barrido por forma trae **todos** los temas y los temas aparecen solos (etiquetado), incluidos los que ningún mentor nombra (profes de yoga, atlas de puntos gatillo, fichas de TCC, auxiliar de enfermería, recetas para diabéticos…).
- **Modo C**: la idea del dueño se contrasta con las hojas cercanas; si no hay hoja, se propone una.
- **Pausas:** `limites.hojas_pausadas` (pedido, no existe `[PENDIENTE: CT-4]`): el dueño puede pausar una hoja; ausente = ninguna pausada.
