# 05 — Registro de riesgos y catálogo de guardarraíles

> Fecha: 2026-11-06. Rol: red team y gestión de riesgos operativos, regulatorios y de plataformas. Subordinado a `docs/_backbone.md` (v2.2). **Esto es un mapa de riesgos y un diseño de controles, no asesoría legal, fiscal ni financiera** (§7).
> Insumos leídos: backbone completo; sección 8 de las 17 especificaciones (`departamentos/00`-`16`); `docs/contratos.md` (índice y reconciliación, no cada contrato); `docs/06`-`09` (bases, puesta en marcha, protocolo estadístico, runtime) y `docs/10-runbook-testeo.md` (índice); notas 03, 04, 05, 07h, 13, 16, 21, 22d, 22f y 25 (§2, §3.3, §9-§11); código existente en `engine/`, `decision/`, `meta/`, `datos/`, `tracking/workers/`, `empresa/*.yaml`.
> Etiquetas: `[HIPÓTESIS]` número a calibrar; `[VERIFICAR]` hecho externo sin confirmar; `[NUEVO]` aporte de este documento; `[CREADORES, C]` cifra autodeclarada por vendedores de cursos; `[DUEÑO]` decisión del dueño.

---

## 0. Estado, límites de esta lectura y conflictos resueltos

**Qué existe hoy (2026-11-06), porque un guardarraíl diseñado no protege nada hasta que está construido y probado:**

| Estado | Componentes |
|---|---|
| **Construido** (con pruebas) | `engine/{errores,comun,limites,parametros,guard,registro,transporte,factibilidad}.py` (cargador de límites con sello, `comprobar_live`, topes, ritmo, agregados, economía única); `decision/{estadistica,presupuesto,reglas,simulacion}.py`; `meta/{cliente,crear,monedas,nombres,payloads}.py`; `datos/{db,etl_meta,etl_stripe}.py`; Workers de `tracking/` (`crear-sesion`, `eventos`, `capi`, `webhook-stripe`); contratos JSON Schema y `scripts/validar_esquemas.py` |
| **Solo diseñado (README o ausente)** | `agentes/` (runner y **hooks**), `compliance/` (X1, `nivel_riesgo.py`, sellos), `landing/`, `postcompra/`, `dashboard/`, `infra/` (**watchdog**, **`scripts/pausar.py`**, preflight), CMP, correo transaccional |
| **No hecho (ola −1, solo el dueño)** | `git init` con línea base y `.claude/settings.json` de piso (`deny`, hooks). Hoy **no existe** `.claude/settings.json` |
| **Valores sin fijar** | `empresa/limites.yaml` está con todos los topes monetarios en `null`: es el único freno real y es **fail-closed** (ninguna operación con gasto pasa). `perdida_max_test_por_oferta` fue diferida por el dueño; todo umbral en dinero de este documento es paramétrico |

**Hallazgo central sobre guardarraíles:** la instalación actual es Claude Code 2.1.205 y `docs/09` §1 (H1) documenta que le faltan `onFailure` en hooks, `--permission-prompts` y los bloqueos fuera del directorio de trabajo que supone el diseño; en la pestaña Code del dueño están cargados los conectores de escritura de Meta (`ads_activate_entity`, `ads_update_entity`, `ads_create_*`) sin hook que los filtre. **Mientras no existan `agentes/hooks/` y la sonda de hooks, la protección en N0 es humana (el dueño no aprueba ni invoca escrituras) y `limites.yaml` en `null`.** Esto es correcto para N0 y debe ser un bloqueante de subida a N1 con gasto real.

**Faltantes de entrada:** `d1-v2-interfaces.md`, `d1-v2-critica-redteam.md` y el piloto `d1-v2-piloto/` **no existen todavía**; el radar (R10, R14, R18) se apoya en las notas 18a-21, la especificación de D1 (§8, §17), la nota 19 y `coordinacion-sesiones.md`; revisarlo cuando aparezcan.

**Conflictos entre fuentes, resueltos (manda el contrato o el código; la nota más reciente sobre la anterior):**

| # | Conflicto | Resolución |
|---|---|---|
| K1 | Alertas de disputas 0,3 %/0,6 % y reembolsos 10 % (03 §5.2, 16 §6) vs. 0,20/0,35/0,50 % y 8/12/15 % (22d §7.3, 25 §9; `parametros.salud_operativa`) | Manda 25 §9 y `parametros.yaml`. Los casos absolutos **2/3/5** no se relajan: con ~400 pagos Visa al mes, 5 casos son 1,25 % |
| K2 | «Abandonar con N compras de M clics» (tabla 16 §6 Nivel 2) vs. regla bayesiana por celda (`decision/reglas.py`, docs/08 §4) | Manda el código. La tabla de 16 queda como contraste manual en el post-mortem |
| K3 | «MCP hasta N2» (backbone 5.5) vs. runner desatendido sin conectores ni en N0-N2 (docs/09 H2: con `ANTHROPIC_API_KEY` no cargan) | Manda docs/09: el MCP vale solo en la sesión interactiva del dueño; el runner usa scripts. Es un guardarraíl gratis |
| K4 | Prepago de Meta «≤ 3 días» (F1) vs. «sin prepago» (preflight M-03 de D0) | Manda M-03: el prepago anula la capa 3 del kill switch |

---

## 1. Premortem: top 25 riesgos

**Ejercicio.** Mayo de 2027, el proyecto fracasó. Cuatro historias plausibles: (a) en Q4 dos anuncios amarillos son rechazados, Meta restringe el portfolio y Stripe retiene pagos 120 días: sin anuncios ni caja; (b) Meta mostraba ROAS 2 pero Stripe, neto de IVA, comisión, reembolsos y tarifa, daba 0,8; (c) un agente obedeció un comentario, o un hook falló abierto, y se gastó algo que nadie aprobó; (d) el radar alimentó candidatos con señales infladas o recolectadas contra los términos de las plataformas, y el reclamo escaló a las cuentas.

**Escalas.** Probabilidad P (1: < 5 %; 2: 5-15 %; 3: 15-35 %; 4: 35-60 %; 5: > 60 %) en los primeros 6 meses con gasto real `[HIPÓTESIS]`. Impacto I (1: molestia; 2: pierde un test; 3: pierde una oferta o semanas; 4: capital relevante o una cuenta crítica; 5: ambas cuentas, la LLC o sanción). Severidad = P×I. **≥ 16 crítico; 12-15 alto; ≤ 11 medio.** Orden: severidad, luego impacto. Los `G-nn` remiten al catálogo (§2).

