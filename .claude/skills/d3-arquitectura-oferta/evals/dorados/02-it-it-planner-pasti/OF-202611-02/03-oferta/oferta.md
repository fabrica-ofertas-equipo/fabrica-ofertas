---
oferta_id: OF-202611-02
version: v1
moneda: EUR
precio_lista: 2490
bump_precio: 996
garantia_dias: 14
veredicto: FACTIBLE
razon: "1.46"
riesgo_nivel: verde
paises: [IT]
peor_pais: IT
marca_propuesta:       # hasta 3 (L1-13); [SUPUESTO] dominios sin verificar disponibilidad; el dueño elige UNA en el gate H antes de comprar
  - {nombre: "Menù Chiaro", dominio: "menuchiaro.example"}
  - {nombre: "Settimana in Tavola", dominio: "settimanaintavola.example"}
  - {nombre: "Lista e Menù", dominio: "listaemenu.example"}
---
# Planner Settimanale dei Pasti con Lista della Spesa — oferta v1 (borrador del Maker, pendiente del gate H)

## A. Para decidir
- **Veredicto de factibilidad: FACTIBLE** tras **1 ciclo de palancas** (precio 14,90 → 24,90 EUR). Razón 1,46 ≥ 1,3; razón_obj 0,88: sirve para testear, **no para escalar** hasta `razon_obj ≥ 1`.
- **Riesgo: VERDE** (P1 · C1 · E1 · N1; N1 por «nutrición general» vigilada, sin medir el cuerpo del comprador). Reencuadre heredado de D1 (RE-02): «Perdi 8 kg in 30 giorni» → planner + lista de la compra.
- **Gasto autorizado: NINGUNO** (`limites.yaml` en `null`). La oferta se calcula; nada gasta ni se activa hasta que el dueño fije y selle los topes.
- Pérdida máxima del test (plan, sin costos fijos): 294,00 EUR = 7 días × 42,00 EUR. Evento: Purchase.
- **Idioma:** it-IT sin revisor nativo (retraducción + segunda lectura con otro modelo); `lint_claims` de X1 aún sin reglas para it-IT [PENDIENTE: X1].

## B. Economía por mercado (salida de `engine.factibilidad`; nada calculado a mano)
| País | IVA (bp) | Meta (bp) | AOV | CPA be visto | CPA obj | CPA real central | razón | razón obj | veredicto | presup. test mín | días | pérdida máx. test |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| IT (peor) | 2200 | 300 | 25,90 EUR | 17,07 EUR | 10,24 EUR | 11,67 EUR | 1.46 | 0.88 | FACTIBLE | 263,70 EUR | 7 | 294,00 EUR |

Entradas: precio 24,90 EUR con IVA incluido + bump 9,96 EUR (40,0 % del precio) con toma del 10 %; escenarios y tasas de `parametros.yaml` sin override; tarjeta y billeteras (v1). Tarifas, IVA 22 % y recargo de Meta 3 %: **[SUPUESTO] / [VERIFICAR]** (no existe `tarifas.json`).

## C. Ciclos de palancas
| Ciclo | Palanca | Precio | Bump | razón (IT) | Veredicto |
|---|---|---|---|---|---|
| 0 | propuesta inicial en el escalón de partida | 14,90 EUR | 5,96 EUR | 0.86 | NO_FACTIBLE |
| 1 | precio (barrido de escalones por el motor) | 19,90 EUR | 7,96 EUR | 1.16 | AJUSTADA |
| 1 | precio (se elige el menor con razón ≥ 1,3) | **24,90 EUR** | **9,96 EUR** | **1.46** | **FACTIBLE** |

