# Escala simétrica en la misma CBO (dueño, 14-nov)

> **Reemplazada el 16-nov por la escala por campaña con el AOV de la tienda: `09-escala-por-campana.md`.** Esta página queda por la historia y por la simulación.

Pedido del dueño (14-nov): «avancemos con las reglas que estimas que son las que abarcan más situaciones y las que podrían funcionar mejor», escalando y renovando **en la misma CBO del test**, sin campañas nuevas por ahora.

## 1. La regla (la aplica `scripts/escalar_presupuesto.py`, paso 7 de la vigilancia)

| Situación (desde el último cambio de presupuesto) | Qué se hace |
|---|---|
| ROAS de Meta > 2, ≥ 2 compras, ≥ 3 h, presupuesto < 500 USD/día | **Surfeo**: +30 % en ROAS 2, lineal hasta +50 % en ROAS 6,5 |
| ROAS 1,75-2 (o > 2 con 500 USD/día o más), ≥ 2 compras, ≥ 24 h | **+30 %** |
| ROAS de **tienda** (bruto con upsells ÷ gasto) < 1,5, ≥ 3 h y ≥ 2 compras o ≥ 1,5 tickets gastados | **−30 %** en el momento, nunca bajo el presupuesto inicial |
| ROAS de tienda entre 1,5 y 1,75 | Nada |
| Meta < 1,5 sin la lectura de la tienda | Leer la tienda antes de bajar (Meta atribuye tarde) |

- Sin «tirón» de 3 h y **sin bloqueo del día**: después de bajar, si vuelve a dar ROAS > 2, vuelve a subir.
- Números redondos. No corre en el día 1 del test. Los números están en `ofertas/_funnels/reglas.json` → `escala`.

## 2. Por qué esta regla (simulación del 14-nov)

Simulador en el scratchpad de esa sesión (`escala/sim7.py`): 21 días en bloques de 3 h, compras al azar alrededor de lo esperado, ticket US$ 40, neto 92 %, fatiga de anuncios del 1,2 % diario, 400 corridas por caso. Cuatro mercados: **escala bien** (más gasto trae casi proporcionalmente más ventas), **se satura**, **techo de público** (a 500 USD/día da ROAS 1,5) y **el ROAS del día 1 fue suerte**. Tres volúmenes: 10, 40 y 260 ventas por día.

Ganancia de 21 días contra dejar el presupuesto fijo:

| Regla | «Escala bien» a 10 / 40 / 260 ventas/día | Peor caso de los otros tres mercados |
|---|---|---|
| Regla del 13-nov (surfeo > 2,5 y tirón) | ×1,34 / ×1,72 / ×2,53 | −1 % |
| Preescala de Santiago Bilbao (+30 % cada 3 h con > 2; −30 % con < 1,5) | ×1,79 / ×2,36 / ×2,30 | −0,5 % |
| Surfeo de Tomi Trimb (saltos ×2 y vuelta a la base a las 00) | ×1,13 / — / ×1,03 | 0 % |
| **Simétrica (esta)** | **×2,67 / ×3,06 / ×3,07** | **−3 %** |
| Simétrica con bajada en 1,75 | ×1,73 / ×2,16 / ×2,90 | −1,5 % |

- El tirón de 3 h era el problema a bajo volumen: con 10 ventas/día un bloque de 3 h suele tener 0 compras, el tirón se disparaba por azar y además bloqueaba el surfeo el resto del día.
- «Mantener» entre el equilibrio y 1,75 dejaba la campaña para siempre en un escalón que ganaba menos que el anterior: la bajada en 1,5 lo resuelve.
- Bajar en 1,75 es más seguro (pierde como máximo 1,5 %) pero a nuestro volumen deja la mitad de la ganancia cuando escalar conviene. Si el dueño lo prefiere: `escala.roas_bajar = 1.75` en `reglas.json`.
- Una regla «por ganancia del escalón agregado» (ROAS de lo agregado ≥ 1,3) es correcta en teoría pero ruidosa: el ROAS de lo agregado es la resta de dos números con ruido. No se usa como disparador; la revisión diaria informa la ganancia del día contra la del escalón anterior.
- Límites del modelo: curvas suaves, sin aprendizaje de Meta, sin horas buenas del día, sin topes de puja.

## 3. Lo que hacen Santiago Bilbao y Tomi Trimb (videos del 2026, transcritos el 14-nov)

- **Santiago Bilbao** (≈ 290 ventas/día): una CBO con conjunto de renovación diario y mínimo de gasto de 1 ticket 2-3 días (igual que nuestra R9); +30 % cada 2-4 h con ROAS 2-2,5; si cae, −30 % o igual; versión conservadora +20 % / −20 % / apagar con 1,8 / 1,3; escala horizontal en CBO «pocket» y otras cuentas (dice 19); bid cap = precio del producto (+30 % con backend), cost cap = CPA medio +30 %; backend con ingreso por comprador ≥ 1,5 × el precio de entrada antes de escalar; ~100 anuncios por semana (70 % variaciones).
- **Tomi Trimb** (10-23 ventas/día en su alumno): testeo, preescala ABO con tope de costo en escalera (2 a 20 USD por conjunto) y escala con CBO; «surfing» de 50 a 100, 300 y 500 en horas y vuelta a 50 a medianoche; CPA de equilibrio con 10 % de comisiones; buen CPA = mitad del equilibrio.
- Ninguno define el ROAS de equilibrio ni si su ROAS incluye upsells: sus umbrales no se trasladan tal cual. A su volumen, ventanas de 3 h tienen decenas de ventas; al nuestro, una.

## 4. Pendiente para más adelante (dueño, 14-nov: «lo de crear nuevas campañas lo podemos ver luego»)

No se hace todavía: hoy se escala y se renueva solo en la CBO del test. Para cuando haya volumen (≈ 50 compras por semana por conjunto) o el surfeo toque techo:

1. **Campaña con tope de puja en paralelo**, chica: bid cap en el precio del producto completo (+30 % si el backend sube el ingreso por comprador) o cost cap en el CPA medio de 7 días +30 %. Si no gasta, subir el tope de a poco (Santiago: de a 0,50).
2. **Preescala de Tomi**: una ABO por anuncio ganador con conjuntos de 8-15 USD y topes de costo en escalera.
3. **CBO «pocket»** con los 3-5 ganadores, y **segunda cuenta publicitaria** (aviso ya existente a 200 USD/día).
4. Medir cada una por ganancia en plata, no solo ROAS, contra la CBO principal.