| # | Riesgo (cómo falla) | P×I | Señal temprana | Mitigación | Guardarraíl | Resp. |
|---|---|---|---|---|---|---|
| R01 | **Meta restringe o inhabilita la cuenta única** (portfolio, Página y perfil personal se contagian; el prepago puede perderse). Hay una cuenta ya deshabilitada por «actividad inusual» (00 §3); creadores reportan bloqueos sin recuperación `[CREADORES, C]` | 4×5 = **20** | «Necesita atención», rechazo de producto, advertencias; 2 rechazos en 7 días | Pausa de la hoja al primer rechazo de producto; activos no compartidos; sin prepago; cuota amarilla y límites de software (kill switch de tres capas); Riesgo residual aceptado por el dueño (decisión 15): sin gestor de contraseñas, llaves físicas ni segundo administrador; los frenos de software no cambian; **jamás** cuentas nuevas, dominios espejo ni re-subir texto rechazado; apela solo el dueño | G-04, G-10, G-12, G-14 | X1 / dueño |
| R02 | **Falso verde:** una promesa de salud o ingresos, un encuadre que afirma un atributo del espectador, un testimonio, un contador o una escasez falsos pasan el clasificador y X1 (en las 230 ideas de prueba un filtro por tema habría bloqueado 71 legítimas y dejado pasar 79 problemáticas; `hwr-resumen-para-el-dueno.md`) | 4×4 = **16** | Rechazo de una pieza «aprobable»; caso nuevo en la suite; sobre-bloqueo > 15 % | Riesgo por candidato (P, C, E, N); ningún LLM baja un nivel que el lint subió; ángulos seguros; cifras de clientes generadas por script (X1-P08); reseñas solo con `compra_id` | G-12, G-13, G-10 | X1 |
| R03 | **IVA/OSS/UK VAT omitido desde la primera venta** (vendedor no-UE: OSS no-Unión sin umbral; UK desde la primera venta). El 18-23 % del bruto es deuda tributaria, no ingreso; la tasa del PDF (5 % o 23 %/22 %) es incierta (16 H5) | 4×4 = **16** | Ventas con `amount_tax` sin registro; pasivo ≠ `amount_tax`; `modelo_cobro` nulo | `modelo_cobro` nulo bloquea UE/UK; `paises_permitidos`; Stripe Tax; pasivo por país en F1; contador **antes** de la primera campaña UE | G-18 | Dueño / F1 |
| R04 | **Disputas y reembolsos suben con tráfico frío en nichos vigilados** y llegan a los 30-120 días: pausar el gasto no detiene el contador. VAMP no conforme = ≥ 0,5 % y ≥ 5 casos (22d) | 4×4 = **16** | `d` ≥ 0,20 % o 2 casos; `r` ≥ 8 % en cohorte madura; EFW | Escalones 25 §9; un escalón más bajo en amarillos; garantía incondicional visible, reembolso en un clic, descriptor claro; fondo de reembolsos 15 %/8 % | G-15, G-17 | F1 / D10 |
| R05 | **Stripe retiene, reserva o cierra** (pausa de 120 días bajo Política de Riesgo Inaceptable; cobrar productos no declarados es uso prohibido; 7-14 días al primer pago) | 3×5 = **15** | Aviso de revisión; payout > 14 d; `risk_reserved` | `perfil_stripe.yaml` fiel al catálogo; carril B (MoR) solo para verdes y probado con 5-10 ventas por trimestre; la caja descuenta reservas; no cuentas alternativas «para diversificar» | G-16, G-15 | Dueño / F1 |
| R06 | **Guardarraíl de papel:** hook que falla abierto (salida distinta de 0 o 2), `deny` esquivado por `Bash`, `-p`/`--bare` sin hooks, `.claude/settings.json` roto ignorado en silencio, MCP no cubierto, Claude Code 2.1.205 sin `onFailure` | 3×5 = **15** | Sonda de hooks < 100 %; `claude doctor` con `Invalid settings`; hash del árbol distinto | `exit 2` ante cualquier excepción; plazo interno < `timeout`; permisos del SO; versión mínima en preflight; sonda tras cada actualización | G-06, G-07, G-08 | D0 / QA |
| R07 | **El modelo no es rentable.** Con costos completos el caso base de PL/IT pierde ~47-55 USD por cada 100 gastados y necesita conversión de 3,8-4,5 % frente a 1,6-2,3 % plausible; solo el optimista gana (16 §2.3, `[HIPÓTESIS]`). Elegir mercado por impresión (Polonia) agrava | 5×3 = **15** | CPA / `cpa_be` > 1,5 en ≥ 1.000 clics; ROAS neto Stripe < 1 | `engine.factibilidad` única con neto completo; bump desde el día 1; presupuestos **iguales** por mercado; criterios de abandono (§4) | G-21, G-22, G-32 | CEO / F1 |
| R08 | **Medición ciega en UE/UK:** sin consentimiento el píxel no ve al visitante (CMP: 55-72 % de aceptación según proveedores, confianza C); BLIK no regresa al navegador; «anuncios menos personalizados»; Meta degrada su optimización y D8 decide a ciegas | 5×3 = **15** | Razón Meta÷Stripe fuera de 0,8-1,3; cobertura de `adid` < 95 % | CMP con rechazo equivalente; CAPI condicionada al consentimiento; Stripe es la verdad; modo ciego G4; optimizar por evento más frecuente | G-20 | D5 / F2 |
| R09 | **Gasto descontrolado y pérdida acumulada:** 1,75× del presupuesto diario, tarifa de ubicación fuera de «Importe gastado», unidad de moneda (×100), conector sin hook, campañas nuevas para esquivar `paso_max`, bucles de agentes y créditos de IA | 3×4 = **12** | Gasto > `gasto_alarma_pct`; factura ≠ gasto leído; `costos.jsonl` crece | Techos en `limites.yaml` (`null` = nada gasta); presupuesto = tope ÷ 1,75; `spend_cap` en Meta; tarjeta con tope; `max_budget_por_corrida_agente`; cotizar antes de generar | G-01, G-02, G-03 | Motor / dueño |
| R10 | **Radar: recolección viola términos o RGPD y el reclamo escala a las cuentas.** Casi todas las plataformas prohíben el raspado; DMCA §1201 si se elude una medida técnica; RGPD aplica (art. 3.2); datos de salud, sexualidad o menores son categoría especial (21 §1). **Hecho:** el freno de captura de la Biblioteca web está activo por un HTTP 403 | 3×4 = **12** | `freno.json`; captcha; PII en el banco; fuente roja | Fuentes por color V/A/R; ciego a la identidad; TTL y borrado verificado; **nunca** evadir un bloqueo (reintentar, cambiar IP o perfil); aviso público de investigación y canal de oposición | G-24 | X1 / dueño |
| R11 | **Daño al lector o producto flojo:** dosis, dieta, consejo financiero o de pareja mal aplicado; datos alucinados; unidades mal convertidas (`cucchiaio`/`cucchiaino`, `1,5` vs `1.5`); relleno que un chatbot reproduce | 3×4 = **12** | Reportes; R11 bajo en la rúbrica; afirmación sin fuente o > 14 d | Contenido anclado a fuentes T1 con `afirmaciones.jsonl`; pisos y «cuándo parar»; ayuda verificada del país; retiro a 3 reportes en 30 d; prueba del chatbot | G-29, G-13 | D4 / X1 / D10 |
| R12 | **Secretos filtrados** (clave en chat, repositorio, log, salida de un validador; agente que escribe en rutas protegidas; token del operador copiado en el watchdog) | 3×4 = **12** | Hallazgo de `gitleaks`; patrón `sk_`/`whsec_`/`EAA` en logs | Sin secretos en chats; una credencial por función con mínimo privilegio; redactor en hooks; rotación; firmas asimétricas | G-27, G-08 | Dueño / D0 |
| R13 | **Deriva tras el sello:** Advantage+ o «mejoras» de Meta reescriben copy; la landing cambia (*cloaking* involuntario); anuncio vivo ≠ sellado; aprobación forjada | 3×4 = **12** | Hash vivo ≠ sellado (K03); `copy` del generador ≠ `copies.json` | `meta_enhancements` en `false`; rastreo diario del sitio vivo desde tres países; X1 compara cada creativo vivo con el sellado; firma Ed25519 | G-10, G-11 | X1 / Motor |
| R14 | **Inyección de prompts** en páginas, comentarios, reseñas, títulos de anuncios, UTM, metadata de Stripe o texto del banco; el agente cambia de tarea o llama herramientas no previstas | 4×3 = **12** | Un agente cita instrucciones; herramienta fuera de lista; hit en fixtures hostiles | Contenido externo = dato; agentes de lectura sin escritura ni red; salida validada por esquema fuera del modelo; el LLM del dashboard solo recibe números e IDs | G-23, G-08, G-09 | QA / Motor |
| R15 | **Decidir con ruido:** matar un ganador o escalar un perdedor; «con una venta está validado»; espiar a diario; maldición del ganador entre 5 conjuntos (91 % de P(≥ 1 venta) con conversión de 1 %; 16 §3) | 4×3 = **12** | Pausas revertidas; INCONCLUSO; pausas en A/A | `evaluar_celda` bayesiano; ventana de no decidir 72 h; 6/8/10 USD solo como alerta; INCONCLUSO es un resultado | G-21 | Script / QA |
| R16 | **Desistimiento y consentimiento digital inválidos en UE/UK:** sin casilla separada de renuncia, sin función de desistimiento (Directiva (UE) 2023/2673, art. 11a, desde 2026-06-19 `[VERIFICAR]`; art. 54-bis en Italia; proyecto polaco suspendido al 2026-06-12 `[VERIFICAR]`), garantía mezclada con el derecho legal | 4×3 = **12** | C10/C11; solicitud rechazada; denuncia | Plantillas por país generadas por el sistema; J07 como bloqueante; plazo = máximo legal; chequeos automáticos de X1; el resto queda como riesgo residual aceptado (decisión 14, §7) | G-19, G-18 | X1 / dueño |
| R17 | **Saturación y copia entre creadores:** todos los alumnos buscan lo mismo (kit DSA en Italia ya tiene imitadores); *herding*; «modelar» se vuelve clonar; el mismo ángulo vuelve en otro idioma | 4×3 = **12** | Similitud ≥ 8 palabras; mecanismo igual al del líder; `entrantes_30d` alto | Filtro MU/EU frente a la competencia; K02 multilingüe; penalizar lo que «el cerebro de otros» también encuentra; presupuesto de exploración | G-28, G-31, G-32 | D2 / M1 / X2 |
| R18 | **Radar: señal falsa, sesgada o sin disposición de pago, y Goodhart.** Foros con astroturfing o bots; sesgo de plataforma e idioma (Reddit es anglo y masculino-técnico; Quora «preguntas SEO»); anuncios = oferta, no demanda; dolor ≠ pago; fichas MU/EU redactadas para pasar el filtro; el chatbot gratuito como sustituto | 4×3 = **12** | `evidencia_vencida_pct`; un macro bajo la cuota; fichas con un «cómo» genérico | Cuatro familias de señales (dolor, pago, demanda, oferta persistente) y mínimo de independencia; evidencia por `locale`; QA ciego de la ficha; prueba de un prompt de una línea; contramuestra | G-28, G-23 | D1 / QA |
| R19 | **QA de sello de goma, deriva de skills y dueño que aprueba sin leer** (Goodhart sobre el gusto del dueño; evals circulares; aprobaciones < 30 s) | 4×3 = **12** | QA con 0 hallazgos; `pct_sin_edicion` sube sin `tasa_validadas`; aprobaciones < 30 s | ≥ 3 hallazgos o evidencia; defectos sembrados (≥ 90 %) y dorados; canary y reversión de skills; cambios a QA siempre H; tarjeta de una página | G-25, G-26 | Dueño / X2 |
| R20 | **Kill switch lento o muerto:** vigilante caído, token de pausa revocado, Meta API 613, peor caso de ~35-40 min `[HIPÓTESIS]`, prepago que anula la capa 3 | 2×5 = **10** | Latido ausente; A-10 falla; aprobaciones de reanudación sin preflight | Tres capas independientes; watchdog dead-man con supervisión mutua; alertas por dos canales; reanudación solo humana | G-04, G-03 | Motor / dueño |
| R21 | **DSA y exposición de la LLC:** anuncios UE exigen beneficiario y pagador; la LLC aparece en la Biblioteca (1 año según 08 §8 `[VERIFICAR]`); sin DSA no se publica; el nombre público une ofertas «independientes» | 5×2 = **10** | Preflight de Meta en ROJO por DSA; anuncio UE sin publicar | Decidir el nombre antes del primer gasto; C14/PX1 como bloqueo; aceptar que la Biblioteca vincula ofertas (§6) | G-34 | Dueño |
| R22 | **Costos de canal y dependencia de Meta:** CPM de Q4 (Black Friday 2026-11-27), tarifa de ubicación (§6), «menos personalizados»; todo el tráfico pasa por un canal y una cuenta | 5×2 = **10** | CPM real > `mult_cpm` × atlas; factura ≠ plan | `mult_cpm` 1,2-1,5; leer el piloto como «Q4»; tarifas en línea aparte; `tarifas.json` ≤ 30 d | G-35, G-22 | F1 / M1 |
| R23 | **Credenciales vencidas y conectores no disponibles desatendidos** (los de claude.ai no cargan con API key; `needs-auth`; Stripe MCP solo OAuth o claves de agente desde 2026-11-30 `[VERIFICAR]`; scheduler caído) | 5×2 = **10** | `estado.json` > 6 h; M-01/S-01 ROJO; latido ausente | Fail-closed: sin `estado.json` VERDE no hay gasto; scripts propios con tokens de sistema desde N3; vigencias en la rutina semanal; `pg_dump` cifrado diario | G-05, G-09, G-33 | D0 |
| R24 | **PI, licencias y transparencia de IA:** patrones o imágenes con licencia ambigua, copia de ofertas ajenas, producto 100 % IA sin autoría humana protegible, art. 50 del AI Act (desde 2026-08-02), C2PA borrado al recodificar | 3×3 = **9** | Licencia ambigua; similitud; `c2pa_final=no` | Registro de prompts y licencias; K02; divulgación según `politica_divulgacion_ia`; no quitar marcas ni metadatos | G-31, G-13 | D4 / D6 / X1 |
| R25 | **Idioma obligatorio y traducción mala:** texto legal o producto sin revisor nativo (obligatorio por ley en Polonia, 08 §3), calcos, concordancias, números | 3×3 = **9** | Retraducción diverge; quejas de comprensión | Revisor nativo por idioma × macro-nicho (it, pl, ro, fr, de), retraducción, glosario | G-30 | M1 / QA |

