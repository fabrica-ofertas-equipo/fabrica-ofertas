# Formatos de las líneas que escribe `/cerebro-cerrar`

Todas son JSONL de una línea por registro, ASCII (JSON escapado), terminadas en `\n`, **solo agregadas**. Las escribe únicamente `scripts/guardar_pendiente.py` (valida, sanea, rechaza claves y tokens, calcula el id bajo `flock` y agrega con `O_APPEND` + `fsync`). Los textos son **datos**: se guardan limpios de controles y de caracteres de dirección, nunca se interpretan.

## 1. `pendiente` y `regla_propuesta` → `empresa/panel/pulido.jsonl` (la lista única)

Mismo formato que escribe el panel (`dashboard/pulido.py`; contrato en `dashboard/CONTRATO.md` §6). Una prueba compara byte a byte la línea del script con la del panel.

```json
{"id":"PUL-0007","ts":"2026-11-09T12:00:00Z","autor":"dueno","evento":"alta","oferta_id":null,"etapa":"D10","titulo":"Elegir proveedor de correo transaccional","detalle":"","severidad":"alta","tipo":"pendiente","estado":"abierta","responsable":"dueno","prioridad":"P1","origen":"sesión 2026-11-09 /cerebro-cerrar","bloquea":["D10","primera_venta"],"vence":"2026-11-20"}
```

| Campo | Regla |
|---|---|
| `titulo` | obligatorio, ≤ 140 |
| `detalle` | ≤ 4000 |
| `etapa` | M1, D1…D10, O0, D0, F1, F2, X1, X2 (por defecto `O0`) |
| `oferta_id` | opcional, `OF-AAAAMM-NN` o `_ejemplo` |
| `tipo` | `pendiente` o `regla_propuesta` (el script pone el que corresponde a la clase) |
| `responsable` | `dueno` · `ia` · `robot` · `otro`; en `regla_propuesta` siempre `dueno` |
| `prioridad` | P0 frena gastar o activar · P1 frena una etapa · P2 mejora · P3 idea |
| `severidad` | por defecto derivada de la prioridad (P0/P1 alta · P2 media · P3 baja) |
| `categoria` | `error` · `regla` · `pref` · `riesgo` · `contexto` (las de `docs/03-plan-de-forja-de-skills.md` §2.2) |
| `origen` | ≤ 80, letras, números y `. _ : / # @ ( ) + , § -`; por defecto `sesión AAAA-MM-DD /cerebro-cerrar` |
| `bloquea` | hasta 8 ids o etapas (≤ 40 c/u) |
| `vence` | `AAAA-MM-DD` o `AAAA-MM-DDTHH:MM:SSZ` reales |

`autor: "dueno"` significa «confirmado por el dueño»: el script no corre sin que él haya dicho que sí a esa línea. El **estado** lo cambia el dueño en el panel (línea `{"id","ts","autor","evento":"estado","estado"}`); esta skill nunca lo hace.

## 2. `decision` → `empresa/memoria/decisiones_dueno.jsonl`

```json
{"id":"DEC-0002","ts":"2026-11-09T12:00:00Z","autor":"dueno","tipo":"decision","titulo":"Una baja al día sin venta, solo si la campaña gastó su presupuesto","detalle":"«se deja un día, si el primer día no vendió, se da de baja»","alcance":"sistema","etapa":"D8","origen":"sesión 2026-11-09 /cerebro-cerrar","vigente":true,"reemplaza":"DEC-0001"}
```

`alcance`: `sistema` · `oferta` · `etapa` · `macro_nicho` · `nicho` · `locale` · `formato` · `universal`. `reemplaza` (opcional) debe existir; la anterior **no se toca**: deja de ser vigente porque una línea posterior la reemplaza. `evidencia` opcional (`[{ruta, sha256}]`, hasta 5). Una decisión ya anotada en la bitácora con tipo `decision` cuenta como guardada.

## 3. `leccion` → `empresa/memoria/lecciones.jsonl`

```json
{"id":"LEC-0001","ts":"2026-11-09T12:00:00Z","autor":"dueno","tipo":"leccion","titulo":"Medir el tiempo con la corrida en frío","leccion":"Un tiempo prometido sin medir con un novato en frío no se sostiene.","etapa":"D4","oferta_id":"OF-202611-01","confianza":"B","alcance":"solo_esta_vez","estado":"candidata","origen":"sesión 2026-11-09 /cerebro-cerrar","evidencia":[{"ruta":"ofertas/OF-202611-01/qa/d4-v1.json","sha256":"sha256:…"}]}
```

