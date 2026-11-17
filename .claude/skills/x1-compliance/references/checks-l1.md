# Checks L1 (deterministas), CLI real y qué cubre hoy el código

Fuente: spec 14 §6.1 y nota 25 §10.3. **L1** = dos ejecuciones dan el mismo resultado sin juicio. **L1p+L2** = el patrón deja falsos negativos y se completa con juicio **citado**. **L2/L3** = juicio o visión. El 100 % de bloqueantes se exige solo a los L1. Ids canónicos: `L1-01…14`, `L1-PUB`, y por eje `L1-HWR-<id>` (en prosa `X1-P01`).

## 1. Comandos reales (verificados contra `compliance/*.py` el 2026-11-06)

| Qué | Comando (raíz del repositorio, `.venv/bin/python`) | Salida | Quién lo corre |
|---|---|---|---|
| Lint de claims | `python -m compliance.lint_claims (--archivo F \| --oferta OF --etapa E) --locale L [--macro-nicho M] [--json]` (el envoltorio `scripts/lint_claims.py` hace lo mismo pero falla sin `PYTHONPATH`) | 0 verde/amarillo · **3 rojo, reglas alteradas, locale sin reglas o archivo ilegible** · 2 uso | **el código** (`lint-x1.json`); el Maker lo corre solo si el hook lo admite (D-06) y el QA **lo lee, no lo corre** |
| Lint por etapa | `--oferta OF-AAAAMM-NN --etapa D3` lintea los archivos sellados de la etapa (`ARCHIVOS_SELLADOS` de `scripts/validar_esquemas.py`: D2 `validacion.json`; D3 `oferta.json`+`economia.json`; D5 `assets.json`, `checkout.json`, `tracking.json` y `rutas.json` **y el sitio servido** (`DIRECTORIOS_SELLADOS`); D6 `paquete.json`; D7 `campana.json`) | igual | igual |
| HTML | `python -m compliance.html_checks --archivo sitio/index.html [--locale L] [--macro-nicho M] [--json]` | 0 · 3 rojo · 2 | **el código** (`lint-x1.json`); la forma `python -m` no está en la allowlist de agentes (`dependencias.md` D-06) |
| Sello | `python -m compliance.sellar --oferta OF --etapa-objetivo E --artefacto RUTA --dictamen qa/x1-<e>-v<n>.json --locale L [--macro-nicho M] [--object-ids a,b] [--vigencia-dias N] [--live]` | dry-run por defecto; `--live` escribe `empresa/compliance/sellos/<hex>.json` con **Ed25519** (`--clave-privada` del dueño; HMAC solo pruebas) | **nunca el agente** |
| Verificar sello | `python -m compliance.verificar --hash sha256:<hex> [--artefacto-sha256 H] [--object-ids …]` | imprime el sello vigente o **sale 4** | motor, hooks y humano |
| Ejes → nivel | `python -m scripts.nivel_riesgo --P P2n --C C1 --E E0 --N N1 --reencuadre --json` (la única implementación) | `nivel`, `subnivel`, `colores`, `veredicto_riesgo` | Maker; al QA le llega calculado en `lint-x1.json` |
| Dictamen válido | `.venv/bin/python .claude/skills/x1-compliance/scripts/validar_dictamen.py RUTA` | 0 · 3 · 2 | Maker (antes de entregar) |
| Copia K02 | `python3 .claude/skills/x1-compliance/scripts/ngrama_copia.py --propio A --referencia B` (umbral = `compliance.ngrama_copia_palabras`) | 0 · 3 coincide · 2 | Maker y QA |

**Nota de nombres:** la spec dice `compliance.sellar --etapa`; el código real es `--etapa-objetivo`. **Cómo distinguir un «3» del lint:** léelo en el mensaje: `semáforo=rojo` (hallazgo real) ≠ `locale sin reglas de cumplimiento: it-IT` (no hay reglas: **no es un pase**, no se puede sellar) ≠ `hash_contenido no coincide` (reglas alteradas: el lint NO corre). Ante duda, falla cerrado.

**Lo que el lint hace:** busca léxico de cura/plazo (salud), verbos de cambio sobre el cuerpo o el dinero (finanzas), garantías absolutas, urgencia falsa y prueba social fabricada, por `locale` (hoy es-ES, es-AR, es-MX, en-US, it-IT, pl-PL, ro-RO, fr-FR y de-DE en `compliance/reglas_sensibles.yaml`, más `empresa/compliance/terminos_sensibles/<locale>.yaml` como léxico aditivo; la categoría `relaciones` ya tiene léxico). `claims_prohibidos`, `claims_a_evitar` y `campos_prohibidos` no se lintean bajo esa clave exacta, pero su misma frase en otro campo da ROJO. `patron_clave` sale como `categoria:hash` (con `:` y `_`): **para el dictamen conviértelo a kebab** (`:` y `_` → `-`), porque `qa.schema.json` exige kebab.