**Cobertura.** Dinero: R07, R09. Plataformas: R01, R02, R05, R13, R21. Cumplimiento: R03, R16, R08, R24, R25, R02 (testimonios, urgencia). Calidad: R11, R24, R25. Medición: R08, R15. Agentes: R06, R12, R14, R19, R09. Mercado y negocio: R07, R17, R22. Operativo: R20, R23. Radar: R10, R14, R17, R18.

---

## 2. Catálogo de guardarraíles

Tipo: **D** determinista (código; dos ejecuciones dan lo mismo), **H** humano, **P** proceso. «Estado» al 2026-11-06: ✔ construido y con pruebas; ◐ contrato o esquema hecho, componente por construir; ○ solo diseño.

### 2.1 Dinero y límites

| ID | Guardarraíl | Tipo | Dónde vive · estado | Responde a |
|---|---|---|---|---|
| G-01 | `limites.yaml` firmado, solo el dueño; cualquier clave necesaria en `null` o sello ausente ⇒ salida 5 (nada gasta); `deny` + hash para agentes | D | `engine/limites.py`, `engine/guard.py` ✔ | R09, R07 |
| G-02 | Techo teórico 1,75× el presupuesto diario; paso ≤ 20 % cada ≥ 72 h; ≤ 4 cambios por hora por conjunto, ≥ 30 s entre ediciones; agregados por cartera; tope de pérdida por oferta y acumulada | D | `engine/limites.py` (`exigir_tope`, `exigir_ritmo`, `exigir_agregados`), `decision/presupuesto.py` ✔ | R09 |
| G-03 | Segundo y tercer candado: presupuesto Meta = tope ÷ 1,75; `spend_cap` de la cuenta (recalcular en cada alta de oferta); tarjeta virtual con tope en el emisor; **sin prepago** | H | Dueño en Meta y emisor; D0 M-03 ○ | R09, R20 |
| G-04 | **Kill switch de tres capas:** (1) `empresa/PAUSA` escrito en tres sitios (almacén del motor, KV del watchdog, archivo) y verificado; (2) `scripts/pausar.py` por API de Meta, idempotente; (3) límite de gasto de la cuenta. Watchdog dead-man (cron `*/5`, solo `GET` y `POST status=PAUSED`, sin ruta de activación); supervisión mutua; alertas por dos canales; borrar `PAUSA` **no** reactiva | D+H | `infra/` ○; contrato `senal_pausa` ◐ | R01, R20 |
| G-05 | Preflight de 43 ítems: sin `estado.json` VERDE y < 6 h nadie gasta ni activa; sonda no ejecutable ⇒ ROJO; modo `simulado` rechazado por los hooks | D | `infra/plantillas/preflight-items.yaml` ◐ | R23, R09 |

