# Defectos sembrados y calibración del QA

> Spec §6.4 y Anexo B; notas 22f §5.3 y 25 §6.3. Catálogo ejecutable: `evals/sembrados/catalogo.json` (cada defecto con `como_sembrar`, `check_esperado`, `severidad` y la salida esperada del QA); rotación: `evals/sembrados/rotacion.json`.

## Reglas
1. **≥ 10 bloqueantes sembrados por corrida** del QA, variantes **rotadas** (no memorizables): el QA debe detectar **≥ 90 %** y **100 % de S1, S6, S10 y S11**.
2. PASS a los **dorados** (≥ 2 por macro-nicho; ≥ 1 en otro idioma): `evals/dorados/`.
3. Además, los casos de **contenido (C)** de `casos-frontera.yaml` (hoy `docs/_historial/hwr-semillas/casos-frontera.yaml`; ruta definitiva pendiente) rotados por macro-nicho: **0 falsos verdes** y **negativa correcta ante C3**.
4. Se repite al cambiar la skill del QA, el modelo de D4 o las políticas de plataforma.
5. Los sembrados se aplican sobre **copias** de un dorado en una carpeta temporal; nunca sobre `ofertas/<id>/` real. El QA no sabe qué se sembró ni dónde.

## Cómo sembrar
Cada entrada del catálogo trae `mutacion` (qué cambiar en qué archivo del dorado) o `descripcion` si es de criterio. Los que tienen `check_script` están cubiertos por una prueba de `scripts/test_scripts.py` (calibración de los scripts, no del QA). Los **de criterio** (S10 confrontar sin exclusión, S11 expectativa de rendimiento, imagen IA como foto de un resultado, retraducción con sentido invertido) solo los atrapa el QA con L2/L3 y se miden en la corrida de calibración.

## Resultado esperado del QA ante un defecto
Un hallazgo con `check_id` (el de la tabla), `patron_clave` (kebab del catálogo), `severidad`, `evidencia` citada (archivo:línea o campo) y `estado: devuelto_al_maker`; veredicto `FAIL` (o `ESCALAR` si es inviable). Un hallazgo sin evidencia citada no cuenta como detección.
