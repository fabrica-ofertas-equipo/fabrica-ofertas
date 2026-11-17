# Rutas de producción, cotización previa y control de créditos

Fuentes: spec §4 pasos 6–8, §5, §7; `docs/09-runtime-de-agentes.md` §8.1 y §14.2; `docs/06-bases-del-testeo.md` N10; `docs/_investigacion/02-conectores.md`. **Cada generación gasta créditos reales del dueño.** Todo tope es paramétrico (`empresa/limites.yaml`: `creditos_max_pieza`, `creditos_max_oferta`, `max_budget_por_corrida_agente`); en `null` nada se genera.

## 1. Ejecución semiasistida

D6 es **semiasistido**: Higgsfield solo existe en la **sesión interactiva del dueño**; el runner desatendido (`claude -p` con clave de API) **no carga conectores de claude.ai** (Higgsfield, Meta), así que el Maker con Higgsfield corre en la **sesión Code del dueño**, con `ask` por generación, hasta que exista una API propia **[VERIFICAR]**. Sin esa sesión solo existe la Ruta A. Los conectores pueden estar caducados: `needs-auth` ⇒ se continúa sin ellos y se declara (no se «arregla» con otra herramienta).

## 2. Las dos rutas

| | **Ruta A — HTML→PNG** | **Ruta B — Higgsfield** |
|---|---|---|
| Costo | 0 créditos | Créditos (cotizar siempre) |
| Qué produce | `imagen` (estáticos 4:5, 1:1, 9:16) y `carrusel`; capturas de la hoja o el PDF real (`demo-pantalla`) | `video` (clips, voz, subtítulos por script), y como máximo fondos **sin texto ni personas** para estáticos |
| Herramientas | Chrome/Brave sin interfaz (`render_estatico.py`; Playwright es el motor alternativo, no instalado) y las WOFF2 de D5 con `@font-face`; el texto sale de `copies.json` | `ads_studio_quote`, `generate_image`/`generate_video`/`generate_audio` con `get_cost: true`, `list_voices`, `reframe`, `upscale_*`, `balance`, `transactions`, `show_generations` |
| Dónde corre | Cualquier equipo con Chrome o Brave; no necesita conector | Sesión Code del dueño con el conector autenticado |
| Riesgo propio | Texto fiel por construcción; el riesgo es visual (zona segura, contraste) | Texto roto en imágenes generadas, claims en el audio, C2PA perdido, créditos |
| Requisito | `generar_creativos` verde (preflight) | Lo anterior **más** cotización aprobada y piloto |

**Cuándo usar cada una (orden de decisión):**
1. ¿Hay topes de créditos en `limites.yaml`, conector autenticado y `balance` suficiente? **No** → todo Ruta A; se declara en el brief que el video queda sin probar (hipótesis de formato no testeada).
2. ¿La ficha de formato del referente local usa imagen? **Sí** → se empieza con imagen (Ruta A); el video entra después, en iteración.
3. ¿El concepto necesita movimiento o voz (demostración paso a paso, escena, locución)? → Ruta B para ese anuncio.
4. Mezcla objetivo con créditos disponibles: ≥50 % video si alcanza el tope (los creadores usan 70/30–80/20 video/imagen; confianza B).
5. **Fondo generado** para un estático: solo si el concepto lo pide; nunca con personas en salud ni relaciones; el texto siempre lo pone el HTML.

`ads_studio_generate` solo para estáticos y su copy generado **se descarta** (Meta o el generador pueden inyectar texto no revisado: el copy de `ads_studio_get_run` ≠ `copies.json` es defecto).

## 3. Cotización y registro (antes de gastar)

