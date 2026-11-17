# Entrevista del brief (≤ 10 preguntas, con defaults)

Salida: `empresa/propuestas/00-brief.<slug>.borrador.yaml` válido contra `contratos/brief.schema.json` (1.1.0). Plantillas: `templates/00-brief.*.borrador.yaml`. Validación por código: `scripts/validar_brief.py` (`references/comandos-engine-orq.md` §3). **Nada de esto crea una oferta ni asigna el `oferta_id`**: lo crea el motor (`orq crear`) después de que el dueño firma el brief (gate H).

Regla de defaults: cada default aplicado se anota en `supuestos[]` como `[SUPUESTO] <clave> = <valor> (default de <fuente>)`. Un default **nunca** contradice un límite; si la fuente del default está en `null`, la pregunta no tiene default y se pregunta (o el brief queda bloqueado). Preguntar en el idioma del dueño, una por mensaje o agrupadas; mostrar siempre el default y su fuente.

## Las 10 preguntas

| # | Pregunta (texto sugerido) | Claves del brief | Default y fuente | Validación |
|---|---|---|---|---|
| 1 | «¿Qué candidato del banco elegís?» (muestra `candidato_id`, problema en voz del cliente, macro-nicho, nivel de riesgo y reencuadre, mecanismo, entregable) | `slug` (kebab del `microsegmento`), `tema_semilla` (opcional), `nichos.permitidos` | **Sin default** (elige el dueño; gate H hasta N3). `nichos.permitidos` = los de `limites.macro_nichos_permitidos` recortados al macro-nicho elegido o más amplios, nunca más; `subnichos_prohibidos` ⊇ `limites.subnichos_prohibidos` | candidato existe en el snapshot, no ROJO, `macro_nicho` ∈ `nichos.permitidos` |
| 2 | «¿En qué idioma y mercado se lanza, y cobra en qué moneda?» | `mercado_objetivo{locale, paises_segmentacion, moneda_cobro, es_hipotesis}` | La propuesta de M1 (`ofertas/<id>/mercado.json`); sin M1 todavía, `mercado` del snapshot (`locale`, `paises`). `es_hipotesis: true` siempre salvo datos propios de ventas (`mercado.evidencia_propia`) | `locale` ∈ `limites.locales_permitidos`; países ⊆ `limites.paises_permitidos`; **evidencia del candidato en el mismo `locale`**; coincide con `mercado.json` |
| 3 | «¿Entre qué precios se vende?» | `precio_rango{min, max}` | `precio_plausible` del candidato (snapshot); sin ese dato, sin default | moneda = `moneda_cobro`; `min ≤ max`; el precio de lista de D3 caerá dentro |
| 4 | «¿Cuánto es lo máximo que aceptás gastar en total en el test de esta oferta?» | `presupuesto.test_total_max` | `economia.presupuesto_test_min` **del mercado** (D3/F1; `decision/presupuesto.py`); sin economía aún: `limites.gasto_total_test_por_oferta` y `[SUPUESTO]` «el plan real lo fija D3» | ≤ `limites.gasto_total_test_por_oferta`; moneda = `limites.moneda_limites`; ≥ `presupuesto_test_min` (si no, MAYOR: la oferta solo podría morir) |
| 5 | «¿Y lo máximo por día?» | `presupuesto.test_diario_max` | el menor entre ⌊`limites.gasto_diario_por_oferta` ÷ `limites.factor_techo_teorico_diario`⌋ y `test_total_max` | `× factor ≤ gasto_diario_por_oferta` (Meta puede gastar hasta ese múltiplo del diario); `≤ test_total_max` |
| 6 | «¿Tope de gasto en IA para esta oferta?» | `presupuesto.ia_max` | `limites.costo_max_producto` + `limites.costo_max_validacion`; si alguno es `null`, sin default | misma moneda que los otros dos topes |
| 7 | «¿Apetito de riesgo?» (conservador, moderado, agresivo) | `apetito_riesgo` | `conservador` | enum del esquema; no relaja ningún límite |
| 8 | «¿Cuántos días dura el test?» | `ventana_test_dias` | `parametros.veredicto.dias_max`, acotado al rango del esquema (5 a 30) | entero en rango; recordar `espera_madurez` (el veredicto espera la cohorte madura) |
| 9 | «¿A qué nivel de autonomía corre esta oferta?» | `nivel_autonomia` | el nivel de O0 en `empresa/autonomia.yaml` (hoy N0) | **nunca mayor** que el de `autonomia.yaml` |
| 10 | «Confirmá los datos operativos» (en bloque) | `dominio`, `cuenta_meta_id`, `canal_alertas`, `politica_ia_creativos`, `reembolso_dias`, `ventana_veto_min` (solo N4) | `dominio`: **sin default** (marca y dominio por oferta, `[DUEÑO]`). `cuenta_meta_id`: la única de `limites.cuentas_permitidas` (si hay más de una, se pregunta). `canal_alertas`: el configurado por el dueño; sin dato `[SUPUESTO] correo del dueño`. `politica_ia_creativos`: `limites.politica_divulgacion_ia`. `reembolso_dias`: `limites.politica_reembolso_dias`. `ventana_veto_min`: `limites.ventana_veto_min` | `cuenta_meta_id` ∈ `cuentas_permitidas`; `dominio` con el patrón del esquema |

