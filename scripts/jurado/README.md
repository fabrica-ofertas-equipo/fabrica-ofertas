# scripts/jurado — Jurado de creativos (v0.1.0, sin pulir)

Código determinista del jurado de la pieza 3 del sistema de Juan Pablo Mentor: 10 clientes ideales simulados por mercado votan los creativos **a ciegas, antes de gastar**; el resultado se compara con lo cobrado. Solo biblioteca estándar, sin red, sin claves, sin Meta/Stripe/Kie y **sin llamar nunca a un LLM**: la IA vota (agente `jurado-votante`), el código hace todo lo demás. Skill: `.claude/skills/jurado-creativos/SKILL.md`.

**Honestidad.** Nace en **modo sombra**: predice, se compara y no decide nada; solo ordena y avisa. Hoy no hay etiquetas reales: el estado de cualquier jurado es `acumulando` y no tiene ninguna precisión demostrada. La fuente (JPS) no da el prompt de los avatares, la ponderación ni cómo se calcula «acierta» (H-11): lo que falta es `[SUPUESTO]` (`_comun.py › PARAMETROS_DEFECTO`).

## Módulos

| Módulo | Qué hace |
|---|---|
| `avatares.py` | Panel de avatares de un mercado SOLO desde `voz_cliente.json`: cada rasgo es una cita con `frase_id` y fuente; edad/género/ocupación `sin_dato`; N limitado por la evidencia; registro de procedencia (`sha256` de la voz, semilla) y reemplazo con `registro_avatares.jsonl`. Subcomandos `generar`, `validar`, `reemplazar`. |
| `paquetes.py` | Paquetes ciegos: una pieza por llamada, orden aleatorio con semilla registrada, anclas conocida-ganadora y conocida-perdedora, ids opacos, sin métricas ni nombres de formato. Rechaza piezas sin QA-A/lint, video, más llamadas que `max_llamadas` y un jurado apagado. Subcomandos `armar`, `verificar` (informe de ceguera). |
| `agregar.py` | Valida votos (rechaza los malformados), desanonimiza con la llave y escribe `jurado.json`: ranking, dispersión, acuerdo entre jueces (kappa de Fleiss), **banda de confianza** (Wilson 95 % + rango de puestos por bootstrap de avatares), anclas, ideas, `modo: sombra`, `aplica_orden: false`, sello sha256. Subcomandos `agregar`, `verificar` (L1 de código). |
| `calibrar.py` | Con etiquetas reales (hoy, fixtures): etiquetas por madurez (inversión, gancho, clics, pago iniciado, ventas), AUC con IC95 de DeLong, p contra el azar, Brier, comparación con el azar y con la rúbrica (DeLong pareado), anclas, estado (`acumulando`, `sombra`, `apagar`, `elegible_asesor`), propuestas de reemplazo y anclas sugeridas; fusiona `precision` en `jurado.json` sin romper el sello. |
| `estadistica.py` | AUC, DeLong (1 y 2 AUC), permutación, Brier, Wilson, kappa, bootstrap de puestos. |
| `demo.py` | **Demostración** sin LLM con votos sintéticos sobre los 11 ganchos candidatos del piloto OF-202611-91 (marcada `demostracion: true`). |
| `_comun.py` | JSON, hashes, parámetros (`[SUPUESTO]`, un solo lugar), limpieza de texto, errores. |

## El ciclo (quién hace qué)

```
 D6 (noche) ─► QA-A + lint ─► 07:00 ─┐
                                      ▼
 1 avatares.py generar ──► avatares.json (una vez por oferta y mercado)          [código]
 2 piezas.json + anclas.json  (copiados de lo aprobado; sin inventar resultados)  [orquestador]
 3 paquetes.py armar ──► ciego/ (lo que ve el votante) + privado/ (llave, manifiesto)  [código]
 4 por cada llamada del manifiesto, EN ESE ORDEN:                                   [ORQUESTADOR → IA]
       jurado-votante  ← contenido del paquete          → voto JSON  → votos/
 5 agregar.py agregar ──► jurado.json (sellado) + privado/l1.json                  [código]
 6 jurado-qa (solo lectura) revisa ceguera, anclas, trazabilidad, honestidad       [IA independiente]
 7 copiar jurado.json a ofertas/<id>/06-creativos/jurado.json  (lo lee #/jurado)   [orquestador]
 ── 3 días después: metricas.jsonl por anuncio (S-B) ──
 8 miércoles: calibrar.py ──► calibracion.json  (+ precision en el jurado.json)     [código]
       acumulando / sombra / apagar / elegible_asesor → decide el DUEÑO (promoción, reemplazos)
```

