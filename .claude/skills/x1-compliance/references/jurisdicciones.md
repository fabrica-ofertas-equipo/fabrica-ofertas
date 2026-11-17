# Jurisdicciones: semilla de `paises.yaml`, J01-J08 y fundación por país/idioma

**Todo lo de esta página es `[VERIFICAR]` hasta que X1 lo cierre con fuente oficial y fecha** (spec 14 Anexo B; notas 05, 07a-07d, 22e, 25 §8). No es asesoría legal. **Riesgo residual aceptado por el dueño (decisión 14): no hay revisión de abogado local por país**; X1 aplica los chequeos automáticos y la plantilla, el dueño decide con gate H y lo registra, y lo fiscal va al contador. **Ningún país es prior** (Polonia e Italia son hipótesis a probar en paralelo): sin `paises.yaml` aprobado, ningún país pasa.

## 1. Semilla por región (Anexo B)

- **UE común:** desistimiento 14 días; en digital se pierde con consentimiento expreso previo, reconocimiento y confirmación (art. 16 m CRD): casilla **separada, sin premarcar**, correo de confirmación; **botón de 2 pasos desde 2026-06-19** (Dir. 2023/2673; alcance a no UE, B) [VERIFICAR]. Información en el idioma del mercado (art. 6.7). CMP con rechazar = aceptar; OSS no-Unión sin umbral; **DSA: beneficiario y pagador obligatorios en todo anuncio nuevo o editado** (A); AI Act art. 50 (desde 2026-08-02; el 50(2) con plazo transitorio a 2026-12-02 para sistemas previos [VERIFICAR]); precio previo = el mínimo de los 30 últimos días.
- **DE / AT:** § 356 BGB y § 356a (botón), *Abmahnung*; **Impressum** § 5 DDG (AT: ECG § 5 + MedienG § 25); sin formato «curso» (FernUSG); HWG §§ 3 y 11; AT tarifa de ubicación de Meta 5 %.
- **FR:** L221-28 13°; **Loi Toubon** (francés; multa, C); mentions légales y *médiateur* [VERIFICAR]; tarifa de ubicación 3 %.
- **IT:** art. 59 lett. o Codice del Consumo; art. 54-bis función de desistimiento (fecha discrepante); la AGCM sanciona «senza dieta» y plazos; Garante: sin *cookie wall*; tarifa 3 %.
- **PL:** **Ley del Idioma Polaco art. 7a y 8**: nombres, garantías, facturas, recibos y contratos en polaco (B); BLIK/P24 no admitidos por Managed Payments.
- **ES:** art. 103 m TRLGDCU; RD 1907/1996 art. 4; tarifa 3 %. **UK:** CCR 2013 reg. 37; DMCC Act 2024; **IVA desde la primera venta**; PECR; tarifa 2 %.
- **CA:** Quebec exige francés (Bill 96; alcance a extranjeros discutido, C): segmentar aparte. **EE. UU.:** sin desistimiento federal; la garantía prometida obliga (FTC §5); 16 CFR 465, ROSCA; categoría financiera de Meta si se promociona un producto financiero.
- **LatAm:** AR 10 días + **botón de arrepentimiento** (Disp. 954/2025); MX y CO 5 días hábiles; CL 10 corridos y Ley 21.719; BR 7 días (CDC art. 49, zona gris), portugués y régimen propio; CMP opt-in en BR; sin campos DSA [VERIFICAR].

## 2. Checks de jurisdicción (nota 25 §10.3 / spec §6.1)

| Id | Comprueba | Falla si |
|---|---|---|
| J01 | **matriz país × nivel** (`matriz_pais_nivel.yaml`), **por bandera, no por macro primario** | el nivel del candidato excede el permitido para ese país × macro |
| J02 | `ayuda_por_pais.yaml` presente, de la **categoría central**, verificada ≤ `ayuda_max_antiguedad_dias` (pendiente de MINOR), «24 h» solo si la fuente lo dice | falta o vencida. **Sin ayuda verificada de la categoría, el producto no sale en ese país** (salvo 112/911). X1 no verifica los datos que él mismo cargó: la verificación la hace una **segunda persona o D10 con llamada de prueba documentada** |
| J03 | DE: sin formato «curso» ni soporte humano (FernUSG); sin asesoría fiscal individual | existe |
| J04 | ES y DE salud: ninguna pieza ni producto usa, referidos a un método o producto, los términos del RD 1907/1996 art. 4 (enfermedades transmisibles, cáncer, insomnio, diabetes…, adelgazante, utilidad terapéutica, alivio o curación cierta, respaldo de autoridades sanitarias, uso en centros sanitarios o farmacias, testimonios de profesionales o famosos, sustitución del régimen de alimentación en maternidad/lactancia/infancia/tercera edad) ni el equivalente HWG | aparece |
| J05 | UK, IT, FR, EE. UU. dinero: sin instrumento, ingresos ni inversión | existe |
| J06 | divulgación de IA y responsabilidad editorial (art. 50; `limites.politica_divulgacion_ia`) | falta |
| **J07** | checkout UE/UK: (a) casilla separada, sin premarcar, de consentimiento expreso a la entrega inmediata y pérdida del desistimiento; (b) función de desistimiento en línea de 2 pasos, visible todo el plazo; (c) correo de confirmación; (d) garantía comercial **separada** del derecho legal | falta alguno |
| **J08** | idioma obligatorio (PL, FR, Quebec); Impressum; beneficiario/pagador DSA coherente con la landing; OSS/UK VAT señalados al contador; `mp_elegible` | incumplido |