1. **Cotizar cada pieza:** `ads_studio_quote` (mismos argumentos que `ads_studio_generate`; no gasta) o `get_cost: true` en `params` de `generate_image`/`generate_video`/`generate_audio` (no envía el job ni reserva créditos). Modelos y duraciones con `models_explore` (**ocupa decenas de miles de caracteres: filtrar a lo necesario**).
2. **Sumar con margen de regeneración:** la spec fija +20 % (constante de la skill, sin clave en `parametros.yaml`; `scripts.creativos.cost_preflight` lo lee de `creativos.margen_regeneracion_pct`, que falta en el esquema: **[PENDIENTE: CT]**, y mientras falte sale 5; hasta entonces se cita el valor de la spec como `[SUPUESTO]`).
3. **Contrastar con topes:** cada pieza ≤ `creditos_max_pieza`; el acumulado de la oferta ≤ `creditos_max_oferta`; el saldo `balance` cubre el total. Si algo no cabe, se recorta (menos videos, menos duración) antes de pedir más tope: **el Maker no propone subir un tope** salvo en un pedido explícito `limites.propuesta.yaml`.
4. **Mostrar al dueño** el desglose (pieza, herramienta, modelo, duración, créditos) y el total con margen; **esperar su aprobación en el chat** (no hay aprobación implícita ni «app allocation» que la sustituya).
5. **Registrar antes de enviar:** una línea por pieza en el **borrador** `06-creativos/costos.jsonl` (esquema `costos`; el libro real es `empresa/costos.jsonl` y lo escribe solo el motor, que consolida el borrador; `scripts.creativos.cost_preflight --aplicar` lo corre el motor, no el Maker): `etapa: D6`, `origen: creditos`, `ejecucion_id`, `concepto` («`<tool> <ad_name> cotizado=<n> job=<pendiente>`»), `creditos: <n con margen>`, `monto` en `0` de la moneda de la oferta `[SUPUESTO: F1 los valora]`. El `job_id` real se agrega a `assets.json` al volver.
6. **Hook de gasto** (`agentes/hooks/pretooluse_gasto.py`): rechaza una herramienta de créditos si falta `AGENT_COSTO_PREVIO`, si supera `creditos_max_pieza` o si el acumulado supera `creditos_max_oferta`; también bloquea con `empresa/PAUSA` o infra no verde. **El prompt solo no basta**; el hook es el control.
7. **Piloto:** 1 clip por concepto con video, aprobado por el dueño, antes del lote.
8. **Conciliar:** tras cada pieza, `balance` y `transactions` (lectura) contra lo cotizado; la diferencia se anota en `assets.json` (`creditos_reservados`, `creditos_reales`) y el QA la revisa. Real > reservado = hallazgo MAYOR.

## 4. Parámetros útiles de las herramientas (leídos del esquema del conector; [VERIFICAR] cambios)

- `ads_studio_generate`: exige `idempotency_key` **estable** (se repite igual en un reintento; no se inventa otra) y `expected_credits` = el costo aprobado; sin eso devuelve `approval_required`. Relaciones 1:1, 9:16, 16:9, 3:4; **sin 4:5**. Hasta 4 imágenes de referencia por URL pública (nunca de terceros).
- `generate_image` / `generate_video` / `generate_audio`: `params.model` obligatorio; `get_cost: true` cotiza; `count` 1–4 solo para variantes del mismo prompt; **`use_unlim` no se pasa** (el default es no; solo si el dueño pide usar sus generaciones gratuitas); sin `use_free_gens` salvo petición explícita.
- Voz: `generate_audio` con el modelo de voz por defecto del catálogo y `voice_type: "preset"` + `voice_id` de `list_voices` en el idioma; **no** `voice_type: element` con audio de una persona (clonación), **no** `create_voice*`. Texto de entrada = guion congelado, sin añadidos.
- Video: modelos por defecto del catálogo (`marketing_studio_video` para anuncios, `seedance_2_5` general, `kling3_0` multi-plano) `[VERIFICAR]`; 9:16 explícito (`aspect_ratio: "9:16"`), el default puede ser 16:9.
- **Denegados al Maker:** `ads_create_*`, `ads_activate_entity`, `ads_update_entity`, `ads_creative_*`, `create_voice*`, clonación de voz o rostro, `ai_influencer_*`, `publish_*`, `deploy_website`, `tiktok_*`, `execute_preset`, `ads_studio_add_product`/`create_brand` (solo con permiso expreso del dueño). Meta: ninguna (la Biblioteca de Anuncios es de D1/D2).

## 5. Refresco y loop (`pedidos_creativos`)

