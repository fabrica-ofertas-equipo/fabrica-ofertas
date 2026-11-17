# Formato de salida y tabla de decisión del próximo paso

## 1. Formato fijo (≤ 25 líneas)
Plantilla: `templates/informe-proximo-paso.md`. Orden: bloqueos del dueño · dónde estoy · qué falta · qué espera tu firma · comando exacto · avisos. Lenguaje de negocio, sin jerga; cada cifra con su archivo y fecha; una cifra vieja o ausente se dice, no se inventa.

## 2. Tabla de decisión (la implementa `scripts/proximo_paso.py`; los tests de `scripts/test_proximo_paso.py` la fijan). Comandos = los de la CLI REAL de `engine.orq` (`o0-orquestador-portafolio/references/comandos-engine-orq.md`)

Entradas: `estado.json` (`fase`, `nivel`, `pausa`, `etapas.<E>.{estado, gate, gate_pendiente, obsoleta, entradas, hash_salida, nivel, bloqueo}`), `contratos/gates.json`, `empresa/autonomia.yaml` (sin archivo: N0, lo más estricto), `empresa/PAUSA`, `00-brief.yaml`, `limites.acciones_gate_humano`. Se recorre la cadena `D1, M1, D2, D3, D4, D5, D6, D7` y se **detiene en la primera etapa no cerrada**.

| Condición (en este orden) | `accion` | Comando que se sugiere | ¿Espera firma? |
|---|---|---|---|
| `empresa/PAUSA` existe o `estado.pausa` | `pausa` | ninguno | no (decide el dueño la causa) |
| `fase = borrador` y el brief sin `aprobado_por.firma` | `firmar` (O0, H) | ninguno: la firma del brief va antes de `orq crear` y `orq firmar` no admite etapa O0 `[PENDIENTE: LT-54]` | sí |
| etapa `aprobado` y vigente (hashes de entrada = `hash_salida` aguas arriba) | (sigue a la siguiente) | — | — |
| etapa `obsoleta` o hash de entrada cambiado | `reejecutar` | `orq ejecutar … --modo fixture --fixture DIR` (dry-run/live `[PENDIENTE: SB-9]`), o `ingresar` si N0 o etapa interactiva | no |
| `pendiente` con dependencias sin aprobar | `esperar` | — | no |
| `pendiente`, nivel efectivo N0 | `ingresar` | `orq ingresar … --origen humano` | no |
| `pendiente`, nivel ≥ N1 y etapa en {D1, D2, D6} (conectores solo en sesión interactiva) | `ingresar` con `requiere_sesion_interactiva` | `orq ingresar … --origen sesion_code` (el `--origen` aún no se propaga) | no |
| `pendiente`, nivel ≥ N1, resto de etapas | `ejecutar` | `orq ejecutar … --modo fixture --fixture DIR` (la CLI solo corre fixture; el Maker real con `agentes.runner` es `[PENDIENTE: SB-9]`) | no |
| `en_progreso` | `esperar` | `orq estado --oferta OF` | no |
| `en_QA` con `gate_pendiente` y gate H | `firmar` | `orq firmar … --etapa E --hash-objetivo <hash_salida> --clave-privada <RUTA_DE_TU_CLAVE_PRIVADA>` (luego repetir el `ingresar`/`ejecutar`) | **sí** |
| `en_QA` con `gate_pendiente` y gate S | `firmar` (revisión por excepción) | ídem | no (con PASS limpio el motor aprueba) |
| `en_QA` sin gate pendiente | `esperar` | `orq estado` | no |
| `bloqueado` | `resolver_bloqueo` | `orq estado` | no |
| `escalado` | `orden_humana` | `orq firmar … --etapa E --hash-objetivo … --clave-privada <RUTA…>` tras leer `qa/` y el veto de X1 | sí |
| D1-D7 aprobadas, `fase = en_construccion` | `esperar` (preflight, sello de X1, infra VERDE, compra real mínima) | `orq estado` | no |
| D1-D7 aprobadas, `fase = listo_para_activar` | `activar` (gate efectivo **H** por `acciones_gate_humano`, hasta que el dueño decida D-02) | antes `orq firmar --accion activar_campana --hash-objetivo <hash_config> --clave-privada <RUTA…>`; luego `orq activar … --live` con `object_ids` y `hash_config` de `07-campana/` (**`--live` no está en la CLI** `[PENDIENTE: B5]`) | **sí** |
| cualquier otra fase (`en_test`, `pausada`, `validada`…) | `operacion` | `orq estado`; D8/D9/D10 según su skill (`reanudar` no está en la CLI) | según fase |

**Gate efectivo** de una etapa = el más estricto entre `gates.json[etapa:E][nivel efectivo]` y el `gate` guardado en `estado.json`; nivel efectivo = el menor entre oferta, etapa y `autonomia.yaml`. En M1, si el gate saldría S o A, se avisa que es **H si es el primer lanzamiento en el país o idioma** (`acciones_gate_humano`). Las excepciones que fuerzan H en cualquier nivel (candidato amarillo-b, primer idioma de un macro-nicho, nombre de marca nuevo, precio fuera de rango, dominio o legales nuevos) **no se calculan**: se avisan.

## 3. Cómo redactar cada acción
- **`firmar`**: qué se aprueba en una frase, hash corto, ruta del QA, **qué pasa si dices no** (vuelve al Maker, ronda < `parametros.orquestador.max_rondas_qa`), y que firmar es en **su terminal** con su clave (`--hash-objetivo` y `--clave-privada` son obligatorios; la ruta de la clave la pone él, nunca en un chat ni en el repositorio).
- **`ingresar`**: qué carpeta preparar, validación local previa (`scripts.validar_esquemas`), ficha de ingreso y entrada en `Pulido` (`o0-orquestador-portafolio/references/metodo-manual-y-ingresar.md`).
- **`ejecutar`**: hoy solo `--modo fixture --fixture DIR` (rondas grabadas); el dry-run y el live con Maker real son `[PENDIENTE: SB-9]`; qué entradas consume (hashes); costo esperado contra `limites.max_budget_por_corrida_agente`; que el motor aplica límites y PAUSA.
- **`activar`**: lista de verificación previa (preflight verde, sello de X1 vigente, compra real mínima, `object_ids`, `hash_config`), recuerda que **es la única acción que gasta**, que el `guard` revalida 7 pasos y que exige **tu orden firmada vigente**; pon `[PENDIENTE: B5]` porque la CLI rechaza `--live`; y sin `--live` el comando solo simula (no lo ofrezcas como alternativa).
- **`pausa`**: causa, qué quedó pausado, qué **no** se detiene (entrega del producto pagado y correos transaccionales), quién levanta.

## 4. Relación con el `proximo_paso` del panel
La salida `--json` de `proximo_paso.py` (`accion, etapa, gate, nivel_efectivo, espera_firma, motivo, falta[], comando, avisos[]`) **no es idéntica** a la forma única del panel, `{motor_disponible, tipo, etapa, texto, comando}` (`dashboard/api_ofertas.py`). La correspondencia `accion` → `tipo` y el pedido de documentarla en `dashboard/CONTRATO.md` están en `o0-orquestador-portafolio/references/dependencias.md` §F.1.