### 2.2 Agentes y ejecución

| ID | Guardarraíl | Tipo | Dónde vive · estado | Responde a |
|---|---|---|---|---|
| G-06 | Hooks con envoltorio fail-closed (`exit 2` ante toda excepción, plazo interno < `timeout`, redacción de secretos); **sonda de hooks** (entradas sintéticas que deben dar `exit 2`) en CI y preflight; versión mínima de Claude Code verificada; `claude doctor` sin `Invalid settings` | D | `agentes/hooks/` ○ (diseño en docs/09 §14) | R06 |
| G-07 | Lista blanca de herramientas (`herramientas.yaml`): lo desconocido es escritura; `ads_update_entity` solo con `{"status":"PAUSED"}` (el campo `fields` llega como cadena JSON); sin `ads_delete_*` ni `ads_catalog_*`; Bash solo por script nombrado con argumentos dentro de la carpeta de la oferta | D | `agentes/hooks/pretooluse_*.py` ○ | R06, R09 |
| G-08 | Permisos: `deny` de `.claude/skills/**`, `.claude/agents/**`, `contratos/**`, `limites.yaml`, `parametros.yaml`; permisos del SO y diff del árbol tras cada corrida (los `deny` de `Bash` no son frontera); Makers sin Bash libre; QA con `--tools "Read,Grep,Glob"` y `--disallowedTools "mcp__*"` | D | `.claude/settings.json` (ola −1) ○ | R06, R12, R14 |
| G-09 | El runner desatendido **no tiene conectores MCP**; escrituras vivas solo por scripts (`meta.*`, `pausar`, `subir_presupuesto`) con credenciales de mínimo privilegio (un usuario de sistema de lectura, otro de pausa) | D | `agentes/runner.py` ○, `meta/` ✔ | R14, R23 |
| G-10 | **Sellos por hash:** X1 sella landing, creativos y configuración (`hash_config` + `object_ids` exactos); el hook de activación exige sello vigente, `qa_veredicto == PASS`, `h_firmado == true`, cuenta en `cuentas_permitidas`; firma Ed25519 con clave fuera del alcance de los agentes; registro de sellos de solo lectura para el runner | D | `compliance/` ○; `engine/limites.py::verificar_firma_sello` ✔ | R01, R02, R13 |
| G-11 | Vigilancia post-sello (K03): rastreo diario del sitio vivo con JavaScript desde tres países y dos agentes de usuario, con y sin UTM; comparación de cada creativo vivo con el sellado; mejoras de Meta apagadas | D | X1 ○ | R13 |
| G-23 | **Datos ≠ instrucciones:** delimitadores y cuarentena del texto externo; la salida del Maker se valida por esquema fuera del modelo (el runner revalida; el hook `Stop` es cortesía); escape total y CSP en el dashboard (el LLM recibe solo números e IDs); fixtures hostiles | D | `agentes/runner.py` ○; `tests/agentes/` | R14, R18 |
| G-25 | **Anti-sello-de-goma:** el QA lista ≥ 3 hallazgos o justifica; calibración con dorados (deben dar PASS) y defectos sembrados (≥ 90 % de los bloqueantes); canary y reversión de skills; cambios al QA siempre con gate H | P | Protocolo QA (backbone §6); `skills/` ○ | R19 |
| G-26 | Firma H del dueño **fuera del dashboard** (el motor re-valida); idempotencia y CSRF del botón; alerta si una aprobación tarda < 30 s; autonomía por etapa con descenso automático; tarjeta de una página por gate | D+H | `engine.orq`, `empresa/autonomia.yaml` (todo en N0) ◐ | R19 |
| G-27 | Secretos: `gitleaks` y sonda en CI, redactor de patrones (`sk_`, `rk_`, `whsec_`, `sk-ant-`, `EAA`) antes de loguear, manifiesto de variables, rotación, nada de secretos en chats | D | `.gitignore`, `.env.example` ✔; CI ○ | R12 |

