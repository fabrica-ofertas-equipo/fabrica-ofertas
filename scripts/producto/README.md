# scripts/producto — Render, lint y empaquetado de D4

Propósito: convertir un entregable fuente en un `producto.json` empaquetado deterministamente, con lint de
contenido y render a PDF, sin LLM en el cálculo (departamentos/05-producto.md, `contratos/producto.schema.json`).

Propietario y etapa: **B1** (ola 2, B1c), D4. Módulos: `render.py`, `lint.py`, `empaquetar.py`.

## CLI

```
.venv/bin/python -m scripts.producto.render --html FUENTE.html --salida SALIDA.pdf [--chrome RUTA] [--timeout 60] [--json]
.venv/bin/python -m scripts.producto.lint PRODUCTO.json --fuente DIR [DIR ...] [--parametros empresa/parametros.yaml]
.venv/bin/python -m scripts.producto.empaquetar ENTRADA.json --raiz 04-producto/entregables --prometido-min 20 [--salida producto.json]
```

Ejemplos con los fixtures de este repo (dry por diseño: no publican ni gastan nada):

```
.venv/bin/python -m scripts.producto.lint tests/fixtures/producto/producto-lint-ok.json \
    --fuente tests/fixtures/producto/entregables/guia.md
.venv/bin/python -m scripts.producto.empaquetar tests/fixtures/producto/entrada-empaquetar.json \
    --raiz tests/fixtures/producto/entregables --prometido-min 20
```

Salidas (convenciones §8): 0 ok · 2 uso (archivo/URL inválida, salida ya existe) · 3 entrada o resultado
inválido (incluye un hallazgo `BLOQUEANTE` de `lint`) · 5 falta un parámetro oficial o no hay navegador
disponible (`render`, nunca sigue sin uno: verde falso prohibido) · 6 el navegador externo falla o excede el
tiempo (`render`).

## Decisiones

1. **`lint.py` es una porción acotada, no el léxico completo.** La skill
  `.claude/skills/d4-producto/scripts/lint_contenido.py` trae listas extensas por idioma (palabras vetadas,
  diagnóstico, testimonios, credenciales falsas…) que viven en `_patrones.py` y en
  `compliance/reglas_sensibles.yaml` (dueño B6/X1). Replicarlas aquí sin dueño claro de su mantenimiento
  violaría "no se duplica a ciegas". Este módulo cubre, con datos deterministas y SIN lista de palabras:
  marcas pendientes (`[VERIFICAR]`/`[SUPUESTO]`/`[TODO]`/`{{placeholder}}`/lorem ipsum), coherencia de
  `matriz_promesas` contra `items` (toda promesa debe referenciar un entregable real, tener texto y prueba;
  `pendiente` es una nota, `MAYOR`, no bloquea), tamaño de archivo contra los parámetros oficiales
  `producto.peso_max_mb_pdf`/`producto.peso_max_mb_paquete`, y datos personales obvios (correo, teléfono).
  Pedido: cuando X1/QA tenga listo el léxico completo en una ruta canónica (no en una skill), sumarlo aquí
  como una regla más.
2. **`empaquetar.py` recalcula SIEMPRE `sha256` y `peso_mb`** desde el archivo real: nunca confía en lo que
  trae `ENTRADA.json` (evita que un Maker declare un hash que no corresponde al contenido). `producto_sha256`
  (hash del mapa `{item_id: sha256}`, para que `postcompra.publicar_producto` de B7 lo use al subir a R2,
  docs/06 N07) se devuelve APARTE de `producto.json`: el esquema `contratos/producto.schema.json` tiene
  `additionalProperties: false` y no define ese campo.
3. **`tiempos.prometido_min` se exige por `--prometido-min`** (R10: debe ser igual a
  `oferta.promesa.tiempo_prometido_min`) porque `empaquetar.py` no lee `oferta.json` (no es su carpeta);
  quien invoque el script (el motor, vía `engine.orq ejecutar --etapa D4`) debe pasarlo desde la oferta ya
  aprobada.
4. **`render.py` simplifica la detección de recursos remotos dentro del HTML** que la skill hace con varias
  expresiones regulares (`<link>`, `@import`, `url()` remotos); esta versión de B0 confía en que X1/QA revisa
  eso con el léxico completo antes de llamar a `render`. Mantiene lo esencial de seguridad: solo `file://`
  local, nunca una URL remota, y el PDF se verifica sin librerías (cabecera `%PDF-`, `%%EOF`, páginas).
5. **El binario del navegador es inyectable** (`renderizar(..., ejecutar=...)`): las pruebas usan un doble que
  escribe un PDF de muestra, nunca abren un navegador real (no hay red ni GUI en las pruebas, convenciones §11).
  Sin un navegador instalado y sin `--chrome`, `buscar_navegador` falla con código 5: nunca sigue sin
  verificar (ningún "verde falso").

## Cómo probar

```
.venv/bin/python -m unittest discover -s tests/scripts -t . -p "test_producto_*.py"
```
