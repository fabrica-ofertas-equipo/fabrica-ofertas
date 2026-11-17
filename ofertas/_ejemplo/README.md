# ofertas/_ejemplo
Oferta FICTICIA y COMPLETA de punta a punta (no se lanza): guía de reincorporación laboral tras una pausa larga («Mi Regreso Laboral», es-ES, EUR; caso VERDE de dinero, riesgo reencuadrado de amarillo a verde, sin claims de salud ni de ingresos). Sirve para que el esqueleto camine con ella.

| Carpeta o archivo | Etapa | Artefacto |
|---|---|---|
| `00-brief.yaml`, `estado.json`, `mercado.json` | O0, M1 | brief firmado (clave de prueba), máquina de estados, mercado como hipótesis |
| `01-descubrimiento/` | D1 | `candidatos.json` (2 candidatos, 4 descartados con motivo canónico), `crudo/` con hashes |
| `02-validacion/`, `03-oferta/` | D2, D3 | `validacion.json`, `oferta.json` (incluye ángulos y avatar), `economia.json` (sale de `engine.factibilidad`; recalculable con `python -m engine.factibilidad verificar`) |
| `04-producto/` | D4 | `producto.json`, entregables y `muestras/muestra-guia-v1.md` |
| `05-landing/` | D5 | `sitio/` (3 páginas de ángulo, `gracias`, **siete** páginas `legal/{vendedor,terminos,privacidad,reembolsos,cookies,aviso,entrega}.html`, `css/`, `js/consentimiento.js` y `js/pixel.js`), `rutas.json`, `assets.json`, `checkout.json`, `tracking.json` (`consent_gating.plataforma = banner_propio_v1`) |
| `06-creativos/` | D6 | `paquete.json` y 6 imágenes provisionales (`placeholder_de_ejemplo`) |
| `07-campana/` | D7 | `campana.json` en estado `borrador` (sin IDs de Meta ni aprobación) |
| `08-operacion/`, `10-postcompra/` | D8, D10 | un día de operación, una orden, un veredicto INCONCLUSA, una entrega, un reembolso y una señal: **DATOS SINTÉTICOS** (`sintetico: true`) porque la campaña nunca gastó |
| `qa/` | QA de M1 y D1-D7 + dictámenes de X1 (D5, D6, D7) | `<etapa>-v1.json` |
| `_empresa/` | O0, F1 | muestra de `registro.jsonl` (encadenado por hash) y `costos.jsonl` |

Los datos de mercado (CPM, CTR, conversión, tarifas, evidencia y sus URLs `.invalid`) son `[SUPUESTO]` de ejemplo, no hechos. Nada de aquí contiene datos personales ni secretos (las firmas usan la clave de prueba `FABRICA_FIRMA_CLAVE=clave-de-prueba-no-real`, que no protege nada).
Validar con reglas cruzadas: `.venv/bin/python -m scripts.validar_esquemas oferta ofertas/_ejemplo` (usa los límites y la autonomía de prueba de `contratos/ejemplos/`).
Propietario: contratos / A0. Probar: `.venv/bin/python -m unittest discover -s tests/contratos -t .`

**Regenerar y re-sellar** (landing, economía, assets, `qa/`, `estado.json` y los ejemplos de `contratos/ejemplos/` que son copias): `.venv/bin/python -m tests.contratos.regenerar_ejemplo` (`--comprobar` no escribe y sale con 1 si habría cambios). El texto de las páginas es ficticio y lleva `[EJEMPLO]` solo en un comentario HTML; el lint de publicación lo rechaza en producción (`L1-EJEMPLO-COMENTARIO`). Mutaciones sembrables de B0-11: `tests/fixtures/contratos/mutaciones_landing/`.
