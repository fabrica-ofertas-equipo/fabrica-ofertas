# Dependencias de `/cerebro-abrir`

> v0.2 sin pulir. El detalle compartido con `/cerebro-cerrar` (nombres frente a X2, X2 completo, importar las demás listas de pendientes, inyección de la memoria a los agentes) está en **`../../cerebro-cerrar/references/dependencias.md`**: no se repite aquí. Hooks y resumen diario (solo texto, nada instalado): `hooks-propuestos.md`.

## Lo que lee y de dónde

| Qué | Fuente | Estado |
|---|---|---|
| **La lista única** de pendientes (P0-P3, reglas y preferencias propuestas, vencidos y próximos) | `empresa/panel/pulido.jsonl` (la misma que lee `#/cerebro`, «Mis tareas» y las alertas) | existe |
| Gates que esperan al dueño | `ofertas/*/estado.json`, `etapas.<E>.gate_pendiente == true` (las ofertas `_…` de demostración se excluyen) | existe; el motor `engine.orq` lo escribe |
| **Lo preparado sin tu OK** | `ofertas/<id>/{03-oferta/oferta.json, 04-producto/producto.json, 05-landing/copy.json, 06-creativos/paquete.json, 07-campana/campana.json}` frente a `etapas.<E>.estado` de `estado.json`; una etapa con `parada.json` o que ya espera tu firma no cuenta | existe (hoy: `OF-202611-91`, carpeta de práctica, sin `estado.json`) |
| PAUSA y freno de captura | `empresa/PAUSA`, `empresa/captura/freno.json` (solo lectura: nunca se borran desde aquí) | existen |
| Decisiones vigentes y su antigüedad | `empresa/memoria/decisiones_dueno.jsonl` (sembradas J1-J21; buzón de `/cerebro-cerrar`) y, solo contados, `docs/00-decisiones-y-tareas-del-dueno.md` y `docs/_historial/mentor-sistema/decisiones-del-dueno.md` | existen |
| Preferencias aprobadas | `empresa/memoria/preferencias.jsonl` (lo escribe `guardar_pendiente.py preferencia_resolver`) | nace con la primera aprobación |
| Último cierre | el `origen` «… /cerebro-cerrar» de las líneas de la lista única y de `empresa/memoria/*.jsonl` | deducido (no hay registro de cierres) |
| Jardinero | solo los **nombres** de `empresa/memoria/jardin/AAAA-MM-DD.json` | nace con la primera propuesta guardada |
| Idea por significado | `scripts/cerebro/buscar.py` (lista única, memoria, documentos de decisiones, `know-how.md`, pantallas) | existe |

## Una sola lista: cómo se comprueba

`empresa/panel/pulido.jsonl` es la lista única. `tests/cerebro/test_lista_unica.py` calcula la misma bitácora con **el JavaScript real del panel** (`dashboard/web/lib/cerebro.js` y `lib/tareas.js`, vía `tests/cerebro/puente_panel.mjs`), con `scripts/alertas/hechos.py` y con `resumen_abrir.py`, y exige los mismos P0, P1, reglas por aprobar, vencidos y «pendientes tuyos»; también sobre una copia de la bitácora real. Un tipo de entrada desconocido cuenta como pendiente (igual que el panel) para que nada se esconda.

**Divergencias conocidas (documentadas por una prueba, para que alguien las alinee):**

1. *Vencimiento con hora.* El panel, este script y el jardinero cuentan por **día** (`vence: 2026-11-09T00:00:00Z` el día 9 es «vence hoy»); `scripts/alertas/hechos._pulido` cuenta por instante (pasada la hora ya está «vencido»). Con fecha sin hora coinciden los cuatro.
2. *Prioridad mal escrita.* Una `prioridad` como `p0` o ` P0 ` (solo posible editando el archivo a mano) este script la trata como P0 y avisa; el panel la ignora (la muestra sin prioridad). Se prefirió que un P0 no pueda esconderse por una errata.
3. *Conteo de decisiones de los documentos.* `contar_decisiones` de este script cuenta cada fila de las tablas «Decisiones tomadas» **y** «Decisiones posteriores», con la cabecera de cada tabla aparte y sin las filas «—» (hoy: 21 para `decisiones-del-dueno.md`); la de `dashboard/api_cerebro.py` solo cuenta las de «tomadas» y trata la cabecera de las tablas siguientes como decisión. **PEDIDO a S-A/S-C del panel:** alinear `api_cerebro.contar_decisiones` y el rótulo «J1 a J9» (`FUENTES_DECISIONES`), que hoy dice 9 y son 21.

## Lo que falta o se pide

1. **Comando exacto de cada gate:** el script nombra oferta, etapa y hash; el comando `python -m engine.orq firmar …` lo da `/o0-lanzar-oferta OF-…` (mismas reglas: nunca firma). Hasta que el panel y O0 compartan la forma única de `proximo_paso` (`o0-orquestador-portafolio/references/dependencias.md` §F), no se duplica esa lógica aquí.
2. **Registro de cierres:** hoy el último cierre se deduce del `origen` de las líneas guardadas. `[PENDIENTE: registro de cierres, con X2]`.
3. **Instalar el hook de apertura y el resumen diario:** propuestos como texto en `hooks-propuestos.md`; los instala el dueño (o S-B para el planificador y el canal). El canal de avisos sigue sin decidir (`PUL-0003`).
4. **Lo que el dueño aprobó, a los agentes que corren solos:** hoy `/cerebro-abrir` es para la sesión interactiva; los runners corren con la auto-memoria apagada (`docs/09-runtime-de-agentes.md`). **PEDIDO a S-B:** que el runner inyecte la ficha de contexto y `scripts/cerebro/preferencias.py --etapa <E> --texto` (B1-03).
5. **El panel `#/cerebro`:** el bloque «Jardín» solo cuenta archivos de `empresa/memoria/jardin/`; las preferencias propuestas ya aparecen como «Regla propuesta» con su categoría «Preferencia». **PEDIDO a S-A/S-C del panel:** mostrar el detalle de la propuesta (las correcciones con su prueba) y un botón «Aprobar/Rechazar» que escriba `preferencias.jsonl` con las palabras del dueño (hoy se hace con `/cerebro-cerrar`).
6. **Ofertas reales:** hoy solo existe la carpeta de práctica `OF-202611-91` y la demostración `_ejemplo`; hasta que haya una oferta real con `estado.json`, «gates que esperan tu firma» sale vacío (y lo dice) y «preparado sin tu OK» muestra lo de la práctica.
