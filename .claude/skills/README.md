# .claude/skills

Skills: `.claude/skills/<slug>/` con `SKILL.md`, `references/`, `rubric.md`, `templates/`, `scripts/`, `evals/` (`dorados/`, `sembrados/`) y `CHANGELOG.md` (SemVer). Los agentes de cada etapa viven en `.claude/agents/<id>-maker.md` y `<id>-qa.md` (el QA solo con Read, Grep y Glob).

## Cómo nacen y cómo se promueven (orden del dueño, 2026-11-06)

- **Nacen en v0.1 «sin pulir»**: se generan a partir de la especificación de cada etapa (`departamentos/NN-….md` §10) y de los contratos reales. La primera línea del cuerpo de cada `SKILL.md` y de su `CHANGELOG.md` lo dice. **Ninguna v0.1 se promueve sola.**
- **El dueño las pule a mano**: corre cada paso con una oferta real en la pestaña Code, anota lo que corrige en la bitácora **Pulido** del panel y se ajusta la skill hasta que el resultado es el buscado (método del dueño: a mano → pulir → skill → el agente la usa).
- **v1.0.0 solo con** una corrida manual real + retro de 30-45 min + definición de listo (DoD) **firmada por el dueño** (`docs/03-plan-de-forja-de-skills.md` §2.6). El runner no promueve; solo usa lo que está fijado en `skills_pin`.
- Editar una skill ya promovida: solo con aprobación del dueño (vía el script de X2); las v0.1 las edita quien las forja o las pule.

## Registro de promoción (formato; va al final de cada `CHANGELOG.md`)

Una fila por versión, nunca se borran filas:

| Versión | Estado | Fecha | Corrida manual (oferta_id · locale · modo) | Retro (informe o fecha) | DoD firmado por el dueño | Notas |
|---|---|---|---|---|---|---|
| 0.1.0 | borrador sin pulir | 2026-11-06 | — | — | — | generada desde la spec |
| 0.2.0 | pulida (en uso) | AAAA-MM-DD | OF-… · es-ES · a mano | ruta al informe | — | qué se corrigió |
| 1.0.0 | **v1** | AAAA-MM-DD | OF-… · it-IT · a mano | ruta al informe | `dueño` AAAA-MM-DD | DoD §2.6 cumplido |

Estados admitidos: `borrador sin pulir` → `pulida (en uso)` → `v1`. El panel (`#/skills`) lee el estado de esta tabla y del `CHANGELOG.md`.

## Lo que se usa de verdad (2026-11-13)

El flujo que corre son cuatro skills: `buscar-ofertas` → `modelar-y-lanzar-oferta` → `escalar-oferta` (vigilancia, apagado, revisión, renovar y escalar), con `backend-ofensivo` disparada por la revisión diaria. Las reglas de cada situación están en `escalar-oferta/references/02-decidir.md` y el mapa vivo en el panel (`#/flujo`). Las skills por etapa (D1-D10) de abajo son la especificación larga y no se usan en el día a día; donde contradigan a estas cuatro, mandan estas.

## Qué hay hoy (2026-11-07)

**19 skills** en el repositorio, todas **sin pulir**: ninguna tiene corrida manual del dueño, retro ni DoD firmado, así que ninguna está en v1. Los estados son los del registro de promoción de cada `CHANGELOG.md` (el panel `#/skills` los lee de ahí): «v0.1 sin pulir» (borrador generado desde la spec) o «v0.2 sin pulir» (D5 y D6, alineadas con J6-J21 y la práctica de OF-202611-91).

### Mapa etapa → skill → agentes

