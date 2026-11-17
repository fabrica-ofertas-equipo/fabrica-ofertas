# Conflictos de la especificación vieja (departamentos/09, docs/06, 08, 10) y del código con J1-J4

> v0.1 sin pulir (skill 0.1.0). **Manda el dueño.** `decisiones-del-dueno.md` (J1-J21) está por encima de `departamentos/09-optimizacion.md`, `docs/06`, `docs/08` y `docs/10`; el backbone y los contratos mandan sobre los nombres y valores, pero no sobre una decisión del dueño tomada después (J2 cambia a propósito algo que el diseño original no permitía «ni con firma»). Cada fila: lo que dice la spec o el código con `archivo:línea` (verificado el 2026-11-07), qué decisión la sustituye, qué cambia para D8 y el pedido (`PEDIDOS.md`, a S-A o S-B; esta skill no edita nada fuera de su carpeta). Hasta que se resuelva, la skill sigue **J** y lo declara en el expediente.

## A. J3 (baja a 1 día, salvaguarda de presupuesto gastado, sin tope de pérdida por oferta)

| ID | La spec o el código dicen | Decisión que manda | Efecto en D8 | Pedido |
|---|---|---|---|---|
| C-01 | `departamentos/09-optimizacion.md:45`: ventana «acumulado para matar y veredicto, 3 d vs 7 d para fatiga y escala, **nunca 1 día**» (marcada «resuelto») | J3: **1 día** sin venta con el presupuesto gastado ⇒ baja | la métrica y ventana «resueltas» de la spec contradicen la regla del lanzamiento | P-03 (S-A): separar LANZAMIENTO (1 día de cuenta) de CONTINUO (tendencia de 3 días, regla de oro 3) |
| C-02 | `09:74` `testeo.ventana_no_decidir_h` = 72 («solo rigen G y K1»); `decision/reglas.py:261` y `:269`: con 0 compras solo se mata a partir de `0,5 × 72` = **36 h** | J3 decide al cierre del primer día de cuenta | el motor no puede proponer la baja antes de 36 h | P-03, P-04 (S-B): la ventana de 72 h no aplica a la baja de lanzamiento |
| C-03 | `09:111` K1: matar con «gasto ≥ `k_corte`·`cpa_be` y 0 compras»; `docs/08-protocolo-estadistico-del-testeo.md:157` (orden 2): MATAR exige gasto ≥ `k_min_matar` × BE y P(CPA > BE) ≥ 95 % | J3: «no se deja correr **hasta un umbral de plata**» | K1 es literalmente un umbral de plata; además P ≥ 95 % necesita muchas más muestras que un día | P-04: la baja de lanzamiento es una regla propia (`baja_lanzamiento`), no K1 |
| C-04 | `decision/entradas.py:301-303`: `evidencia_celda` **excluye del gasto y de los clics los últimos `estadistica.dias_madurez_compra` (3) días** (`parametros.yaml:2423`) | J3 evalúa el día 1 | con el motor actual, el día 1 de un lanzamiento es **invisible**: gasto 0, clics 0 ⇒ `SEGUIR sin_evidencia` | P-04 (S-B): la madurez de 3 días vale para las compras **de Meta**, no para el gasto ni para las ventas de Stripe |
| C-05 | `09:105` G2 (pausar si el gasto de la oferta supera `gasto_total_test_por_oferta` o `perdida_max_test_por_oferta`); `09:261` (pérdida máxima «diferida»: con `null` nada gasta); `engine/d8.py:254-257` (`ciclo` exige `gasto_total_test_por_oferta`) | J3: «sin tope de pérdida por oferta»; la acota la regla (~1 día) | si `gasto_total_test_por_oferta` se fija en 1 día para cumplir «sin tope», un **ganador** se pausa el día 2 (`INCONCLUSO`) | P-05 (S-A + dueño): significado y valores de los tres topes por oferta bajo J3 |
| C-06 | `09:83` «nunca dejar la campaña a cero sola»; `09:111` «nunca se pausa el último anuncio activo ni más de `max_pausas_dia_conjunto` (2)» | J3: la baja es de la **campaña entera** | la regla de seguridad de la spec bloquearía la baja | P-03: excepción explícita «la baja de lanzamiento J3 pausa la campaña completa» |
| C-07 | `09:81` y `09:130`: la oferta se valida en 7-14 días (`veredicto.dias_min/max`) y D7 arma el test con `campana.dias_test_defecto` = 10 (`parametros.yaml:932`) | J1: «D7 deja de ser un test estadístico de semanas» y pasa al ciclo diario | dos relojes distintos para la misma oferta | P-11 |

