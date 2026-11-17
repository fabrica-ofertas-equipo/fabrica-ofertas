# Pedidos de la skill `jurado-creativos` (v0.1.0)

La skill no toca `contratos/`, `engine/`, `empresa/*.yaml`, `departamentos/`, la configuración de Claude Code ni la pantalla del panel. Lo que el jurado necesita de otros está aquí, numerado. Resumen en `docs/_historial/coordinacion-sesiones.md` («Avisos de S-C — jurado»).

## A S-A (contratos, parámetros, documentos)

1. **Contrato `jurado.schema.json`.** Propuesta lista en `templates/jurado.schema.json` (Draft 2020-12, validada contra la corrida de demostración y contra `dashboard/web/lib/jurado.js`; hace cumplir `aplica_orden = false` en sombra y apagado). Alta en `contratos/`, `docs/contratos.md` y `ofertas/*/06-creativos/` como salida admitida de D6/del jurado (`jurado.json` y la carpeta `jurado/`). En el MINOR de `creativos` que traiga `virality`: `anuncios[].jurado` (posición, `share_si`, banda) como campo opcional, nunca compuerta (P3-04).
2. **Grupo `jurado.*` en `parametros.yaml`** con los valores de `templates/parametros.propuesta.json`: `n_avatares` 10, `n_min_etiquetas` 150, `auc_min` 0,60, `alfa` 0,05, `anclas_min_pct` 0,6, `max_llamadas` 200, etc. **Todos `[HIPÓTESIS]`** salvo el AUC de azar. `gasto_min_ventas` no tiene valor por diseño: sale de `economia.json` (CPA máximo × k). Fijar también el tope de tokens del jurado dentro de `max_budget_por_corrida_agente`.
3. **Etapa del jurado en `qa.schema.json`** (`comunes.schema.json#/$defs/etapa`): hoy `templates/qa_jurado.json` usa `etapa: "D6"` y `subetapa: "jurado"` con los mismos nombres de campo para migrarlo sin reescribir.
4. **Carpeta de datos `empresa/jurado/`** (calibraciones semanales, promociones, avatares compartidos por `locale` si se quiere calibrar entre ofertas del mismo mercado). Hoy los avatares y tandas viven por oferta en `06-creativos/jurado/`.
5. **Regla de X2 explícita:** la calibración del jurado nunca realimenta la generación de claims (X2:94) y el banco de hooks no se alimenta del orden del jurado mientras esté en sombra.

## A la pantalla del panel (otra sesión; solo lectura de `jurado.json`)

6. `dashboard/web/lib/jurado.js` y `pages/jurado.js` deberían:
   - leer **`modo`**, **`aplica_orden`** y **`precision.estado`** (hoy deciden «útil» solo por `auc ≥ 0,6` y dicen «los primeros salen antes a la prueba» sea cual sea el modo; con el archivo nuevo el AUC puede ser ≥ 0,6 y el estado seguir siendo `sombra` por no ganarle a la rúbrica o por anclas);
   - mostrar `demostracion` (banner), `advertencias[]`, `anclas.discrimina`, `acuerdo` (kappa, tasa de «sí»), y por pieza `banda_confianza`, `rango_puestos` y `confianza` (hoy solo ve «7 de 10»);
   - mostrar el estilo de decisión de cada avatar (`avatares[].estilo_decision`) y las advertencias del panel de avatares.
   El archivo ya es compatible con la lectura tolerante actual (claves `votos`, `orden`, `precision`, `ideas`, `modo`, `sello`, `generado_en`, `locale`); no usa `auc`, `brier`, `etiquetas`, `n`, `baselines` en la raíz.

## A S-B (motor, hooks, datos)

7. **Allowlist de Bash** (`agentes/hooks/herramientas.yaml`): `python -m scripts.jurado.{avatares,paquetes,agregar,calibrar}` para el orquestador. `jurado-votante` y `jurado-qa` no usan Bash.
8. **Bucle de votación en el runner**: leer `privado/manifiesto.json › orden_llamadas`, lanzar un `jurado-votante` por paquete (contexto limpio, sin `CLAUDE.md` ni memoria: el agente ya declara `omitClaudeMd`), pegar el **contenido** del paquete (no la ruta) y la ruta absoluta de la imagen si la hay, guardar la respuesta **tal cual** en `votos/`. Un reintento por JSON inválido. Descontar los tokens de `max_budget_por_corrida_agente`. Sonda de que el votante no alcanza `privado/`.
9. **Scheduler**: 07:00 diario tras QA-A y el lint (después de la fábrica nocturna de D6 y antes de la aprobación de la mañana); miércoles `calibrar.py`. Hora del mercado, no UTC (E-14).
10. **Productor de `metricas.jsonl`** por anuncio (`ad_name`, `oferta_id`, `fecha_lectura`, gasto, impresiones, clics del enlace, vistas de 3 s, pagos iniciados, compras netas con `adid`) a los 3 días y a mayor madurez; sin él no hay etiquetas y el jurado queda en `acumulando` para siempre. Requiere `dim_anuncio` con `ad_name`/`hook_tipo`/`variante_formato` (B1-04).

## A quien mantenga D6

11. El QA de D6 puntúa el **paquete** (R1-R10), no cada pieza. La línea base «rúbrica sin perfil» se obtiene hoy con un juez más del panel (`--incluir-baseline-rubrica`, `av-<locale>-rubrica`). Si prefieren la rúbrica real del QA por pieza, que `d6-qa` emita R1-R3 por `ad_name` (`calibrar.py --baseline rubrica_qa=archivo.jsonl` ya lo acepta).
12. Que `tanda.py bandeja` y `paquete.json` dejen las `precondiciones` (QA-A y lint en PASS) por pieza, que es lo que `paquetes.py` exige.

## Al dueño

13. **Los 3 videos de JPS** (jurado, surfeo, creativos; B2-33/H-11): probable fuente del prompt de los avatares, la ponderación y el cálculo de «acierta». Hasta entonces todo eso es `[SUPUESTO]`.
14. **Ampliar la voz del cliente** del piloto (35 frases, 13 fuentes, solo 5 focos con ≥ 2 fuentes): con N = 10, 5 avatares se apoyan en una sola fuente. Hasta entonces, N = 5 es lo que el material sostiene.
15. **Anclas**: quién escribe los controles sintéticos de arranque (no hay ninguna pieza medida todavía) y cuándo se aceptan las anclas medidas que sugiera la calibración.
16. **Firma de la promoción** cuando una calibración sea `elegible_asesor`; y decidir si, mientras esté en sombra, el orden se muestra en el panel o se guarda sin mostrar.
17. **Costo**: 143 llamadas por tanda de 11 piezas con 10 avatares + línea base (78 con 5 avatares). Fijar con S-A el tope de tokens por tanda; probar un modelo más barato para el votante (la calibración dirá si pierde acierto).
