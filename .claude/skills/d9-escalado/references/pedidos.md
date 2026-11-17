# Qué hace la skill mientras cada pedido siga abierto

> La lista formal de pedidos (qué, a quién, archivo:línea, texto propuesto) está en `../PEDIDOS.md`. Esta página dice **cómo se comporta D9 hoy** frente a cada uno y qué desbloquea. Regla común: **lo que falta se declara, no se simula ni se rellena** (fail-closed).

| Pedido | A | Mientras no esté, la skill… | Desbloquea |
|---|---|---|---|
| P-01 paso > 100 % y horas fraccionales | S-A | no propone ×3/×5 ni escalera de 30 min; máximo ×2 | etapas 2-3 |
| P-02 claves nuevas de `escalado.*` en `parametros.yaml` | S-A | `dictamen` responde `PARAMETRO_FALTANTE` (5): **no propone ninguna suba ni graduación** | todo SUBIR/GRADUAR |
| P-03 grupo `mercados.*` (J5) | S-A | `replica` responde `PARAMETRO_FALTANTE` (5) | REPLICAR |
| P-04 `gates.json` (J2, `reducir`, `graduar`) y `limites.acciones_gate_humano` | S-A | usa el gate más estricto (H) y lo declara; `reducir` se trata como la suba (H) | ejecución sin clic dentro de frenos |
| P-05 `estrategia_puja`/`cost_cap` y `locales_meta` en `campana.schema` | S-A (+P-13) | la ESCALA se propone sin tope de costo y sin filtro de idioma; lo anota en `no_ejecutable_hasta` | CBO con cost cap; hijas fieles al idioma |
| P-06 esquemas: propuesta, `lanzamiento_idioma`, `variante_de`, banco de creativos | S-A | la propuesta valida solo su `orden_presupuesto`; el tablero se declara «sin código» | tablero y familia |
| P-07 reescribir `departamentos/10-escalado.md` a J1-J5 | S-A | sigue esta skill y deja `conflictos-con-la-spec-vieja.md` | una sola verdad |
| P-08 `stop_loss_escala` y lectura de «300 US$/día» | dueño / S-A | `stop_loss_escala` en `null` = nada escala; aplica la lectura del código | `escalar` |
| P-09 4.º nicho en `macro_nichos_permitidos` | S-A | `macro_nicho_permitido` falso para hobbies | ofertas del 4.º nicho |
| P-10 `engine/escala.py` (E0, ganador, señales, paso, reducir, caja) | S-B | usa `scripts/escala_lectura.py` (provisional, solo lectura) y las banderas de E0 las reúne quien arma la entrada citando fuente | dictamen oficial |
| P-11 `guard`/`subir_presupuesto`: verificar % de paso y gate | S-B | declara que el guard no verifica el %; el dictamen sí | defensa en profundidad |
| P-12 vigilante continuo de pérdida y gasto | S-B | informa que −3.000 se comprueba solo al activar o subir | pausa real a −3.000 |
| P-13 `meta/payloads.py`: cost cap y `locales_meta`, `ajustar_costo` | S-B | ver P-05 | ídem |
| P-14 auditor de acierto (`decisiones.jsonl` con `resultado`) | S-B | etapa 0; el informe pone «acierto: sin dato» | etapas 1-3 |
| P-15 bug `engine/d8.py:335` (`session_id` → `checkout_session_id`) | S-B | no puede contar con `veredicto` VALIDADA sobre la base real; usa lo que haya y lo declara | VALIDADA real |
| P-16 medición horaria y `presupuesto_previo_gastado_pct` | S-B | la entrada la arma quien la cita; sin dato, `[SIN DATO]` y no sube | señal H-01 por código |
| P-17 `engine.orq`: ruta de ingreso de la propuesta | S-B | la propuesta queda en `09-escalado/` para el dueño | tubería |
| P-18 `engine.orq` familia/hija, P26 en `meta.preflight` | S-B | la hija es un borrador para O0 | REPLICAR de punta a punta |

**Dependencias de otras sesiones S-C** (no son pedidos a S-A/S-B): script del tablero `scripts/lanzamiento_idioma.py` (B3-18), ejecutor de las capas 4-5 del QA lingüístico (B3-22), skills D8 y `d6` modo tanda, `empresa/mercados/` y glosarios por locale (M1). Mientras no existan, las tarjetas correspondientes quedan `pendiente`.

**Para pasar de 0.1 a 1.0.0** (checklist en `CHANGELOG.md`): corrida manual del dueño con una oferta real y chica en la pestaña Code, retro de 30-45 min, DoD firmado por el dueño, evals en otro nicho e idioma, y los pedidos P-02, P-04, P-10 y P-11 resueltos o aceptados por escrito.
