# 10 — Runbook operativo del primer testeo

> **Para el dueño, no técnico.** Versión 1.0 (2026-11-06) · Adelantado en la ola 0c (RB), según `docs/06-bases-del-testeo.md` §8. Subordinado a `docs/_backbone.md` (v2.2) y a `docs/06` (que prevalece sobre este documento si hay contradicción). Fuentes citadas: `docs/06` §4 (interfaces y CLI), §5 (estados), §6 (modo prueba y B0); `docs/07` §9 (kill switch), §12-13 (checklist final); `docs/08` §6, §8 (veredicto); `docs/09` (hooks y runner).
>
> **Qué es esto.** La guía de "qué hago hoy" durante un testeo: la mañana de activación, la rutina diaria, la semanal, qué hacer ante un incidente y cómo cerrar. No explica cómo se construye el sistema (eso está en `docs/06`); explica cómo se **opera** una vez construido.
>
> **Etiquetas de este documento:** `[PENDIENTE]` = el módulo que ese comando invoca **todavía no existe** (se construye en la ola 1 de `docs/06` §8; a la fecha de esta versión solo existen `contratos/`, `decision/` y `scripts/validar_esquemas.py`; todo lo demás es solo `README.md`); en cuanto el módulo quede construido y pruebe verde, el comando ya es real y la etiqueta se retira. `[DUEÑO]` = acá decide o firma el dueño, nadie más puede. `[HIPÓTESIS]` = valor o tiempo a calibrar con la operación real, no tomar como definitivo.
>
> **Antes del primer testeo en vivo, este runbook sirve igual para el simulacro.** Hasta que `docs/06` §6.2 (B0, "esqueleto caminante") esté verde, todo este runbook se **ensaya con `--modo fixture` o en modo dry-run**, sin gastar ni publicar nada real (`FABRICA_ENTORNO=prueba`); los pasos y las señales son los mismos, solo cambia que nada de lo que ves salió de Stripe o Meta reales, sino de datos sintéticos. Practicar la rutina diaria y los incidentes con el simulacro **antes** de ir en vivo es la mejor preparación: si un paso no tiene sentido en la práctica, es una señal para pedir un ajuste al constructor del componente, no para inventar un atajo.
>
> **Dos formas de operar, según cómo quede resuelta la topología (`docs/06` D-20, decisión [DUEÑO] pendiente):**
> - **Motor en Railway** (opción por defecto propuesta): el motor manda su propio "estoy vivo" cada pocos minutos y un vigilante (`watchdog`) pausa solo si deja de oírlo. La rutina diaria de este runbook (sección 2) no necesita ningún paso extra para esto.
> - **Motor local** (alternativa si el dueño prefiere no depender de un servicio en la nube todavía): no hay vigilante automático; el propio dueño tiene que avisar "estoy presente" una vez por jornada con `python -m engine.orq presente --como dueno` `[PENDIENTE]`. Si el dueño no manda esa señal dentro del plazo de `limites.yaml` (`watchdog.latido_max_min` o el que corresponda), el sistema se pausa solo. **Si esta es la opción elegida, agregar ese comando como primer paso de la rutina diaria (sección 2.0) antes de leer nada más.**
>
> Mientras `docs/06` D-20 no esté confirmado por el dueño, se asume la primera opción (Railway) en los ejemplos de abajo.

---

## 1. La mañana del primer día (antes de activar)

Esta sección es el paso previo a que el dinero empiece a moverse. No se activa nada sin haber marcado **todo** lo de 1.1.

### 1.1 Lo que tiene que estar cerrado (checklist final, cita `docs/07` §13)

`docs/07-puesta-en-marcha.md` §13 tiene la checklist completa e imprimible, con siete bloques (A. Personas y acceso, B. Meta, C. Stripe, D. Cloudflare/Railway/GitHub, E. Correo y legales, F. Kill switch y control, G. Estado final). **No se repite acá para no tener dos copias que se desactualicen distinto**: ábrela, imprímela o tenla en una pestaña, y marca cada ítem con la evidencia guardada en `empresa/infra/`. Un ítem sin marcar significa que el sistema **no se activa**, no es una sugerencia.

Dos ítems de esa checklist merecen una nota especial la primera vez:

- **"A-7 aprobada" (bloque B, Meta).** Es una **puerta**, no una prueba más: si nadie logró comprobar que el `spend_cap` no se puede tocar con el token del operador, la tercera capa del kill switch no es de verdad independiente. Sin A-7, no se activa, aunque todo lo demás esté en verde.
- **"Compra real mínima con reembolso" (bloque C, Stripe).** Es la única prueba que mueve dinero real antes del testeo en sí. Tiene que quedar hecha y con el reembolso confirmado, con la propia tarjeta del dueño, antes de activar cualquier campaña.

