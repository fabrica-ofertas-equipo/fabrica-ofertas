# Bibliotecas de N unidades, imágenes y créditos

> **Hoy D4 no genera imágenes ni llama a Higgsfield** (spec 05 §4.4 «Sin Higgsfield en D4»; `docs/09` §8.1: D4 no figura en la tabla de MCP). Las imágenes del producto son capturas veraces del render; las de ambiente o de unidades que exijan generación las produce D6 (cotización previa, `creditos_max_*` y permiso del dueño; productor `D6`) o las aporta el dueño. En v1 las bibliotecas van con tipografía, íconos vectoriales propios o stock licenciado. Una biblioteca con imágenes generadas en D4 es [PENDIENTE: decisión del dueño de agregar a D4 a la tabla §8.1 de `docs/09`]: este archivo describe el flujo que entonces aplicaría (y que D6 ya aplica).
>
> Spec §4.1 (bibliotecas), §5 (herramientas), §7; backbone 5.6 y 9. Parámetros y topes: `empresa/limites.yaml` → `creditos_max_pieza`, `creditos_max_oferta`, `costo_max_producto`, `max_budget_por_corrida_agente`, `politica_divulgacion_ia` (hoy **todos `null`** ⇒ D4 trabaja **solo con texto**). Script: `scripts/cotizar_creditos.py`.

## 1. Biblioteca de N (paso a paso)

1. **Ficha por unidad** en JSONL (`unidad_id, titulo, contenido, imagen_id, fuente, licencia_id`; `templates/ficha_unidad.ejemplo.jsonl`) y **una plantilla HTML/CSS** que las renderiza (`pdf_base.html`, `.ficha`): la uniformidad es de construcción. `n_unidades` prometido = entregado (`cobertura_matriz.py`).
2. **Guía de estilo** (`templates/guia_estilo_imagenes.md`: paleta, aspecto, luz, semilla/modelo, prohibidos) **antes** de generar.
3. **QA-A previo al gasto** (solo si hay imágenes generadas; checkpoint, no cuenta como ronda): guía de estilo + **3 unidades piloto**; el QA aprueba o devuelve. Solo entonces el lote, dentro de `creditos_max_*`.
4. **Verificación por tipo:** receta → tabla con fuente T1; patrón con conteos → script de consistencia + **muestra construida por una persona** (≥ `producto.biblioteca_muestra_fisica_min` [propuesto], primer lanzamiento del tipo); hoja → casos dorados; tarjeta o guion → revisión de seguridad.
5. **Imágenes:** visión sobre el **100 %** (texto basura, proporciones imposibles, objeto que no corresponde al paso, estilo fuera de guía) y **muestreo humano** (`producto.biblioteca_muestra_qa_pct` [propuesto]); un defecto → **barrido de la clase**. Una imagen de IA **nunca** es foto real de un resultado y lleva rótulo «IA».
6. **Licencias y PI al 100 % de los activos** (`licencias-y-activos.md`).

## 2. Cotización previa de créditos (obligatoria antes de generar; hoy la aplica D6, no D4)

Flujo (sesión interactiva del dueño, hasta N2; desde N3 el equivalente son scripts propios con credencial de mínimo privilegio [PENDIENTE]). El Maker de D4 no tiene MCP: estos pasos son del dueño o de D6:
1. Consultar el saldo (`balance`, lectura) y el modelo (`models_explore`, lectura).
2. **Cotizar pieza por pieza SIN generar:** `generate_image` con `get_cost: true` devuelve el costo en créditos **sin enviar ningún trabajo**. **`generate_image_batch` no admite cotizar** (`get_cost` no soportado en lote): el lote se cotiza pieza por pieza antes.
3. Anotar en `04-producto/cotizacion_creditos.json` (`templates/cotizacion_creditos.ejemplo.json`): piezas con créditos, modelo y `prompt_ref`; `gastado_antes`; `permiso_dueno`.
4. `python3 scripts/cotizar_creditos.py --cotizacion … --limites empresa/limites.yaml` → **AUTORIZADO** o **DENEGADO**. Se deniega si: algún tope `null` (⇒ solo texto), pieza > `creditos_max_pieza`, `gastado + Σ` > `creditos_max_oferta`, `empresa/PAUSA`, infraestructura no VERDE/vigente, falta `permiso_dueno: true` del chat, o `use_unlim`/`use_free_gens` sin permiso explícito.
5. Solo con **AUTORIZADO** y el **permiso explícito del dueño en el chat** se llama a `generate_image` (nunca `use_unlim`/`use_free_gens` por iniciativa propia). **El costo lo imputa el motor** en `empresa/costos.jsonl` (el Maker no lo escribe; hoy nadie lo anota: SB-8, SB-10 [PENDIENTE]); el Maker solo deja el borrador `04-producto/costos.jsonl` con los créditos reales y los anota en `licencias.json`.
6. Si un límite falta: el Maker escribe `04-producto/limites.propuesta.yaml` (`templates/limites.propuesta.ejemplo.yaml`) con **cotización, no con un tope inventado**, y trabaja solo con texto.
7. Un timeout de envío **no se reenvía** (resultado desconocido): se reutiliza el `job_id` y se confirma antes de reintentar.

## 3. Qué pasos con interfaz gráfica los hace una persona

Aprobar o ajustar la guía de estilo con los ojos; elegir entre variantes; comprobar el tipo de licencia **en la web** de la herramienta (plan y términos vigentes el día de la generación); subir a la herramienta imágenes de referencia propias (selector de archivos); abrir hojas en Google Sheets/Excel; imprimir a PDF si la ruta de render es la C; probar el PDF en el móvil. El agente **marca** esos pasos `no_verificado_por_agente`; no los simula.

## 4. Si no hay créditos o permiso

Producto **solo con texto**: portada tipográfica y sin ilustraciones generadas; no es un defecto. Lo que se prometió en la oferta con imágenes y no se puede producir sin créditos se **devuelve a D3** (no se recorta en silencio).