### 2.3 Cumplimiento y plataformas

| ID | Guardarraíl | Tipo | Dónde vive · estado | Responde a |
|---|---|---|---|---|
| G-12 | **Riesgo por candidato:** tabla única ejes (P, C, E, N) → nivel; el LLM no la reemplaza; suite `casos-frontera.yaml` (230 casos); conjunto de **retención** sellado por hash (≥ 60 positivos, 0 falsos verdes, cota superior ≤ 5 %); veto de X1 que ningún nivel de autonomía relaja | D | `compliance/nivel_riesgo.py` ○; suite en `docs/_historial/hwr-semillas/` | R01, R02 |
| G-13 | Lints L1 de X1: léxico de cura y plazo por idioma (P01), verbos de cambio sobre el cuerpo o el dinero (P07), cifras de clientes generadas por script (P08), `terminos_sensibles/<locale>.yaml` en slug/URL/UTM/eventos (D01), OCR de fotogramas y transcripción del audio (M01-M02), hojas y PDF ocultos (M04-M05) | D | `compliance/` ○ | R02, R11, R24 |
| G-14 | Cuotas y congelación: amarillo-A ≤ 30 % del gasto, amarillo-B ≤ 10 % `[HIPÓTESIS]`; un rechazo de producto congela la hoja, dos en 7 días congelan la cuenta; `nivel_max_lanzable` | D | `limites.yaml`, `parametros.compliance` ◐ | R01 |
| G-15 | Escalones de salud operativa: disputas + EFW 0,20/0,35/0,50 %, casos 2/3/5, reembolsos 8/12/15 %, avisos de Stripe; un escalón más bajo en amarillos; `senal_pausa`; fondo de reembolsos `max(15 % amarillos, 8 % verdes)` liberado a los 120 días | D | `parametros.salud_operativa` ◐; F1/D10 ○ | R04, R05 |
| G-16 | `perfil_stripe.yaml` (descriptor, categoría, MCC) contra catálogo y producto (N05); jamás cobrar lo no declarado ni repartir ventas entre descriptores | D | D0/X1 ○ | R05 |
| G-17 | Garantía simple, reembolso en un clic, descriptor estático, email inmediato; EFW ≤ tarifa de disputa se reembolsa solo; segundo canal de contacto | D | D10 ○ | R04 |
| G-18 | Fiscal por país: `modelo_cobro` nulo bloquea UE/UK; `paises_permitidos`; Stripe Tax y OSS; exposición firmada por el dueño si se acepta `sin_tax`; condiciones C0.1-C0.3 de 16 §6 | D+H | D5/M1/F1 ◐ | R03, R16 |
| G-19 | Checkout UE/UK: casilla separada y sin premarcar de entrega inmediata y renuncia, función de desistimiento visible todo el plazo, garantía comercial separada (X1-J07) | D | D5 ○ | R16 |
| G-34 | DSA: beneficiario y pagador = LLC en cada conjunto con UE (C14); sin DSA no se publica; verificación de categoría financiera de Meta (AU, IE, ES) como parada dura | D | `meta/` ✔ (campo), preflight ○ | R21 |
| G-35 | `tarifas.json` ≤ 30 días con tarifa de ubicación por país y comisiones por método; F1 concilia con la factura de Meta | D | F1 ○ | R22 |

### 2.4 Medición, decisión y economía

| ID | Guardarraíl | Tipo | Dónde vive · estado | Responde a |
|---|---|---|---|---|
| G-20 | `event_id` determinista (`purchase_<session>`); Checkout Session creada en servidor con `adid`; CMP con rechazo equivalente y modo sin consentimiento; conciliación semanal con rango 0,8-1,3 y cobertura de `adid` ≥ 95 %; modo ciego G4 | D | `tracking/workers/*` ✔; CMP ○ | R08 |
| G-21 | Reglas secuenciales bayesianas puras (`evaluar_celda`): BLOQUEADO si falta tope, moneda distinta o datos inválidos; MATAR solo con gasto ≥ `k_min_matar`·CPA_BE y tracking sano; ventana de no decidir 72 h; ESCALAR solo propone a D9; INCONCLUSO al tope | D | `decision/reglas.py`, `decision/estadistica.py` ✔ | R15, R07 |
| G-22 | Economía única con neto completo (IVA, Stripe Tax, reembolso esperado, disputas, FX, tarifa de Meta); la prueba de vectores falla si hay dos economías | D | `engine/factibilidad.py` ✔ | R07, R22 |
| G-32 | Mercados como hipótesis: `es_hipotesis`, presupuestos iguales por mercado, paridad de evidencia por `locale`, brazo de exploración, sin prior de creadores | P | M1 `departamentos/16` ○ | R07, R17 |
| G-33 | `pg_dump` cifrado diario a R2 con restauración mensual; webhook idempotente; eventos de Stripe recuperables por ~30 días `[VERIFICAR]` | D | `infra/` ○ | R23 |