| Etapa | Skill | Versión · estado | Agentes (`.claude/agents/`) | Qué falta (detalle en la propia skill) |
|---|---|---|---|---|
| **M1** Mercados e idiomas | `m1-mercados-localizacion` | 0.1.1 · v0.1 sin pulir | `m1-maker`, `m1-qa` | corrida real; atlas y glosarios por locale; el contrato `mercado` 1.1.0 ya existe |
| **D1** Descubrimiento (modos A-C y Modo D) | `d1-descubrimiento` | 0.1.1 · v0.1 sin pulir | `d1-maker`, `d1-qa` | ola CT-4 (banco, candidatos 1.1.0), 2 dorados del dueño, calibración del juicio; en el Modo D desarma y plan v0 vía `modelado-oferta` |
| **Modelado** (entre D1 y D3, MOD-1…9) | `modelado-oferta` | 0.1.1 · v0.1 sin pulir | `modelado-maker`, `modelado-qa` | contratos de los artefactos, `scripts/modelado/{palancas,similitud}.py`, claves `modelado.*`, corrida real (`PENDIENTES.md`) |
| **D2** Validación de mercado | `d2-validacion` | 0.1.2 · v0.1 sin pulir | `d2-maker`, `d2-qa` | semiasistida (Biblioteca de Anuncios en la sesión Code); paso 7b de inmersión; parámetros de D2 en `parametros.yaml` |
| **D3** Arquitectura de la oferta | `d3-arquitectura-oferta` | 0.1.3 · v0.1 sin pulir | `d3-maker`, `d3-qa` | modo `modelado` con L1-16 a mano; `tarifas.json` de F1; bloque `modelado` en `oferta.json` |
| **D4** Producto digital | `d4-producto` | 0.1.2 · v0.1 sin pulir | `d4-maker`, `d4-qa` | corrida con una oferta real; compliance de X1 por locale |
| **D5** Landing, checkout y tracking | `d5-landing-checkout` | 0.2.1 · v0.2 sin pulir | `d5-maker`, `d5-qa` | chequeo `modelado_estructura`, productor de `prueba_social_real.json`, Impulstienda (decide el dueño), imágenes J21 de una oferta real |
| **D6** Creativos para Meta | `d6-creativos` (+ sub-formato `d6-sketch-animado` 0.1.0, experimental) | 0.2.1 · v0.2 sin pulir | `d6-maker`, `d6-qa` | `PEDIDOS.md` (14 pedidos a S-A, S-B y dueño); la Ruta B (Higgsfield) nunca se corrió |
| **D7** Campañas de Meta | `d7-campanas-meta` | 0.1.2 · v0.1 sin pulir | `d7-maker`, `d7-qa` | `dependencias.md` (el motor no escala un lanzamiento inestable, C.11); activar sigue siendo H (J2 pendiente) |
| **D8** Optimización diaria | `d8-optimizacion` | 0.1.1 · v0.1 sin pulir | `d8-maker`, `d8-qa` | `engine/d8.py` aún no implementa J3; grupo `lanzamiento` de umbrales; criterio de campeón sin firma (`PEDIDOS.md`) |
| **D9** Escalado | `d9-escalado` | 0.1.1 · v0.1 sin pulir | `d9-maker`, `d9-qa` | `PEDIDOS.md`; escalera ×2 como máximo; grupo `mercados` de parámetros para la réplica |
| **D10** Poscompra, entrega y soporte | `d10-poscompra` | 0.1.1 · v0.1 sin pulir | `d10-maker`, `d10-qa` | cableado de correo, bandeja y reseñas (`PEDIDOS.md`); compra real propia para la corrida |
| **X1** Cumplimiento (veto y sello) | `x1-compliance` | 0.1.2 · v0.1 sin pulir | `x1-maker`, `x1-qa` | cuarto macro-nicho en las reglas, reglas pl-PL; el sello lo emite el código |
| **Jurado** de creativos (pieza 3 de JPS; entre QA-A de D6 y la carga de D7) | `jurado-creativos` | 0.1.0 · v0.1 sin pulir | `jurado-votante` (un voto), `jurado-qa` | nace en **modo sombra** (no decide nada; solo ordena y avisa); sin etiquetas reales no hay precisión; `PEDIDOS.md` (contrato, parámetros `jurado.*`, pantalla, runner y métricas por anuncio); código en `scripts/jurado/` |
| **O0** Orquestador y cartera | `o0-orquestador-portafolio` | 0.1.2 · v0.1 sin pulir | `o0-maker`, `o0-qa` | `portafolio.py`, firma del brief (LT-54), `orq validar` |
| **O0** Recorrido «lanzar una oferta» | `o0-lanzar-oferta` | 0.1.2 · v0.1 sin pulir | — (solo lectura; sin agentes) | C-04 (activar = H hasta que el dueño decida D-02/J2); `activar --live` sin integrar |
| **Buscar ofertas** (banco, barrido por forma, seguimiento diario, elegir) | `buscar-ofertas` | 0.1.0 · separada el 2026-11-13 | — (la sesión del dueño y la tarea «buscar-ofertas», 08:15) | primera vuelta diaria |
| **Backend ofensivo** (upsells post-compra) | `backend-ofensivo` | 0.1.0 · separada el 2026-11-13 | — (la dispara la revisión diaria de `escalar-oferta`) | segunda corrida |
| **Recorrido completo** (elegir, modelar, producir, tienda, landing, creativos, campaña) | `modelar-y-lanzar-oferta` | 0.1.0 · nacida de una corrida real a mano (México, 2026-11-11); sin corrida como skill | — (la sesión interactiva del dueño) | primera oferta siguiendo la skill; las fases de elegir oferta y mercado están diseñadas, no probadas |
| Cerebro (sesión) | `cerebro-abrir` · `cerebro-cerrar` | 0.2.0 · v0.1 sin pulir | — (comandos del dueño) | corrida del dueño; el panel lee `empresa/panel/pulido.jsonl` |