Cada pedido es otro paquete `v(n+1)` con su cotización: el ciclo pedido→paquete cabe en `creativos.sla_pedido_h`. El refresco típico es cada `creativos.refresco_dias_min`–`max` por conjunto activo. Un pedido de «3 hooks sin tocar el cuerpo» solo **reescribe el hook y el puente** y reusa el cuerpo y las piezas: el costo de Ruta A es 0; en video, solo se regenera el tramo del gancho y se reusa el resto (no se regenera lo que no cambia). Cada anuncio nuevo es un creativo nuevo (otro `ad_name` y `v`).

## 6. Fallas y reintentos

- **Timeout o error de transporte:** el resultado puede haberse cobrado. No se reenvía: se consulta `show_generations` (todos los estados) o `transactions`, se reutiliza el `job_id` y recién entonces se decide.
- **Rechazo del modelo a un claim:** se corrige el claim (registrar en fallas conocidas); nunca se esquiva con otro pretexto.
- **URLs que caducan:** el Maker guarda copia local de cada asset en `assets/` y registra `sha256`; si el generador solo da una URL, se descarga el mismo día. Términos de uso comercial por plan **[VERIFICAR]**: `licencias.json`.
- **PAUSA, infra no verde o cotización sobre el tope:** se detiene toda generación y se avisa.

## 7. IA, C2PA y licencias (por pieza; `assets[]` del contrato)

| Campo | Regla |
|---|---|
| `ia_generado` | `true` si cualquier parte (fondo, clip, voz) lo es |
| `herramienta`, `modelo`, `job_id` | Higgsfield: `modelo` y `job_id` obligatorios; `placeholder`/`null` solo en piezas 100 % propias de Ruta A (`herramienta: "chrome-headless-html"`, `modelo: null`, `job_id: null`) |
| `c2pa_origen` | `si` / `no` / `n.a.` (Higgsfield no emite C2PA: `n.a.` **[VERIFICAR]**) |
| `c2pa_final` | `si` o `no` tras la recodificación; **nunca se elimina a propósito**. Si se perdió y `ia_generado = true`, `etiqueta_ia_visible = true` |
| `etiqueta_ia_visible` | Según `limites.politica_divulgacion_ia`: `declarar_siempre` → toda pieza con `ia_generado: true` lleva etiqueta visible en el idioma; `declarar_si_corresponde` → obligatoria si hay humano fotorrealista o contenido que parezca real (AI Act art. 50, J06); `no_declarar_donde_legal` → donde la ley no la exija, sin etiqueta, **sin quitar C2PA** (`[VERIFICAR]` por país de `paises_segmentacion`). **Avatar IA fotorrealista: siempre** «Presentador generado con IA» dentro del creativo |
| `copy_hash` | sha256 del texto sellado que la pieza muestra o dice |
| `licencia_ref` | Clave de `licencias.json` (fuente tipográfica, imagen, música, modelo y plan); obligatorio si `ia_generado` o hay fuente, imagen o pista de terceros |
| `costo_creditos` | Entero (0 en Ruta A); la suma por anuncio = `anuncios[].costo_creditos`; la suma total = `costo_total_creditos` |

`politicas.divulgacion_ia` del paquete copia `limites.politica_divulgacion_ia`; con `null` en límites el paquete no se arma (se pregunta al dueño).

## 8. Costo por pieza (a medir al pulir)

Aún no hay costo real medido (la spec lo exige en el DoD). Durante el pulido el Maker anota en `brief-creativo.md` §5 el costo real por tipo de pieza (video 9:16 de N segundos, fondo, audio) para fijar `creditos_max_pieza` con datos; el dueño decide el tope. Los valores que dé el catálogo hoy no se copian a esta skill (cambian).

## 9. Tanda y control de calidad (0.2.0)

La **tanda** (`modo-tanda.md`) es solo Ruta A: 0 créditos, y no pasa por cotización. `qc6.py` no gasta créditos (OCR, ffmpeg y whisper son locales). Si una pieza de una tanda pasara a Ruta B, vuelve a las reglas de §3 (cotización registrada antes, tope, piloto, aprobación del dueño).