### 2.5 Contenido, radar y localización

| ID | Guardarraíl | Tipo | Dónde vive · estado | Responde a |
|---|---|---|---|---|
| G-24 | **Recolección:** fuentes por color (V/A/R) y `fuentes_permitidas[]`; `freno.json` ante 403, captcha o `Disallow` (se detiene, no reintenta; solo el dueño lo levanta); identidad borrada al ingresar; TTL y borrado verificado; extractos ≤ 25 palabras; sello VC de X1 antes de cada corrida | D+P | `scripts/modelado/barrido/` ✔ (freno); X1 ○ | R10 |
| G-28 | Filtro MU/EU (5.11) con rechazos canónicos; QA ciego que ejecuta «el prompt de una línea» de un chatbot; contrastación con la competencia (D2); evidencia por `locale` | P+D | D1/D2 `departamentos/02`, `03`; nota 19 | R17, R18 |
| G-29 | Producto seguro (D4): `afirmaciones.jsonl` con fuente T1 y fecha, `afirmaciones_sin_fuente_max = 0`, pisos, `ayuda_por_pais.yaml` ≤ 180 d verificada por una segunda persona, RHS en el primer lanzamiento por hoja × idioma, revisión por volatilidad, L1 de unidades y decimales | D+H | D4/X1 ○ | R11 |
| G-30 | Localización: revisor nativo por idioma × macro-nicho (una vez, luego muestreo 1 de 5), retraducción, segunda lectura con otro modelo, glosarios por `locale` | H | M1/D6 ○ | R25 |
| G-31 | Similitud (n-gramas y coseno de un modelo local fijo) contra todo texto rechazado por Meta, Stripe o X1 en **cualquier** oferta, idioma u hoja; registro de licencias y prompts; divulgación de IA | D | X1-K02 ○ | R17, R24 |

**Brechas hoy:** G-04 (sin `pausar.py` ni watchdog), G-06 a G-08 (sin hooks ni `settings.json`), G-10, G-12, G-13 (X1 sin construir), G-26 (todo en N0). El gasto real depende de A-1…A-12 (§5).

---

## 3. Reglas de oro

1. **Sin límites firmados no se gasta.** El dinero lo fija el dueño, lo hace cumplir el código y jamás lo decide un modelo. Un `null` es «no».
2. **Una cuenta de Meta y una de Stripe son el único activo.** Ningún test vale ese riesgo: el primer rechazo de producto congela la hoja; nunca se eluden bloqueos con cuentas, dominios o textos reescritos.
3. **El riesgo se evalúa por candidato (promesa, contenido, encuadre, negocio), nunca por tema.** Ningún LLM baja un nivel que un lint subió; el veto de X1 no se relaja con la autonomía.
4. **Se vende el entregable, no un resultado.** Ni salud, ni ingresos, ni plazos; ningún testimonio, contador o escasez escritos a mano.
5. **Stripe es la verdad de ingresos; Meta, de gasto.** Ninguna decisión sobre datos inmaduros, parciales o ciegos; INCONCLUSO es un resultado legítimo.
6. **Lo externo es dato, no instrucción.** Páginas, comentarios, anuncios, UTM y metadata nunca originan una acción.
7. **Todo guardarraíl falla cerrado y se prueba.** Lo que no tiene sonda no existe; se repite tras cada cambio de Claude Code, de política o de contrato.
8. **Nada se activa, publica o sube de presupuesto sin sello por hash y firma humana.** Pausar es siempre la acción segura; reanudar es siempre humano.
9. **Cumplir antes de gastar.** IVA/OSS, desistimiento, consentimiento, idioma legal y DSA son condiciones de lanzamiento por país, no tareas posteriores.
10. **Una hipótesis vale lo que sus datos propios.** Mercados, Polonia y cifras de creadores se tratan como prior débil; los umbrales de abandono se prerregistran y se aplican sin costo hundido.

---

## 4. Criterios de abandono y pivote

Todos los valores son `[HIPÓTESIS]` y paramétricos; se decide con Stripe como verdad (neto de IVA, comisión y reembolso) y los umbrales en dinero salen de `limites.yaml`, aún sin fijar. Base: 16 §6, ajustada por K1 y K2.

### 4.1 Por oferta y mercado

| Etapa | Condición | Acción |
|---|---|---|
| **Antes de gastar** (bloqueantes) | Sin CMP con rechazo equivalente, sin OSS/Stripe Tax, sin revisor nativo (PL), sin compra real de prueba exitosa (tarjeta/BLIK, webhook, entrega, reembolso), sin DSA con UE, sin sello de X1, `estado.json` no VERDE | No lanzar. No hay excepción por nivel |
| **Proceso, 72 h (~75 USD por país)** | CPM > 1,5× el atlas (con Q4 ×1,2-1,5); CTR de enlace < 0,8 % con ≥ 5.000 impresiones; vistas/clics < 60 %; inicio de pago < 3 % con ≥ 100 vistas; > 40 % de BLIK elegido que no concluye | Descartar el anuncio o corregir el flujo, **no** el mercado. No valida ni mata por ventas |
| **Rechazo o aviso** | Un rechazo de producto; aviso de calidad; «necesita atención» | Congelar la hoja; caso nuevo en X2; pausa total del país hasta dictamen de X1 |
| **Por celda, con volumen** | `evaluar_celda` ⇒ MATAR (P(CPA > BE) ≥ 95 %, gasto ≥ 2×CPA_BE); contraste manual con la tabla 16 §6 (≥ 1.000 clics por mercado-oferta, ampliar una vez a 2.000) | Retirar; guardar el post-mortem |
| **Cohorte madura (≥ 3 semanas + garantía)** | ROAS neto < 1,0 con ≥ 40 compras; reembolsos ≥ 12 % o 2 cohortes > 12 %; disputas + EFW ≥ 0,35 % o 3 casos; BLIK < 30 % de las compras polacas (refuta su relevancia); compras Stripe vs. Meta con diferencia > 30 % | Pausar la oferta y recalcular la economía con la tasa observada |
| **Cumplimiento y costos fijos** | Una disputa por renuncia inválida; consulta de UOKiK, AGCM, Garante u otra autoridad; costo fijo mensual del país (revisor, CMP, representante RGPD, OSS) > margen esperado | Cerrar el país |

