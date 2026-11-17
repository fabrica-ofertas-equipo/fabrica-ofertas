# Cadena de etapas, gates y máquina de estados

Fuentes que mandan (en este orden): `contratos/gates.json` (v1.1.0), `contratos/estado.schema.json`, `docs/contratos.md` §2-§3, `docs/06-bases-del-testeo.md` §5, código del motor cuando exista. **Esta copia es informativa** (verificada el 2026-11-06): `o0-lanzar-oferta/scripts/proximo_paso.py` lee el JSON real; si difiere de esta tabla, manda el JSON.

## 1. Cadena y dependencias

`D1 → M1 → D2 → D3 → D4 → D5 → D6 → D7` y luego `orq activar` (acción aparte) → `D8` (ciclo diario) → `D9` (escala) · `D10` (postcompra, depende de D4 y D5). Transversales: F1 finanzas, F2 panel (origen del botón), X1 compliance (**veto**, sella por hash), X2 memoria. **Modelado** (skill `modelado-oferta`): no es etapa del motor (sin `etapa:modelado` en `gates.json` ni en `estado.json`); su plan de mejora lo aprueba el dueño en `ofertas/<id>/modelado/plan_mejora.json` y se verá en el gate H de D1 (plan v0) y en el de D3 (tarjeta antes/después) `[PENDIENTE: S-A: etapa o gate propio]`.

| Etapa | Depende de | Salida sellada (hash de `hash_salida`) | Carpeta |
|---|---|---|---|
| D1 | — | `candidatos.json` | `01-descubrimiento/` |
| M1 | D1 | `mercado.json` | raíz de la oferta |
| D2 | D1, M1 | `validacion.json` | `02-validacion/` |
| D3 | D2 | `oferta.json` + `economia.json` | `03-oferta/` |
| D4 | D3 | `producto.json` | `04-producto/` |
| D5 | D3, D4 | `assets.json` + `checkout.json` + `tracking.json` | `05-landing/` |
| D6 | D3, D5 | `paquete.json` | `06-creativos/` |
| D7 | D5, D6 | `campana.json` | `07-campana/` |
| D8 · D9 · D10 | D7 · D8 · D4+D5 | ver sus skills | `08-` · `09-` · `10-` |

Una etapa aprobada exige `entradas[dep] == hash_salida` de cada dependencia; si no, está **obsoleta** (`obsoleta=true`, vuelve a `pendiente`, se conserva la versión previa; una campaña activa se **pausa**).

## 2. Tabla de gates (A automático · S semi, el humano audita por excepción · H humano obligatorio)

| Etapa o acción | N0 | N1 | N2 | N3 | N4 |
|---|---|---|---|---|---|
| `etapa:O0` brief firmado | H | H | H | H | S (clic autenticado; conflicto C03) |
| `etapa:M1` | H | H | H | S | S |
| `etapa:D1` elegir candidato | H | H | H | H | S |
| `etapa:D2` · `D4` · `D6` | H | H | S | S | A |
| `etapa:D3` · `D5` · `D7` (armado) · `D9` (plan) | H | H | H | S | S |
| `etapa:D8` · `D10` | H | H | A | A | A |
| `accion:activar_campana` | H | H | H | S (solo regla preaprobada) | S |
| `accion:reactivar_tras_pausa` | H | H | H | H | H |
| `accion:subir_presupuesto_d9` | H | H | H | A | A |
| `accion:subir_presupuesto_sobre_tope` · `cambiar_limites` · `asignar_capital` · `confirmar_validada` · `extender_test` · `compra_real_minima` · `ascender_nivel` · `reabrir_fallida` · `cambiar_skill` · `disputa` | H | H | H | H | H |
| `accion:lanzamiento_pais_idioma_nuevo` | H | H | H | S | S |
| `accion:cerrar_oferta` | H | H | H | S | S |
| `accion:retirar_oferta` | H | H | S | S | S |

**Gate efectivo** = el más estricto entre: (a) `gates.json` evaluado con el **menor** nivel entre `estado.nivel`, `estado.etapas.<E>.nivel` y `autonomia.yaml`; (b) `limites.acciones_gate_humano` (siempre contiene `activar_campana`, `reactivar_tras_pausa`, `subir_presupuesto_sobre_tope`, `cambiar_limites`, `cambiar_entidad_stripe`, `lanzamiento_pais_idioma_nuevo`). Consecuencia: las seis acciones mínimas **no se pueden quitar** de la lista (ni con firma: esquema, `validar_esquemas.py` y `engine.guard`), así que activar una campaña (D7) y el primer lanzamiento en país o idioma nuevo (M1) son H también en N3 y N4; la «S» de la tabla describe el máximo que permitiría `gates.json`, no lo que el guard aplica (exige orden firmada). Ni el veto de X1 ni el sello por hash se relajan con el nivel. **C-04 = gate efectivo H hasta que el dueño decida D-02** (abierta, no resuelta aquí): `gates.json` pone `activar_campana` en S en N3/N4 pero `limites.acciones_gate_humano` la fija H; manda lo más estricto, así que el botón de punta a punta termina en `listo_para_activar` esperando tu firma (`dependencias.md` §B2). Salidas posibles del dueño: (a) cambio estructural de validador, esquema y guard, o (b) `gates.json` en H en N3/N4 y N4 = «armar todo y esperar la firma». **C-06 (D1 «a las 24 h» en N3): resuelta**, la spec de D1 es v1.1 y dice N0-N3 = H sin avance tácito.

## 3. Excepciones que fuerzan H en cualquier nivel (nota 25 §13)

