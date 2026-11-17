# Ficha EU/MU y motivos de devolución (paso 1 del SOP)

> Backbone 5.11; spec §4 paso 1 y 5.11. Salida: `04-producto/verificacion.json` (`templates/verificacion.ejemplo.json`; devolución: `verificacion.devolucion.ejemplo.json`). D4 **verifica, no rediseña**: contrasta el plan con `candidato.entregable` y `oferta.mecanismo`; si falla, **devuelve sin recortar en silencio**.

## 1. Qué se comprueba

| Ítem | Fuente | Regla |
|---|---|---|
| Formato | `candidato.entregable.formato` ↔ `oferta.vehiculo.formato` | Coinciden y el archivo de cada ítem es uno de los permitidos de `formatos-de-producto.md` |
| Alcance cerrado | `entregable.alcance` | Lo entregado = lo prometido; sin «y más». `n_unidades` prometido = entregado |
| A → B demostrable | `entregable.estado_a_b` | Un paso del método lleva de A a B y está en `autoprueba.json` |
| Tiempo al primer resultado | `entregable.tiempo_al_primer_resultado` | Medido o estimado (`tiempo-y-novato.md`); cabe en `prometido_min` |
| Licencias | `entregable.licencias` | `licencias.json` cubre el 100 % |
| **Sin servicio humano, comunidad, vivo, suscripción ni mantenimiento continuo** | `oferta.bonus`, `oferta.bump`, `entregables` | **También en bonus y bump** (L1-14, `cobertura_matriz.py` y `lint_contenido.py`) |
| **MU visible y operable** | `oferta.mecanismo`, `candidato.mecanismo.prueba_logica` | El mecanismo (nombre, cómo funciona) se **ve** en el producto (sección/hoja) y se **opera** (`autoprueba.json`); el MU no es claim de salud ni de ingresos |
| Prueba de una frase | `oferta.prueba_una_frase` | Se puede escribir con el producto real: «Para [audiencia]… [MU] es [EU] que lleva de [A] a [B] sin [obstáculo]» |
| Riesgo de contenido (eje C) | `oferta.riesgo` + producto real | D4 recalcula C con el producto con `python -m scripts.nivel_riesgo`; solo puede **subir** |

## 2. Motivos canónicos de devolución (`rechazo.motivo`) y a quién

| Motivo | Cuándo | Devuelve a | Redención |
|---|---|---|---|
| `requiere_servicio` | Bonus/bump/producto exige una persona (sesión 1:1, revisión, respuesta personalizada) | D3 | Reformular sin el servicio (sustituir por guion descargable) o dividir |
| `requiere_comunidad_o_en_vivo` | Grupo privado, clase en vivo, comunidad, suscripción | D3 | Quitarlo |
| `no_producible_o_sin_licencia` | No se puede producir con licencias claras (material ajeno imprescindible, imagen sin licencia) | D1 (volver al banco) o D3 | Cambiar de entregable o fuente propia |
| `multi_mecanismo` | El producto necesita dos «cómo» distintos para cumplir | D3 | Dividir en dos ofertas |
| `sin_mecanismo` | El mecanismo no se ve ni se opera en el producto | D3/D1 | Reformular |
| `sustituto_gratis_dominante` | Un chatbot con un prompt simple da lo mismo (R5 ≤ 2 sin salida) | D3/D1 | Palanca de salida (cálculo, hoja, fuentes T1) o descartar |
| `claim_de_salud_o_ingresos` | El MU o el nombre es un claim | D3/D1 | Reencuadre seguro |
| `linea_roja_de_contenido_o_negocio` | El contenido cae en la columna «se niega» de la política | D3/D1 (X1 decide bajar nivel) | Reencuadre o descarte |
| `fuera_de_macro_nicho`, `dependencia_de_marca_personal`, `mercado_demasiado_estrecho` | Heredados de D1 | D1 | — |
| **Tiempo** (no es motivo canónico de EU) | El método no entra en `prometido_min` | D3 | Recortar alcance o prometer más tiempo (`ESCALAR` con motivo «tiempo») |

Al devolver: `verificacion.json#eu.resultado = "devuelve"`, `rechazo{motivo, detalle, destino, redencion}`, `salida_maker.estado_final = "devuelto"` y **no se produce nada más**. El % de ofertas devueltas por motivo es un KPI de D4 que alimenta a D1 y X2.
