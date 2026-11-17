# contratos
Contratos de datos del sistema: JSON Schema 2020-12 por artefacto (`<nombre>.schema.json`, `$id` estable con MAJOR: `https://fabrica-ofertas.example/contratos/v1/<nombre>.schema.json`), definiciones compartidas (`comunes.schema.json`) y la tabla única de gates (`gates.json`).
Propietario: constructor de contratos / A0 (arquitectura). Ruta protegida contra escritura de agentes: los cambios entran solo por el script de aplicación aprobado.
Índice humano, matriz de artefactos, gates, estados y registro de reconciliación: `docs/contratos.md`.

## Módulos y archivos
- `comunes.schema.json`: dinero, moneda, locale, IDs, hash, timestamp, nivel de autonomía, gate, veredicto QA, severidad, tipos de evidencia, macro-nicho, motivos de rechazo, patrones de nombres de Meta.
- Un esquema por artefacto: `brief, estado, mercado, candidatos, validacion, oferta, economia, producto, assets, checkout, tracking_plan, creativos, campana, orden_presupuesto, veredicto_oferta, senal_pausa, entrega, reembolso, qa, registro, costos, infra_estado, limites, parametros, autonomia, portafolio, pnl, kpi, gates` y, desde la ola 0b-1, `aprobacion, ids_meta, preflight, sello, decision, ledger, conciliacion, tipo_cambio, postmortem, orden_firmada, traspaso`, y desde CT-3 B1 `catalogo` (catálogo firmado por oferta) y `alertas` (una línea de `alertas.jsonl`).
- `gates.json`: gate por etapa/acción y nivel (N0 a N4), coherente con el backbone 5.5.
- `monedas_iso4217.json` (1.0.0, CT-3): exponente ISO 4217 por moneda operable, para consumo desde JavaScript (`capi`); volcado de `scripts.validar_esquemas.EXPONENTE_ISO4217` (fuente única; una prueba falla si difieren). No es un esquema: `cargar_esquemas` lo ignora.
- `ejemplos/`: un válido y un inválido (con `.motivo.txt`) por esquema; fixtures de límites y autonomía de PRUEBA.

## CLI (`scripts/validar_esquemas.py`)
```
.venv/bin/python -m scripts.validar_esquemas                      # esquemas + ejemplos + plantillas de empresa/ + ofertas/_ejemplo
.venv/bin/python -m scripts.validar_esquemas esquemas
.venv/bin/python -m scripts.validar_esquemas ejemplos
.venv/bin/python -m scripts.validar_esquemas oferta ofertas/_ejemplo [--limites ruta.yaml]
.venv/bin/python -m scripts.validar_esquemas limites empresa/limites.yaml --operacion gastar   # fail-closed
```
Códigos de salida: 0 correcto · 2 uso incorrecto · 3 validación (esquema o regla cruzada) · 5 dato de límites faltante. Sin red ni efectos externos. Parámetros fail-closed: `... parametros empresa/parametros.yaml --operacion runner_vivo` (salida 5 si falta algo). Variable opcional `FABRICA_FIRMA_CLAVE` para verificar firmas HMAC (la oferta de ejemplo usa una clave de prueba).

## Reglas
- Dinero = entero en unidad menor + ISO 4217; sin `float`; tiempo UTC con `Z`; `additionalProperties: false`.
- Cambio de esquema: SemVer (política de rupturas en preproducción: `docs/contratos.md` §8), actualizar ejemplos y `ofertas/_ejemplo/`, correr las pruebas.
- Firmas: Ed25519 para aprobación humana, sello de X1 y orden firmada (HMAC solo pruebas y servicio a servicio); el validador comprueba el formato, `engine.guard` verifica con la clave pública.
- Probar: `.venv/bin/python -m unittest discover -s tests/contratos -t .`