- **`evidencia` obligatoria** (≥ 1, ≤ 5): archivo **existente** dentro del repositorio; el script calcula el `sha256` (si se da uno, debe coincidir). Rutas absolutas, con `..` o de archivos `.env`, `*.pem`, `*.key`, `secretos*` se rechazan.
- `confianza`: `C` (anecdótica o externa; por defecto) o `B` (una oferta conclusiva; exige `oferta_id`). `A` (replicada en ≥ 2 ofertas) solo la asigna X2.
- `alcance` (vocabulario de X2): `solo_esta_vez` (por defecto) · `formato` · `locale` · `nicho` · `macro_nicho` · `universal`. «Universal» exige ≥ 2 macro-nichos y ≥ 2 `locale`: lo decide X2, no una sesión.
- `estado: "candidata"` hasta que X2 la valide con su ingesta (no existe aún: `dependencias.md`).
- `leccion` ≤ 280 (`afirmacion ≤ 280` de X2).

## 4. `preferencia` (la PROPUESTA) → `empresa/panel/pulido.jsonl`

Una corrección repetida (≥ 2 veces) que podría ser un criterio del dueño. Es una **regla propuesta de categoría `pref`, abierta, para el dueño**; no rige y ninguna skill la lee hasta que él la apruebe (§5). Entrada:

```json
{"titulo": "Estáticos con fondo claro", "criterio": "Los estáticos de D6 llevan fondo claro y un solo titular.", "etapa": "D6", "alcance": "formato",
 "instancias": [{"fecha": "2026-11-03", "sobre": "estatico-02", "cita": "ese fondo oscuro no, claro", "evidencia": ["ofertas/OF-202611-01/06-creativos/estatico-02.png"]},
                {"fecha": "2026-11-05", "sobre": "estatico-07", "cita": "otra vez oscuro: pon claro"}]}
```

| Campo | Regla |
|---|---|
| `titulo` | obligatorio, ≤ 140 |
| `criterio` | obligatorio, ≤ 280: el criterio en una frase |
| `etapa` | obligatoria: la etapa que lo leerá (M1, D1…D10, O0, D0, F1, F2, X1, X2) |
| `alcance` | `etapa` (por defecto) · `formato` · `oferta` (exige `oferta_id`) · `nicho` · `locale`. «universal» y «macro_nicho» los decide X2 con datos de varias ofertas |
| `instancias` | de 2 (`N_MIN_PREFERENCIA`, `[SUPUESTO]` del video 27:30, no un parámetro firmado) a 5 correcciones **distintas** |
| `instancias[].fecha` | fecha real AAAA-MM-DD, no futura |
| `instancias[].sobre` | ≤ 140: qué pieza o archivo se corrigió |
| `instancias[].cita` | las palabras del dueño, ≤ 25 palabras (200 caracteres) |
| `instancias[].evidencia` | opcional: archivo(s) del repositorio; el script calcula el `sha256` (reglas de §3). Con archivo en todas: respaldo `archivo`; en algunas: `parcial`; en ninguna: `citas` |
| `prioridad` | `P2` (por defecto) o `P3`: una preferencia nunca frena gastar ni una etapa |

Dos correcciones son «la misma» —y el script rechaza la propuesta (código 3, `correcciones_repetidas`)— si comparten fecha y pieza o si sus palabras se parecen ≥ 0,80. Con menos de 2: código 3, `pocas_correcciones`. Lo ya aprobado o rechazado por el dueño (parecido ≥ 0,80 con el criterio) o ya propuesto no se vuelve a proponer (código 5); una propuesta ya cerrada en la lista no bloquea (si la aprobó o rechazó, lo dice el buzón).

La línea que se guarda es la de una alta del panel (§1) con `tipo: "regla_propuesta"`, `categoria: "pref"`, `responsable: "dueno"`, un `detalle` legible (las correcciones con su prueba) y **una clave más**, `preferencia`, que el panel ignora al leer:

```json
{"id":"PUL-0020","ts":"2026-11-09T12:00:00Z","autor":"dueno","evento":"alta","oferta_id":null,"etapa":"D6","titulo":"Estáticos con fondo claro","detalle":"PREFERENCIA PROPUESTA (no rige hasta que tú la apruebes) · …","severidad":"media","tipo":"regla_propuesta","estado":"abierta","responsable":"dueno","prioridad":"P2","origen":"sesión 2026-11-09 /cerebro-cerrar","categoria":"pref","preferencia":{"criterio":"Los estáticos de D6 llevan fondo claro y un solo titular.","alcance":"formato","n":2,"respaldo":"parcial","instancias":[{"fecha":"2026-11-03","sobre":"estatico-02","cita":"ese fondo oscuro no, claro","evidencia":[{"ruta":"ofertas/OF-202611-01/06-creativos/estatico-02.png","sha256":"sha256:…"}]},{"fecha":"2026-11-05","sobre":"estatico-07","cita":"otra vez oscuro: pon claro"}]}}
```

`dashboard/pulido.py` **rechaza** campos extra al crear por la API, pero esta línea no pasa por la API (la escribe el script) y el panel, `scripts/alertas/hechos.py` y `resumen_abrir.py` solo leen los campos que conocen. **PEDIDO a S-A (panel):** si algún día valida las líneas al leerlas, admitir la clave opcional `preferencia` de las altas con `categoria: "pref"`.

## 5. `preferencia_resolver` → `empresa/memoria/preferencias.jsonl` (el buzón de preferencias)

La **única** forma de que una preferencia rija. Solo con las palabras del dueño (`cita`, ≤ 25 palabras) y con `--escribir`. Nada más escribe `aprobada` (lo comprueba `tests/cerebro/test_preferencias.py`). Entradas:

```json
{"id": "PUL-0020", "estado": "aprobada",  "cita": "sí, así me gusta siempre"}
{"id": "PUL-0020", "estado": "rechazada", "cita": "no, eso era solo por esta vez"}
{"id": "PRF-0001", "estado": "revocada",  "cita": "ya no, cambié de idea"}
```

Aprobar o rechazar exige una propuesta (`PUL-…`) que exista, sea de categoría `pref` con su `preferencia`, **siga abierta** y no tenga ya una resolución (código 5). Revocar exige una `PRF-…` aprobada y vigente. Líneas que escribe:

```json
{"id":"PRF-0001","ts":"2026-11-09T12:30:00Z","autor":"dueno","tipo":"preferencia","estado":"aprobada","pul_id":"PUL-0020","etapa":"D6","criterio":"Los estáticos de D6 llevan fondo claro y un solo titular.","alcance":"formato","n_instancias":2,"respaldo":"parcial","instancias":[…],"cita":"sí, así me gusta siempre","origen":"sesión 2026-11-09 /cerebro-cerrar","vigente":true}
{"id":"PRF-0002","ts":"…","autor":"dueno","tipo":"preferencia","estado":"revocada","revoca":"PRF-0001","pul_id":"PUL-0020","etapa":"D6","criterio":"…","cita":"ya no, cambié de idea","origen":"…","vigente":false}
```

- **Vigente** = `estado: "aprobada"`, `autor: "dueno"`, `tipo: "preferencia"`, con `criterio`, no marcada `vigente: false` y no referida por una `revoca` posterior. Una línea de otro autor o tipo no cuenta jamás.
- La lista única **no se reescribe** al aprobar: la propuesta (`PUL-…`) queda abierta hasta que el dueño la cierra en el panel; `/cerebro-abrir` se lo recuerda («ya resolviste N preferencia(s) pero siguen abiertas») y el jardinero lo propone.
- Nombre del archivo frente a X2: es un **buzón de entrada** (X2 pide `perfil_dueno.md`, «preferencias y criterios de elección con fecha; nunca regla ni límite»); `dependencias.md` §B.

## 6. Códigos de salida de `guardar_pendiente.py`

`0` ok (previsualizado o escrito) · `2` uso · `3` campo inválido, prueba inexistente, pocas correcciones o resolución imposible (`pocas_correcciones`, `correcciones_repetidas`, `no_es_propuesta`, `no_abierta`, `no_vigente`) · `4` parece una clave o un token (no se guarda y el mensaje no repite el valor) · `5` repetido (parecido ≥ 0,80 con algo ya guardado, o una propuesta ya resuelta) · `6` no se pudo escribir (destino no regular o enlace, archivo lleno…). Errores en stderr como JSON `{ok:false, codigo, mensaje}`.