### 1.2 El último semáforo antes de activar

1. Correr el preflight completo y mirar el semáforo:
   ```
   python -m scripts.preflight --modo completo   [PENDIENTE: construye B8]
   ```
   **Qué debes ver:** `semaforo: "VERDE"` en la salida y en `empresa/infra/estado.json`, con `generado_en` de hace menos de las horas que fije `infra.hc_preflight_vigencia_horas` (tope duro: nunca más de 6 h, backbone §5.6).
   **Si no:** cualquier ítem crítico en AMARILLO o ROJO bloquea. El mensaje de cada ítem dice qué falta (sin secretos). Resuelve ese ítem puntual y repite; no hay forma de "forzar" el verde.
   **Cuándo escalar:** si el mismo ítem crítico sigue ROJO después de dos intentos razonables, es trabajo para el constructor del bloque correspondiente (Meta → B5, Stripe → B2/B7, Cloudflare/Railway → B8), no para insistir a mano.

2. Comprobar que los límites de dinero están completos y firmados (este comando **ya existe** hoy, de la ola 0b):
   ```
   python -m scripts.validar_esquemas limites empresa/limites.yaml --operacion activar
   ```
   **Qué debes ver:** código de salida `0` y un informe sin errores.
   **Si no:** sale `5` y te dice qué clave de `empresa/limites.yaml` falta o es `null`. No se improvisa un número: se completa esa clave (`[DUEÑO]`, fijado desde los presupuestos de testeo que se decidieron con el dueño, nunca inventado acá) y se vuelve a sellar con `python -m engine.limites sellar --propuesta RUTA --como dueno` `[PENDIENTE: construye B1]`.

3. Firmar el gate humano de "infra verde" (bloque G de la checklist): `[DUEÑO]`
   ```
   python -m engine.orq firmar --accion infra_verde --como dueno   [PENDIENTE: construye B1]
   ```

### 1.3 Secuencia de activación de la primera campaña

Con 1.1 y 1.2 cerrados, y con D1-D7 ya aprobados para la oferta (`python -m engine.orq estado --oferta OF-AAAAMM-NN` debe mostrar `fase: "listo_para_activar"`):

1. Armar el borrador y el preflight de la campaña en Meta (crea todo en pausa, nunca activo):
   ```
   python -m scripts.meta_crear --oferta OF-AAAAMM-NN --live       [PENDIENTE: construye B5]
   python -m scripts.meta_activar --oferta OF-AAAAMM-NN --object-ids ... --hash-config ...   # NO todavía: este es el paso 3
   ```
   **Qué debes ver:** `ids_meta.json` con los IDs de campaña, conjunto y anuncios, todos con `effective_status` en pausa, y `preflight.json` con P01-P24 en verde.
   **Si no:** un P en rojo señala qué falta (cuenta, presupuesto, nombres). No se activa con preflight de campaña incompleto.

2. X1 tiene que haber sellado D5, D6 y D7 con un sello **vigente** (`empresa/compliance/sellos/`). Si el sello venció o el artefacto cambió después de sellar, no hay paso siguiente: se vuelve a sellar.

3. Firmar la activación (gate H, `accion:activar_campana`) y ejecutarla: `[DUEÑO]`
   ```
   python -m engine.orq firmar --oferta OF-AAAAMM-NN --accion activar_campana --como dueno   [PENDIENTE]
   python -m engine.orq activar --oferta OF-AAAAMM-NN --object-ids <los de ids_meta.json> --hash-config <el de preflight.json> --live   [PENDIENTE: construye B1+B5]
   ```
   **Qué debes ver:** salida `0`, `fase: "en_test"` en `estado.json`, y en Meta los tres objetos (anuncios → conjunto → campaña, en ese orden) con `effective_status = ACTIVE`.
   **Si no:** cualquiera de estos motivos frena **todo** antes de tocar Meta, sin excepción: falta el sello, el `hash_config` no coincide con el que Meta tiene en vivo (alguien cambió algo), sobra o falta un `object_id`, no hay firma, o existe `empresa/PAUSA`. Si el segundo `POST status=ACTIVE` falla a mitad de camino, el sistema pausa lo que ya activó: no debe quedar una campaña con entrega a medias. Lee el mensaje de error, no reintentes a ciegas: cada motivo tiene una causa distinta (ver sección 4).
   **Cuándo escalar:** si la relectura de Meta después de activar muestra algo `ACTIVE` que no debería, o algo que no quedó `ACTIVE` y debería, para todo con `empresa/PAUSA` y revisa manualmente en el Administrador de anuncios antes de seguir.

### 1.4 La primera hora, las primeras 24 horas

Revisa con más frecuencia que la rutina normal (sección 2) durante el primer día:

