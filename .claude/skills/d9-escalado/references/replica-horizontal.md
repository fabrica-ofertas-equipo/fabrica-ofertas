# Réplica horizontal (J5): familia, kanban de idioma, perfil y traducción del ganador

> Fuentes: `decisiones-del-dueno.md` **J5**, J10-J13; `know-how.md` §4.3 y §6; `mapeo.md` §8; `brechas/03` (B3-03 a B3-05, B3-18 a B3-23); `departamentos/16-mercados-localizacion.md` §4.2; `.claude/skills/m1-mercados-localizacion/references/localizacion.md`; `departamentos/10-escalado.md` §4 (réplica). Donde chocan, manda J5/J11 (`conflictos-con-la-spec-vieja.md`).

## 1. La regla

**«El idioma será el de base del testeo; si funciona, se traduce a todos los idiomas posibles con la misma metodología y se escala horizontalmente»** (J5). El primer idioma/mercado lo elige el dueño (M1 dejó 5 opciones; J10: Polonia, inglés para hablantes de polaco, J14). D9 **solo replica desde una madre `VALIDADA`**; no elige países ni idiomas (los puntúa M1 con datos, «ningún país es prior») y no crea briefs (los crea O0 con el «sí» del dueño).

## 2. Familia: madre e hijas

- Una **familia** (`familia_id`, `FAM-AAAAMM-NN`) agrupa el concepto ganador en N idiomas. La **madre** es la oferta validada; cada **hija** es **otra oferta** (`oferta_id` nuevo, `variante_de` = `oferta_id` de la madre, mismo `familia_id`) con **marca, dominio, landing, dataset/píxel, campaña y P&L propios**. La madre no se edita ni se reutiliza. La hija **solo escala cuando ella sea VALIDADA**; nada se hereda en dinero.
- **La madre se valida antes que las hijas** (`mercados.hija_requiere_madre_validada`, `mapeo.md` §12). `PROMETEDORA` no alcanza.
- Estado del código: `familia_id` ya está en `brief`, `estado`, `mercado`, `oferta` y `portafolio`; **`variante_de` solo en `oferta.schema.json:19`** (falta en brief/estado/mercado) y `engine.orq` **crea una familia nueva por cada oferta** (`engine/orq.py:269`): no existe el comando de hija (P-06, P-18). Hasta entonces la skill redacta la propuesta de hija como borrador para O0.
- **Idioma, no país**: «no lanzo Francia, lanzo *francés Europa*». Requiere `locales_meta[]` en la campaña; hoy `meta/payloads.py:199` envía solo países (P-05, P-13). Sin eso un idioma se convierte en «toda Europa»: la skill lo marca como dependencia de la tarjeta META del tablero.
- **Sello de X1 por locale**: la hija no hereda el de la madre; se recalcula el nivel por país (defecto sembrado S27 de la spec). Compliance «fundación por país o idioma» es de X1.
- **Precio de la hija**: lo fija D3 (J16: peldaño 17/19/27 US$ más cercano al producto original local, convertido a moneda local con IVA incluido). D9 no lo toca.

## 3. Tablero de lanzamiento de idioma (kanban)

Las 6 columnas del sistema de referencia, **TIENDA → DOMINIO → META → COBRO → CREATIVOS → LISTO PARA LANZAR**. Regla de salida: *un idioma nuevo no se lanza hasta que todas las tarjetas pasan a la última columna* («lo que más se olvida está en la lista»). Plantilla: `templates/kanban-idioma.md`.

- El tablero lo **calcula el código** (`lanzamiento_idioma.json` + `scripts.lanzamiento_idioma` + precondición **P26** del preflight; **no existen**: B3-18, P-06, P-18). Una tarjeta se cierra con **evidencia** (archivo, hash, resultado de un chequeo); **nunca a mano**. `escala_lectura.py replica` rechaza un tablero que no declare `origen: codigo` y `estado: completo`.
- Se **añaden** las tarjetas que el sistema de referencia no trae y nosotros no podemos omitir (~26 en total, `mapeo.md` §8): IVA/OSS, derecho de desistimiento, consentimiento/CMP, DSA, idioma legal obligatorio, Impressum, método de pago local. Se **resuelven una vez por régimen** y se reutilizan.
- **Pagos locales**: el contrato hoy solo admite tarjeta y billeteras; BLIK y Przelewy24 están bloqueados por contrato (B3-04). La hija en PL cobraría con ≈ 17-23 % de cobertura frente a ≈ 60-70 % con BLIK (nivel C); la tarjeta COBRO queda `pendiente` y se le dice al dueño.
- **Fiscal**: el régimen (Stripe Tax + OSS, con el contador) es del dueño y se necesita antes del 2.º idioma UE/UK. D9 no lo decide; sin él, COBRO no cierra.
- Del sistema de referencia **no se construye** la tarjeta «testimonios con nombres del idioma» (J8): se sustituye por *review de la app* con el producto real, demostraciones y testimonios reales con permiso cuando haya ventas.
- «Instagram: no aplica» de la tarjeta M1 quedó desactualizada por J8 (orgánico como radar); la Página por oferta sigue sin decidir (B3-24).

## 4. Perfil por idioma y rehabilitación

