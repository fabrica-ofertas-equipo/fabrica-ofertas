# Mutaciones sembrables de B0-11 (landing de `ofertas/_ejemplo`)

Defectos sembrados para probar que el lint de publicación (`landing.validar` de B4) falla el 100 % de ellos y que la base pasa limpia.

- `catalogo.json`: **8** mutaciones (`ML-01`…`ML-08`) del encargo de la ola 0b-2 y **4** complementarias (`MC-01`…`MC-04`) de la lista de `docs/06` B0-11 (moneda distinta, garantía distinta, salud en `tracking.json`, casilla premarcada). Cada una: `id`, `nombre`, `descripcion`, `parches[]` (operaciones deterministas `borrar`, `reemplazar`, `insertar_antes`, `json_establecer`, con el número exacto de coincidencias), `regla_esperada` (identificador `L1-*`), `reglas_colaterales` (las únicas otras que pueden dispararse) y `check_d5` (columna de `departamentos/06-landing-checkout.md` §6.1).
- Se aplican con `tests/contratos/aplicar_mutacion_landing.py` (`copiar_ejemplo` + `aplicar`), **solo sobre copias temporales marcadas**; nunca sobre `ofertas/_ejemplo/`. Si el ejemplo cambia y un ancla deja de existir, la mutación falla en voz alta.
- La regla se comprueba con `tests/contratos/lint_landing_referencia.py` (oráculo de referencia; ver su docstring con las 19 reglas). B4 puede mapear sus propios identificadores a estos.
- `ML-01` borra `legal/cookies.html`; `ML-03` y `ML-08` usan el dominio reservado `.invalid`; el catálogo no contiene correos ni datos personales.
- Pruebas: `.venv/bin/python -m unittest tests.contratos.test_mutaciones_landing`.
- No cubierto: el píxel **en línea** en el `<head>` sin condición lo detecta la misma regla (`L1-CONSENT-PIXEL`) pero no tiene mutación propia; ML-06 siembra el equivalente enlazando `pixel.js`.