```
python -m meta.monitor --oferta OF-AAAAMM-NN --ventana-h 1    [PENDIENTE: construye B5]
python -m meta.monitor --oferta OF-AAAAMM-NN --ventana-h 6
python -m meta.monitor --oferta OF-AAAAMM-NN --ventana-h 24
```

**Qué debes ver:** gasto acumulado por debajo de lo esperado para esas horas (presupuesto diario del `brief`/`campana.json`, nunca una cifra puesta acá), clics entrando, y ningún anuncio en `DISAPPROVED`.
**Si no:** gasto muy por encima de lo esperado en la primera hora → revisa el `spend_cap` y el presupuesto de la campaña, puede ser un error de configuración, no esperes al día siguiente. Cero clics con gasto > 0 → revisa la landing manualmente en el navegador (un enlace roto no lo detecta Meta). Un anuncio `DISAPPROVED` → ver sección 4.7.
**Cuándo escalar:** cualquier cosa que no entiendas en la primera hora de la primera activación real: para con `empresa/PAUSA`, revisa con calma, reactiva con la firma de siempre. El costo de pausar una hora de más es mínimo; el de no pausar a tiempo, no.

---

## 2. Rutina diaria (≈ 20 minutos)

Hazla todos los días que haya una oferta `en_test`, a la misma hora si es posible (después del cierre del día de la zona horaria de la cuenta ayuda a ver gasto completo del día anterior).

### 2.0 (Solo si la topología es "motor local", sección 0)

```
python -m engine.orq presente --como dueno   [PENDIENTE]
```
Sin esto, el sistema interpreta que no hay nadie y se pausa solo al vencer el plazo. Hazlo primero, antes de leer nada.

### 2.1 Estado general

```
python -m engine.orq estado --oferta OF-AAAAMM-NN --json   [PENDIENTE: construye B1]
```
**Qué debes ver:** una línea JSON `{"ok": true, "modo": "live", "codigo": 0, "datos": {...}, "avisos": []}` con `fase: "en_test"`, sin `espera_madurez.activa` (eso llega más adelante), y `avisos: []`.
**Si no:** `ok: false` o `avisos` con algo adentro → lee el mensaje; si dice `PAUSA` ver sección 4.1; si dice `infra` o `estado.json vencido`, corre de nuevo el preflight (sección 1.2).

### 2.2 La decisión del día de D8 (matar, seguir, escalar, inconcluso)

D8 corre solo (es código, no espera a nadie); tu trabajo es leer qué decidió, no decidir en su lugar:

```
python -m engine.orq ciclo-d8 --oferta OF-AAAAMM-NN   [PENDIENTE: construye B1]
```
**Qué debes ver:** una lista de decisiones (vacía si no hubo novedad) con `accion` ∈ `MATAR`, `SEGUIR`, `BLOQUEADO`, `ESCALAR`, `INCONCLUSO`. `SEGUIR` y `ESCALAR` (que solo se registra, no se ejecuta) no exigen nada de ti hoy. `MATAR` sobre un anuncio pausa ese anuncio solo; `MATAR` sobre la oferta-mercado cierra la campaña y pone `fase: "fallida"` sin pedirte permiso (pausar nunca espera a un humano, `docs/06` §5).
**Si no:** `BLOQUEADO` significa que algo le falta a D8 para decidir (tope sin definir, moneda distinta, datos inválidos): no gasta, no decide, y hay que mirar el motivo exacto en la salida.
**Cuándo escalar:** un `INCONCLUSO` o una `FALLIDA` no se revierten solos; léelos con calma en la rutina semanal (sección 3) o al cierre (sección 5), no hace falta actuar el mismo día salvo que el motivo sea una falla técnica del embudo (entrega, tracking), en cuyo caso avisa al constructor del componente señalado.

### 2.3 Reembolsos y disputas

```
python -m postcompra.metricas --oferta OF-AAAAMM-NN   [PENDIENTE: construye B7]
```
**Qué debes ver:** porcentaje de reembolsos y de disputas por debajo de lo que fija `empresa/parametros.yaml` (`salud_operativa.*`) y `empresa/limites.yaml` (`ratio_disputas_pausa`); ninguna disputa sin responder.
**Si no:** ver sección 4.6 (disputa abierta) y 4.8 (pico de reembolsos o disputas).
**Cuándo escalar:** cualquier disputa nueva (`charge.dispute.created`) exige tu respuesta dentro del plazo de `postcompra.disputa_contestar_min`; no es para la rutina semanal, es para hoy.

### 2.4 Rechazos de anuncios

```
python -m meta.monitor --oferta OF-AAAAMM-NN --ventana-h 24   [PENDIENTE: construye B5]
```
**Qué debes ver:** cero anuncios `DISAPPROVED` nuevos.
**Si no:** ver sección 4.7. Si ya van dos rechazos en 7 días para la misma oferta, el sistema se congela solo para nuevos lanzamientos (`compliance.rechazos_congelar`): no es un error, es la regla funcionando; revisa con X1/D6 antes de insistir.