### 4.2 Del modelo completo

| Criterio | Regla | Pivote posible |
|---|---|---|
| Tope de aprendizaje | 8 pares mercado-oferta con ≥ 1.000 clics cada uno (~2.500-4.800 USD) y ninguno con ROAS neto ≥ 1,0 ⇒ detener la expansión en la UE; con 12 pares la prueba es concluyente al ~90 % (16 §6) | Subir ticket y bump, backend de valor, mercado anglo (UK mostró CPA ~51 % del equilibrio en un caso `[CREADORES, C]`), o carril B |
| Rentabilidad agregada | ROAS neto combinado < 1,0 a los 60 días con ≥ 3.000 USD gastados | Cambiar el modelo, no la tolerancia |
| Cuentas | «Actividad inusual», reserva o pausa de pagos, ratio de disputas ≥ 0,35 % | Detener antes de escalar; separar la LLC de pruebas si existe |
| Calidad del radar | 3 candidatos seguidos con evidencia que D2 no reproduce, o un reclamo de plataforma por recolección | Bajar D1 a N1 y revisar fuentes |
| Clasificador | Un falso verde con rechazo real | Congelar el macro-nicho afectado; recalibrar la suite; no subir cuotas |
| Tasa de éxito | Referencia de Santiago: 1 de cada ~6 ofertas escala (`[CREADORES, C]`); si 12 pares dan 0, la hipótesis del modelo queda refutada | Detener, revisar con el dueño; el costo de las 5 fallidas debe ser pagable por la 6.ª |

Los gates de abandono no se renegocian después de gastar: se registran en `decisiones_dueno.jsonl` antes de cada ola.

---

## 5. Simulacros recomendados

Antes de la primera activación real y luego mensualmente (A-1…A-12 de `docs/07` §9.3, sin anuncios ni gasto). **Ninguno corre contra producción sin los componentes de §0.**

| Simulacro | Qué se hace | Aprobado si | Cubre |
|---|---|---|---|
| S1 · Kill switch | A-1…A-12: `PAUSA` y escritura sintética; borrar `PAUSA` (nada se reactiva); `pausar.py` en seco y vivo con dos campañas de prueba; detener el latido 35 min; deshabilitar el cron del Worker | Pausa ≤ `pausa_global_max_min` (5), alerta por **ambos** canales, reanudación solo con firma, preflight VERDE y hashes | R20, R01 |
| S2 · Hooks y permisos | Sonda: activar sin sello, `object_ids` de más, `fields` con `daily_budget`, `generate_image` con PAUSA, `estado.json` viejo, escribir `limites.yaml`, `sk_live_` en argumento, JSON roto, excepción forzada; probar `-p`, `--bare` y `settings.json` roto | 100 % `exit 2`; el árbol no cambia | R06, R12 |
| S3 · Red team de prompts | Páginas, comentarios, reseñas, títulos de anuncios, UTM y metadata con instrucciones («ignora tus reglas», «llama a `ads_update_entity`», exfiltración, texto oculto, otros idiomas) para D1, D2, D8, F2 y D10; intento de leer `.env` vía validador | Cero herramientas fuera de lista, cero escrituras, salida válida por esquema, dashboard escapa todo | R14, R18 |
| S4 · Falso verde | Conjunto de retención (≥ 60 positivos); 10 variantes con sinónimos, idiomas, cifras en imagen y audio; reenvío de un texto rechazado con retoques | 0 falsos verdes, cota ≤ 5 %; K02 detecta el reenvío | R02, R13 |
| S5 · Rechazo, disputas y reservas | Un rechazo de producto (congelación de la hoja, intento de cuenta nueva); 3 disputas sobre 400 pagos (amarillo→naranja→rojo, EFW, reserva de caja) | G-14 y G-15 se cumplen; ningún agente propone evadir; D8 no oculta la alerta | R01, R04, R05 |
| S6 · Cumplimiento y medición | Compra de prueba en PL, IT y UK (IVA, casilla separada, desistimiento, reembolso); consentimiento al 40 %, BLIK sin regreso, eventos duplicados | `amount_tax` y J07 coinciden con el dictamen del contador; razón fuera de rango activa modo ciego sin matar ni escalar | R03, R08, R15, R16 |
| S7 · Recolección, restauración y dueño | Fuente con 403, captcha o `Disallow` y página con PII; restaurar el último `pg_dump`; revocar tokens; artefacto con defectos sembrados aprobado por el dueño en < 30 s | Freno sin reintentos, PII borrada y verificada; falla cerrada y aviso; QA ≥ 90 % y alerta de aprobación rápida | R10, R23, R12, R19 |

Cadencia: S1-S2 en cada actualización de Claude Code y antes de subir de nivel; S3-S4 mensuales y tras cada cambio de política (30 días); S5-S7 trimestrales o por evento.

---

## 6. Riesgos específicos de la estrategia global

**6.1 Tarifa de ubicación de Meta.** Desde 2026-07-01: Italia, Francia y España 3 %, Austria y Turquía 5 %, Reino Unido 2 %; Polonia no figura (16 §2.1; mediapost.com/publications/article/413395, insights.vaizle.com/news/meta-to-add-new-ad-fees-in-six-countries-starting-july-2026; confianza B). Puede aparecer solo en la factura y no en «Importe gastado» `[VERIFICAR]`: el CPA de Ads Manager subestima el costo real 3 % en Italia. Control: línea aparte en F1, conciliación con la factura y máximo teórico sobre lo **facturado** (G-35); revalidar mensualmente.

**6.2 DSA y la LLC visible.** Los anuncios a la UE exigen beneficiario y pagador (`default_dsa_beneficiary`/`default_dsa_payor` en `meta.yaml`) y la LLC puede quedar expuesta en la Biblioteca de Anuncios (1 año según 08 §8 `[VERIFICAR]`). Consecuencias: (a) cualquiera puede vincular las «marcas independientes» con la misma entidad, y un reclamo contra una afecta a las demás (R01); (b) sin DSA no hay entrega en la UE; (c) el nombre público se decide **antes** del primer gasto (C14/PX1). `[DUEÑO]` pendiente.