Candidato **AMARILLO-B** o ROJO reencuadrado · primer B de un macro-nicho · primer idioma de un macro-nicho · bandera L1/L2 abierta · primer rechazo de una hoja · nombre de producto, método o marca nuevo (D3) · nicho nuevo o precio fuera de rango · dominio o legales nuevos. El esquema de `candidatos` solo distingue `verde|amarillo|rojo` (el campo `subnivel` lo pide CT-3, LT-04); la variante A/B la calcula `python -m scripts.nivel_riesgo` (existe) desde los ejes P/C/E/N, y si el snapshot no trae `ejes_codigo` se deriva de los colores: **≥ 2 ejes amarillos = B** (gate H) `[SUPUESTO]`. Ya no rige «todo amarillo = B».

## 4. Máquina de estados (solo escribe el motor)

**Etapa** (`estado_etapa`): `pendiente`, `en_progreso`, `en_QA`, `aprobado`, `bloqueado`, `escalado`. «Gate pendiente» es el booleano `gate_pendiente` dentro de `en_QA`, no un estado.

| De → a | Condición | Quién |
|---|---|---|
| pendiente → en_progreso | dependencias aprobadas y vigentes, sin `PAUSA`, límites OK | motor |
| en_progreso → en_QA | salida válida (esquema + invariantes) | motor |
| en_progreso → bloqueado | falta input o credencial, timeout, API caída | motor |
| en_QA → aprobado | PASS o PASS_CON_NOTAS y gate: A automático; S automático si PASS (humano con notas o por muestreo); H firma del dueño | motor / humano |
| en_QA → en_progreso | FAIL o MAYOR abierto y `ronda_qa` < `parametros.orquestador.max_rondas_qa` | motor |
| en_QA → escalado | ronda máxima con BLOQ/MAYOR, `ESCALAR` o veto de X1 | motor |
| bloqueado → en_progreso | causa resuelta | motor / humano |
| escalado → en_progreso / aprobado | orden humana firmada | humano |
| aprobado → pendiente | una entrada cambió (`obsoleta=true`) | motor |

**Fase de la oferta** (`fase`): `borrador → en_construccion` (brief firmado y primera etapa en progreso) `→ listo_para_activar` (D1-D7 aprobadas y vigentes, `campana.estado = aprobada`, sello de X1 vigente, infra VERDE en modo vivo con < 6 h) `→ en_test` (**solo** `orq activar`: gate + `guard` + relectura de Meta) `→ {validada | fallida | inconclusa}`; `en_test → pausada` automático (PAUSA, guardarraíl de D8, `senal_pausa`, deriva de X1, watchdog: **pausar nunca espera a un humano**); `pausada → en_test` solo con `reactivar_tras_pausa` (H siempre); `inconclusa → en_test` una vez (`extender_test`, H); `validada` solo con `accion:confirmar_validada` (H) sobre cohorte **madura** (`espera_madurez{activa, hasta}`); `fallida → en_construccion` con `reabrir_fallida`; `validada → escalando` (D9); cualquiera → `retirada` (decisión del dueño; única fase final). «Oferta validada» = backbone 5.9 (Stripe, neta de reembolsos, cohorte madura, CPA ≤ objetivo), jamás el conteo de Meta.

## 5. Después de D7

1. Preflight y sello de X1 vigentes, compra real mínima (`accion:compra_real_minima`, H) → el motor marca `listo_para_activar`.
2. `orq activar` (con `object_ids` exactos y `hash_config` de `07-campana/`): lo ejecuta código con `guard` de 7 pasos (entorno, PAUSA, infra, límites, topes agregados, credenciales, orden firmada vigente), **nunca un LLM**.
3. D8 lee cada ciclo (`orq ciclo-d8`), `veredicto`, y la cartera semanal (modo B) recomienda; D9 propone, el dueño firma. Cierre: `orq cerrar` (`accion:cerrar_oferta`): el Maker de cierre redacta `08-operacion/postmortem.json` (`retraso_clic_compra` obligatorio), el dueño confirma y se anexa una línea a `empresa/memoria/eventos.jsonl` para X2.

## 6. Idempotencia y reanudación

`idempotency_key = sha256(oferta_id + etapa + hashes de entradas + skill_version + ronda_qa + hash de hallazgos previos)`: misma clave ⇒ se reutiliza la salida (sin ronda ni hallazgos, la ronda 2 reutilizaría la rechazada). *Write-ahead* de efectos externos: se guardan los IDs de Meta (`cid`, `asid`, `adid`); al reanudar se busca por ID y, sin ID, por el prefijo `{oferta_id}_{fase}_`. Nada depende de fechas y toda unión usa IDs. Proceso muerto ⇒ se reanuda por idempotencia **sin duplicar** (no repitas una etapa a mano «por si acaso»: pide `orq estado`).

## 7. Ascenso de nivel (lo recomienda el motor, lo firma el dueño con `orq nivel`; `[HIPÓTESIS]`)

**N0→N1** skill con DoD y evals en verde · **N1→N2** ≥ 5 corridas, sin edición ≥ 70 %, QA calibrado · **N2→N3** ≥ 3 ofertas, sin edición ≥ 85 %, escape ≤ 10 %, 0 incidentes de gasto, 0 falsos verdes en la suite de frontera · **N3→N4** ≥ 5 ofertas, sin edición ≥ 90 %, escape ≤ 5 %, 60 días sin incidente, Meta vs Stripe ≤ 5 %, ≥ 1 oferta validada (5.9), propuestas sin cambios ≥ 80 % durante 6 semanas. Son hipótesis del spec: se calibran con datos propios. El descenso es automático (`barreras-y-frenos.md`).
