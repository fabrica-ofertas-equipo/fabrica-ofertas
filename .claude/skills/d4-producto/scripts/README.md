# scripts/ de la skill d4-producto (offline, biblioteca estándar, probados)

Ayudas deterministas pequeñas. **Sin red, sin secretos.** Los umbrales salen de `empresa/parametros.yaml` (`--parametros`) o de una bandera; sin dato, salida 5 (fail-closed). Salida: un JSON por stdout; código 0 = sin BLOQUEANTE/MAYOR, 1 = con hallazgos, 2 = uso, 3 = entrada inválida, 5 = falta un parámetro. Ejecutar desde la raíz con `.venv/bin/python`.

| Script | Checks | Qué hace | Ejemplo |
|---|---|---|---|
| `cobertura_matriz.py` | L1-01/02/14 | Matriz promesas ↔ ítems en los dos sentidos, bump separable, servicio oculto, idioma, n_unidades | `… --oferta-dir ofertas/OF-AAAAMM-NN [--permitir-pendientes]` |
| `tiempo_total.py` | L1-03 | Lectura + pasos humanos vs `tiempo_prometido_min` (estimado o cold run) | `… --producto P --oferta O --lectura A.html B.md [--autoprueba autoprueba.json]` |
| `similitud_ngrama.py` | L1-06 | Tramos idénticos vs fuentes/competidores; muestra de frases para búsqueda web | `… --producto entregables/fuente --fuentes respaldo/fuentes [--muestrear 10]` |
| `verificar_respaldo.py` | L1-12/13/08 | `afirmaciones.jsonl` + snapshots: sha256, cita, nivel, fechas, cifra/unidad por locale, cifras sin respaldo | `… --respaldo-dir respaldo --producto entregables/fuente --locale it-IT --paises IT --hoy AAAA-MM-DD` |
| `lint_contenido.py` | L1-05/09/13/14/15 | Léxico interino por idioma: claims, diagnóstico, testimonios, credenciales, servicio, secretos, formato numérico, ayuda de otro país, literales obligatorios | `… --producto entregables/fuente --locale es-ES --requiere "ayuda=…"` |
| `lint_hoja.py` | L1-17 | `.xlsx`: macros, enlaces externos, hojas/filas ocultas, fórmulas de estado, metadatos | `… --hoja entregables/x-v1-hoja.xlsx` |
| `empaquetar.py` | L1-11/03 | sha256 y peso de cada ítem (`--actualizar`), nombres neutros, pesos máximos, huérfanos | `… --oferta-dir ofertas/OF-AAAAMM-NN --actualizar` |
| `cotizar_creditos.py` | L1-GASTO | Autoriza o deniega el gasto de créditos según topes, PAUSA, infraestructura y permiso | `… --cotizacion cotizacion_creditos.json` |
| `render_pdf.py` | Paso 7 · L1-04 (parte) | HTML → PDF con Chrome/Brave/Chromium sin pantalla (ruta A): perfil temporal nuevo, sin red, entorno mínimo, timeout con terminación, no sobrescribe; verifica cabecera, páginas, fuentes embebidas, `/ToUnicode`, `/Title`, `/Lang`; `--cronometrar` = prueba en frío (JSON `segundos, paginas, bytes, fuentes_embebidas, navegador`). **Salida propia:** 0 ok · 2 uso (URL, salida existente) · 3 HTML o PDF inválido, timeout · 5 sin navegador; no es un check: no emite hallazgos BLOQUEANTE/MAYOR | `… --html entregables/fuente/x.html --salida entregables/x-v1.pdf --cronometrar` |
| `_comun.py`, `_patrones.py` | — | Utilidades y léxicos (interinos hasta `terminos_sensibles/<locale>.yaml` de X1) | — |
| `test_scripts.py` | — | 59 pruebas (defectos sembrados incluidos y las plantillas de la skill) | `.venv/bin/python .claude/skills/d4-producto/scripts/test_scripts.py` |
| `test_render_pdf.py` | — | 26 pruebas de `render_pdf.py` (navegador falso para timeout, salida inválida, banderas y entorno; Chrome real con diacríticos, red bloqueada y cronómetro; se omiten sin navegador) | `.venv/bin/python -m unittest discover -s .claude/skills/d4-producto/scripts -p "test_*.py"` |

Lo que falta (`scripts/producto/*` de proyecto: render de las rutas B/C y kit de marca, lint de PDF, captura de fuentes, subida a preproducción, recálculo de hojas, `l1_d4`, `similitud_web`) está en `references/dependencias.md` como `[PENDIENTE]` con su SB/LT. Ya existen `scripts/producto/{render,lint,empaquetar}.py` y `python -m scripts.nivel_riesgo` (L1-16). Quedaron fuera de la lista `sandbox_metodo`, `aplicar_parche` y `scripts/qa/*` (resueltos: no se construyen). `cotizar_creditos.py` queda dormido mientras D4 no genere imágenes.