### 2.5 Buzón de soporte y mensajes de la página

Esto no lo hace ningún script: revisa a mano `soporte@<dominio_oferta>` y la bandeja de mensajes de la fan page de Meta.
**Qué debes ver:** nada urgente, o pedidos de reembolso fuera de regla que ya conoces por 2.3.
**Si no:** un reclamo por no haber recibido el producto → revisa `entregas.jsonl` antes de responder (puede ser un correo en spam, no una falla real). Un reclamo que amenaza con disputa → responde rápido y con calma: una respuesta a tiempo evita muchas disputas. Una pregunta sobre el contenido que no sabes responder → no inventes: dilo con honestidad y deriva a lo que el producto sí promete (`oferta.json`).
**Cuándo escalar:** cualquier mensaje que mencione fraude, un cargo no reconocido, o amenaza legal, se guarda tal cual (sin compartir datos personales fuera de este canal) y se trata como posible disputa, no como soporte normal.

---

## 3. Rutina semanal (≈ 1 hora)

Hazla un día fijo de la semana, aparte del diario.

### 3.1 Conciliación

```
python -m datos.ledger --oferta OF-AAAAMM-NN --periodo semana   [PENDIENTE: construye B3]
```
**Qué debes ver:** `conciliacion.json` con diferencia `0` entre lo que dice Stripe, lo que dice Meta y lo que dice el ledger propio.
**Si no:** una diferencia distinta de cero **no se ignora ni se redondea**: la cifra afectada se marca tachada con la causa hasta explicarla (nunca se muestra un número sin su marca). Revisa primero compras internas o de verificación mal excluidas (deben estar fuera siempre) y huecos de webhooks (sección 4.4).

### 3.2 Lectura de F2 (el panel)

```
python -m dashboard.build --salida empresa/dashboard --oferta OF-AAAAMM-NN   [PENDIENTE: construye B10]
```
Abre el HTML generado. **Qué debes ver:** las cifras de la semana (gasto, compras netas, CPA, reembolsos, disputas) con su fecha de frescura. **Si no:** una cifra tachada con "frescura roja" significa que el dato detrás está viejo o el ETL falló: no se trata como cero, se investiga la causa (sección 4.4 si es el webhook, o el ETL de datos si es otra cosa).

### 3.3 Vencimientos de secretos y tokens

Revisa contra `docs/07` §8.2 (tabla de rotación) y lo que anote `infra/plantillas/registro-verificacion-conexiones.yaml`: token de usuario del sistema de Meta (60-90 días), `rk_*` de Stripe (90), `whsec_` (90), tokens de Cloudflare y R2 (90), HMAC propios (180). `infra.token_alerta_dias_antes` (14 días antes) debería avisarte solo, pero revisar una vez por semana es la segunda defensa.
**Qué debes ver:** nada vencido, nada a menos de 14 días sin un plan de rotación.
**Si no:** rota el secreto siguiendo `docs/07` §8.3 (nunca por un chat ni pegado en un archivo); prueba que sigue funcionando (columna "Prueba posterior" de esa tabla) antes de dar de baja el anterior.

### 3.4 X1 y sellos vigentes

Revisa que los sellos de `empresa/compliance/sellos/` que están en uso sigan con `vigencia_hasta` en el futuro. Un sello vencido no bloquea nada que ya esté `ACTIVE` (la campaña sigue corriendo), pero **sí** bloquea cualquier cambio nuevo que necesite sellarse (una landing nueva, un creativo nuevo, otra activación).
**Si no:** si un sello está por vencer y vas a necesitar algo nuevo pronto, pide a X1 que renueve antes de que haga falta, no el mismo día.

---

## 4. Incidentes

Cada incidente tiene la misma forma: **Señal** (cómo te enteras) → **Confirmar** (comando para estar seguro, no para adivinar) → **Qué hacer** → **Cuándo escalar** (a qué humano, con qué urgencia).

### 4.1 `PAUSA` (activada sola, o hay que activarla a mano)