**Modos de decisión** (`desistimiento_modo`, `consent_modo`): lo más simple y estricto primero. `desistimiento_modo`: **reembolso 14 d uniforme** (por defecto) o doble casilla de renuncia. `consent_modo`: **`global_estricto`** (rechazar pesa igual que aceptar; todo apagado hasta aceptar; el píxel no dispara antes). `mp_elegible`: Managed Payments solo con producto 100 % automatizado y sin servicio humano (+ sin BLIK ni Przelewy24).

## 3. Exposición por país × nivel (semilla de `matriz_pais_nivel.yaml`, nota 25 §8.1, [HIPÓTESIS])

**V** bajo · **A** medio · **A+** medio-alto · **R** alto. El overlay **solo sube** y **no reemplaza a los lints**: un país queda restringido a verde solo si el lint de jurisdicción (J03-J05) no puede verificar la condición que causa la «R». Máximo **sin gate H**: V → hasta amarillo-b con ayuda verificada (J02); A → amarillo-a (B con gate H y ayuda verificada, **sin «revisión profesional»: texto fiel a la fuente verificado por script + gate H**); A+ → amarillo-a **solo con gate H del dueño por país × macro-nicho × nivel** (registra el riesgo residual en `empresa/decisiones_dueno.jsonl`); R → verde y solo producto de hogar sin cifra de ahorro, sin instrumento y sin ingreso.

| País | Salud | Relaciones | Dinero |
|---|---|---|---|
| Polonia | A+ | V | A+ (sin cripto) |
| Italia | A+ | A (ruptura y duelo con ayuda verificada: Telefono Amico Italia 02 2327 2327 leído 2026-11-06, reverificar antes de 2027-05-05) | A+ con J05 (sin instrumento, ingresos ni inversión) y gate H; R para ingresos e inversión |
| Rumanía | A | V (**sin ayuda de crisis verificada**) | A (segunda ola) |
| Francia | A+ | A | A+ (mismas condiciones que Italia; gate H) |
| España | R condicional a «finalidad sanitaria» (J04) | V | A+ (verificación financiera de Meta: parada dura) |
| Alemania | R para eficacia («gegen» + dolencia; solo verde hasta el gate H) | A (FernUSG si «curso») | A+ (StBerG §5: veto de ayuda fiscal personalizada) |
| Reino Unido | A+ | V | A+ con J05; R para ingresos e inversión |
| EE. UU. | A | A | A+; inversión **roja**; hipotecas LM-11 |
| Australia, Irlanda | verde y amarillo-a / como UK | verde y amarillo-a / como UK | solo verde de hogar (AU) / como UK (IE); regla de parada si Meta pide verificación financiera |
| Canadá | verde y amarillo-a | verde y amarillo-a | verde y amarillo-a; sin hipotecas |
| NZ, PT | no evaluados: heredan por analogía [SUPUESTO] | — | — |

## 4. Fundación por país/idioma (Modo D; la pide M1)

Entradas: `locale` BCP-47 y países (sin default), `empresa/mercados/atlas.json`/`ofertas/<id>/mercado.json`, notas 05, 07a-07d, 22e. Pasos y «listo»:

1. **`paises.yaml`** (`templates/paises.yaml`): por país/`locale`: `estado` (`pendiente`/`aprobado` — **solo el dueño con firma**), desistimiento, `idioma_obligatorio`, identidad del vendedor, consentimiento, IVA, `mp_elegible`, `tarifa_ubicacion_meta`, `dsa`, exposición V/A/A+/R por macro y nivel, `fuente_url`, `fecha_lectura`. Cada dato con fuente y fecha o `[VERIFICAR]`. *Listo:* ningún campo sin fuente ni `[VERIFICAR]`; `estado: pendiente`.
2. **`matriz_pais_nivel.yaml`** (J01) y **`ayuda_por_pais.yaml`** (J02: línea, `verificada_por` ≠ quien la cargó, fecha). *Listo:* cada línea con verificación de una segunda persona o llamada de D10 documentada.
3. **`terminos_sensibles/<locale>.yaml`** y `reglas_claims.yaml` (`templates/`): regex por idioma con `alternativa_segura`, `fuente`, `fecha_lectura`; ≥ 10 frases rojas por categoría e idioma y ≥ 3 verdes por macro-nicho (también para el corpus adversarial). **Con revisor nativo** (`mercado.json#revision_linguistica`): sin él, un idioma que es obligación legal da X1 ROJO. *Listo:* corre contra `evals/adversarial/corpus.json` sin falsos verdes y contra los legítimos sin falsos positivos. **Integración al linter real:** `[PENDIENTE: B6]` (`dependencias.md` D-02).
4. **Plantillas legales y banner de consentimiento: las genera el sistema** (no hay abogado); X1 solo comprueba que existan, respondan 200, estén en el idioma obligatorio y cumplan J07. 
5. **Dossier para el dueño y el contador** (`templates/dossier.md`): entidad, país de cobro y modelo de impuestos (Stripe directo + Stripe Tax, Managed Payments o MoR), IVA/OSS UE, registro UK, cruce de umbrales de ventas por país/estado (alerta de F1). X1 **no decide** lo fiscal.
6. **Gate H** del dueño para país o idioma nuevo (M1) y para cada A+ por país × macro × nivel.

**Riesgo residual sin dueño legal** (lo clasifica X1 por nivel; decide el dueño y lo registra): cualquier promesa monetaria o nicho de riesgo alto; requerimiento de autoridad, reclamo masivo o cierre de cuenta; voces o rostros parecidos a personas reales.
