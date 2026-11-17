---
oferta_id: OF-202611-03
version: v1
moneda: PLN
precio_lista: 8900
bump_precio: 3560
garantia_dias: 14
veredicto: FACTIBLE
razon: "1.41"
riesgo_nivel: verde
paises: [PL]
peor_pais: PL
marca_propuesta:       # hasta 3 (L1-13); [SUPUESTO] dominios sin verificar disponibilidad; el dueño elige UNA en el gate H antes de comprar
  - {nombre: "Pytania na Wieczór", dominio: "pytanianawieczor.example"}
  - {nombre: "Karty Rozmów", dominio: "kartyrozmow.example"}
  - {nombre: "Wieczorne Rozmowy", dominio: "wieczornerozmowy.example"}
---
# Karty Rozmów dla Par — oferta v1 (borrador del Maker, pendiente del gate H)

## A. Para decidir
- **Veredicto de factibilidad: FACTIBLE** tras **1 ciclo de palancas** (precio 49 → 89 zł). Razón 1,41 ≥ 1,3; razón_obj 0,84: sirve para testear, **no para escalar** hasta `razon_obj ≥ 1`.
- **Riesgo: VERDE** (P1 · C1 · E1 · N1). Reencuadre heredado de D1: «karty na randki» (facilitación de citas, N2) → «karty rozmów dla par, które mieszkają razem». Sin «randki» en nombre, subtítulo, ángulos ni landing.
- **Gasto autorizado: NINGUNO** (`limites.yaml` en `null`).
- Pérdida máxima del test (plan, sin costos fijos): 1.120,00 PLN = 7 días × 160,00 PLN. Evento: Purchase.
- **Mercado/idioma:** pl-PL exige polaco en toda la documentación al consumidor y revisor nativo (`mercado.revision_linguistica.obligacion_legal_idioma = true`); `lint_claims` de X1 sin reglas para pl-PL ni léxico propio de «relaciones» [PENDIENTE: X1].
- **BLIK diferido:** v1 calcula con tarjeta y billeteras; con BLIK la cobertura en Polonia sería mucho mayor [VERIFICAR 07g].

## B. Economía por mercado (salida de `engine.factibilidad`; nada calculado a mano)
| País | IVA (bp) | Meta (bp) | AOV | CPA be visto | CPA obj | CPA real central | razón | razón obj | veredicto | presup. test mín | días | pérdida máx. test |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| PL (peor) | 2300 | 0 | 92,56 PLN | 62,55 PLN | 37,53 PLN | 44,44 PLN | 1.41 | 0.84 | FACTIBLE | 938,25 PLN | 7 | 1120,00 PLN |

Entradas: precio 89 zł con IVA incluido + bump 35,60 zł (40,0 % del precio) con toma del 10 %; escenarios y tasas de `parametros.yaml` sin override. Tarifas, IVA 23 % y tipo de cambio USD/PLN 3,72: **[SUPUESTO]** (no existe `tarifas.json`).

## C. Ciclos de palancas
| Ciclo | Palanca | Precio | Bump | razón (PL) | Veredicto |
|---|---|---|---|---|---|
| 0 | propuesta inicial en el escalón de partida | 49 zł | 19,60 zł | 0.76 | NO_FACTIBLE |
| 1 | precio (barrido de escalones por el motor) | 69 zł | 27,60 zł | 1.08 | AJUSTADA |
| 1 | precio (se elige el menor con razón ≥ 1,3) | **89 zł** | **35,60 zł** | **1.41** | **FACTIBLE** |

## D. Riesgo
| Activo | P | C | E | N | Nota |
|---|---|---|---|---|---|
| Producto, nombre, marca, subtítulo | P1 | C1 | E1 | N1 | Sujeto = las cartas; «para parejas que conviven» es rol en tercera persona; sin «randki» ni promesas sobre la relación |
| 3 bonus y bump | P1 | C1 | E0 | N1 | Sin servicio, comunidad ni terapia |
| Ángulo «pytanie-na-wieczor» | P1 | C1 | E1 | N1 | Sin atributos ni preguntas sobre el estado de la pareja |
Nivel = máximo = VERDE. Todo producto de conflicto de pareja o familia (también VERDE) lleva el aviso de seguridad y la línea de ayuda del país.