- **Señal:** una alerta por correo o push; o `orq estado` dice que hay `PAUSA`.
- **Confirmar:** `python -m engine.orq estado --oferta OF-AAAAMM-NN --json` — revisa `avisos`. También puedes mirar si existe el archivo espejo en `empresa/PAUSA` (solo informativo: la verdad vive en el almacén del motor, no en ese archivo).
- **Qué hacer:** `PAUSA` detiene gasto, activación, publicación y reembolsos automáticos. **No** detiene la entrega de lo ya pagado ni los correos transaccionales — eso es intencional (`docs/06` R17): nadie se queda sin el producto que pagó solo porque el sistema está en pausa. Mientras esté activa, no hay nada que "arreglar" con prisa: léelo con calma y decide por qué se activó antes de tocar nada.
- **Si la activaste tú a mano** (por sospecha, por una alerta, por precaución): no hace falta nada más mientras decides.
- **Si se activó sola:** revisa qué la disparó (latido detenido, tope de gasto, guardarraíl de D8, señal de D10, deriva de hash) antes de reanudar; reanudar sin entender la causa es el error más común.
- **Reanudar:** `[DUEÑO]`, siempre con firma, siempre revalidando preflight y hashes (nunca automático, ni aunque la pausa haya sido "un error"):
  ```
  python -m engine.orq firmar --oferta OF-AAAAMM-NN --accion reactivar_tras_pausa --como dueno   [PENDIENTE]
  python -m engine.orq reanudar --oferta OF-AAAAMM-NN   [PENDIENTE]
  ```
- **Cuándo escalar:** si no puedes identificar la causa en menos de una hora, deja todo pausado (es el estado seguro) y revisa manualmente en el Administrador de anuncios de Meta y en el Dashboard de Stripe antes de reanudar.

### 4.2 Token filtrado

- **Señal:** un secreto apareció donde no debía (un chat, un log, un commit, una captura de pantalla compartida por error).
- **Confirmar:** no hace falta un comando — si lo viste, ya es cierto. No esperes confirmación técnica para actuar.
- **Qué hacer, en este orden:**
  1. **Revocar ya** el secreto en el panel del proveedor correspondiente (Meta, Stripe, Cloudflare, Railway, GitHub, correo), aunque no estés seguro de que alguien más lo vio. Revocar de más no cuesta nada; revocar tarde sí.
  2. Generar uno nuevo siguiendo `docs/07` §8.3 (por terminal propio o panel, nunca en una conversación con un modelo ni en un archivo del repositorio).
  3. Cargarlo donde corresponde (Worker, servicio de Railway, secreto de GitHub) y probar con la columna "Prueba posterior" de `docs/07` §8.2.
  4. Revisar `empresa/registro.jsonl` por si hubo uso indebido mientras el secreto estuvo expuesto (gasto, activación, reembolso que no reconoces).
- **Cuándo escalar:** si el secreto filtrado tiene permisos de escritura de dinero (`rk_reembolso`, el token operador de Meta, `rk_checkout`) y pasaron más de unos minutos antes de revocarlo, revisa manualmente el historial de la cuenta de Meta y de Stripe en busca de algo que el registro propio no haya capturado (un atacante no pasa por el motor).

### 4.3 Cuenta de Meta restringida o deshabilitada

- **Señal:** `meta.monitor` o el preflight dejan de poder leer la cuenta; o Meta avisa directamente por correo o en el Centro de seguridad.
- **Confirmar:** lectura manual, sin tocar nada: `GET /act_<id>?fields=account_status,disable_reason` (ver `docs/07` §1.2 para la tabla de `disable_reason` y qué decisión corresponde a cada código).
- **Qué hacer:** **no se opera la cuenta mientras el motivo no esté claro.** El preflight debería marcar M-01 en ROJO y, si hay campañas activas, el sistema pausa solo. Sigue la tabla de decisión de `docs/07` §1.2 según el `disable_reason` (apelar, crear portfolio nuevo, no reutilizar un método de pago, cerrar un incidente de seguridad, etc.). Nunca se oculta nada ni se intenta "esquivar" la restricción con una segunda cuenta: eso está explícitamente prohibido por los Términos de Meta y pone en riesgo todo lo demás.
- **Cuándo escalar:** `[DUEÑO]` siempre decide esto (es irreversible: cuentas y datasets no se borran ni se transfieren). No hay paso intermedio automático.

### 4.4 Webhook caído o huecos de eventos

- **Señal:** el preflight marca S-04 (huecos de eventos de Stripe) o el dashboard muestra conciliación distinta de cero; o simplemente no ves entregas nuevas aunque sabes que hubo ventas.
- **Confirmar:**
  ```
  python -m scripts.preflight --modo ligero   [PENDIENTE]
  ```
  Revisa el ítem de Cloudflare/Stripe correspondiente y, si hace falta, el panel de destinos de webhook de Stripe directamente (ahí se ve si hay reintentos pendientes o un destino deshabilitado).
