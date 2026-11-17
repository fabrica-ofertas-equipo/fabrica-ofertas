# Changelog de modelado-oferta (SemVer)

v0.1 sin pulir (borrador destilado del Proceso de Modelado y del piloto manual de Polonia; no promover a 1.0.0 hasta cumplir el DoD y una corrida manual del dueño con retro de 30-45 min)

## 0.1.1 — 2026-11-07 — agentes `modelado-maker` y `modelado-qa`; estado de las referencias de PENDIENTES A
Sigue siendo **v0.1 sin pulir**.
**Aplicado:** creados `.claude/agents/modelado-maker.md` (Read, Write, Edit, Glob, Grep y Bash acotado a `analizar_html.py --no-red` y `scripts.nivel_riesgo`; sin web ni `mcp__*`; escribe solo en `ofertas/<id>/modelado/`) y `modelado-qa.md` (Read, Grep, Glob; contexto limpio; puntúa el antes/después a ciegas); ambos precargan la skill. `PENDIENTES.md` sección A pasa a tabla de estado: A1-A12 aplicadas por S-C el 2026-11-07 (con las adaptaciones anotadas) y lo bloqueado marcado «bloqueado: S-A/S-B». `SKILL.md` cita los agentes.
**No aplicado a propósito:** `scripts/imagenes/*` en la lista blanca del Maker (A12): contradice `references/imagenes-kie.md` §1 (el modelado no produce, cotiza ni gasta imágenes) y la regla de D5; lo produce D6 o la sesión de imágenes que el dueño autorice.

## 0.1.0 — 2026-11-07 (borrador)
Creada por el redactor de skills del equipo S-C a partir de `docs/_historial/modelado-piloto/` (`proceso-de-modelado.md` §5, `desarme-referente-mapas-mentales.md`, `plan-de-mejora-v1.md`, `estructura-funnel-referentes.md`, `referentes/analisis-html-axon.md` y los HTML reales, `piloto-bitacora-d3.md`) y de las decisiones J10-J21 de `docs/_historial/mentor-sistema/decisiones-del-dueno.md`. **Ningún caso se corrió con el dueño ni con el Maker o el QA reales todavía.**

**Incluye**
- `SKILL.md`: reglas duras, entradas, modos (`completo`, `desarme`, `revisar`, `variante`), procedimiento MOD-1…MOD-9 con salidas y «listo cuando», reparto IA/código/dueño y rutas bajo `ofertas/<id>/modelado/`.
- `references/`: `palancas` (R-1…R-7 y PAL-01…16 con las correcciones de J16, J17, J18, F-30, F-40 y F-51), `derechos-j13`, `inmersion-mercado` (J11/J12), `funnel-completo` (J17), `imagenes-kie` (J21), `lecciones-del-piloto`, `analizar-html`.
- `rubric.md` (QA independiente: QM-01…14 con QM-03 y QM-08 reescritos para J17/J18, R1-R8, simulaciones L3), `templates/` (desarme, plan de mejora, tarjeta antes/después de 12 dimensiones, esqueleto del funnel, informe del QA), `evals/` (caso dorado de Polonia, script contra HTML reales, contenido hostil, 10 sembrados), `PENDIENTES.md`.
- `scripts/analizar_html.py` (biblioteca estándar): `esqueleto_html.json` y `mapa_ranuras.json` desde un archivo o URL; trata el HTML como dato; `--no-red`; límites de bytes, nodos, profundidad y tiempo; no guarda ids de checkout ni de píxel; señala texto con forma de instrucción. Pruebas: `tests/modelado/test_analizar_html.py` (72, sin red).
- Decisión de frontmatter: **con `disable-model-invocation: true`** (como D5, D6 y D7) porque la skill llega hasta el encargo de imágenes con gasto de créditos y entrega a etapas que publican.

**No cubre / falta para 1.0.0** (detalle en `PENDIENTES.md`)
1. Una corrida manual del dueño con una oferta real (3 referentes de nichos e idiomas distintos) y retro de 30-45 min.
2. Código del antes/después y de los QM (`scripts/modelado/palancas.py`, `similitud.py`; `[PENDIENTE: S-B]`) y capas 3-5 del QA lingüístico: hoy se hacen a mano y el QA repite una muestra.
3. Contratos de los artefactos y del bloque `modelado` en `oferta.json`; agentes `modelado-maker` y `modelado-qa`; referencias desde D1, D2, D3, D5.
4. Calibración de los tipos de bloque del script con más referentes y de los umbrales `modelado.*` con 5 ofertas.
5. QA calibrado: ≥ 90 % de los bloqueantes sembrados y PASS al dorado.

## Registro de promoción (formato de `.claude/skills/README.md`)
| Versión | Estado | Fecha | Corrida manual (oferta_id · locale · modo) | Retro (informe o fecha) | DoD firmado por el dueño | Notas |
|---|---|---|---|---|---|---|
| 0.1.0 | borrador sin pulir | 2026-11-07 | — | — | — | destilada del piloto de Polonia; script probado contra los dos HTML reales del piloto |
| 0.1.1 | borrador sin pulir | 2026-11-07 | — | — | — | agentes `modelado-maker` y `modelado-qa`; estado de las referencias de PENDIENTES A; sin corrida |
