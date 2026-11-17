# Control de calidad de 6 puntos (`scripts/qc6.py`): el L1 de código del tramo B

Brecha B1-17. La fuente revisa cada pieza «cuadro por cuadro» con seis puntos y dos estados (OK / REV; la leyenda es ilegible). Aquí hay un chequeo de código con **tres estados por punto y por pieza**: `ok` · `revisar` · `falla`. Corre con lo que ya está instalado en esta Mac: Vision de macOS (OCR y personas), `ffmpeg`/`ffprobe`, `whisper-cli` + el modelo de `~/.cache/whisper`, `pdftoppm`. Sin red, sin gasto, sin claves.

**Regla de oro:** nunca hay un verde sin comprobar. Si un motor no existe, el punto sale `revisar` con la causa. `revisar` no es un fallo: es «lo mira una persona o el QA».

## 1. Los 6 puntos

| Punto | Qué comprueba | Cómo | `ok` | `revisar` | `falla` | Check del QA |
|---|---|---|---|---|---|---|
| **QC1 · Audio** (solo video) | Sin cortes ni desfases; audio = guion | `ffprobe` (duraciones), `ffmpeg silencedetect` (−35 dB, ≥ 0,6 s), `whisper-cli` contra la línea hablada del guion | desfase ≤ 0,3 s, sin pausas interiores, similitud con el guion ≥ 85 % | video sin audio; desfase 0,3-1 s; pausa interior 0,6-2 s; cola muda ≥ 2 s; similitud 60-85 %; sin whisper | archivo ilegible; el guion tiene voz y no hay audio; desfase > 1 s; pausa ≥ 2 s; audio mudo con voz esperada; similitud < 60 % | D6-L1-07 |
| **QC2 · Idioma** | Un solo idioma de punta a punta | Idioma del audio (whisper) y del texto de pantalla y del copy (palabras función + caracteres del idioma) frente al `locale` | todo en el idioma del `locale` | mezcla de dos idiomas; texto demasiado corto para decidir | el audio o el texto están en otro idioma | D6-L1-06 |
| **QC3 · Texto** | Texto en pantalla sin errores | OCR de Vision por cuadro (video a ≤ 1 fps, PDF por página) contra `copies.json › texto_en_pieza`; mojibake | cada texto esperado aparece tal cual y no hay texto sobrante | solo coincide sin diacríticos; letras sueltas distintas (¿errata?); líneas que no están en el copy; sin copy esperado; sin OCR | un texto esperado no aparece; caracteres corruptos (�, Ã©) | D6-L1-06 |
| **QC4 · Caras y manos** | Presencia de rostros, personas y manos | Vision (`qc6_personas.swift`) en hasta 12 cuadros | ninguna detectada | hay manos o personas (revisar anatomía, etiqueta de IA, labios); sin detector | hay personas o rostros en **salud o relaciones** (solo producto, hojas o manos: SKILL regla 5) | D6-L1-07 |
| **QC5 · Material ajeno** | Sin logos ni marcas detectadas por texto | Texto de pantalla, audio y copy contra marcas de terceros, medios, marcas de agua de stock, ™/®, enlaces y @usuarios; `--prohibir` (nombres de referentes) | nada ajeno | marca de tercero (mención nominativa), ™/®, enlace o @usuario; sin texto | marca de agua o crédito de stock, logo de medio, o un nombre de `--prohibir` | D6-L1-08 |
| **QC6 · Precios y promesas** | Sin precios ni promesas prohibidas | `qc6_reglas.py` (red multi-idioma de las listas de claims rojos de D5/D6), `compliance.lint_claims` (si hay reglas del `locale`), claims prohibidos de la oferta, importes contra `precio_visible` y el precio de la oferta | ningún patrón y el precio, si está, es el de la oferta con `precio_visible` | patrón amarillo; hay un precio y no se sabe si el anuncio debe mostrarlo | patrón rojo; precio con `precio_visible = false`; precio distinto al de la oferta; un claim prohibido de la oferta | D6-L1-02 |

La pieza queda en el **peor** de sus seis puntos. Las seis columnas de la fuente («Cuadro 1 / Texto / Voz / Idioma / Música / Final») no se replican: la unidad aquí es el punto, con la evidencia del cuadro en `evidencia`.

## 2. Cómo se usa

```bash
# una pieza (flags útiles: --copies, --guion, --oferta-dir, --html-fuente, --prohibir, --permitir, --precio-visible, --precio, --presentador)
.venv/bin/python .claude/skills/d6-creativos/scripts/qc6.py pieza ofertas/<id>/06-creativos/assets/<ad_name>.png \
  --locale pl-PL --ad-name <ad_name> --copies ofertas/<id>/06-creativos/copies.json --oferta-dir ofertas/<id> \
  --html-fuente ofertas/<id>/06-creativos/assets/src/<ad_name>.html --prohibir "Lingua Chiara" --json

# todo un paquete (lee paquete.json, copies.json, matriz.json, guiones/ y la oferta)
.venv/bin/python .claude/skills/d6-creativos/scripts/qc6.py lote --oferta-dir ofertas/<id> \
  --salida ofertas/<id>/06-creativos/qc6.json --salida-l1 ofertas/<id>/06-creativos/qc6-l1.json

# qué motores hay en esta máquina
.venv/bin/python .claude/skills/d6-creativos/scripts/qc6.py motores
```