- **Qué hacer:** Stripe reintenta solo hasta 3 días y permite reenviar eventos manualmente hasta 15-30 días (panel/CLI) — no se pierde nada en ese plazo, pero no hay que dejarlo así. Si el Worker `webhook-stripe` está caído, es un problema de Cloudflare/Railway, no de datos: revisa el estado del servicio antes que la base. La entrega de lo ya pagado sigue intentándose sola; si pasa `postcompra.entrega_alerta_min` sin marcar `entregado`, hay una alerta aparte (no esperes al webhook para que el cliente reciba lo que compró).
- **Cuándo escalar:** si el hueco supera las 24 h o afecta a compras reales (no de prueba), trátalo como prioridad del día, no de la semana.

### 4.5 Deriva de hash (`hash_config`)

- **Señal:** un intento de activar o de operar una campaña se rechaza porque el `hash_config` que el sistema tiene aprobado no coincide con lo que Meta devuelve en vivo.
- **Confirmar:** la salida del propio comando rechazado ya lo dice (no hace falta otra comprobación): compara el `hash_config` esperado contra el leído.
- **Qué hacer:** esto significa que algo cambió en Meta **por fuera** del flujo del sistema (alguien editó algo a mano en el Administrador de anuncios, o el conector MCP del dueño tocó algo en la sesión de Code). **No se activa con un hash distinto, nunca.** Hay que decidir cuál de las dos versiones es la correcta: si el cambio manual fue intencional y bueno, hay que volver a pasar por el flujo normal (preflight → sello → aprobación) para que el sistema lo adopte como nuevo `hash_config` aprobado; si fue un error, revertir el cambio en Meta.
- **Cuándo escalar:** cualquier deriva de hash detectada **con la campaña ya activa** (no solo al intentar activar) es más seria: alguien tocó algo mientras corría dinero real. Pausa con `empresa/PAUSA` mientras averiguas qué cambió.

### 4.6 Disputa abierta

- **Señal:** alerta por `charge.dispute.created` (dos canales).
- **Confirmar:**
  ```
  python -m postcompra.metricas --oferta OF-AAAAMM-NN   [PENDIENTE]
  ```
  y mira el panel de Stripe para leer el motivo exacto de la disputa.
- **Qué hacer:** con una disputa abierta, el reembolso automático para ese pedido se **rechaza siempre**, aunque esté dentro de garantía (una disputa y un reembolso a la vez confunden a Stripe y pierden evidencia). Arma el paquete de evidencia:
  ```
  python -m postcompra.evidencia --session cs_... --salida DIR   [PENDIENTE: construye B7]
  ```
  Este comando **no incluye datos personales** del cliente en el paquete. Responde desde el panel de Stripe dentro de `postcompra.disputa_contestar_min`, con los hechos (entrega confirmada, fecha, descriptor claro, política de reembolso visible en la landing).
- **Cuándo escalar:** si ya van dos disputas en la ventana que define `salud_operativa.*`, el sistema debería emitir `senal_pausa` y D8 pausa la oferta solo (sección 4.8). Si pasa de `ratio_disputas_pausa` de `empresa/limites.yaml`, no se reactiva sin revisar la causa raíz (producto, promesa, descriptor) con calma.

### 4.7 Anuncio rechazado (`DISAPPROVED`)

- **Señal:** `meta.monitor` lo marca en la rutina diaria (sección 2.4), o una alerta de Meta.
- **Confirmar:** la salida de `meta.monitor` trae el motivo que da Meta.
- **Qué hacer:** el sistema pausa ese anuncio solo, lo cuenta en `rechazos_7d` y abre un pedido a D6/X1 (creativos/cumplimiento) para que revisen la pieza. **No se reenvía el mismo creativo con el mismo hash** — eso sería pedir el mismo rechazo otra vez. Espera a que D6/X1 produzcan una versión corregida y vuelve a pasar por el flujo normal (lint, sello, preflight) antes de subir el anuncio de nuevo.
- **Cuándo escalar:** con `rechazos_7d ≥ compliance.rechazos_congelar`, el sistema congela lanzamientos nuevos (`empresa/PAUSA` de lanzamientos, no de lo ya activo) y baja el nivel de autonomía de D5-D9 un escalón. Es una señal de que el problema es sistemático (un claim, un formato), no de un anuncio suelto: revisa `reglas_claims.yaml` y el proceso de X1 antes de insistir con más creativos.

### 4.8 Pico de reembolsos o disputas

- **Señal:** `senal_pausa.json` con `emitida: true` y `nivel` en `amarillo` o `rojo`; o simplemente el porcentaje de reembolsos de la semana (sección 3) se ve alto.
- **Confirmar:**
  ```
  python -m postcompra.metricas --oferta OF-AAAAMM-NN   [PENDIENTE]
  ```
  Fíjate primero en `metricas.muestra_suficiente`: con pocos pagos, un solo reembolso puede parecer un porcentaje enorme sin serlo. El sistema no actúa sobre una muestra chica, y tú tampoco deberías.