**Cadena del recorrido guiado:** D1 (desarme y plan v0) → M1 → D2 (7b inmersión) → modelado (plan v1, lo aprueba el dueño) → D3 → D4 → D5 (con imágenes J21) → D6 → D7 → activar → D8 → D9 · D10. Detalle y gates en `o0-lanzar-oferta/SKILL.md` §3b.

**Costuras entre etapas** (quién escribe qué): D7→D8 (`07-campana/traspaso.json` → `08-operacion/`) · D8→D9 (`GRADUAR` → `09-escalado/`) · D8→D6 (`pedidos_creativos.json`) · D9→M1/D1 (réplica por idioma; `modelado-oferta` modo `variante`) · D10→D5/D6/D8 (`prueba_social_real.json`, reseñas reales, `senal_pausa.json`). Cada una está escrita en las dos skills que une.

### Todavía sin skill
**D0** (fundaciones), **F1** (finanzas), **F2** (dashboard/BI) y **X2** (memoria y aprendizaje): son sobre todo código determinista (`infra/`, `datos/`, `dashboard/`) y se forjan después. No faltan D8, D9 ni D10: ya existen.

### Formatos de vídeo e imagen
Dentro del repo, solo la **Ruta A** de `d6-creativos` (estáticos HTML a PNG) y el sub-formato `d6-sketch-animado`. Las skills de formato del creador (`reel-3d-tuotroproyecto`, `reel-estilo-fleta`, `sketch-estilo-pixar`, `videos-estilo-cs`, `videos-estilo-fifa`, `videos-retro-mario`, `editor-video`, `planificador-video`, `ideador-guiones`) viven en `~/.claude/skills/`, no se versionan aquí y los agentes desatendidos no las leen; su inventario y por qué no entran a D6 tal cual: `d6-creativos/references/productores-de-formato.md` §2. Las imágenes de la landing (J21, Kie.ai) siguen `modelado-oferta/references/imagenes-kie.md` y el código de `scripts/imagenes/`.

Cada skill declara en su `dependencias.md` (o en `PEDIDOS.md` / `PENDIENTES.md`) lo que la spec pide y aún no existe en código (`[PENDIENTE: …]`) y en su `preguntas-abiertas.md` las decisiones del dueño que la bloquean. Las referencias de rutas entre skills y agentes se comprueban con `.venv/bin/python scripts/skills_refcheck.py` (informe: `docs/_historial/mentor-sistema/brechas/ref-check.md`).

Ver `docs/03-plan-de-forja-de-skills.md`.
