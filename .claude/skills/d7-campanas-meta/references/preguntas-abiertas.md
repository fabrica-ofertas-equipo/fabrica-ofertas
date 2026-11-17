# Preguntas abiertas y supuestos (v0.1)

Instrucción de arranque del spec (§10.1): «preguntas bloqueantes primero (máx. 8)». En esta forja no hubo interlocutor, así que cada una avanzó con un supuesto marcado. El Maker real las **pregunta** al dueño antes de armar, salvo que la respuesta ya esté en `limites.yaml`, `mercado.json` o `meta.yaml`.

## A. Bloqueantes (sin respuesta no se arma ni se gasta)

| # | Pregunta | Quién responde | `[SUPUESTO]` usado en v0.1 |
|---|---|---|---|
| 1 | ¿Qué `oferta_id`, `locale`, países y moneda? (ningún país es prior) | `mercado.json` (M1); si falta, el dueño | no se asume ninguno; los evals usan it-IT, pl-PL y de-DE solo como casos |
| 2 | ¿Están cargados `gasto_diario_por_oferta`, `gasto_total_test_por_oferta` y `perdida_max_test_por_oferta` (hoy diferida)? | dueño (`limites.yaml`) | con `null`: salida 5, no se arma (fail-closed) |
| 3 | ¿Cuenta elegida, `cuentas_permitidas` y moneda/huso (irreversibles)? ¿Qué hacer con la cuenta deshabilitada previa (apelar o abandonar; nunca abrir otra para esquivarla)? | dueño | sin `meta.yaml` no se lee la cuenta |
| 4 | ¿Alta de la oferta hecha: dominio verificado, dataset `DS_<oferta_id>`, token CAPI? | dueño (`alta-por-oferta.md`) | si falta, bloqueo de entrada |
| 5 | Nombre público del **beneficiario y pagador DSA** (LLC o marca) si hay UE | dueño | no se inventa |
| 6 | `self_ai_disclosure` (`limites.politica_divulgacion_ia`) y mejoras automáticas de Meta | dueño | mejoras siempre apagadas; disclosure = la política, sin inferirla |
| 7 | ¿Género o edad distintos de «todos / 18–65»? | dueño | amplia, todos, 18–65 |
| 8 | ¿Autorizas crear el borrador con el conector en esta sesión (N0–N1)? | dueño | **no**: el Maker entrega los payloads exactos sin ejecutarlos |

## B. No bloqueantes (decisiones del dueño que cambian parámetros)

1. ¿`INITIATE_CHECKOUT` como fase de señal y que un test chico «solo refute»? (la skill lo declara en la tarjeta; el dueño decide si sube el tope).
2. Cuotas por nivel (30 % / 10 %, 3 envíos por semana): hoy `[HIPÓTESIS]` de la nota 25; claves pendientes en `limites`.
3. Excluir o no FR/IT/ES/AT por la tarifa de ubicación (Meta no garantiza reducirla).
4. Dónde guarda su clave Ed25519 (custodia) y cuándo se genera (`docs/00` §0 D).
5. Primer idioma/mercado: un mercado a la vez (R-C01); Polonia e Italia son hipótesis, no priores, y el dueño decide con M1. Comparar mercados = comparar ofertas de una familia con presupuesto igual (docs/08 §7).
6. Cuenta con **un solo administrador**: decisión 15 la acepta como riesgo residual; `meta.preflight._p07` ya es informativo (solo exige página vinculada). Resuelto.
7. Tolerancia de «ventana omitida» (`campana.tolerancia_ventana_min`, LT-52, `[PENDIENTE: CT-3]`) y quién dispara `meta.monitor` mientras `engine.orq` no tenga el subcomando (hoy el dueño).
8. Confirmar que **D7 es dueño de la ventana T0 → T+72 h** (la spec 08 §4 ya lo recoge; falta la ratificación en el pulido).
9. K-02/D-02: ¿el botón activa sin tu clic en N3/N4? Hasta que decidas, el gate efectivo de activar es H (C-04 abierta).

## C. `[SUPUESTO]` técnicos principales

- Presupuesto visible = `max(corte, validar)`; facturado = visible × (1 + tarifa); el techo se compara con el peor caso facturado del `spend_cap`.
- `gasto_esperado` de una ventana = techo permitido (no ritmo medio).
- Amarillo-B y rojo no se arman; amarillo-a solo con claves de riesgo y RHS registrada.
- Formato de `lanzamiento.log` (JSON por línea) definido por la skill.
- Subnivel amarillo: el del snapshot si existe (`scripts.nivel_riesgo`); si no, derivado de los colores de los ejes (≥ 2 amarillos entre P, C, N = B).
- La lectura de cuenta (`cuenta_meta`) se anota en el log hasta que exista `empresa/infra/meta.yaml`.