**Quién invoca a los agentes:** el orquestador (la sesión del dueño o el runner de S-B). Ningún módulo de aquí importa un cliente de LLM, abre un socket ni ejecuta un comando externo. El orquestador lee `privado/manifiesto.json › orden_llamadas`, lanza un `jurado-votante` por cada paquete **pegando su contenido** (no la ruta) y guarda la respuesta tal cual en `votos/`.

## Uso (desde la raíz del repositorio, con `.venv`)

```bash
# 1. avatares (una vez por oferta y mercado)
.venv/bin/python -m scripts.jurado.avatares generar --voz ofertas/<id>/02-validacion/voz_cliente.json --n 10 --semilla 7 \
    --salida ofertas/<id>/06-creativos/jurado/avatares.json --incluir-baseline-rubrica
.venv/bin/python -m scripts.jurado.avatares validar ofertas/<id>/06-creativos/jurado/avatares.json --voz ofertas/<id>/02-validacion/voz_cliente.json

# 3. paquetes ciegos de una tanda (piezas.json y anclas.json: ver templates/ de la skill)
.venv/bin/python -m scripts.jurado.paquetes armar --avatares …/avatares.json --piezas <tanda>/entrada/piezas.json \
    --anclas <tanda>/entrada/anclas.json --semilla auto --salida <tanda> [--calibracion calibracion.json]
.venv/bin/python -m scripts.jurado.paquetes verificar --tanda-dir <tanda>

# 5. agregar los votos
.venv/bin/python -m scripts.jurado.agregar agregar --tanda-dir <tanda> --avatares …/avatares.json
.venv/bin/python -m scripts.jurado.agregar verificar --tanda-dir <tanda>

# 8. calibrar (miércoles; cuando existan métricas reales)
.venv/bin/python -m scripts.jurado.calibrar --jurados <tanda1>/jurado.json <tanda2>/jurado.json --metricas metricas.jsonl \
    --salida calibracion.json --fusionar-en <última tanda>/jurado.json

# Demostración (votos sintéticos, sin LLM)
.venv/bin/python -m scripts.jurado.demo corrida --salida .claude/skills/jurado-creativos/evals/demostracion
```

Códigos de salida: `0` ok · `2` uso · `3` entrada inválida o regla violada (mensaje en stderr).

## Reglas que el código hace cumplir (y las pruebas comprueban)

- **Misma entrada y misma semilla = los mismos bytes** (paquetes, manifiesto, orden). La semilla y su origen quedan registrados; sin semilla no se arma.
- **Ceguera**: el paquete es una lista blanca; `paquetes.py verificar` busca cada `ad_name`, `ancla_id`, `id_origen`, nombre de formato y palabra de rendimiento; los activos se copian con nombre opaco.
- **Una pieza por llamada** y cada juez ve ≥ 1 ancla ganadora y ≥ 1 perdedora (mismo idioma y formato); las anclas no entran al orden.
- **Votos estrictos**: booleano de verdad, enteros 0-10, ≤ 25 palabras, sin campos de más; malformados, duplicados, ajenos y sintéticos-en-real se rechazan y no cuentan; con alerta de ceguera van a cuarentena.
- **Sombra**: `aplica_orden = false`; `asesor` solo con `promocion.json` firmada, calibración vigente `elegible_asesor`, mismo mercado, hash coincidente y sin caducar; `apagar` ⇒ `paquetes.py armar` se niega.
- **Sin precisión inventada**: con menos de 150 etiquetas el estado es `acumulando`; una sola clase ⇒ `None`; `ventas` no se etiqueta sin `gasto_min_ventas` (de `economia.json`).
- **El sello** cubre la predicción (no `precision`): una calibración posterior no lo rompe, y una predicción modificada o sellada después de leer el resultado no entra a la calibración.
- Los jurados de **demostración** no entran a una calibración real (`--fixture` los marca `valido_para_decidir: false`).

## Pruebas

```bash
.venv/bin/python -m unittest discover -s tests/jurado -t . -p "test_*.py"
```

Sin red ni LLM; todo se genera en cada prueba. Cubren determinismo con semilla, ceguera, anclas, agregación correcta, rechazo de votos malformados, calibración con casos sintéticos (jurado perfecto, aleatorio, invertido, acumulando), la regla de apagado y de promoción, el reemplazo de avatares con registro, la compatibilidad con la pantalla `#/jurado` y los sembrados de `evals/`.

## Lo que NO hace (v0.1)

Votar video (el votante solo tiene `Read`), ponderar jueces, llamar a un modelo, leer métricas de Meta (las produce S-B), decidir qué se prende o se apaga, ni publicar nada. Pedidos a otros: `.claude/skills/jurado-creativos/PEDIDOS.md`.