## 2. Checks por id

| Id | Verifica | Falla si | Cobertura del código hoy |
|---|---|---|---|
| L1-01 | esquema, hash, firma | hash del artefacto ≠ el del dictamen o sello; sello vencido o de otra versión | `compliance.sellar/verificar`, `validar_esquemas`: sí |
| L1-02 | cobertura | regla sin estado (ni probada ni retirada) | no |
| L1-03 | linter reproducible | dos corridas dan ROJOS distintos | sí (determinista); correr dos veces y comparar |
| L1-04 | frescura de políticas | política sin URL/fecha o más vieja que `compliance.edad_max_politica_dias` | no |
| L1-05 | mercado | país o `locale` fuera de `paises.yaml` aprobados o de `limites.paises_permitidos`/`locales_permitidos`; edad < 18; nivel > `nivel_max_lanzable` o > exposición del país (J01) | no: `paises.yaml` no existe; `limites` vacíos ⇒ ningún país pasa |
| L1-06 | urgencia | temporizador o «quedan N» sin modo real; JS (`setInterval`, `Date`, `localStorage`), CSS/JS huérfano de cupos o notificaciones | parcial: `html_checks` ve `countdown` sin fecha verificable y escasez/«quedan N» fija sin `data-cupos-verificable`; **no** ve `setInterval` suelto |
| L1-07 | consentimiento | píxel/CAPI antes del consentimiento | `html_checks`: sí (casilla premarcada, píxel antes de consentir, píxel en `<head>` sin condición); Playwright cuando D0/D5 lo habiliten |
| L1-08 | identidad y legales | falta razón social, contacto, privacidad, términos, reembolso, desistimiento o Impressum; enlace ≠ 200; legales fuera del idioma obligatorio | `html_checks`: las siete rutas `/legal/*`; el 200 lo comprueba el preflight |
| L1-09 | IA | fotorrealista sin etiqueta o `c2pa_preservado = false`; soporte con IA sin aviso | no (`assets.json`: `ia_generado`, `etiqueta_ia_visible`, `c2pa_final`: leer) |
| L1-10 | coherencia | precio, moneda, promesa, `claim_id`, descriptor o garantía distintos entre anuncio, landing, producto y checkout; enlaces de anuncio sin los parámetros de 5.2-5.3 o con términos sensibles | parcial: `validar_esquemas` X06/X14/X19 |
| L1-11 | reseñas | reseña sin `compra_id`; cifra escrita a mano | no |
| L1-12 | bitácora y salud | cadena de la bitácora rota; salud más vieja que `compliance.salud_max_antiguedad_h` | parcial: `compliance.salud` (`python -m compliance.salud evaluar`) decide la salud y la frescura; la cadena de la bitácora no tiene código |
| L1-13 | claims | claim sin `claim_id` o con evidencia más vieja que `compliance.edad_max_evidencia_claim_dias` | no |
| L1-14 | post-compra y activos | correo de marketing sin opt-in/baja; activo sin licencia; respuesta automática que no es plantilla aprobada | no |
| **L1-PUB** | publicación de landing (antes del gate H) | (a) «EJEMPLO», «DEMOSTRACIÓN», «TESTIMONIOS DE EJEMPLO» o `lorem`, **también en comentarios HTML**; (b) opiniones sin `compra_id` (si no hay, se omiten); (c) cifra sin traza a `producto.json` o `trazabilidad.md`; (d) garantía ≠ política de reembolso o < desistimiento de la jurisdicción; (e) «se puede vender lo que creás / generar ingresos» (P2n); (f) el **mecanismo único** (nombre, H1, marca, dominio) es claim de salud o ingresos (P07) | **(a) sí** (`html_checks`: `html:plantilla-sin-reemplazar`); **(b)-(f) no**: `Grep` (§3) |

## 3. Greps del QA para lo que el código no ve (reproducibles)

Corre con `Grep` y cita archivo:línea:
- L1-PUB (a): `EJEMPLO|DEMOSTRACI|lorem|TESTIMONIOS DE EJEMPLO` (sin distinguir mayúsculas) sobre `05-landing/sitio/**` **incluidos comentarios**.
- L1-06: `setInterval|setTimeout|Date\(|Date\.now|localStorage|sessionStorage|countdown|quedan|restan|últim|only \d+ left` sobre `**/*.html` y `**/*.js`.
- Cifras de clientes escritas a mano (L1-11, P08): `\d[\d.,]*\+?\s*(personas|clientes|alumnos|ventas|reseñas)` y `★|⭐|5 estrellas`.
- Afiliados (N01): `aff=|ref=|affiliate|utm_source=(?!meta)` en enlaces del entregable.
- Eventos y URL sensibles (D01): lee `tracking.json#eventos`, `rutas.json` y los `utm_*`; compara con `terminos_sensibles/<locale>.yaml`.
- Mejoras de Meta (L1-10, P16): `meta_enhancements` en `paquete.json`; `text_optimizations`, `image_touchups`, `image_animation`, `inline_comment`, `enhance_cta` en `campana.json` deben estar en `OPT_OUT`.

