# Preguntas abiertas y supuestos (forja v0.1.0, 2026-11-06)

Se avanzó con supuestos marcados; ninguna pregunta bloqueó la v0.1.

## Preguntas bloqueantes para el dueño (cerrarlas antes de 1.0.0)

| # | Pregunta | Supuesto con el que se avanzó |
|---|---|---|
| ~~P1~~ | **RESUELTA** (spec `departamentos/00` §4, pasos 2-4): la validación en seco no crea nada; el gate H del brief va primero y el `oferta_id` nace en `orq crear` después | el borrador lleva `OF-000000-00`; el hash del contenido excluye el ID (MA-09) |
| ~~P2~~ | **RESUELTA en la spec** (paso 1): `empresa/propuestas/candidatos.<slug>.json` con `oferta_id: OF-000000-00`; tras `orq crear` entra como salida de D1 con `orq ingresar --etapa D1` y el `oferta_id` real (S-B copia y reescribe el ID: SB-8 `[PENDIENTE]`) | el modo A lo recibe por ruta; el validador lo acepta de donde venga |
| P3 | Pérdida máxima por oferta (`perdida_max_test_por_oferta`) y `perdida_neta_acumulada_max` | diferidos: todo `null` ⇒ nada gasta |
| P4 | Horas semanales de revisión, ofertas en paralelo, día de la propuesta | sin respuesta ⇒ nada nuevo se gasta |
| P5 | ¿El clic del botón vale como firma del brief en N4 (C03)? | no: hoy el clic no firma |
| P6 | Topología: ¿motor en Railway o local?; canal de alertas ajeno a Railway/Cloudflare; `ventana_veto_min` | ninguna: la skill no asume topología; lee el estado de los archivos que le pasen (`docs/06` §4.10 exige escribir una de las dos antes de la ola 1) |
| P7 | `moneda_limites` y tipo de cambio; política de IA en creativos; cuenta de Meta deshabilitada (apelar o abandonar, nunca abrir otra para esquivarla) | el brief exige `moneda_limites` ≡ moneda del presupuesto |
| P8 | Aprobar o recortar las 30 líneas rojas, las cuotas amarillas y las zonas cerradas | `lineas_rojas: []` hasta que confirme |
| P9 | `ratio_disputas_pausa`: `"0.006"` (spec) frente a `"0.005"` (nota 25 §9) | no se cita ningún valor |
| ~~P10~~ | **RESUELTA**: `scripts/nivel_riesgo.py` existe; el subnivel A\|B sale de los ejes (o de los colores: ≥ 2 amarillos = B `[SUPUESTO]`); ya no rige «todo amarillo = B» | — |

## `[SUPUESTO]` principales de la skill
- Borrador del brief en `empresa/propuestas/00-brief.<slug>.borrador.yaml` con IDs sin asignar y `aprobado_por.firma: null` (cumple «Write solo `00-brief*` y `empresa/propuestas/`»).
- Defaults de la entrevista derivados de claves de `limites`/`parametros` (`brief-entrevista.md`), nunca de números del texto.
- `proximo_paso.py` replica la tabla de gates y las dependencias de `docs/contratos.md` como ayuda más detallada que `orq siguiente` (que existe y manda si difieren).
- Nivel del brief comparado con el de **O0** en `autonomia.yaml` (el spec no dice con cuál etapa).
- Propuesta semanal `.json` sin esquema validable.

## `[VERIFICAR]`
Ver `dependencias.md` §C.