- **Qué hacer:** si `nivel: "rojo"` y `accion_solicitada: "pausar"`, D8 ya pausó la campaña solo en su próximo ciclo y lo registró en `consumida_por`. Revisa el `motivo` (`disputas`, `reembolsos`, `caida_de_entrega`, `queja_de_correo`, `fraude`) para saber por dónde empezar a investigar: no es lo mismo un problema de producto (reembolsos) que uno de entrega (revisa `entregas.jsonl` antes de nada) que uno de reputación de correo.
- **Cuándo escalar:** `nivel: "amarillo"` con `accion_solicitada: "alertar"` no pausa nada todavía, pero no se ignora: es la oportunidad de corregir (ajustar la promesa, revisar el descriptor, mejorar el soporte) antes de que escale a rojo.

---

## 5. Cierre del testeo

### 5.1 Cuándo llega el cierre

El cierre no lo decides tú mirando el calendario: lo dispara el sistema cuando se agota `campana.presupuesto.dias` (el tope de días de la campaña) o se alcanza un tope sin veredicto final. En ese momento el sistema **pausa y cierra la campaña sola** (gasto = 0 desde ahí), pero **sigue leyendo** datos sin gastar (`espera_madurez.activa: true`) hasta que la última compra termine de madurar — entre el día 28 y 35 desde la activación, nunca antes, porque hace falta esperar la garantía completa más el margen. No fuerces un veredicto antes de esa fecha: `VALIDADA` no puede salir antes de `espera_madurez.hasta`, aunque todo se vea bien.

### 5.2 Comando de cierre

```
python -m engine.orq veredicto --oferta OF-AAAAMM-NN   [PENDIENTE: construye B1]
python -m engine.orq cerrar --oferta OF-AAAAMM-NN       [PENDIENTE: construye B1]
```
**Qué debes ver:** `veredicto_oferta.json` con `estado` ∈ `VALIDADA`, `PROMETEDORA`, `FALLIDA`, `INCONCLUSA` (nunca otro valor), con la evidencia (compras netas, CPA neto, cohorte madura) citada ahí mismo — nunca una afirmación sin esos números. **El primer testeo de una oferta nueva suele terminar `FALLIDA`, `INCONCLUSA` o `PROMETEDORA`: no es un fracaso del sistema, es lo esperado** (`docs/06` D-11).
**Si no:** si faltan compras netas al llegar `espera_madurez.hasta`, el veredicto sale `INCONCLUSA` por diseño, no por error.

### 5.3 Post-mortem

El cierre deja redactado un `postmortem.json` (para X2, fuera de este alcance) con lo que pasó. Léelo antes de decidir en 5.4: ahí está documentado el motivo del veredicto, no en la memoria de nadie.

### 5.4 Tu decisión: confirmar, extender o retirar

| Veredicto | Tu decisión posible | Comando | Nota |
|---|---|---|---|
| `VALIDADA` | Confirmar (siempre con tu firma, nunca automático) | `python -m engine.orq firmar --oferta OF-… --accion confirmar_validada --como dueno` `[PENDIENTE]` | Deja una propuesta registrada para D9 (escalar), que **no se ejecuta sola**: queda para después, fuera de este alcance. |
| `INCONCLUSA` | Extender una sola vez, con un tope nuevo dentro de lo que permita `empresa/limites.yaml`; o cerrar y aceptar la falta de evidencia | `python -m engine.orq firmar --oferta OF-… --accion extender_test --como dueno` `[PENDIENTE]` | Solo se puede extender **una vez**. Si la segunda ventana tampoco alcanza, no hay una tercera: toca decidir con lo que hay. |
| `FALLIDA` | Aceptarla, o reabrir si aparece evidencia nueva que la vista inicial no tenía (una `FALLIDA` con datos inmaduros puede ser un falso negativo) | `python -m engine.orq firmar --oferta OF-… --accion reabrir_fallida --como dueno` `[PENDIENTE]` | Reabrir vuelve la oferta a `en_construccion`, no la reactiva directo. |
| Cualquiera | Retirar la oferta (es la única fase sin vuelta atrás) | `python -m engine.orq firmar --oferta OF-… --accion retirar_oferta --como dueno` `[PENDIENTE]` | `retirada` es **final**; las demás fases admiten reabrir o extender, esta no. |

**Cuándo escalar:** ninguna de estas cuatro decisiones la toma el sistema por ti — todas son gates H siempre, en cualquier nivel de autonomía (`docs/06` §5, `contratos/gates.json`). Tómate el tiempo de leer la evidencia antes de firmar: una firma no se puede "deshacer" con otro comando, solo con una reapertura o una extensión que, igual que las compras, no son ilimitadas.

---

## 6. Nota de temporada: el CPM de noviembre-diciembre (Q4)