## 4. Por eje (nota 25 §10.3; ids `L1-HWR-*`)

| Eje | Ids y tipo |
|---|---|
| P | P01 L1 (léxico de cura y plazo de resultado; no dispara si el plazo es del formato, «plan de 14 días») · P02 L1p+L2 (cifra + unidad + plazo con el lector como sujeto) · P03 L2 (garantía atada a un resultado) · P04a L1 (reseñas sin `compra_id` o con cifras) / P04b L3 (testimonios, antes/después, capturas en imágenes) · P05 L1 (escasez, contador y precio de referencia contra `oferta.json#urgencia`) · P06 L1p+L2 (claims fisiológicos) · **P07 L1 (detiene y decide una persona**: verbo de cambio con el producto de sujeto, o nombre de estado en producto, método, marca, Página o dominio) · P08 L1 (toda cifra de clientes, ventas o estrellas la genera un script) |
| C | C01 L1p+L2 (dosis, medicación, kcal, ayuno, LC-10) · C02 L1p+L2 (diagnóstico, IMC, quizzes clínicos) · C03 L2 (instrumento con verbo de acción, tasa histórica como expectativa) · C04 L2 (documentos legales personalizados; plan de salida) |
| E | E01 L1p+L2 (atributo del espectador y autopercepción negativa, en cualquiera de las cadenas del §2.2 de `criterio-riesgo.md`) · E02 L2 (espectador ajeno) · E03 L1p+visión (menores) · E04 L1 (segmentación: intereses sensibles, lookalike, edad < mínima) |
| N | N01 L1 (afiliado, comisión, enlace a proveedor financiero) · N02 L1p+L2 (servicio humano o conexión entre usuarios) · N03 L1p+L2 (multinivel, reventa) · N04 L1p+L2 (bonos, bumps, bots: nivel = máximo de todos) · N05 L1 (descriptor y catálogo contra `perfil_stripe.yaml`) |
| Datos | D01 L1 (slug, URL, UTM, `content_name` y eventos sin términos sensibles) · D02 L1p (quiz con puntaje que envía un estado) · D03 L1 (restricciones de datos activadas, consentimiento UE/UK) · D04 L1 (ninguna lista de compradores hacia plataformas; recibo y asunto neutros) |
| Jurisdicción | J01 matriz país × nivel (por bandera) · J02 ayuda del país vigente · J03 DE sin formato curso · J04 ES/DE salud sin RD 1907/1996 art. 4 ni HWG · J05 UK/IT/FR/US dinero sin instrumento ni ingresos · J06 divulgación de IA · J07 checkout UE/UK (casilla separada sin premarcar, correo, desistimiento de 2 pasos, garantía comercial separada) · J08 idioma obligatorio, Impressum, DSA, OSS/UK VAT, `mp_elegible` → `jurisdicciones.md` |
| Coherencia | K01 L1+L2 (igualdad de `claim_id`, precio y moneda entre anuncio, landing, producto y descriptor) · K02 L1p+L2 (≥ `ngrama_copia_palabras` palabras idénticas con un competidor o con **todo texto rechazado** por Meta, Stripe o X1, en cualquier oferta o idioma) · K03 L1 (rastreo diario del sitio vivo: compara el texto visible con el hash sellado; deriva) |
| Multimodal | M01 L1p (OCR de cada fotograma a 1/s y de cada imagen; los lints P, E, C corren sobre ese texto) · M02 L1 (transcripción del audio final vs guion sellado) · M03 L3 (clasificador visual: cuerpos, básculas, píldoras, efectivo, rostros angustiados, menores) · M04 L1 (XLSX/ODS/Sheets: fórmulas, hojas ocultas, macros, comentarios, enlaces externos) · M05 L1 (PDF: texto oculto o blanco, enlaces, metadatos) |

Los checks sin herramienta determinista (OCR, transcripción, visión, K03 con JavaScript, M04, M05) son **[PENDIENTE: los construyen B4/B6/D5/D6]**; mientras tanto, el QA los hace como L3 con `Read` sobre los archivos y **lo declara en `checks_l1[].detalle`** (`no_aplica` solo con razón escrita; nunca `pass` sin haberlo corrido).
