# Contradicciones abiertas y límites de ejecución (documentadas, **no resueltas** aquí)

Fuente: `docs/_historial/auditoria-pedidos-primera-sesion.md` (§4 W3/W6, §5 C-04), `docs/_historial/ct3-backlog.md` (H-1, A-05, D-02) y `docs/_historial/ingesta-skills-cierre.md` (O0-C04, O0-C04b, O0-C06, SC-18). Esta skill **no edita** `limites.yaml`, `gates.json` ni la spec de D1: aplica la regla más estricta y lo dice.

## 1. C-04 — gate efectivo = H hasta que el dueño decida D-02
- **Dónde:** `empresa/limites.yaml` (`acciones_gate_humano` contiene `activar_campana` y `lanzamiento_pais_idioma_nuevo`) frente a `contratos/gates.json` (`accion:activar_campana`: N3 y N4 = S); `docs/_historial/w3-reconciliacion.md` §6 K-02 (C-W3-02 de la spec).
- **Hecho verificado (`ct3-backlog.md` H-1):** las seis acciones mínimas **no se pueden quitar** de `acciones_gate_humano`, ni con firma: lo impiden el esquema (`limites.schema.json`, `contains`), el validador (`ACCIONES_GATE_MINIMAS` en `scripts/validar_esquemas.py`) y `engine.guard`, que exige orden firmada para ellas en todo nivel. Lo que decían las skills («quita la acción con firma») **era inexacto**. La «S» de `gates.json` describe el máximo que permitiría la tabla, no lo que se aplica.
- **Efecto:** el gate **efectivo** es H en todo nivel (también en N3/N4) y **el botón «Lanzar nueva oferta» de punta a punta termina en `listo_para_activar`** esperando la firma del dueño (con `ventana_veto_min` solo relevante si algún día se acepta la S en N4).
- **Qué hace la skill:** muestra `activar` como acción H que espera firma y avisa «C-04 abierta: gate efectivo H hasta que el dueño decida D-02». No sugiere quitar la acción ni firmar una regla.
- **Decisión que falta (dueño, D-02/K-02):** (a) cambio estructural de `ACCIONES_GATE_MINIMAS` (validador), del esquema y de la lógica de gate por nivel de `engine.guard`, con firma del dueño en `limites` (cambio MAJOR si ya hay `limites` sellado); o (b) `gates.json` en **H** en N3/N4 para `activar_campana` y `lanzamiento_pais_idioma_nuevo`, y N4 = «armar todo y esperar la firma». Cualquiera cierra la contradicción; hoy ninguna está hecha.

## 2. C-06 — D1 «avanza a las 24 h» en N3: **RESUELTA**
`departamentos/02-descubrimiento.md` ya es v1.1 y dice N0-N3 = H, «el dueño elige siempre; no hay avance tácito» (N4 = S), igual que `contratos/gates.json` (`etapa:D1`) y el backbone §3.2. La skill sigue `gates.json`; `proximo_paso.py` nunca avanza D1 por silencio. Ya no es una contradicción abierta.

## 3. Pasos que exigen sesión interactiva con conectores
(`docs/09` H2, backbone 5.5, auditoría W6; decisión del dueño O0-C07 pendiente.) Los conectores de claude.ai existen solo en la sesión **interactiva** del dueño (pestaña Code); un `claude -p` desatendido usa clave de API propia y **no carga ningún conector MCP**. Por eso los agentes `o0-maker` y `o0-qa` no usan web ni MCP.

| Etapa | Qué necesita | Hasta N2 | Desde N3 |
|---|---|---|---|
| D1 (lectura de la Biblioteca de Anuncios; fuentes con muro) | `ads_library_search`; navegador asistido con perfil dedicado | en Code, entra con `orq ingresar` (`--origen sesion_code`, que la CLI aún no propaga) | scripts con APIs oficiales y `fuentes_permitidas` `[PENDIENTE]` |
| D2 (inteligencia competitiva) | `ads_library_search` (8 campos, sin texto ni gasto) | ídem | `[PENDIENTE]` |
| D6 (creativos) | Higgsfield (`generate_*`, `ads_studio_*`): cotizar y aprobar créditos | ídem | `gen_creativo.py` `[PENDIENTE]` |

Los demás pasos (M1, D3, D4, D5 en prueba, D7 en `PAUSED`) los corre el motor con el runner cuando esté integrado: hoy `orq ejecutar` solo corre `--modo fixture --fixture DIR` (`[PENDIENTE: SB-9]`); D5/D7 usan scripts propios. **Efecto en `proximo_paso.py`:** para D1/D2/D6 con nivel ≥ N1 sugiere `ingresar` y marca `requiere_sesion_interactiva`; desde N3 avisa que la alternativa por API es `[PENDIENTE]`. Los servicios deterministas de producción (motor, Workers) no están alcanzados por esta restricción.

## 4. Otras contradicciones y pendientes que afectan a O0
Ver `o0-orquestador-portafolio/references/dependencias.md` §B: `variante_de`/`radar` ausentes en los esquemas, esquema `propuesta` inexistente, firma del brief antes de que exista la oferta (LT-54), el brief del `_ejemplo` frente al check 2 (÷ factor de techo teórico), `limites.boton_max_lanzamientos_dia` sin crear. **Resueltas:** cuándo nace el `oferta_id` (en `orq crear`, tras el gate H), `departamentos/02` en v1 (falso: es v1.1), `nivel_riesgo.py` pendiente (existe), claves de nichos de `limites` (están en 1.3.0).