## B. J2 (autonomía «su modelo desde el día 1») y gates

| ID | La spec o el código dicen | Decisión que manda | Efecto en D8 | Pedido |
|---|---|---|---|---|
| C-08 | `09:181-185`: N0-N1 todo humano, pausas automáticas desde N2; `contratos/gates.json` `accion:pausar` N0=H, N1=H, N2+=A; `empresa/autonomia.yaml` D8 = N0 (`:51-54`) | J2: los robots «prenden, suben, apagan y frenan» solos desde el día 1 | **hoy toda baja la aplica el dueño** (gate efectivo H) aunque el diseño diga «pausar nunca espera a un humano» (`docs/06` §5) | P-01 (S-A): `accion:pausar` pasa a A desde N0 con las condiciones de J2 (sello X1 vigente, preflight, frenos, PAUSA, vigía, auditor) |
| C-09 | `engine/d8.py:296`: cada decisión se anota con `"gate": "A"` fijo; `ejecutor.pausar` no consulta `gates.json` | J2 conserva auditor y gates por código | el registro dice A cuando el gate vigente es H | P-17 (S-B) |
| C-10 | `09:185`: «los creativos nuevos pasan por D6 + X1 + D7 (**H para activar**)» | J2: `activar_campana` deja de ser gate H del dueño, conservando sello X1, preflight, `nivel_max_lanzable`, PAUSA, frenos | D8 no activa; el texto desactualiza la cola diaria | P-03 (S-A); la activación autónoma es de S-A/S-B (B2-03) y no es de esta skill |
| C-11 | `09:113` (E: «solo con VALIDADA confirmada por H»), `09:182` (N3: aumento solo con VALIDADA, sin plan de D9 y riesgo verde) | J2: los robots suben presupuesto solos dentro de un techo; graduación por etapas | VALIDADA (15 compras, cohorte madura día 28-35, `docs/08:345`) no es el criterio de «ganador» del ritmo diario | P-13 (S-A + dueño, B2-06): un criterio único de ganador/campeón/escala |
| C-12 | `docs/08:342` (PROVISIONAL: «se permite escalar solo un paso pequeño») contra `09:131` («PROMETEDORA… sigue optimizando creativos sin escalar. El PROVISIONAL de docs/08 = PROMETEDORA») | — (contradicción interna, brecha B2-32) | no queda claro si una oferta con cohorte inmadura escala | P-03 |

## C. J4 (frenos de empresa 300 USD/día y pausa a -3.000 USD)

| ID | La spec o el código dicen | Decisión que manda | Efecto en D8 | Pedido |
|---|---|---|---|---|
| C-13 | `09:105` G2 vigila gasto por oferta, por día y de la cuenta; **no hay regla de pérdida acumulada de cartera**. `engine/limites.py:343` comprueba `perdida_neta_acumulada_max` solo **al activar o subir**; el watchdog recibe gasto `null` | J4: «pausa automática a los 3.000 USD perdidos acumulados» | nadie dispara la pausa global por pérdida acumulada | P-07 (S-B): vigilante continuo, y una guardia G2b en D8 que escriba la pausa |
| C-14 | `limites.yaml`: `gasto_diario_global`, `perdida_neta_acumulada_max`, `moneda_limites` y todos los topes en `null` | J4: 300 y 3.000 (firma del dueño) | `engine.d8.ciclo` lanza `ErrorLimite` (5); D8 devuelve `BLOQUEADO`; la skill devuelve `NO_DECIDIR` | el dueño firma (U-01 a U-09); `engine.propuestas proponer` debe cargar J4 (B2-04) |
| C-15 | brecha E-04: «300/75 = 4 lanzamientos simultáneos» | `engine/limites.py:268-290` y `docs/06:181` suman **máximos teóricos** (× 1,75) | con 75 USD caben **2**, con 50 USD 3, con 100 USD 1 `[cálculo nuestro]` | P-05, P-12 |

## D. Ritmo de J (tanda diaria, relevos, ganador sigue, ~10 creativos)

