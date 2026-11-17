"""Elige el país de destino con números y sin caer siempre en el mismo.

Historia:
- v1 (2026-11-12): pedido del dueño «crea algo para no tirar siempre en el mismo mercado».
- v2 (2026-11-13): tras «¿con qué criterio se eligió este mercado nuevamente?». México había ganado solo por un cobro
  puesto de memoria; ahora el cobro sale de Impul Pay, el castigo por repetir crece y se imprime la sensibilidad.
- v3 (2026-11-13): «no dejes afuera países por no producir en esos idiomas, no nos limitemos». Todos los países donde
  se puede cobrar entran, en cualquier idioma (Impultienda arma la tienda en ~50 idiomas y Gemini escribe y locuta en
  todos ellos). Se suman: CPA observado en nuestros tests, poder de compra, temporada, abandono del referente y una
  regla de exploración.
- v5 (2026-11-14): tras «¿por qué Oferta D se corrió en el mismo mercado donde pauta la original, con 127 anuncios?».
  La presencia del referente era un PESO (hueco 0 contra 1): cuando pautaba en todos los países medidos, el hueco daba 0
  en todos, dejaba de distinguir y ganaba México por cobro. Ahora es un VETO: un país donde el referente tiene anuncios
  activos (en cualquier idioma) sale del orden, también en ofertas nuevas. Si no queda ningún país libre, el script no
  recomienda nada y sale con código 3: la oferta se DESCARTA y se vuelve a buscar-ofertas (no se elige «el menos malo»).
- v6 (2026-11-14): «57 no son todos los países del mundo… ampliala, revisá qué países tendría sentido correr ofertas
  teniendo en cuenta Impul Pay (Whop) y Stripe». La lista pasa de 57 a 93 países (+36). Criterio para entrar: Meta
  pauta ahí; Whop no lo bloquea por sanciones (ni es Benín); hay al menos tarjeta; y o el cobro es razonable (≥ 0.6),
  o el mercado es grande (≥ 20 M en línea) y con poder ≥ 0.15. Cobro releído en el panel (lista de 37 métodos de
  Impul Pay, 14-nov) y en la documentación de Stripe para una cuenta de EE. UU. La columna `cobro con Stripe`
  (STRIPE_MEJORA) dice cuánto sube el cobro con Stripe.
- v6.1 (2026-11-14): el dueño tiene cuenta de Stripe (EE. UU.) y la regla es «tener como válido Stripe y solo
  conectarlo en las tiendas que vamos a lanzar con método de Stripe» (nunca en una tienda apagada o por archivar).
  STRIPE_DISPONIBLE = True: el orden ya cuenta lo que suma Stripe. Si el ganador gana gracias a Stripe, el script
  imprime «REQUIERE STRIPE»: en la fase de tienda se conecta Stripe en las tiendas de ESA oferta (y solo en ellas)
  y se prenden sus métodos locales. Sin Stripe ese día (no se pudo conectar), se vuelve a ordenar con --sin-stripe
  y se toma ese ganador: nunca se lanza un mercado de Stripe sin Stripe.
  Fuera a propósito (ver FUERA): sancionados por Whop, China (Meta no llega), países con control de cambios que
  traba la tarjeta internacional, mercados chicos (< 0.5 M en línea) o con cobro y poder muy bajos.

Qué mide (pesos: lectura del asistente, no del dueño; se cambian aquí):
  VETO (v5)         país con anuncios activos del referente (cualquier idioma) → fuera del orden, sin excepción.
  hueco 40 %        entre los que quedan: 1; ×0.8 si el referente pautó ahí y se fue (inactivos > 0, activos 0).
  tamaño 20 %       población con internet, escala log.
  competencia 15 %  misma frase del producto traducida en cada país (anotada en "consulta_competencia").
  cobro 20 %        tabla COBRO (Impul Pay leído el 2026-11-13 + hábito de pago local; ver notas de cada fila).
  poder 5 %         poder de compra (PIB per cápita PPA, orden de magnitud): ¿un PDF de 13-27 USD es compra de impulso?

Ajustes multiplicativos:
  repetir país      ×0.6 por cada vez en las últimas 4 ofertas. Si el país ya dio un test rentable contra Meta
                    (neto > gasto en ofertas/_funnels/libro-de-tests.json) el castigo es ×0.8 por vez: repetir lo que
                    funciona es razonable, repetir por costumbre no.
  repetir idioma    ×0.9 por cada vez de más en las últimas 3.
  exploración       si las últimas 3 ofertas fueron a países ya usados antes, el mejor país NUNCA probado se marca como
                    «exploración recomendada» (se le avisa al dueño aunque no gane).

Datos de apoyo que se imprimen al lado (no suman, informan):
  CPA observado por país (libro de tests), «r» económico (scripts/mercados, CPA/neto, menor es mejor), temporada
  (si la fecha de inicio cae en una ventana de compras fuerte: CPM más caro y más ruido de ofertas).

Uso:
  python3 elegir_mercado.py plantilla > ofertas/_borrador-<slug>/modelado/mercados.json
  python3 elegir_mercado.py ordenar ofertas/_borrador-<slug>/modelado/mercados.json [--inicio AAAA-MM-DD] [--oferta "<nombre en el libro>"]
      --oferta (v4, 14-nov; réplica de una oferta ya lanzada, regla E6): saca del orden los países donde corre el referente según
      ficha.referente_paises del libro de tests (buscar-ofertas/scripts/paises_referente.py) y los que esa oferta ya usa.
      --medicion M.json (v5): completa "referente" de cada país con una medición de paises_referente.py
      ({"paises": {"US": 147, ...}, "sin_anuncios": [...]}) para no medir dos veces.
  Salida: 0 con recomendado; 3 = DESCARTAR (el referente corre en todos los países medidos y no falta medir ninguno);
  4 = ningún país medido queda libre pero faltan países por medir (medirlos antes de descartar).
  python3 elegir_mercado.py cobro     # tabla de cobro con su origen y lo que suma Stripe
  ... ordenar ... --sin-stripe        # orden solo con Impul Pay (cuando Stripe no se pudo conectar en la tienda)
  python3 elegir_mercado.py historial # CPA observado por país

Por país hay que medir: "referente" (anuncios activos del referente que llegan), "referente_idioma_local",
"referente_inactivos" (opcional), "competencia" y "consulta_competencia", y dejar "medido": true. Medir todos es
mucho: medir primero los 12-15 mejores por tamaño, cobro y poder (orden de la plantilla) y ampliar si el primero sale
frágil.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[4]
HIST = RAIZ / "ofertas" / "historial-modelado.json"
LIBRO = RAIZ / "ofertas" / "_funnels" / "libro-de-tests.json"
ECON = RAIZ / "scripts" / "mercados" / "resultados" / "escenarios.json"
REGLAS = RAIZ / "ofertas" / "_funnels" / "reglas.json"


def bloqueados_por_meta() -> dict:
    """{país: motivo} donde Meta no deja crear conjuntos sin anunciante y pagador verificados (reglas.json → meta).
    Oferta J se armó entera para Singapur el 14-nov y quedó trabada en el último paso."""
    try:
        m = json.loads(REGLAS.read_text(encoding="utf-8")).get("meta") or {}
    except Exception:
        m = {}
    if m.get("anunciante_verificado"):
        return {}
    return {c: "Meta exige anunciante verificado (reglas.json → meta.anunciante_verificado)"
            for c in m.get("paises_exigen_verificacion") or ["SG", "TW", "TH", "MY", "AU", "IN"]}

PESOS = {"hueco": 0.40, "tamano": 0.20, "competencia": 0.15, "cobro": 0.20, "poder": 0.05}

# (pais, idioma de la tienda, moneda, online_m, poder 0-1, cobro 0-1, origen del cobro)
# cobro: 1 = el medio que el comprador local más usa está en Impul Pay (o la tarjeta domina); 0.8 = tarjeta y PayPal
# en país donde la tarjeta es común pero falta un medio local fuerte; 0.6 = solo tarjeta donde la tarjeta es minoría
# relevante; 0.4 = falta el medio dominante y la tarjeta es minoría. «medido» = el medio aparece en Impul Pay;
# «hábito» = juicio del asistente sobre cómo paga la gente ahí (verificar si el país gana).
PAISES = [
    # Latinoamérica
    ("MX", "es-MX", "MXN", 100, 0.5, 1.0, "medido: OXXO, SPEI"),
    ("BR", "pt-BR", "BRL", 180, 0.5, 1.0, "medido: Pix, Boleto"),
    ("CO", "es-419", "COP", 40, 0.4, 1.0, "medido: PSE, Nequi, Bre-B, Bancolombia, Efecty (Addi con financing)"),
    ("CL", "es-419", "CLP", 18, 0.6, 1.0, "medido: Mercado Pago, Sencillito, Servipag"),
    ("PE", "es-419", "PEN", 26, 0.4, 1.0, "medido: Yape"),
    ("AR", "es-AR", "ARS", 40, 0.5, 0.6, "medido: Impul Pay no cobra en Argentina; requiere MercadoPago del dueño"),
    ("EC", "es-419", "USD", 14, 0.35, 0.6, "hábito: solo tarjeta y PayPal"),
    ("UY", "es-419", "UYU", 3, 0.6, 0.6, "hábito: solo tarjeta y PayPal"),
    ("GT", "es-419", "GTQ", 11, 0.3, 0.6, "hábito: solo tarjeta y PayPal"),
    ("DO", "es-419", "DOP", 9, 0.4, 0.6, "hábito: solo tarjeta y PayPal"),
    ("CR", "es-419", "CRC", 4, 0.5, 0.6, "hábito: solo tarjeta y PayPal"),
    ("PA", "es-419", "USD", 3, 0.6, 0.6, "hábito: tarjeta; Impul Pay no cobra en balboas: market en USD"),
    ("BO", "es-419", "BOB", 7, 0.25, 0.4, "hábito: sin QR Simple"),
    ("PY", "es-419", "PYG", 5, 0.3, 0.6, "hábito: solo tarjeta y PayPal"),
    # Norteamérica y Oceanía
    ("US", "en-US", "USD", 310, 1.0, 1.0, "medido: tarjeta, ACH, PayPal"),
    ("CA", "en-US", "CAD", 37, 0.9, 1.0, "medido: tarjeta, PayPal"),
    ("AU", "en-US", "AUD", 25, 0.9, 1.0, "medido: tarjeta, PayTo, BECS"),
    ("NZ", "en-US", "NZD", 5, 0.85, 1.0, "hábito: tarjeta domina"),
    # Europa
    ("GB", "en-US", "GBP", 65, 0.85, 1.0, "hábito: tarjeta domina; PayPal"),
    ("IE", "en-US", "EUR", 5, 1.0, 1.0, "hábito: tarjeta domina"),
    ("ES", "es-ES", "EUR", 45, 0.75, 0.8, "medido: tarjeta, PayPal; Bizum solo con Stripe"),
    ("PT", "pt-PT", "EUR", 9, 0.7, 1.0, "medido: MB WAY"),
    ("IT", "it", "EUR", 51, 0.8, 1.0, "medido: Satispay, tarjeta, PayPal"),
    ("FR", "fr", "EUR", 60, 0.85, 1.0, "hábito: tarjeta (CB) domina; PayPal; Oney y Alma solo con financing aprobado en Whop"),
    ("BE", "nl", "EUR", 11, 0.9, 1.0, "medido: Bancontact"),
    ("NL", "nl", "EUR", 17, 0.95, 1.0, "medido: iDEAL"),
    ("DE", "de", "EUR", 78, 0.9, 0.8, "medido: tarjeta, PayPal; falta transferencia/factura"),
    ("AT", "de", "EUR", 8, 0.9, 0.8, "medido: tarjeta, PayPal; falta EPS"),
    ("CH", "de", "CHF", 9, 1.0, 0.8, "medido: sin TWINT (ni Impul Pay ni Stripe EE. UU.)"),
    ("SE", "sv", "SEK", 10, 0.9, 0.8, "medido: sin Swish (ni Impul Pay ni Stripe EE. UU.)"),
    ("NO", "no", "NOK", 5, 1.0, 0.8, "medido: sin Vipps (ni Impul Pay ni Stripe EE. UU.)"),
    ("DK", "da", "DKK", 6, 0.95, 0.8, "medido: sin MobilePay (ni Impul Pay ni Stripe EE. UU.)"),
    ("FI", "fi", "EUR", 5, 0.85, 0.8, "hábito: tarjeta y PayPal; falta banca en línea"),
    ("PL", "pl", "PLN", 33, 0.65, 0.4, "medido: Impul Pay sin BLIK ni Przelewy24 (los dos sí con Stripe)"),
    ("CZ", "cs", "CZK", 10, 0.7, 0.8, "hábito: tarjeta común"),
    ("RO", "ro", "RON", 16, 0.6, 0.8, "hábito: tarjeta común"),
    ("HU", "hu", "HUF", 9, 0.6, 0.8, "hábito: tarjeta común"),
    ("GR", "el", "EUR", 8, 0.6, 0.8, "hábito: tarjeta común"),
    ("TR", "tr", "TRY", 72, 0.6, 0.8, "hábito: tarjeta domina (cuotas)"),
    # Asia, África y Medio Oriente
    ("MY", "ms", "MYR", 31, 0.6, 1.0, "medido: DuitNow, GrabPay, ShopeePay, Touch 'n Go"),
    ("SG", "en-US", "SGD", 5, 1.0, 1.0, "medido: GrabPay; tarjeta"),
    ("PH", "en-US", "PHP", 80, 0.3, 1.0, "medido: GCash"),
    ("HK", "zh-TW", "HKD", 7, 1.0, 1.0, "medido: AlipayHK; tarjeta"),
    ("KE", "en-US", "KES", 25, 0.15, 1.0, "medido: M-Pesa"),
    ("AE", "ar", "AED", 10, 1.0, 0.8, "hábito: tarjeta domina (Tabby/Tamara requieren financiación)"),
    ("SA", "ar", "SAR", 35, 0.8, 0.6, "hábito: falta mada"),
    ("IL", "he", "ILS", 9, 0.8, 0.8, "hábito: tarjeta domina"),
    ("ZA", "en-US", "ZAR", 45, 0.35, 0.8, "hábito: tarjeta común"),
    ("NG", "en-US", "NGN", 100, 0.15, 0.4, "hábito: transferencia y USSD dominan"),
    ("EG", "ar", "EGP", 80, 0.2, 0.4, "hábito: efectivo y Fawry dominan"),
    ("MA", "fr", "MAD", 32, 0.2, 0.4, "hábito: efectivo domina"),
    ("JP", "ja", "JPY", 115, 0.8, 0.8, "hábito: tarjeta común; falta konbini y PayPay"),
    ("KR", "ko", "KRW", 50, 0.85, 0.4, "hábito: tarjetas locales y KakaoPay/Naver Pay"),
    ("IN", "hi", "INR", 750, 0.15, 0.4, "hábito: UPI domina"),
    ("ID", "id", "IDR", 210, 0.25, 0.4, "hábito: e-wallets y transferencia virtual"),
    ("VN", "vi", "VND", 78, 0.2, 0.4, "hábito: e-wallets y transferencia"),
    ("TH", "th", "THB", 60, 0.35, 0.6, "hábito: falta PromptPay (Stripe EE. UU.: lista de espera)"),
    # ── v6 (14-nov): 36 países más. online_m y poder son orden de magnitud (juicio del asistente, no medición);
    # en monedas poco comunes, si Whop no cobra en la moneda local se arma un market en USD (como Honduras y Panamá).
    # Europa
    ("SK", "sk", "EUR", 5, 0.65, 0.8, "hábito: tarjeta común"),
    ("SI", "sl", "EUR", 1.8, 0.75, 0.8, "hábito: tarjeta común"),
    ("HR", "hr", "EUR", 3.3, 0.6, 0.8, "hábito: tarjeta común"),
    ("BG", "bg", "EUR", 5.3, 0.5, 0.8, "hábito: tarjeta común (euro desde 2026)"),
    ("LT", "lt", "EUR", 2.4, 0.75, 0.8, "hábito: tarjeta común; banca en línea"),
    ("LV", "lv", "EUR", 1.7, 0.7, 0.8, "hábito: tarjeta común; banca en línea"),
    ("EE", "et", "EUR", 1.2, 0.8, 0.8, "hábito: tarjeta común; banca en línea"),
    ("LU", "fr", "EUR", 0.6, 1.0, 1.0, "hábito: tarjeta domina"),
    ("CY", "el", "EUR", 1.0, 0.75, 0.8, "hábito: tarjeta común"),
    ("RS", "sr", "RSD", 6, 0.45, 0.6, "hábito: tarjeta; moneda a confirmar en Whop (si no, market en USD)"),
    ("BA", "bs", "BAM", 2.7, 0.35, 0.6, "hábito: tarjeta; market en USD si Whop no cobra BAM"),
    ("MK", "mk", "MKD", 1.7, 0.4, 0.6, "hábito: tarjeta; market en USD si Whop no cobra MKD"),
    ("MD", "ro", "MDL", 2.0, 0.35, 0.6, "hábito: tarjeta; market en USD si Whop no cobra MDL"),
    ("UA", "uk", "UAH", 30, 0.3, 0.6, "hábito: tarjeta común (Monobank); Whop no cobra en Crimea, Donetsk, Lugansk, Zaporiyia ni Jersón"),
    ("GE", "ka", "GEL", 3.0, 0.4, 0.6, "hábito: tarjeta; market en USD si Whop no cobra GEL"),
    ("AM", "hy", "AMD", 2.3, 0.4, 0.6, "hábito: tarjeta; market en USD si Whop no cobra AMD"),
    ("AZ", "az", "AZN", 8, 0.4, 0.6, "hábito: tarjeta; market en USD si Whop no cobra AZN"),
    ("KZ", "ru", "KZT", 18, 0.45, 0.6, "hábito: tarjeta Visa de Kaspi común; falta Kaspi QR"),
    # Medio Oriente
    ("QA", "ar", "QAR", 2.9, 1.0, 0.8, "hábito: tarjeta domina"),
    ("KW", "ar", "KWD", 4.3, 0.95, 0.6, "hábito: falta KNET (débito local)"),
    ("OM", "ar", "OMR", 4.5, 0.75, 0.8, "hábito: tarjeta común"),
    ("BH", "ar", "BHD", 1.5, 0.8, 0.8, "hábito: tarjeta común; falta BenefitPay"),
    ("JO", "ar", "JOD", 9, 0.35, 0.6, "hábito: tarjeta; falta CliQ"),
    # Asia
    ("TW", "zh-TW", "TWD", 22, 0.9, 0.8, "hábito: tarjeta común; faltan LINE Pay y JKO Pay"),
    ("PK", "ur", "PKR", 110, 0.15, 0.4, "hábito: JazzCash y Easypaisa dominan; tarjeta minoría"),
    ("BD", "bn", "BDT", 75, 0.15, 0.4, "hábito: bKash domina; tarjeta minoría"),
    ("LK", "si", "LKR", 11, 0.25, 0.6, "hábito: tarjeta; market en USD si Whop no cobra LKR"),
    ("MN", "mn", "MNT", 2.8, 0.3, 0.6, "hábito: tarjeta; falta QPay"),
    # África
    ("GH", "en-US", "GHS", 20, 0.2, 0.4, "hábito: mobile money domina (sin MoMo en Impul Pay ni Stripe)"),
    ("BW", "en-US", "BWP", 1.8, 0.4, 0.6, "hábito: tarjeta común"),
    ("MU", "en-US", "MUR", 0.9, 0.55, 0.6, "hábito: tarjeta común"),
    # Centroamérica y Caribe
    ("HN", "es-419", "USD", 6, 0.25, 0.6, "medido: Impul Pay no cobra lempiras: market en USD (Stripe sí cobra HNL)"),
    ("SV", "es-419", "USD", 4.5, 0.3, 0.6, "hábito: tarjeta; dolarizado"),
    ("PR", "es-419", "USD", 2.9, 0.8, 1.0, "hábito: tarjeta, ACH, Cash App (como EE. UU.)"),
    ("JM", "en-US", "JMD", 2.5, 0.35, 0.6, "hábito: tarjeta; market en USD si Whop no cobra JMD"),
    ("TT", "en-US", "TTD", 1.2, 0.6, 0.6, "hábito: tarjeta; market en USD si Whop no cobra TTD"),
]

# Lo que suma conectar Stripe (cuenta de EE. UU.; documentación de Stripe leída el 14-nov). Solo países donde sube.
# No suman (Stripe EE. UU. no los ofrece): Swish, TWINT, MobilePay, Vipps, PayPay, Konbini, GrabPay, FPX, PayNow,
# Revolut Pay, Boleto; PromptPay está en lista de espera.
STRIPE_DISPONIBLE = True   # cuenta de Stripe de EE. UU. del dueño; se conecta por tienda, solo donde hace falta
STRIPE_MEJORA = {
    "PL": (1.0, "BLIK y Przelewy24"),
    "ES": (1.0, "Bizum"),
    "AT": (1.0, "EPS"),
    "DE": (0.9, "Klarna sin financing de Whop (factura y cuotas)"),
    "KR": (1.0, "tarjetas coreanas, Kakao Pay, Naver Pay, PAYCO, Samsung Pay"),
    "IN": (0.9, "UPI"),
    "FI": (0.9, "Pay by Bank"),
    "HN": (0.8, "cobra en lempiras sin market en USD"),
    "PA": (0.8, "cobra en balboas sin market en USD"),
}

# Fuera a propósito (no se mide ni se lanza): por qué.
FUERA = {
    "sanciones (Whop no cobra)": "AF BY BI CF KM CU CD ER HT IR IQ LB LS LY MM KP PS PG RU SO SS SD SY VE YE",
    "Whop no cobra": "BJ",
    "Meta no llega": "CN",
    "control de cambios: la tarjeta internacional casi no pasa": "DZ ET",
    "cobro y poder muy bajos (mobile money sin método)": "TZ UG RW ZM CM CI SN NE ML BF NP KH UZ AL NI",
    "mercado chico (< 0.5 M en línea)": "IS MT BS BB BZ GY SR FJ ME",
}
# NG sigue en la lista desde v3 con cobro 0.4: se puede lanzar, pero casi no paga con tarjeta internacional.
COBRO_FECHA = "2026-11-13"

# Ventanas de compra fuerte (aprox.; los años cambian unos días). (paises, nombre, mes, día desde, día hasta)
TEMPORADA = [
    (["MX"], "Buen Fin", 11, 13, 17), (["MX"], "Hot Sale", 5, 26, 3),
    (["US", "CA", "GB", "IE", "AU", "NZ", "DE", "AT", "CH", "FR", "IT", "ES", "PT", "NL", "BE", "SE", "NO", "DK", "FI",
      "PL", "CZ", "RO", "HU", "GR", "BR", "CO", "CL", "PE", "AR", "ZA"], "Black Friday / Cyber Monday", 11, 21, 2),
    (["MY", "SG", "PH", "HK", "ID", "VN", "TH"], "11.11 / 12.12", 11, 9, 12),
    (["*"], "Navidad", 12, 15, 31),
]


def _en_ventana(fecha: dt.date, mes, d1, d2) -> bool:
    """Ventana del día d1 del mes hasta el día d2 (del mes siguiente si d2 < d1)."""
    ini = dt.date(fecha.year, mes, d1)
    if d2 >= d1:
        fin = dt.date(fecha.year, mes, d2)
    else:
        fin = dt.date(fecha.year + 1, 1, d2) if mes == 12 else dt.date(fecha.year, mes + 1, d2)
    return ini <= fecha <= fin


def temporada(pais: str, fecha: dt.date) -> str:
    hits = [n for (ps, n, m, a, b) in TEMPORADA if ("*" in ps or pais in ps) and _en_ventana(fecha, m, a, b)]
    return ", ".join(hits)


def plantilla() -> None:
    orden = sorted(PAISES, key=lambda p: -(0.5 * min(1, math.log10(max(p[3], 1)) / math.log10(300)) + 0.3 * p[5] + 0.2 * p[4]))
    print(json.dumps({"referente_page_id": "", "fecha": "", "frase_producto": "", "_nota": "ordenados por tamaño, cobro y poder: medir de arriba hacia abajo (12-15 primero)", "paises": [
        dict(pais=p[0], idioma=p[1], moneda=p[2], online_m=p[3], referente=None, referente_idioma_local=None,
             referente_inactivos=None, competencia=None, consulta_competencia="", medido=False, nota="")
        for p in orden]}, ensure_ascii=False, indent=1))


def cobro_tabla() -> None:
    print(f"Cobro (Impul Pay leído el {COBRO_FECHA}, lista de 37 métodos releída el 14-nov; «medido» = visto en el panel o en la "
          f"documentación, «hábito» = juicio a verificar). Stripe {'disponible (se conecta solo en las tiendas que lo necesitan)' if STRIPE_DISPONIBLE else 'fuera del cálculo'}. {len(PAISES)} países.")
    for p in PAISES:
        st = STRIPE_MEJORA.get(p[0])
        print(f"  {p[0]}: {p[5]}" + (f" → {st[0]} con Stripe ({st[1]})" if st and st[0] > p[5] else "") + f"  {p[6]}")
    print("\nFuera a propósito:")
    for motivo, cods in FUERA.items():
        print(f"  {motivo}: {cods}")


def _libro() -> dict:
    """Por país: tests, gasto Meta, neto, CPA observado, si alguno fue rentable contra Meta."""
    out = {}
    try:
        d = json.loads(LIBRO.read_text(encoding="utf-8"))
        tc = d.get("tipos_de_cambio", {})
        for t in d.get("tests", []):
            pais = t.get("mercado")
            gasto = float((t.get("meta") or {}).get("gasto_usd") or 0)
            ventas = t.get("ventas") or []
            neto = sum(float(v.get("neto") or 0) * float(tc.get(v.get("moneda", "USD"), 1)) for v in ventas)
            o = out.setdefault(pais, {"tests": 0, "gasto": 0.0, "ventas": 0, "neto": 0.0, "rentable": False})
            o["tests"] += 1; o["gasto"] += gasto; o["ventas"] += sum(1 for v in ventas if v.get("tipo", "principal") not in ("upsell", "bump", "downsell")); o["neto"] += neto
            if gasto > 0 and neto > gasto:
                o["rentable"] = True
        for o in out.values():
            o["cpa"] = round(o["gasto"] / o["ventas"], 2) if o["ventas"] else None
    except Exception:
        pass
    return out


def historial_paises() -> None:
    for k, o in _libro().items():
        print(f"  {k}: {o['tests']} tests · gasto US$ {o['gasto']:.2f} · {o['ventas']} ventas · neto US$ {o['neto']:.2f} · "
              f"CPA {o['cpa'] if o['cpa'] is not None else '—'} · {'rentable' if o['rentable'] else 'sin test rentable'}")


def _econ() -> dict:
    try:
        d = json.loads(ECON.read_text(encoding="utf-8"))
        return {f["codigo"]: f.get("r") for f in d["escenarios"]["corregido"].get("orden", []) if f.get("codigo")}
    except Exception:
        return {}


FICHA = {p[0]: p for p in PAISES}


def _puntaje(p, ult4, idiomas3, libro, sin=()):
    f0 = FICHA[p["pais"]]
    ref = p.get("referente") or 0
    loc = p.get("referente_idioma_local")
    hueco = 1.0 if ref == 0 else (0.6 if loc == 0 else 0.0)   # con el veto v5 aquí solo llegan países con ref == 0
    por = []
    if ref == 0 and (p.get("referente_inactivos") or 0) > 0:
        hueco *= 0.8
        por.append("el referente pautó ahí y se fue ×0.8 en hueco")
    tam = min(1.0, math.log10(max(f0[3], 1)) / math.log10(300))
    comp = 1 - min(1.0, math.log10(1 + (p.get("competencia") or 0)) / math.log10(501))
    cobro, poder = f0[5], f0[4]
    if STRIPE_DISPONIBLE and f0[0] in STRIPE_MEJORA:
        cobro = max(cobro, STRIPE_MEJORA[f0[0]][0])
    if "cobro" in sin:
        cobro = 1.0
    if "competencia" in sin:
        comp = 1.0
    base = (PESOS["hueco"] * hueco + PESOS["tamano"] * tam + PESOS["competencia"] * comp
            + PESOS["cobro"] * cobro + PESOS["poder"] * poder)
    fac = 1.0
    if "castigo" not in sin:
        n = ult4.count(p["pais"])
        if n:
            k = 0.8 if libro.get(p["pais"], {}).get("rentable") else 0.6
            fac *= k ** n
            por.append(f"país usado {n} de las últimas {len(ult4)} ×{k ** n:.2f}" + (" (ya dio un test rentable)" if k == 0.8 else ""))
        m = idiomas3.count(f0[1])
        if m >= 2:
            fac *= 0.9 ** (m - 1)
            por.append(f"idioma usado {m} de las últimas 3 ×{0.9 ** (m - 1):.2f}")
    return round(base * fac, 3), dict(hueco=round(hueco, 2), tam=round(tam, 2), comp=round(comp, 2), cobro=cobro, poder=poder), por


def excluidos_de_oferta(nombre: str) -> dict:
    """{país: motivo} para la réplica de una oferta del libro: donde corre el referente (ficha.referente_paises.paises > 0) y
    los mercados que la oferta ya usa. Sin medición, sale con error: no se replica a ciegas (medir con paises_referente.py)."""
    d = json.loads(LIBRO.read_text(encoding="utf-8"))
    tests = [t for t in d.get("tests", []) if nombre in (t.get("oferta"), t.get("nombre"))]
    if not tests:
        raise SystemExit(f"No hay una oferta «{nombre}» en el libro de tests.")
    out = {}
    for t in tests:
        for c in str(t.get("mercado") or "").upper().replace(",", "/").split("/"):
            if c.strip():
                out[c.strip()] = "esta oferta ya corre ahí"
    med = next((t["ficha"]["referente_paises"] for t in tests if isinstance(t.get("ficha"), dict) and isinstance(t["ficha"].get("referente_paises"), dict)), None)
    if not med:
        raise SystemExit(f"«{nombre}»: falta medir en qué países corre el referente (buscar-ofertas/scripts/paises_referente.py).")
    for c, n in (med.get("paises") or {}).items():
        if isinstance(n, (int, float)) and n > 0:
            out[c.upper()] = f"el referente corre ahí ({int(n)} anuncios, medido {str(med.get('medido', ''))[:10]})"
    return out


def aplicar_medicion(datos: dict, ruta_med: str) -> None:
    """Copia a cada país de mercados.json los anuncios activos del referente medidos con paises_referente.py."""
    m = json.loads(Path(ruta_med).read_text(encoding="utf-8"))
    paises = {str(k).upper(): v for k, v in (m.get("paises") or {}).items()}
    for c in m.get("sin_anuncios") or []:
        paises.setdefault(str(c).upper(), 0)
    for p in datos["paises"]:
        if p["pais"] in paises:
            p["referente"] = int(paises[p["pais"]] or 0)


def ordenar(ruta: str, inicio: dt.date, oferta: str | None = None, medicion: str | None = None) -> int:
    datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
    if medicion:
        aplicar_medicion(datos, medicion)
    excl = {**bloqueados_por_meta(), **(excluidos_de_oferta(oferta) if oferta else {})}
    hist = json.loads(HIST.read_text(encoding="utf-8")) if HIST.is_file() else []
    todos = [h.get("pais_destino") for h in hist]
    ult4, idiomas3 = todos[-4:], [h.get("idioma") for h in hist if h.get("idioma")][-3:]
    libro, econ = _libro(), _econ()
    validos, fuera = [], []
    for p in datos["paises"]:
        motivo = None
        if p["pais"] in excl:
            motivo = excl[p["pais"]]
        elif (p.get("referente") or 0) > 0:
            motivo = f"VETO: el referente corre ahí ({int(p['referente'])} anuncios activos)"
        elif not p.get("medido"):
            motivo = "no medido"
        elif p.get("referente") is None:
            motivo = "referente sin medir"
        elif p["pais"] not in FICHA:
            motivo = "país sin ficha (agregarlo a PAISES con su cobro)"
        elif not p.get("consulta_competencia"):
            motivo = "competencia sin consulta anotada"
        (fuera if motivo else validos).append((p, motivo))
    print(f"Inicio previsto: {inicio} · últimos 4 países: {ult4 or '—'} · idiomas (últimos 3): {idiomas3 or '—'}")
    print(f"Cobro: Impul Pay {COBRO_FECHA} (ver `cobro`) · Stripe {'disponible (suma STRIPE_MEJORA)' if STRIPE_DISPONIBLE else 'fuera del cálculo (--sin-stripe)'} · {len(PAISES)} países en la lista\n")
    filas = sorted(((*_puntaje(p, ult4, idiomas3, libro), p) for p, _ in validos), key=lambda x: -x[0])
    print("| # | País | Puntaje | Hueco | Tamaño | Compet. | Cobro | Poder | Referente (local) | CPA obs. | r econ. | Temporada | Ajustes |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for k, (s, d, por, p) in enumerate(filas, 1):
        lb = libro.get(p["pais"])
        cpa = (f"{lb['cpa']} ({lb['tests']} t.)" if lb and lb.get("cpa") is not None else (f"sin ventas ({lb['tests']} t.)" if lb else "—"))
        print(f"| {k} | {p['pais']} ({FICHA[p['pais']][1]}) | {s} | {d['hueco']} | {d['tam']} | {d['comp']} | {d['cobro']} | "
              f"{d['poder']} | {p.get('referente')} ({p.get('referente_idioma_local')}) | {cpa} | {econ.get(p['pais'], '—')} | "
              f"{temporada(p['pais'], inicio) or '—'} | {'; '.join(por) or '—'} |")
    if fuera:
        print("\nFuera del orden: " + "; ".join(f"{p['pais']} ({m})" for p, m in fuera))
    if not filas:
        vetados = [p for p, m in fuera if m and (m.startswith("VETO") or m.startswith("el referente corre"))]
        sin_medir = [p for p, m in fuera if m in ("no medido", "referente sin medir", "competencia sin consulta anotada")]
        libres_a_medir = [p["pais"] for p in sin_medir if p.get("referente") == 0]
        ausentes = [c for c in FICHA if c not in {p["pais"] for p in datos["paises"]}]
        if libres_a_medir:
            print(f"\nSin el referente pero sin medir la competencia: {', '.join(libres_a_medir)}. Medirla y volver a ordenar.")
            return 4
        if sin_medir or ausentes:
            print(f"\nNINGÚN PAÍS MEDIDO QUEDA LIBRE ({len(vetados)} con el referente). Faltan {len(sin_medir) + len(ausentes)} países "
                  "por mirar: medir el referente en todos con paises_referente.py (por mitades, ~10-20 consultas) y volver a "
                  "ordenar con --medicion. Si tampoco queda ninguno, se descarta la oferta.")
            return 4
        print(f"\nDESCARTAR LA OFERTA: el referente corre en los {len(vetados)} países de nuestra lista (PAISES, {len(FICHA)} donde "
              "tenemos ficha de cobro; no son todos los del mundo). No hay mercado libre en la lista: no se elige «el menos malo». "
              "Marcarla descartada en el banco y volver a buscar-ofertas.")
        return 3
    ganador = filas[0][3]["pais"]
    print("\nSensibilidad (¿cambia el primero si se quita un factor?):")
    fragil = False
    for etiqueta, sin in [("sin cobro", ("cobro",)), ("sin castigo por repetir", ("castigo",)), ("sin competencia", ("competencia",))]:
        top = max(((_puntaje(p, ult4, idiomas3, libro, sin)[0], p["pais"]) for p, _ in validos))[1]
        fragil |= top != ganador
        print(f"  {etiqueta}: gana {top}" + ("  ← CAMBIA" if top != ganador else ""))
    if len(filas) >= 2 and filas[0][0] - filas[1][0] < 0.05:
        print(f"\nEmpate técnico entre {ganador} y {filas[1][3]['pais']} (< 0.05): decir el porqué de cada uno.")
    if fragil:
        print("La elección es FRÁGIL: depende de un factor. Nombrar el supuesto al dueño.")
    if "hábito" in FICHA[ganador][6]:
        print(f"Ojo cobro: el de {ganador} es juicio («{FICHA[ganador][6]}»): verificar en la vista previa del checkout antes de producir.")
    if temporada(ganador, inicio):
        print(f"Ojo temporada: {ganador} está en «{temporada(ganador, inicio)}» en la fecha de inicio (CPM más caro, mucho ruido de ofertas).")
    usados = set(todos)
    if len(todos) >= 3 and all(x in set(todos[:-3]) or todos[-3:].count(x) > 1 for x in todos[-3:]):
        nuevos = [f for f in filas if f[3]["pais"] not in usados]
        if nuevos and nuevos[0][3]["pais"] != ganador:
            print(f"Exploración recomendada: las últimas 3 ofertas fueron a países repetidos; el mejor país nunca probado es "
                  f"{nuevos[0][3]['pais']} ({nuevos[0][0]}). Proponérselo al dueño aunque no gane.")
    print(f"\nRecomendado: {ganador}")
    st = STRIPE_MEJORA.get(ganador)
    if STRIPE_DISPONIBLE and st and st[0] > FICHA[ganador][5]:
        print(f"REQUIERE STRIPE: el cobro de {ganador} pasa de {FICHA[ganador][5]} a {st[0]} por {st[1]}. Conectar Stripe en las "
              "tiendas de esta oferta (solo en ellas) y prender sus métodos locales (06-tienda-impultienda.md §2b). Si no se "
              "puede conectar hoy, volver a ordenar con --sin-stripe y tomar ese ganador.")
    else:
        print("Stripe: no hace falta en esta oferta (solo Impul Pay).")
    return 0


if __name__ == "__main__":
    a = sys.argv[1:]
    if "--sin-stripe" in a:
        STRIPE_DISPONIBLE = False
        a.remove("--sin-stripe")
    if a[0] == "ordenar":
        ini = dt.date.today() + dt.timedelta(days=1)
        if "--inicio" in a:
            ini = dt.date.fromisoformat(a[a.index("--inicio") + 1])
        sys.exit(ordenar(a[1], ini, a[a.index("--oferta") + 1] if "--oferta" in a else None,
                         a[a.index("--medicion") + 1] if "--medicion" in a else None))
    else:
        {"plantilla": plantilla, "cobro": cobro_tabla, "historial": historial_paises}[a[0]]()