Salida 0 si no hay `falla`; 3 si la hay (con `--estricto`, también si hay `revisar`); 2 por uso incorrecto.

### Salida y relación con `qa/.l1/`

`--json` devuelve `{herramienta, modo, resumen, piezas[{pieza, estado, puntos[6]}], checks_l1[]}`. `checks_l1[]` tiene la forma exacta de `contratos/qa.schema.json#checks_l1` (`check_id`, `resultado` ∈ `pass | fail | no_aplica`, `detalle`) y usa los ids de `rubric.md` §2: `ok` → `pass`, `falla` → `fail`, `revisar` → `no_aplica` (**no cuenta como verde**, y el detalle empieza con «REVISAR»). `--salida-l1` escribe `{"checks": […], "origen": "qc6"}`, la misma forma que D5 propone para `qa/.l1/d5-v<n>.json`. El Maker no puede escribir en `qa/.l1/`: **el runner (S-B) corre `qc6.py lote` antes del QA tramo B y deja ese archivo** (`PEDIDOS.md` #9). El QA lo trata como una afirmación a re-verificar por muestreo, igual que `lint-x1.json` (`rubric.md` §2).

### Modo `--simular`

`--simular` no ejecuta **ningún** proceso externo: los motores devuelven lo que diga `--simulado datos.json` (`ocr`, `personas`, `sonda`, `silencios`, `transcripcion`). Sirve para probar el contrato y el cableado en una máquina sin Vision ni ffmpeg, y para correr solo el lint del copy (sin `--simulado`, los puntos que necesitan un motor salen `revisar`). El resultado lleva `modo: simulado` y **no es evidencia**: todos sus `checks_l1` salen `no_aplica` con el prefijo «SIMULADO», y `tanda.py bandeja` lo rechaza.

## 3. Lo que `qc6` no hace (límites honestos)

- **Caras y manos bien hechas** no se juzga con código: solo se marca la **presencia**. La calidad (dedos, simetría, ojos, piel plástica) sigue siendo la lectura visual del QA con las anclas de R5.
- **Sincronía de labios** (UGC con presentador) y de música no se mide. El audio se compara con el guion por texto, no por tiempo palabra a palabra.
- **Logos e imágenes ajenas dentro de una imagen** solo se detectan si tienen texto. El origen de las imágenes se verifica con `licencias.json` (D6-L1-09) y a ojo.
- **OCR de Vision pierde algunos diacríticos.** Medido el 2026-11-07: lee la `ż`/`Ż` polaca como `z` (el resto de `ąćęłńóśź` bien). Por eso, para una pieza de Ruta A, `--html-fuente` (o `lote`, que lo toma de `assets/src/`) confirma los diacríticos contra el HTML que generó el PNG; sin él, el punto sale `revisar`. En Ruta B (texto dentro de imágenes generadas) un `revisar` por diacríticos es una señal real. El OCR con diacríticos de otros idiomas (`ă ș ț`, `ñ`, `ß`) no está medido: `[NO VERIFICADO]`.
- **whisper puede inventar texto sobre música o silencio.** Un audio sin voz da una transcripción vacía o corta; si el guion no tiene línea hablada, la transcripción solo alimenta QC2, QC5 y QC6.
- Las listas de `qc6_reglas.py` son `[HIPÓTESIS]` sin revisión de un nativo y no sustituyen a `compliance.lint_claims` ni al veto de X1; cubren it, pl, fr, de y ro, que el lint oficial cubre solo en parte (pedido #11). Un ROJO nunca se arregla cambiando palabras.
- Umbrales (0,3 s, 1 s, −35 dB, 0,6/2 s, 60/85 %, 0,88) son `[SUPUESTO]`: se calibran con piezas reales al pulir; cada falso positivo o negativo que encuentre el dueño pasa a un caso de `tests/creativos/test_qc6.py`.
- Compila `scripts/imagenes/ocr_vision.swift` y `scripts/qc6_personas.swift` con `swiftc` en el directorio temporal la primera vez (≈3 s cada uno). Solo macOS. El runner (`herramientas.yaml`) no ve esas llamadas internas; si no puede compilar, los puntos salen `revisar`.

## 4. Adaptador de OCR para `scripts.creativos.ocr_check`

`qc6.OcrVision(locale)` implementa el `Protocol MotorOCR` (`reconocer(ruta) -> str`) de `scripts/creativos/ocr_check.py` sobre Vision. Con eso la CLI de S-B puede dejar de salir 2 «sin motor OCR real»: `ocr_check.main(argv, motor=qc6.OcrVision("pl-PL"))`. Cablear una opción `--motor-ocr vision` es de S-B (`PEDIDOS.md` #9); está probado en `tests/creativos/test_qc6.py`.

## 5. Pruebas

`.venv/bin/python -m unittest tests.creativos.test_qc6` (≈30 s). Motores falsos para cada estado de cada punto; el modo simulado con `subprocess.run` y `shutil.which` bloqueados; y, si la máquina los tiene, **pruebas con motores reales sobre archivos generados en la prueba**: PNG de la Ruta A (`render_estatico.py`), video con `ffmpeg` (audio continuo, sin audio, corte de 3 s, audio más largo que el video, archivo corrupto), voz de `say` transcrita con `whisper-cli`, PDF de Chrome leído con `pdftoppm`.