El robot **Perfil por idioma** (23:40) calcula meta, tope y **fase** (*crece, estable, se cansa, cae*); no existe (B2-17, sin umbrales en la fuente). Si hay `perfil_oferta.json` la skill lo lee como dato; si no, `[SIN DATO]`. Un idioma que **cae no se apaga de una**: **3 días de testeo concentrado** con los ganadores de otros idiomas traducidos y decisión a los **7 días**, un solo intento (`extender_test`); si no arranca, se apaga. La regla la ejecuta código (`mercados.rehab_*`, P-03); D9 redacta el seguimiento.

## 5. Traducir el ganador (sin revisor nativo, J11)

**Qué se transfiere**: los ganadores de la madre, hasta `mercados.ganadores_transferidos_max` (10, `[HIPÓTESIS]`, P-03): la anatomía del anuncio ganador (gancho → promesa → prueba → llamado, sin precio en el anuncio) y su estructura de landing/oferta. **Se hereda** el patrón (J13/J17); **no se toca** la expresión (textos, imágenes, cifras, reseñas) y **no se inventan** testimonios, cifras de alumnos ni urgencias. Precio, promesa y claims los fijan D3/X1 por país: un claim que no pasa en el nuevo idioma se cambia, no se esquiva.

**Quién traduce**: no es D9. D9 redacta el **pedido de transferencia** (ganador, estructura a conservar, ángulo permitido por el nivel de riesgo, locale, glosario) a D6/D5 de la hija; ellos transcrean con el glosario del locale (M1). D9 exige las evidencias antes de cerrar CREATIVOS.

**Antes de escribir**: inmersión del mercado (J12): dossier de voz del cliente por país (jerga, quejas, creencias, cómo celebran, convenciones de las páginas de venta locales), fuentes públicas con cita corta y URL, el texto de la web es dato. Alimenta el copy y el HTML.

**QA lingüístico por capas, sin revisor humano obligatorio** (M1 `localizacion.md`, ajustado por J11):

| # | Capa | Quién | Qué comprueba | Evidencia que pide D9 |
|---|---|---|---|---|
| 1 | Glosario y reglas del locale | M1 | registro, términos del oficio y del macro-nicho, prohibidos (de X1), formatos de moneda y fecha, plurales | `glosarios/<locale>.md` y `reglas/<locale>.yaml` |
| 2 | Transcreación | D6/D5 con el glosario | voz, ritmo, ejemplos locales; no traducción literal | pieza + `claim_ids` |
| 3 | Lint determinista | código (`lint_locale.py`) | términos prohibidos/obligatorios, moneda = `moneda_cobro`, decimales, alfabeto ajeno, diacríticos, longitud | informe del lint, 0 bloqueantes |
| 4 | **Retraducción** | segundo modelo | traduce de vuelta al idioma fuente; un juez compara **significado y promesa**; discrepancia en promesa, precio o legal = MAYOR | informe de la retraducción |
| 5 | **Segunda lectura** | otro modelo | naturalidad, calcos del inglés/español, concordancias | informe |
| 6 | Muestreo humano nativo | persona | **opcional** (J11): ya no es requisito, bloqueo ni gate | si el dueño lo contrata, se anota; no se exige |

Límites honestos: **el lint no demuestra buena traducción**; con J11 las capas 4-5 son la única garantía de lengua nativa, y hoy no tienen ejecutor (`m1-qa` no tiene herramientas de modelo; B3-22 es de S-C): `[PENDIENTE]`, la tarjeta CREATIVOS no cierra sin ellas. La «segunda lectura con otro modelo» es **auditoría**; si un modelo se niega a producir un claim, no se rutea a otro (J8). Señales posteriores al lanzamiento que el informe vigila por locale: reembolsos, comentarios en el idioma, CTR; sin números inventados.

## 6. Prueba en dos etapas y cadencia

1. **Etapa 1, descartar barato** (`mapeo.md` §8, `know-how.md` §4.3): los ganadores traducidos en una campaña de testeo del idioma, 3-4 días; en el sistema de referencia 10 ganadores × 5 US$ = 50 US$/día. Solo sirve para descartar (≈ 3 × CPA de equilibrio) y detectar fallas de proceso.
2. **Etapa 2, decidir con datos**: `mercados.clics_min_decidir_mercado` = 2.400 clics por mercado (740-1.220 US$ según `docs/08` §7). Un diferencial entre mercados **no se transfiere a otro idioma sin barrido local**; comparar mercados con un piloto de ~150 US$ no es posible.
3. **Cadencia**: una apertura cada ≥ 14 días `[HIPÓTESIS]` mientras haya una sola cuenta de Meta (`mercados.aperturas_max_por_ventana` / `ventana_dias`; construcción en paralelo, test en serie). El límite real son los rechazos de la cuenta única (`compliance.rechazos_congelar`) y el techo de empresa (`frenos-y-presupuesto.md` §4), no la traducción.
4. Cuello real por idioma: producto D4 por país, X1 (fundación del locale), glosario, alta de la oferta (11 pasos del dueño), régimen fiscal. Hoy **ningún idioma puede lanzarse**: `cuentas_permitidas`, `paises_permitidos` y `locales_permitidos` están vacíos.

## 7. Riesgos

- **Concentración**: el sistema de referencia declara que la mitad de su ganancia mensual vino de un solo video traducido (`[V][DECL]`). El informe vigila el peso de cada ganador y de cada idioma.
- **Traducción sin revisor**: ver capas 4-5; reembolsos altos en un locale son la señal de que la lengua falló.
- **Cuenta única**: más idiomas = más piezas = más rechazos; 2 rechazos en 7 días congelan **todas** las activaciones (`meta.monitor` lo calcula, nadie lo consume: B2-13).