## E. Supuestos y decisiones de alto impacto (para el gate H)
1. Precio 89 zł (≈ 23,9 USD con USD/PLN 3,72; dentro de `economia.precio_lista_rango`). Con 49 zł la oferta no es factible con los parámetros por defecto y tarjeta.
2. CPM de práctica (8,00 zł) **no es una estimación de mercado**.
3. Texto polaco sin revisión nativa todavía: bloquea el primer lanzamiento en polaco (M1/D6).
4. Sin casos previos: nada de cifras de personas ni testimonios.
5. **Marca (gate H):** el dueño elige **una** de las 3 marcas neutras de la cabecera (`marca_propuesta[]`: sin claim, sin sufijos vedados, sin marcas conocidas; X1 las revisa) **antes** de comprar el dominio. D3 no compra dominio ni crea dataset; la elegida pasa a `marca` en `v<n+1>`.

## F. Declaraciones para D4, D5 y X1
- UE: garantía de 14 días ≠ desistimiento legal; casilla separada y función de desistimiento en línea (D5/X1-J07 [VERIFICAR]). `boton_arrepentimiento = true`.
- **Aviso de seguridad y ayuda (D4/D5, X1-J02):** «Jeśli obawiasz się o swoje bezpieczeństwo, nie korzystaj z tego materiału» + línea de violencia en la pareja de Polonia **800 120 002** (verificada por la nota 25 §7; reverificar ≤ 180 días).
- Descargo: «Materiał edukacyjny; nie jest terapią, diagnozą ani poradą prawną». 18+.

---

## Karta oferty (12 punktów)
1. **Nazwa i podtytuł.** Karty Rozmów dla Par. *50 kart z pytaniami do wydruku, w trzech poziomach, i zasada rozmowy na zmianę na wieczór we dwoje.*
2. **Koncepcja.** Zestaw do wydruku z metodą Rytuał Jednego Pytania: jedna karta na wieczór, trzy poziomy pytań i zasada rozmowy na zmianę.
3. **Odbiorcy.** Pary, które mieszkają razem i rozmawiają głównie o obowiązkach i rachunkach.
4. **Problem i frustracje.** «Rozmawiamy tylko o rachunkach i o tym, kto zmywa»; «Wieczorem każde siedzi w telefonie i nie wiemy, od czego zacząć rozmowę».
5. **Rezultat i obietnica.** Zestaw kart gotowy do wydruku i pierwsza rozmowa w około 15 minut. Nie obiecuje poprawy związku ani żadnego rezultatu.
6. **Pełna zawartość.** 50 kart z pytaniami w trzech poziomach głębokości oraz krótka instrukcja rozmowy na zmianę.
7. **Moduły.** Poziom 1 (lekki) · Poziom 2 · Poziom 3 (głębszy).
8. **Bonusy (3).** Tablica rytuału tygodniowego · 10 kart na wspólną podróż · Plakat A4 z zasadami rozmowy na zmianę.
9. **Korzyści.** Prosty początek rozmowy; kolejność pytań od lekkich do głębszych; zestaw gotowy do wydruku.
10. **Obiekcje.** «Są darmowe listy pytań» (różnica: trzy poziomy i zasada rozmowy na zmianę) · «Czy to nie jest terapia?» (nie; to materiał edukacyjny do rozmowy).
11. **Cena i gwarancja.** 89 zł (z VAT), płatność jednorazowa; dodatek «20 dodatkowych kart: wspólne plany» za 35,60 zł. Zwrot płatności bez warunków w ciągu 14 dni.
12. **Wezwanie do działania.** «Pobierz karty do wydruku».
