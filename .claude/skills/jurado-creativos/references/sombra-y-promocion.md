# Sombra y promoción

El jurado nace **en sombra**: predice, se compara con lo cobrado y no decide nada. Gana peso solo si demuestra acertar más que el azar y que la rúbrica del QA, y solo con la firma del dueño. Esto es lo que lo mantiene honesto: la fuente (JPS) no muestra ninguna validación del suyo (solo «7/10 comprarían» y una anécdota).

## 1. Dos modos (y uno apagado)

| Modo | Qué hace | `aplica_orden` | Quién lo aplica |
|---|---|---|---|
| **`sombra`** (por defecto) | produce `jurado.json` con orden, bandas y avisos; se calibra; **no se usa** para nada | `false` | nadie: es información |
| **`asesor`** | además el **código de la cola/de la tanda** puede usar el `orden` para llenar los cupos del test y ordenar la carga cuando hay más candidatos aprobados que cupos (`n_anuncios_max`) | `true` | el código, no el jurado |
| **`apagado`** | el jurado no corre (`paquetes.py armar` se niega) | `false` | la calibración, sola |

**Lo que el jurado NUNCA hace, en ningún modo:** decidir gasto, subir o bajar presupuesto, apagar o pausar un anuncio, activar una campaña, saltarse QA-A, el lint, el sello de X1 o el preflight, aprobar una pieza o excluirla del test por sí solo. No existe un tercer modo «decide». Incluso en `asesor` las piezas del fondo del orden **no se descartan**: van más tarde o a la reserva, y las reglas de diversidad de la tanda (≥ 3 ángulos, un solo cambio por vez) y los frenos J3/J4 siguen mandando.

## 2. Cuándo se pasa de sombra a asesor

Las seis condiciones, todas (las evalúa `calibrar.py`; el resultado es `estado_global = elegible_asesor`):

1. **≥ 150 etiquetas** (`n_min_etiquetas`) en el nivel principal, de **clics o más maduro**.
2. **Supera al azar**: AUC ≥ 0,60, IC95 entero por encima de 0,5 y p < 0,05 contra el azar.
3. **Supera a la rúbrica sin perfil** (`rubrica_unica`): diferencia de AUC > 0 con DeLong pareado p < 0,05, con ≥ 150 piezas puntuadas por ambos.
4. **Anclas**: en ≥ 60 % de las tandas con ambas anclas, la ganadora queda sobre la perdedora (margen ≥ 0,2), y **hubo al menos una tanda con un ancla medida** (con solo controles sintéticos no se promueve).
5. **Sin contradicción de ventas**: si el nivel `ventas` ya tiene ≥ 150 etiquetas, es él quien decide (y puede apagarlo).
6. **La firma del dueño** en `promocion.json` (`templates/promocion.json`): `aprobado_por`, `fecha`, `calibracion_sha256` (hash de la calibración vigente) y `revisar_en`.

`agregar.py --modo asesor --promocion … --calibracion …` verifica 6 contra 1-5: el archivo sale `asesor` solo si la calibración vigente es `elegible_asesor`, del mismo mercado, con el hash de la promoción y la promoción no caducada; cualquier otra cosa lo deja en `sombra` y dice por qué (`modo_motivo`). Si la calibración siguiente deja de ser elegible, **vuelve solo a sombra**; si dice `apagar`, queda `apagado`. La promoción **caduca** en `revisar_en` `[SUPUESTO: ≤ 4 semanas]` y hay que volver a firmarla con la calibración del momento.

## 3. Qué NO justifica una promoción

- Un AUC alto con menos de 150 etiquetas; un IC que incluye el azar; empatar con la rúbrica (el jurado cuesta ~10 veces más tokens que un evaluador único: si no gana, no se justifica).
- Etiquetas de `inversion` o `gancho` presentadas como «predice ventas».
- Un orden que «se ve bien»; el entusiasmo de un avatar; que las anclas sintéticas se separen.
- Una calibración de demostración o de fixture (`valido_para_decidir: false`).

## 4. Apagado y reactivación

`apagar` = con ≥ 150 etiquetas, AUC ≤ 0,5 o ni el extremo optimista del IC95 llega a 0,60. Efecto: `paquetes.py armar --calibracion <última>` se niega («jurado APAGADO»); no se gastan más tokens. Reactivar es una decisión del dueño (`--reactivado-por`), queda registrada en el manifiesto y debería ir acompañada de un cambio real (nueva voz del cliente, otros avatares, otra consigna): reactivar el mismo panel con los mismos datos es repetir lo que ya falló.

## 5. Qué se ve en la pantalla

`#/jurado` ya muestra «Papel del jurado: En sombra», los votos, el orden y la precisión con la regla de 150. Hoy la pantalla decide «útil» solo por `auc ≥ 0,6` y dice «los primeros salen antes a la prueba» sea cual sea el modo: debería leer `modo`, `aplica_orden` y `precision.estado` (pedido en `PEDIDOS.md` #4). Mientras tanto, el archivo no miente: en sombra `aplica_orden` es `false` y el esquema lo exige.

## 6. Etapas de uso del orden (propuesta para el piloto)

1. **Sombra pura** desde la primera tanda real: votar, sellar, esperar 3 días, etiquetar. Cada semana sin sombra es una semana sin etiquetas (el calendario no se compra).
2. **Sombra visible**: el dueño ve el orden en el panel pero decide como siempre.
3. **Asesor** (solo con §2 completo): el código llena cupos con el orden.
4. No hay etapa 4.