## D. Riesgo
| Activo | P | C | E | N | Nota |
|---|---|---|---|---|---|
| Producto, nombre, marca, subtítulo | P1 | C1 | E1 | N1 | Sujeto = el planner; verbos de la herramienta; cantidades por porción **sin valores nutricionales** (con kcal o criterio nutricional sería C2) |
| 3 bonus y bump | P1 | C1 | E0 | N1 | Sin servicio, comunidad ni asesoría nutricional |
| Ángulo «cosa-cucino-stasera» | P1 | C1 | E1 | N1 | Pregunta del propio texto del cliente, sin atributo del espectador |
Nivel = máximo = VERDE. `claims_prohibidos`: kilos, plazos, «senza dieta», «dimagrire», efectos sobre la salud. Descargo: «Strumento di organizzazione; non fornisce consigli nutrizionali né sostituisce un professionista».

## E. Supuestos y decisiones de alto impacto (para el gate H)
1. Precio 24,90 EUR (≈ 28,9 USD con EUR/USD 1,16; dentro de `economia.precio_lista_rango`). Con 14,90 la oferta no es factible en Italia con los parámetros por defecto.
2. CPM de práctica (2,10 EUR) **no es una estimación de mercado**.
3. IVA 22 % y recargo de Meta 3 % [VERIFICAR]; tipo de IVA del PDF según el contador.
4. Sin casos previos: nada de cifras de personas ni testimonios.
5. **Marca (gate H):** el dueño elige **una** de las 3 marcas neutras de la cabecera (`marca_propuesta[]`: sin claim, sin sufijos vedados, sin marcas conocidas; X1 las revisa) **antes** de comprar el dominio. D3 no compra dominio ni crea dataset; la elegida pasa a `marca` en `v<n+1>`.

## F. Declaraciones para D4, D5 y X1
- UE: la garantía de 14 días no sustituye el desistimiento legal; casilla separada de consentimiento y función de desistimiento en línea (D5/X1-J07 [VERIFICAR Directiva (UE) 2023/2673]). `boton_arrepentimiento = true`.
- Nombre y subtítulo en italiano descriptivo, sin sufijos en inglés (S17); segunda lectura nativa pendiente (backbone 5.10).

---

## Ficha della offerta (12 punti)
1. **Nome e sottotitolo.** Planner Settimanale dei Pasti con Lista della Spesa. *Cinque cene base a blocchi intercambiabili e una lista della spesa settimanale da compilare in circa 20 minuti.*
2. **Concetto.** Un pack stampabile con il metodo Pasti a Blocchi: cinque cene base che condividono gli ingredienti e una lista della spesa pronta per la settimana.
3. **Pubblico.** Chi non sa cosa cucinare ogni sera e improvvisa la spesa della settimana.
4. **Problema e fastidi.** «Ogni sera mi chiedo cosa cucinare e alla fine ordino qualcosa»; «Faccio la spesa senza un piano e metà delle cose le butto».
5. **Risultato e promessa.** Cinque cene pronte e la lista della spesa della settimana, da compilare in circa 20 minuti. Non promette risultati sul corpo né sulla salute.
6. **Contenuto completo.** Planner stampabile di 4 settimane, cinque cene base a blocchi, foglio con le quantità per porzione e lista della spesa settimanale.
7. **Moduli.** Blocchi · Calendario · Lista della spesa.
8. **Bonus (3).** Lista della dispensa base (50 voci) · Cinque menù a tema · Scheda «Cosa c'è in frigo».
9. **Vantaggi.** Meno decisioni ogni sera; una spesa con meno sprechi; un modello pronto da stampare.
10. **Obiezioni.** «Ci sono già modelli gratuiti» (differenza: blocchi con ingredienti in comune e lista della spesa già pronta) · «Mi stancherò di mangiare le stesse cene» (i blocchi si scambiano tra loro).
11. **Prezzo e garanzia.** 24,90 € (IVA inclusa), pagamento unico; extra «10 blocchi cena extra da 20 minuti» a 9,96 €. Rimborso incondizionato entro 14 giorni.
12. **Invito all'azione.** «Scarica il planner e la lista della spesa».
