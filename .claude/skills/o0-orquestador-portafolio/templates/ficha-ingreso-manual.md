<!-- PLANTILLA de la ficha de ingreso de lo hecho a mano (BC-03). Va en <DIR>/FICHA-INGRESO.md junto a los artefactos que entrarán con `orq ingresar`.
     Procedimiento: references/metodo-manual-y-ingresar.md §3. Ejemplo ficticio. -->
# Ficha de ingreso · <OF-AAAAMM-NN> · etapa <Dn> · <vN>

| Campo | Valor |
|---|---|
| Fecha y hora (UTC) | <AAAA-MM-DDThh:mm:ssZ> |
| Quién | dueno |
| `origen` | <humano (lo escribí yo) \| sesion_code (lo produjo Claude en mi sesión con conectores)> |
| Nivel de la etapa (`autonomia.yaml`) | <N0 \| N1 \| N2> |
| Skill y versión usadas | <d3-arquitectura-oferta 0.1.0 \| ninguna: a mano> |
| ¿Versión nueva de algo ya aprobado? | <no \| sí: sustituye a vN-1; dependientes pasarán a obsoletas> |

## Entradas que consumí (hash de `estado.etapas.<E>.entradas`)
| Etapa aguas arriba | `hash_salida` |
|---|---|
| <D3> | <sha256:…> |

## Artefactos (archivos sellados de la etapa, ver `cadena-y-gates.md` §1)
| Archivo (ruta canónica) | Validación local |
|---|---|
| <03-oferta/oferta.json> | <`scripts.validar_esquemas` 0 / errores> |

## Ediciones mías (categoría: `[error]` `[regla]` `[pref]` `[riesgo]` `[contexto]`)
| # | Archivo y sección | Antes → después | Categoría | Mi motivo (con mis palabras) |
|---|---|---|---|---|
| 1 | <…> | <…> | <[regla]> | <…> |

## Efectos externos y costo (nada de esto lo ve el motor solo)
- Consultas a conectores (solo lectura): <ninguna | cuáles y cuántas>
- Créditos / dinero gastados: <ninguno | monto moneda_limites y en qué> — el motor aún no lo asienta en `empresa/costos.jsonl` `[PENDIENTE: SB-10]`; cuando lo haga leerá esta sección
- Cotizado y aprobado por mí antes de gastar: <sí/no>

## Banderas de riesgo L1/L2 abiertas
<ninguna | cuáles>

## Comando (lo corro yo en mi terminal)
`.venv/bin/python -m engine.orq ingresar --oferta <OF-…> --etapa <Dn> --desde <DIR> --origen <humano|sesion_code>`   (existe; el `--origen` se acepta pero aún no se propaga)
Esperado: salida 0 · `resultado` `pendiente_firma` (gate H), `aprobado` (A/S) o `reutilizado` · `hash_salida` registrado · una línea nueva en `registro.jsonl`. Para un gate H: `orq firmar … --hash-objetivo <hash_salida> --clave-privada <RUTA que pones tú>` y repetir el mismo `ingresar`.

## Bitácora del panel (`#/pulido`)
Entrada `nota` «Ingresada a mano: <Dn> <vN>» con la ruta de esta ficha y el `hash_salida`; una `observacion` por cada cosa corregida (severidad).

## Estado del motor
<sin_ingresar | pendiente_firma: hash_salida … | ingresada: hash_salida … | rechazada (3/4): motivo …>