| ID | La spec o el código dicen | Decisión que manda | Efecto en D8 | Pedido |
|---|---|---|---|---|
| C-16 | `09:83`: `max_pedidos_abiertos` = 1, `dias_entre_pedidos` = 5, `cantidad_max_pedido` = 5 (`parametros.yaml:1262-1278`) | J3: ~10 creativos por lanzamiento y «así se sigue todos los días» | un pedido abierto cada 5 días no sostiene relevos diarios | P-14 |
| C-17 | `09:112` FT: compara 3 días con el valor **inicial**; el anuncio viejo «se pausa solo cuando el reemplazo entrega y su CPA 7 d ≥ 2·`cpa_obj`» | JPS (reglas de oro 1 y 2, adoptadas por J1/J8): alarma 3 d contra los 7 anteriores; **el ganador sigue en testeo** | la skill no propone pausar el fatigado | P-09 (S-A) |
| C-18 | `09:120` etapa 0: «gasto < 50 % del presupuesto» | J3: salvaguarda «gastó su presupuesto del día» (90 % `[SUPUESTO]`) | dos umbrales de entrega con propósitos distintos y sin nombres distintos | P-02 (S-A): `testeo.entrega_baja_pct` 50 y `lanzamiento.gasto_cumplido_min_pct` 90 |
| C-19 | `parametros.yaml:917` `campana.n_anuncios_tope` = 6; D7: `CBO_1AS` de 3-6 anuncios; `meta/payloads.py` baja `n_anuncios` por `k_corte × cpa_max` | J3: ~10 creativos en una CBO | el lanzamiento J3 no cabe en lo armado | P-11 (S-A parámetro, S-B payload; la skill D7 la actualiza S-C aparte) |
| C-20 | `09:47` y `:26`: refresco = campaña REFRESCO o prueba por API; `fase` TEST/ESCALA/REFRESCO | JPS/J3: lo nuevo entra cada día en una CBO nueva, no se edita lo que aprende | el mecanismo de relevo cambia | P-03 |
| C-21 | `parametros.yaml:82` `orquestador.paralelas_max_por_nivel` = {1,1,1,2,3} | J3: lanzamientos diarios que viven ≥ 1 día | con 1 oferta en paralelo no se puede lanzar cada día | P-12 |
| C-22 | `09:261`-1: «política ante FALLIDA: pausa automática, post-mortem, reabrir solo con H»; `docs/06` §5: `fallida → en_construccion` es `accion:reabrir_fallida` (H) | J3: «así se sigue y se sigue todos los días» | una firma por cada baja frenaría el relanzamiento | P-08 (S-A + S-B) |

## E. Fuera del alcance de D8 pero que lo tocan

| ID | Dónde | Qué | Quién |
|---|---|---|---|
| C-23 | `09:84`, `09:113`; `contratos/comunes.schema.json` (`porcentaje` ≤ 100) y `limites.horas_min_entre_aumentos` (entero) | JPS: escalera ×2/×3/×5 cada 30 min y -30 %; el esquema solo admite ≤ 100 % y horas enteras (B2-09). Es de D9 y del robot de escalera | S-A/S-B (B2-09, B2-10); no es de esta skill |
| C-24 | `dashboard/web/lib/operacion.js:581-583` imprime `python -m engine.d8 reglas|veredicto`; `engine/d8.py` no tiene `__main__` (los comandos son `python -m engine.orq ciclo-d8|veredicto`) | texto del panel | S-C, otra tarea (anotado en `PEDIDOS.md` §C) |
| C-25 | J16: la factibilidad debe entregar el **CPA máximo** como umbral del test de 1 día, en vez de un veredicto con CPA, CTR y conversión no calibrados | ya pedido a S-A/S-B en `decisiones-del-dueno.md` J16; no se repite aquí | S-A/S-B |

## F. Resumen de qué hace la skill mientras tanto

LANZAMIENTO sigue J3 con `proponer.py` (en sombra); CONTINUO usa las decisiones del motor sin proponer apagar por un día suelto; FATIGA no pausa al anuncio fatigado; todo umbral ausente ⇒ `NO_DECIDIR`; y cada vez que el motor y J discrepan, el expediente lo dice y la propuesta es `NO_DECIDIR` con objeción al dueño.
