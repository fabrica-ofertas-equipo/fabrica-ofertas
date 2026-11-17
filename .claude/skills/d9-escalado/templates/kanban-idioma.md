# Tablero de lanzamiento de idioma — <hija: oferta_id · locale> (madre: <oferta_id · locale>)

> v0.1 sin pulir. **El tablero lo calcula el código** (`lanzamiento_idioma.json` + `scripts.lanzamiento_idioma` + precondición P26 del preflight: **aún no existen**, `PEDIDOS.md` P-06 y P-18). Esta plantilla es lo que el Maker **copia** de esa salida. **Regla: nunca se marca una tarjeta a mano.** Una tarjeta sin evidencia (archivo, hash, resultado de un chequeo) está `pendiente`. Sin el código, el tablero entero va `[SIN DATO: tablero no calculado]` y `escala_lectura.py replica` responde `NO_PROPONER`.
> **Regla de salida (J5):** un idioma nuevo no se lanza hasta que **todas** las tarjetas pasan a LISTO PARA LANZAR. Los ids son los del panel (`dashboard/web/lib/paises.js`, 25 tarjetas); `origen` = «suya» (del sistema de referencia) o «nueva» (la añadimos nosotros por lo legal y fiscal que su método no trae).

## Precondiciones de la familia (las comprueba `escala_lectura.py replica`)
| Precondición | Valor | Fuente |
|---|---|---|
| Madre `VALIDADA` (J5) | <sí/no> | `ofertas/<madre>/08-operacion/veredicto_oferta.json` |
| `variante_de` = madre · mismo `familia_id` · `locale` distinto | <sí/no> | brief/oferta de la hija (borrador para O0) |
| `locale` ∈ `locales_permitidos` y países ⊆ `paises_permitidos` | <sí/no> | `empresa/limites.yaml` (lo firma el dueño) |
| Cadencia de aperturas (`mercados.aperturas_max_por_ventana` en `ventana_dias`) | <ok/no> | `parametros.yaml` + historial de aperturas |
| Ganadores a transferir ≤ `mercados.ganadores_transferidos_max` | <n> | banco de creativos de la madre |
| Régimen fiscal del grupo de países cubierto (C4) | <sí/no> | dueño + contador |

## Columnas y tarjetas
Estado de cada tarjeta: `hecho` (con evidencia) · `pendiente` · `bloqueado` (con el pedido que lo bloquea).

| Col. | Id | Tarjeta | Origen | Evidencia que la cierra | La calcula | Estado |
|---|---|---|---|---|---|---|
| TIENDA | T1 | Tienda del idioma creada desde la plantilla (hija = oferta nueva, landing y catálogo propios) | suya | `05-landing/` de la hija, sello del sitio | código | |
| TIENDA | T2 | Textos, correos y legales en el idioma (idioma legal obligatorio, Impressum si aplica) | suya | informe del lint + capas 4-5 del QA lingüístico (`replica-horizontal.md` §5); **revisor nativo opcional (J11)** | código + IA | |
| TIENDA | T3 | Después de la venta: entrega, soporte y reembolso en el idioma | suya | plantillas E0…En del idioma (D10); entrega probada | código | |
| TIENDA | T4 | Producto del idioma producido y verificado (D4) | nueva | `04-producto/producto.json` con sha256 | código | |
| DOMINIO | D1 | Dominio propio del idioma comprado y activo | suya | alta de la oferta (paso del dueño) | humano + código | |
| DOMINIO | D2 | Dominio verificado en Meta | suya | `infra/alta.json` | humano + código | |
| DOMINIO | D3 | Sitio sin hallazgos de seguridad | suya | informe del chequeo de código | código | |
| META | M1 | Página publicada (Instagram: tarjeta desactualizada por J8) | suya | decisión del dueño sobre la Página | humano | |
| META | M2 | Reloj del mercado definido (una sola cuenta de Meta) | suya | `mercado.json` | código | |
| META | M3 | Medidor de Meta y conversiones por servidor, con permiso del visitante | suya | `tracking.json`, dataset/token | humano + código | |
| META | M4 | **Filtro de idioma en cada conjunto** (`locales_meta[]`: P-05, P-13) | suya | `campana.json` + `lectura_viva.json` | código | |
| META | M5 | Anunciante declarado (DSA) y salud de la cuenta | nueva | preflight VERDE < 6 h | código | |
| META | M6 | Enlaces de anuncio con etiqueta propia (UTM) | suya | lint de D7 | código | |
| COBRO | C1 | Precio local con IVA (J16: peldaño 17/19/27 US$ convertido) y cuentas que cierran | suya | `03-oferta/oferta.json` + `economia.json` | código | |
| COBRO | C2 | Medios de pago coherentes con la moneda (BLIK/P24 bloqueados por contrato: B3-04) | suya | `mercado.json#metodos_pago` | código | |
| COBRO | C3 | Pantalla de pago y compra en el idioma y la moneda | suya | compra de prueba hecha por el dueño | humano | |
| COBRO | C4 | Régimen fiscal del grupo de países cubierto (OSS/Stripe Tax; contador) | nueva | firma del dueño por país | humano | |
| COBRO | C5 | Desistimiento (UE/UK) y garantía comercial separados | nueva | lint de X1 | código | |
| CREATIVOS | K1 | Ganadores de la madre traducidos (transcreación) con QA por capas | suya | pedido de transferencia + evidencias de las capas 1-5 | IA + código | |
| CREATIVOS | K2 | **Prueba social real o ninguna** (sin testimonios inventados, J8) | suya | solo reseñas reales con permiso, o «ninguna» | código + humano | |
| CREATIVOS | K3 | Incluye el ganador del momento de la madre | suya | el campeón vigente | código | |
| CREATIVOS | K4 | Calidad de idioma auditada (retraducción + segunda lectura) | suya | informes de las capas 4-5 (`[PENDIENTE]` ejecutor: B3-22) | IA + código | |
| LISTO | L1 | Auditoría completa: sellos de X1 vigentes **del locale** (no heredados), preflight verde | suya | `empresa/compliance/sellos/` + `preflight.json` | código | |
| LISTO | L2 | Apertura del idioma firmada por el dueño | nueva | orden firmada (`lanzamiento_pais_idioma_nuevo`) mientras sea H | humano | |
| LISTO | L3 | Testeo prendido | suya | `ids_meta.json`, campaña ACTIVE (poscondición) | código | |

Recuento calculado por código: <n>/25 hechas · <n> pendientes · <n> bloqueadas. ¿Puede lanzarse? <sí/no>. Bloqueos y pedido que los resuelve: <…>.

## Seguimiento del idioma (después de abrir)
Fase del perfil por idioma: `<crece|estable|se cansa|cae|[SIN DATO]>` (robot de 23:40: no existe). Si **cae**: 3 días de testeo concentrado con ganadores traducidos y decisión a los 7 días, un solo intento (`mercados.rehab_*`, P-03); lo ejecuta código. Señales de lengua por locale: reembolsos <…>, comentarios en el idioma <…>, CTR <…> (sin cifras inventadas).