**6.3 Managed Payments vs. métodos locales.** El MoR de Stripe quita la carga de IVA, pero cuesta +3,5 % y **no admite BLIK, Przelewy24, Satispay ni MB WAY**: la cobertura de pago en Polonia cae de ~67-75 % a ~23 % (25 §9; 00 §4). Exige elegibilidad, se suma a la lista de prohibidos y Stripe puede reembolsar sin aprobación a las 48 h (22d §0.4). Los MoR alternativos (Paddle, Polar, Lemon Squeezy, Gumroad) son **más** restrictivos en salud, finanzas, citas y oportunidades de negocio. Coherente: Stripe directo (carril A) con IVA gestionado, y un MoR ya onboardeado como carril B solo para verdes.

**6.4 IVA desde la primera venta.** OSS no-Unión sin umbral y registro UK desde la primera venta (00 §4; 05 §6.1). Stripe Tax calcula y cobra pero **no presenta ni remite** (0,5 % o 0,50 USD por API; 16 H1, `[VERIFICAR]`). Los creadores lo difieren (Tomi: «No se preocupen por el IVA si todavía no vendieron», en contexto argentino; 16 H5). Si el contador confirma 23 %/22 % para el PDF (no 5 %/4 %), el neto frontal es ~19 % menor y el caso base empeora (16 §2.5). Control: `modelo_cobro` nulo bloquea UE/UK; pasivo por país reservado en F1; contador antes de abrir cada país.

**6.5 Mercado como creencia: Polonia.** El red team (16 M6, §5.1) ni refuta ni respalda a Polonia: con neto completo Italia (65) queda sobre Polonia (~59), el CPC menor (0,51 vs. 0,56) no compensa un ticket de ~13,2 USD con IVA 23 % y fijo de 0,30 USD, y el corpus no tiene un solo dato de campaña polaco. Sus ventajas son reales (CPM, BLIK sin tarifa de disputa, quizá menos exigencia legal si la función de desistimiento sigue suspendida `[VERIFICAR]`). Control: presupuestos iguales por mercado y `es_hipotesis` (G-32).

**6.6 Otros.** Q4 (Black Friday 2026-11-27): el piloto se lee como «Q4» y no se compara con enero. Liquidación: Meta cobra antes de que Stripe pague (7-14 días); la caja descuenta reservas. Cobrar en PLN/EUR y liquidar en USD suma 1 % + 1,5 % por tarjeta internacional, y los reembolsos vuelven en la moneda del cargo. Los anuncios «menos personalizados» de la UE tienen efecto sin cifra pública `[VERIFICAR]`.

---

## 7. Lo que este sistema NO reemplaza

| Área | Qué hace el sistema | Qué sigue siendo de un profesional o del dueño |
|---|---|---|
| **Contador (EE. UU. y UE/UK)** | Calcula IVA con Stripe Tax, reserva el pasivo por país, alerta | Régimen fiscal de la LLC, registro y presentación de OSS no-Unión y UK VAT, tipo de IVA del PDF, sales tax estatal, tributación del titular, retención en origen |
| **Textos legales y cumplimiento de consumo y datos (sin abogado)** | Genera las páginas legales y el banner como plantilla por país; X1 comprueba lo verificable (claims, avisos, sellos, líneas rojas) y el preflight que las páginas existan y respondan 200 | **Riesgo residual aceptado por el dueño (decisión 14): sin revisión legal humana; lo verificable lo automatiza X1 y lo fiscal lo cubre el contador.** Puntos de riesgo residual sin dueño legal: textos finales por **país × macro-nicho × nivel** (IT, FR, ES, DE), RGPD art. 27, política de recolección (nota 21 §10), reclamos de PI; las apelaciones formales siguen siendo del dueño (fila «El dueño») |
| **Revisor nativo** | Retraducción y segunda lectura con otro modelo | El texto legal en polaco es obligatorio por ley; revisor humano en el primer lanzamiento de cada idioma |
| **Profesional sanitario o financiero** | Fidelidad a fuentes T1, pisos y derivaciones; RHS de 30-60 min | No acredita exactitud clínica ni sustituye a un asesor; **nunca** se afirma «revisado por un profesional» si no es cierto |
| **El dueño** | Propone y registra | Fija `limites.yaml`, el nombre público de la entidad, las apelaciones, el levantamiento del freno de captura y toda reanudación tras una `PAUSA` |
| **Meta y Stripe** | Reduce el riesgo de rechazo | No garantiza aprobación ni evita un cierre sin causa (SSA §10.1); el riesgo de concentración persiste |

Ningún guardarraíl basado solo en un LLM cuenta como control: todo control crítico tiene versión determinista o humana.

---

## 8. Pendientes, decisiones y pedidos

**Hallazgos críticos para el dueño.**
1. El único freno real hoy es `limites.yaml` en `null` (G-01). Antes de fijar cualquier tope hay que construir y probar S1 y S2 (G-04, G-06-G-08, G-10) y hacer la ola −1 (`git init`, `.claude/settings.json`).
2. Los conectores de escritura de Meta están cargados en la sesión interactiva sin hook: hasta entonces, no se invoca ninguno que cree, active, edite o borre.
3. El caso base de Polonia e Italia pierde dinero con costos completos; el piloto sirve para detectar fallas de proceso, no para validar mercados.
4. IVA/OSS/UK VAT y desistimiento son bloqueantes de lanzamiento por país.
5. El freno de captura de la Biblioteca web (HTTP 403) sigue activo: es una decisión solo del dueño y no se evade.

**Decisiones del dueño `[DUEÑO]` pendientes:** `perdida_max_test_por_oferta`, `perdida_neta_acumulada_max`, `capital_en_riesgo_total`, `limite_gasto_cuenta_meta`; nombre público de la entidad para DSA; Merchant of Record (sí/no, carril B); cuántas fan pages; contador; si se levanta o no el freno de captura; nivel máximo de amarillo permitido.

**`[VERIFICAR]` abiertos:** IVA del PDF en PL e IT; Stripe Tax por API vs. «sin código»; función de desistimiento en Polonia (UC82) y art. 54-bis; tarifa de Meta en «Importe gastado»; visibilidad de la LLC (1 año); VAMP «y» vs. «o»; Stripe MCP desde 2026-11-30; términos de cada fuente del radar.

**Pedidos a otras propiedades** (registrados en `docs/_historial/coordinacion-sesiones.md`, sin editar código ajeno): construir `agentes/hooks/` y la sonda de hooks con las 10 entradas de S2; `scripts/pausar.py` y watchdog antes de cualquier activación; ítem de preflight para versión mínima de Claude Code, `.claude/settings.json` presente y `claude doctor` limpio; fixtures hostiles (S3) en `tests/agentes/`; suite de retención del clasificador de X1.