`docs/08` §6.2 y §9.1 ya lo avisan: en Q4 —con el Black Friday del 2026-11-27 como punto más alto— el costo por mil impresiones (CPM) en Meta sube, a veces bastante, por la competencia de anunciantes de temporada. El sistema **no tiene una regla especial para esto**: no existe un ajuste automático de "modo Q4" en los parámetros, y el modelo de decisión de D8 no distingue noviembre-diciembre de cualquier otro mes.

**Qué significa para la rutina diaria de este mes:**
- Un gasto más alto de lo esperado para el mismo número de clics **no es automáticamente una señal de alarma**: puede ser el CPM de la temporada, no un problema del anuncio o de la cuenta. Antes de preocuparte por la sección 2.4, compara con el CPM de referencia que tengas (si lo tienes) en vez de asumir que algo está mal.
- Si D8 decide `MATAR` un anuncio o una oferta durante este período, vale la pena leer con más atención la evidencia del veredicto (sección 5.2): un CPM alto que suba el CPA de equilibrio visto puede parecer un peor desempeño sin que la oferta en sí sea peor. El diseño incluye un caso de prueba específico para esto (`docs/06` B0-16: una celda con diagnóstico "CPM alto" que **no** debe matar), así que la regla ya está pensada para no sobre-reaccionar — pero sigue siendo prudente leer el motivo exacto, no solo el veredicto.
- El CPM real de noviembre-diciembre para este tipo de oferta es **una incógnita hasta que se mida** (`docs/08`, nota 16, M1): no hay una cifra de referencia fiable para anticiparlo. Si el primer testeo cae en este período, trátalo como una medición más incierta de lo normal, no como un mal momento para testear — es simplemente el momento en que toca.

---

## 7. Checklists citadas (no se duplican acá; se referencian para no desactualizarlas)

- **Checklist final imprimible, lista para el primer testeo en vivo:** `docs/07-puesta-en-marcha.md` §13 (bloques A-G). Es la que se usa en la sección 1.1 de este runbook.
- **Pruebas de aceptación del kill switch (A-1…A-12):** `docs/07-puesta-en-marcha.md` §9.3. Se corren antes de la primera activación real y luego una vez al mes; **A-7 es puerta, no opcional** (sección 1.1 de este runbook).
- **Prueba S-1 (corrida real mínima del runner) y E-1 (`e2e_prueba`):** `docs/09-runtime-de-agentes.md` y `docs/07` §10.3; se corren antes de dejar que un agente trabaje desatendido con dinero de verdad, y después de cada actualización de Claude Code (la sonda de hooks tiene que seguir dando `exit 2` al 100 % tras cada actualización, `docs/06` §10 riesgo 3).
- **Corte mínimo del primer testeo en vivo (qué es imprescindible, qué puede esperar):** `docs/06-bases-del-testeo.md` §8.1. Útil para no confundir "falta esto" con "esto puede esperar a N3".
- **Los 25 criterios de B0** (si todavía estás en modo prueba, no en vivo): `docs/06-bases-del-testeo.md` §6.2. Ensayar este runbook contra esos criterios, en fixture, es el simulacro recomendado antes de la sección 1.

---

## 8. Decisiones tomadas al escribir este runbook (sin dueño disponible para preguntar)

Donde el plan de la ola 0c no precisaba un detalle y había más de un camino razonable, se eligió el más conservador (fail-closed) y se deja anotado acá en vez de en un README propio (RB no es dueño de ningún directorio de código, solo de este archivo):

1. **Topología no confirmada (D-20):** se escribió la rutina diaria asumiendo "motor en Railway" (la opción por defecto propuesta en `docs/06` §4.10), con una nota explícita en la sección 0 para agregar `orq presente` si el dueño elige la alternativa de motor local. No se asumió una sin avisar que la otra existe.
2. **Todos los comandos citados se marcaron `[PENDIENTE]`** salvo los dos que ya existen y corren hoy (`python -m scripts.validar_esquemas …` y la lectura de `empresa/infra/estado.json`), verificado contra el estado real del repositorio en el momento de escribir esto (solo `contratos/`, `decision/` y `scripts/validar_esquemas.py` tienen código fuera de `__init__.py`). Prefiero marcar de más que prometer un comando que todavía no corre.
3. **No se repitió la checklist de `docs/07` §13 ni la tabla de A-1…A-12 palabra por palabra:** se citan y se resume cuándo usarlas, para que exista una sola fuente de verdad y no dos copias que alguien olvide actualizar juntas.
4. **No se inventó ninguna cifra de dinero, plazo ni porcentaje:** cada vez que este runbook necesitaba un número (tope de gasto, porcentaje de reembolso, días de rotación), remite a `empresa/limites.yaml`, `empresa/parametros.yaml` o a la tabla de `docs/07` §8.2, nunca a un valor fijo en este texto.