Sin default por diseño: **candidato (1)** y **dominio (10)**. Todo lo demás se puede completar con «defaults» si sus fuentes existen.

## Campos que no se preguntan (los pone el código o el protocolo)

`schema_version` (vigente del esquema) · `oferta_id: OF-000000-00` y `familia_id: FAM-000000-00` (**sin asignar**, `[SUPUESTO]`: los asigna `orq crear`; el hash del contenido los excluye junto con `creado_en`, `hash` y `aprobado_por`) · `version: v1` · `origen_version` (`maker`; `humano` si el dueño edita valores) · `creado_en` (reloj UTC con `Z`) · `hash` (`validar_brief.py --calcular-hash`) · `aprobado_por` (borrador: `{tipo: humano, id: dueno, fecha: <creado_en>, firma: null}`) · `supuestos[]` (siempre ≥ 1 línea: los importes del brief son techos, el plan real sale de `economia.gasto_test_plan`).

**Variante de una oferta madre** (expansión de D9 aprobada por el dueño): `familia_id` de la madre, `mercado_objetivo` del brief hijo desde `09-escalado/expansion.json` + M1 y la línea `[SUPUESTO] variante_de: OF-…` en `supuestos[]` hasta que el esquema tenga `variante_de` (CT-3, LT-02; `dependencias.md` §B). No se reutilizan ni el dominio ni el dataset/píxel de la madre.

## Orden de validación y qué hacer con cada salida de `validar_brief.py`

| Código | Significa | Qué haces |
|---|---|---|
| `B01_ESQUEMA` | no cumple `brief.schema.json` | corrige formato; es tuyo |
| `B02_HASH` | el hash no coincide con el contenido | recalcula con `--calcular-hash`; si cambiaste contenido, `version` nueva |
| `B03_SIN_FIRMA` (aviso) | borrador sin firma | normal: solo el dueño firma |
| `B05_LIMITES` | límites ausentes/`null` (salida 5) | lista las claves y pregunta al dueño; no inventes |
| `B10_MONEDA` | moneda ≠ `moneda_limites` o mezcladas (salida 3) | **no crea nada**; pregunta al dueño; conversión solo con tipo de cambio registrado (F1) |
| `B11_TOPES` | techo sobre el límite o diario × factor > tope (salida 5) | muestra la cifra y la clave; ofrece bajar el techo (el brief solo restringe) |
| `B12_NICHOS` | nicho fuera del marco o sub-nicho prohibido quitado | corrige |
| `B13_LOCALE`/`B13_PAIS`/`B13_CUENTA` | fuera de lo permitido (salida 5) | rechazo con motivo; ampliar la lista es solo del dueño con `engine.propuestas proponer` y `sellar` |
| `B14_NIVEL` | nivel del brief > `autonomia.yaml` | baja el nivel |
| `B20`-`B24` | candidato inexistente, ROJO, fuera de macro-nicho, evidencia de otro `locale` | rechazo con motivo canónico |
| `B30_PRESUPUESTO_MIN` | `test_total_max` < `economia.presupuesto_test_min` | MAYOR: subir el techo (si cabe) o reconocimiento firmado de «solo puede morir» |

Salida del script: 0 sin errores · 2 uso · 3 validación (esquema, hash, moneda, encuadre) · 5 límites. `orq crear` repite hoy solo el esquema, la moneda y los países permitidos; el chequeo completo dentro del motor (`orq validar`, antes del gate H) es `[PENDIENTE: SB-8]` y, cuando exista, **manda sobre el script**. Ninguno de los dos asigna el `oferta_id`: nace en `orq crear`, tras el gate H.

## Prueba de la entrevista

Un brief bueno responde, en 2 minutos de lectura: qué se vende y a quién (frase del candidato), en qué mercado y por qué es hipótesis, cuánto como máximo puede perder el dueño en el test (techo, no plan) y por qué ese número, qué `[SUPUESTO]` aceptó por defecto, y qué firma falta.
