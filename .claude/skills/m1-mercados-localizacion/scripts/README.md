# scripts/ de la skill m1-mercados-localizacion (v0.1 sin pulir; 0.1.1)

Solo biblioteca estándar (+ PyYAML/jsonschema del `.venv` para leer YAML y validar contra `contratos/`). **Sin red, sin reloj** (la fecha es siempre `--hoy`), sin secretos, sin escribir fuera de `--salida`. Ejecutar desde la raíz del repo con `.venv/bin/python -I`. Códigos de salida: 0 · 2 uso · 3 hallazgo bloqueante · 5 dato faltante (fail-closed).

| Script | Qué hace | Estado |
|---|---|---|
| `puntaje.py` | **extiende** `scripts/mercados/rank.py` (no reimplementa la economía): `reproducir`, `cobertura` (por fase, rama Managed Payments, hueco PayPal), `excluir` (R1-R10), `seleccionar` (9 criterios, sensibilidad, bloques) | probado (`autoprueba.py`) |
| `vigencia.py` | trazabilidad (MQ-02) y vigencia (R10 / MQ-03) de fichas | probado |
| `lint_locale.py` | lint determinista de texto por locale (prohibidos, moneda, decimal, alfabeto, plurales…) | probado (muestra) |
| `chequeos_l1.py` | MQ-01…MQ-22 sobre `mercado.json` + `mercado.seleccion.json` (+ fichas, límites, brief, emparejamiento); modos `borrador`/`sellado` | probado con plantillas y sembrados |
| `autoprueba.py` | 25 pruebas (las 22 originales + MQ-03M, `mult_cpm` sin clave de mínimo y niveles en minúscula) + defectos sembrados medibles por script | corre en verde |
| `parametros_m1.fallback.json` | **único** lugar con números iniciales `[SUPUESTO]` (parametros.yaml manda; `producto.linguistica_muestreo_nativo_posterior` se lee del grupo `producto`) | — |
| `semilla_exposicion.json` | matriz país × macro del Anexo D `[SUPUESTO]` hasta que X1 publique la suya | — |
| `mercado_seleccion.schema.propuesta.json` | propuesta de esquema de `mercado.seleccion.json` (pedido a S-A) | propuesta |

`[PENDIENTE]` promover a `scripts/mercados/` con tests en `tests/mercados/` (S-A/S-B) y que `puntaje.py` llame a `engine.factibilidad` cuando sea la economía única.
Autoprueba: `.venv/bin/python -I .claude/skills/m1-mercados-localizacion/scripts/autoprueba.py`
