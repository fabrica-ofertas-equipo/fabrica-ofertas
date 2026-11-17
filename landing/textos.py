"""``landing.textos``: textos fijos por idioma (rótulos de la interfaz y páginas legales genéricas) e importes.

Todo texto **comercial** de la landing sale de ``copy.json``; aquí solo vive lo que la plantilla
necesita y el Maker no redacta: rótulos cortos de accesibilidad y de componentes, y las siete
páginas legales **genéricas** (decisión del dueño, 2026-11-06: sin abogado; son plantilla, no
asesoría legal). Idiomas cubiertos: ``es``, ``en``, ``it``, ``pl``. Otro idioma cae a ``en`` y
``landing.generar`` lo avisa: añadir su tabla aquí antes de publicarlo.

Los importes se formatean con enteros (unidad menor + exponente ISO 4217): nunca ``float``.
"""
from __future__ import annotations

from typing import Mapping

from scripts import validar_esquemas as V

__all__ = ["IDIOMAS", "idioma_de", "rotulos", "titulos_legales", "cuerpo_legal", "cuerpo_desistimiento", "formatear_importe", "etiqueta_metodo", "formatear_fecha",
           "formatear_entero", "formatear_decimal", "formatear_rango", "rotulos_de_imagen", "demo_resenas", "TEXTO_VISTA_PREVIA"]

IDIOMAS = ("es", "en", "it", "pl")
NBSP = " "

_ROTULOS: Mapping[str, Mapping[str, str]] = {
    "es": {
        "salto": "Saltar al contenido", "consulta": "Consulta antes de pagar", "resumen": "Lo esencial de un vistazo", "si": "Encaja si…", "no": "No encaja si…",
        "incluido": "Incluido", "opcional": "Opcional", "sin": "Sin el material", "con": "Con el material", "dias": "días",
        "pago_seguro": "Pago seguro en la página de Stripe", "precio": "Precio", "volver": "Volver al inicio", "legal": "Información legal",
        "compra_rapida": "Acceso rápido a la compra", "banner_titulo": "Tus preferencias de cookies",
        "banner_necesarias": "Necesarias (siempre activas): recordar esta elección.", "banner_mas": "Más información",
        "cabecera": "Cabecera", "pasos": "Contenido", "portada": "Portada",
        "verificada": "Compra verificada", "demo": "DEMO", "elige_nivel": "Elige tu nivel para ver qué incluye", "valoracion": "Valoración", "opiniones": "opiniones",
        "descargas_muestra": "Descargas de la muestra", "ventas": "Compras verificadas", "dato_al": "Dato al", "comparacion": "Comparación con precios del mercado",
        "comparacion_nota": "Precios publicados por terceros, con su fuente y la fecha de lectura. No son ofertas nuestras.", "fuente": "Fuente", "leido": "leído el",
        "nuestro_precio": "Nuestro precio", "paso": "Paso", "bonus": "Bonus", "abrir_nivel": "Ver contenido", "estrellas": "de 5",
        "valido_hasta": "hasta", "con_garantia": "Garantía incluida",
        "rotulo_ilustrativa": "Ilustración orientativa", "rotulo_ilustrativa_pie": "Ilustración orientativa: el diseño y el contenido finales pueden variar.",
        "rotulo_ia": "Imagen generada con ayuda de IA",
        "aviso_barra": "Aviso", "recibes": "Qué recibes", "como_recibes": "Cómo recibes el material", "ver_mas": "Ver más", "sigue": "Sigue leyendo",
    },
    "en": {
        "salto": "Skip to content", "consulta": "Check before you pay", "resumen": "The essentials at a glance", "si": "A good fit if…", "no": "Not a fit if…",
        "incluido": "Included", "opcional": "Optional", "sin": "Without it", "con": "With it", "dias": "days",
        "pago_seguro": "Secure payment on the Stripe page", "precio": "Price", "volver": "Back to home", "legal": "Legal information",
        "compra_rapida": "Quick purchase", "banner_titulo": "Your cookie preferences",
        "banner_necesarias": "Necessary (always on): remembering this choice.", "banner_mas": "More information",
        "cabecera": "Header", "pasos": "Contents", "portada": "Cover",
        "verificada": "Verified purchase", "demo": "DEMO", "elige_nivel": "Pick your level to see what it includes", "valoracion": "Rating", "opiniones": "reviews",
        "descargas_muestra": "Sample downloads", "ventas": "Verified purchases", "dato_al": "Data as of", "comparacion": "Comparison with market prices",
        "comparacion_nota": "Prices published by third parties, with their source and the date they were read. They are not our offers.", "fuente": "Source", "leido": "read on",
        "nuestro_precio": "Our price", "paso": "Step", "bonus": "Bonus", "abrir_nivel": "See contents", "estrellas": "out of 5",
        "valido_hasta": "until", "con_garantia": "Guarantee included",
        "rotulo_ilustrativa": "Illustrative image", "rotulo_ilustrativa_pie": "Illustrative image: the final layout and content may differ.",
        "rotulo_ia": "Image generated with the help of AI",
        "aviso_barra": "Notice", "recibes": "What you get", "como_recibes": "How you get the material", "ver_mas": "See more", "sigue": "Keep reading",
    },
    "it": {
        "salto": "Vai al contenuto", "consulta": "Consulta prima di pagare", "resumen": "L'essenziale in breve", "si": "Va bene se…", "no": "Non va bene se…",
        "incluido": "Incluso", "opcional": "Facoltativo", "sin": "Senza il materiale", "con": "Con il materiale", "dias": "giorni",
        "pago_seguro": "Pagamento sicuro sulla pagina di Stripe", "precio": "Prezzo", "volver": "Torna alla home", "legal": "Informazioni legali",
        "compra_rapida": "Acquisto rapido", "banner_titulo": "Le tue preferenze sui cookie",
        "banner_necesarias": "Necessari (sempre attivi): ricordare questa scelta.", "banner_mas": "Maggiori informazioni",
        "cabecera": "Intestazione", "pasos": "Contenuto", "portada": "Copertina",
        "verificada": "Acquisto verificato", "demo": "DEMO", "elige_nivel": "Scegli il tuo livello per vedere cosa include", "valoracion": "Valutazione", "opiniones": "recensioni",
        "descargas_muestra": "Download del campione", "ventas": "Acquisti verificati", "dato_al": "Dato al", "comparacion": "Confronto con i prezzi di mercato",
        "comparacion_nota": "Prezzi pubblicati da terzi, con la loro fonte e la data di lettura. Non sono offerte nostre.", "fuente": "Fonte", "leido": "letto il",
        "nuestro_precio": "Il nostro prezzo", "paso": "Passo", "bonus": "Bonus", "abrir_nivel": "Vedi il contenuto", "estrellas": "su 5",
        "valido_hasta": "fino al", "con_garantia": "Garanzia inclusa",
        "rotulo_ilustrativa": "Immagine illustrativa", "rotulo_ilustrativa_pie": "Immagine illustrativa: impaginazione e contenuti finali possono variare.",
        "rotulo_ia": "Immagine generata con l'aiuto dell'IA",
        "aviso_barra": "Avviso", "recibes": "Cosa ricevi", "como_recibes": "Come ricevi il materiale", "ver_mas": "Vedi altro", "sigue": "Continua a leggere",
    },
    "pl": {
        "salto": "Przejdź do treści", "consulta": "Sprawdź przed zapłatą", "resumen": "Najważniejsze w skrócie", "si": "Pasuje, jeśli…", "no": "Nie pasuje, jeśli…",
        "incluido": "W cenie", "opcional": "Opcjonalnie", "sin": "Bez tego materiału", "con": "Z tym materiałem", "dias": "dni",
        "pago_seguro": "Bezpieczna płatność na stronie Stripe", "precio": "Cena", "volver": "Wróć na stronę główną", "legal": "Informacje prawne",
        "compra_rapida": "Szybki zakup", "banner_titulo": "Twoje preferencje dotyczące plików cookie",
        "banner_necesarias": "Niezbędne (zawsze aktywne): zapamiętanie tego wyboru.", "banner_mas": "Więcej informacji",
        "cabecera": "Nagłówek", "pasos": "Zawartość", "portada": "Okładka",
        "verificada": "Zweryfikowany zakup", "demo": "DEMO", "elige_nivel": "Wybierz swój poziom, by zobaczyć zawartość", "valoracion": "Ocena", "opiniones": "opinii",
        "descargas_muestra": "Pobrania próbki", "ventas": "Zweryfikowane zakupy", "dato_al": "Dane na dzień", "comparacion": "Porównanie z cenami rynkowymi",
        "comparacion_nota": "Ceny opublikowane przez osoby trzecie, z podanym źródłem i datą odczytu. To nie są nasze oferty.", "fuente": "Źródło", "leido": "odczytano",
        "nuestro_precio": "Nasza cena", "paso": "Krok", "bonus": "Bonus", "abrir_nivel": "Zobacz zawartość", "estrellas": "z 5",
        "valido_hasta": "do", "con_garantia": "Gwarancja w cenie",
        "rotulo_ilustrativa": "Ilustracja poglądowa", "rotulo_ilustrativa_pie": "Ilustracja poglądowa: układ i treść gotowych materiałów mogą się różnić.",
        "rotulo_ia": "Obraz wygenerowany z pomocą AI",
        "aviso_barra": "Informacja", "recibes": "Co dostajesz", "como_recibes": "Jak dostajesz materiał", "ver_mas": "Zobacz więcej", "sigue": "Czytaj dalej",
    },
}

_METODOS: Mapping[str, Mapping[str, str]] = {
    "es": {"card": "Tarjeta"}, "en": {"card": "Card"}, "it": {"card": "Carta"}, "pl": {"card": "Karta"},
}
_METODOS_MARCA = {"apple_pay": "Apple Pay", "google_pay": "Google Pay", "link": "Link", "blik": "BLIK", "satispay": "Satispay",
                  "bancontact": "Bancontact", "eps": "EPS", "mb_way": "MB WAY", "klarna": "Klarna", "paypal": "PayPal"}

_TITULOS: Mapping[str, Mapping[str, str]] = {
    "es": {"vendedor": "Datos del vendedor y contacto", "terminos": "Términos de uso", "privacidad": "Política de privacidad",
           "reembolsos": "Reembolsos y derecho de desistimiento", "cookies": "Política de cookies", "aviso": "Aviso de contenido",
           "entrega": "Entrega y soporte"},
    "en": {"vendedor": "Seller details and contact", "terminos": "Terms of use", "privacidad": "Privacy policy",
           "reembolsos": "Refunds and right of withdrawal", "cookies": "Cookie policy", "aviso": "Content notice",
           "entrega": "Delivery and support"},
    "it": {"vendedor": "Dati del venditore e contatti", "terminos": "Termini d'uso", "privacidad": "Informativa sulla privacy",
           "reembolsos": "Rimborsi e diritto di recesso", "cookies": "Informativa sui cookie", "aviso": "Avviso sui contenuti",
           "entrega": "Consegna e assistenza"},
    "pl": {"vendedor": "Dane sprzedawcy i kontakt", "terminos": "Regulamin", "privacidad": "Polityka prywatności",
           "reembolsos": "Zwroty i prawo do odstąpienia od umowy", "cookies": "Polityka plików cookie", "aviso": "Informacja o treści",
           "entrega": "Dostawa i pomoc"},
}

# Cuerpos genéricos (párrafos). Marcadores: {marca}, {dominio}, {garantia_dias}. Plantilla sin revisión legal (decisión 14).
_CUERPOS: Mapping[str, Mapping[str, tuple[str, ...]]] = {
    "es": {
        "vendedor": ("Vendedor: {marca}. Sitio web: {dominio}.",
                     "Contacto: responde al correo con el acceso a tu compra o escribe al buzón de soporte del dominio {dominio}."),
        "terminos": ("Al comprar en {marca} aceptas estos términos de uso. El material es digital, informativo y se entrega según lo descrito en la página del producto.",
                     "El uso es personal: no se puede revender ni redistribuir.",
                     "Podemos actualizar el contenido del sitio y del material; los cambios no afectan a las compras ya realizadas."),
        "privacidad": ("{marca} trata los datos necesarios para procesar el pedido y entregar el material. El pago lo gestiona Stripe; los datos de la tarjeta no pasan por nosotros.",
                       "No se piden datos de salud ni otros datos sensibles. Puedes solicitar la baja de tus datos respondiendo al correo con el acceso a tu compra.",
                       "La medición de anuncios (píxel de Meta) solo se activa si aceptas las cookies de marketing."),
        "reembolsos": ("Dispones de {garantia_dias} días desde la compra para pedir la devolución íntegra del importe, sin dar explicaciones.",
                       "Además se aplica el derecho de desistimiento donde la ley lo reconoce; en contenido digital de entrega inmediata puede extinguirse si aceptas expresamente que la entrega empiece de inmediato."),
        "cookies": ("{marca} usa una cookie propia para recordar tu elección y, solo si aceptas, cookies de marketing para medir los anuncios.",
                    "Puedes cambiar tu elección en cualquier momento con el botón de preferencias del pie de página."),
        "aviso": ("El contenido de {marca} es informativo y no sustituye el consejo de un profesional. No se garantizan resultados concretos.",),
        "entrega": ("La entrega es digital e inmediata tras el pago, mediante un enlace enviado a tu correo.",
                    "El enlace tiene una vigencia y un número de descargas limitados; si caduca, puedes pedir un reenvío respondiendo a ese correo."),
    },
    "en": {
        "vendedor": ("Seller: {marca}. Website: {dominio}.",
                     "Contact: reply to the email with your purchase access or write to the support mailbox of {dominio}."),
        "terminos": ("By buying from {marca} you accept these terms of use. The material is digital, informational and delivered as described on the product page.",
                     "Use is personal: it may not be resold or redistributed.",
                     "We may update the site and the material; changes do not affect purchases already made."),
        "privacidad": ("{marca} processes the data needed to handle your order and deliver the material. Payment is handled by Stripe; your card details never pass through us.",
                       "We do not ask for health or other sensitive data. You can ask for your data to be deleted by replying to the email with your purchase access.",
                       "Ad measurement (Meta pixel) only runs if you accept marketing cookies."),
        "reembolsos": ("You have {garantia_dias} days from purchase to ask for a full refund, no questions asked.",
                       "Statutory withdrawal rights also apply where the law grants them; for digital content delivered immediately they may lapse if you expressly agree that delivery starts right away."),
        "cookies": ("{marca} uses one first-party cookie to remember your choice and, only if you accept, marketing cookies to measure ads.",
                    "You can change your choice at any time with the preferences button in the footer."),
        "aviso": ("The content of {marca} is informational and does not replace professional advice. No specific results are guaranteed.",),
        "entrega": ("Delivery is digital and immediate after payment, through a link sent to your email.",
                    "The link has a limited validity and number of downloads; if it expires you can ask for a new one by replying to that email."),
    },
    "it": {
        "vendedor": ("Venditore: {marca}. Sito web: {dominio}.",
                     "Contatti: rispondi all'email con l'accesso al tuo acquisto o scrivi alla casella di assistenza del dominio {dominio}."),
        "terminos": ("Acquistando da {marca} accetti questi termini d'uso. Il materiale è digitale, informativo e viene consegnato come descritto nella pagina del prodotto.",
                     "L'uso è personale: non può essere rivenduto né ridistribuito.",
                     "Possiamo aggiornare il sito e il materiale; le modifiche non riguardano gli acquisti già effettuati."),
        "privacidad": ("{marca} tratta i dati necessari per elaborare l'ordine e consegnare il materiale. Il pagamento è gestito da Stripe; i dati della carta non passano da noi.",
                       "Non chiediamo dati sulla salute né altri dati sensibili. Puoi chiedere la cancellazione dei tuoi dati rispondendo all'email con l'accesso al tuo acquisto.",
                       "La misurazione degli annunci (pixel di Meta) si attiva solo se accetti i cookie di marketing."),
        "reembolsos": ("Hai {garantia_dias} giorni dall'acquisto per chiedere il rimborso integrale, senza dover dare spiegazioni.",
                       "Si applica inoltre il diritto di recesso dove la legge lo prevede; per i contenuti digitali consegnati subito può venire meno se accetti espressamente che la consegna inizi immediatamente."),
        "cookies": ("{marca} usa un cookie proprio per ricordare la tua scelta e, solo se accetti, cookie di marketing per misurare gli annunci.",
                    "Puoi cambiare la tua scelta in qualsiasi momento con il pulsante delle preferenze nel piè di pagina."),
        "aviso": ("I contenuti di {marca} sono informativi e non sostituiscono la consulenza di un professionista. Non si garantiscono risultati specifici.",),
        "entrega": ("La consegna è digitale e immediata dopo il pagamento, tramite un link inviato alla tua email.",
                    "Il link ha una validità e un numero di download limitati; se scade puoi chiederne uno nuovo rispondendo a quell'email."),
    },
    "pl": {
        "vendedor": ("Sprzedawca: {marca}. Strona internetowa: {dominio}.",
                     "Kontakt: odpowiedz na wiadomość z dostępem do zakupu albo napisz na adres pomocy w domenie {dominio}."),
        "terminos": ("Kupując w {marca}, akceptujesz niniejsze zasady korzystania. Materiał jest cyfrowy, ma charakter informacyjny i jest dostarczany zgodnie z opisem na stronie produktu.",
                     "Materiał jest przeznaczony do użytku osobistego: nie wolno go odsprzedawać ani udostępniać dalej.",
                     "Możemy aktualizować stronę i materiał; zmiany nie wpływają na zakupy już dokonane."),
        "privacidad": ("{marca} przetwarza dane niezbędne do realizacji zamówienia i dostarczenia materiału. Płatność obsługuje Stripe; dane karty do nas nie trafiają.",
                       "Nie prosimy o dane dotyczące zdrowia ani inne dane wrażliwe. Możesz poprosić o usunięcie swoich danych, odpowiadając na wiadomość z dostępem do zakupu.",
                       "Pomiar reklam (piksel Meta) działa wyłącznie po wyrażeniu zgody na marketingowe pliki cookie."),
        "reembolsos": ("Masz {garantia_dias} dni od zakupu, aby poprosić o zwrot całej kwoty, bez podawania przyczyny.",
                       "Poza tym przysługuje Ci ustawowe prawo do odstąpienia od umowy tam, gdzie przyznaje je prawo; w przypadku treści cyfrowych dostarczonych od razu może ono wygasnąć po wyraźnej zgodzie na natychmiastową dostawę."),
        "cookies": ("{marca} używa jednego własnego pliku cookie, który zapamiętuje Twój wybór, oraz — tylko po Twojej zgodzie — marketingowych plików cookie do pomiaru reklam.",
                    "Swój wybór możesz zmienić w dowolnym momencie przyciskiem preferencji w stopce strony."),
        "aviso": ("Treści {marca} mają charakter informacyjny i nie zastępują porady specjalisty. Nie gwarantujemy konkretnych rezultatów.",),
        "entrega": ("Dostawa jest cyfrowa i następuje natychmiast po płatności, przez link wysłany na Twój adres e-mail.",
                    "Link ma ograniczony czas ważności i liczbę pobrań; jeśli wygaśnie, możesz poprosić o nowy, odpowiadając na tę wiadomość."),
    },
}


# Desistimiento: derecho legal en dos pasos, sin cuenta y con acuse, por correo (la función POST /api/desistimiento es de D10, pendiente).
# Marcadores: {dias} (mercado.consumo.desistimiento_dias), {garantia_dias}.
_DESISTIMIENTO: Mapping[str, tuple[str, ...]] = {
    "es": ("Tienes derecho a desistir de la compra, sin dar explicaciones, durante {dias} días desde que la haces. Ese derecho puede extinguirse si aceptas expresamente que la entrega digital empiece de inmediato y reconoces que así lo pierdes.",
           "Paso 1. Responde al correo con el acceso a tu compra y escribe que quieres desistir.",
           "Paso 2. Recibirás por correo un acuse de recibo con la fecha y la hora de tu solicitud: es tu comprobante.",
           "No necesitas crear una cuenta ni iniciar sesión.",
           "La garantía comercial de {garantia_dias} días es independiente de este derecho y no lo sustituye."),
    "en": ("You have the right to withdraw from the purchase, without giving a reason, within {dias} days of buying. That right may lapse if you expressly agree that the digital delivery starts right away and acknowledge that you lose it.",
           "Step 1. Reply to the email with your purchase access and say that you want to withdraw.",
           "Step 2. You will receive an acknowledgement by email with the date and time of your request: it is your proof.",
           "You do not need to create an account or log in.",
           "The commercial guarantee of {garantia_dias} days is separate from this right and does not replace it."),
    "it": ("Hai diritto di recedere dall'acquisto, senza dover dare spiegazioni, entro {dias} giorni dall'acquisto. Il diritto può venire meno se accetti espressamente che la consegna digitale inizi subito e riconosci di perderlo.",
           "Passo 1. Rispondi all'email con l'accesso al tuo acquisto e scrivi che vuoi recedere.",
           "Passo 2. Riceverai via email una conferma di ricezione con data e ora della richiesta: è la tua prova.",
           "Non serve creare un account né accedere.",
           "La garanzia commerciale di {garantia_dias} giorni è indipendente da questo diritto e non lo sostituisce."),
    "pl": ("Masz prawo odstąpić od umowy zakupu, bez podawania przyczyny, w ciągu {dias} dni od zakupu. Prawo to może wygasnąć, jeśli wyraźnie zgodzisz się, aby dostawa treści cyfrowych rozpoczęła się od razu, i przyjmiesz do wiadomości, że w ten sposób je tracisz.",
           "Krok 1. Odpowiedz na wiadomość z dostępem do zakupu i napisz, że odstępujesz od umowy.",
           "Krok 2. Otrzymasz e-mailem potwierdzenie przyjęcia zgłoszenia z datą i godziną: to Twój dowód.",
           "Nie musisz zakładać konta ani się logować.",
           "Gwarancja handlowa na {garantia_dias} dni jest niezależna od tego prawa i go nie zastępuje."),
}


def cuerpo_desistimiento(locale: str, *, dias: int, garantia_dias: int) -> tuple[str, ...]:
    """Párrafos (texto plano) de la página de desistimiento en el idioma del ``locale``."""
    return tuple(p.replace("{dias}", str(int(dias))).replace("{garantia_dias}", str(int(garantia_dias))) for p in _DESISTIMIENTO[idioma_de(locale)[0]])


def idioma_de(locale: str) -> tuple[str, bool]:
    """(idioma con tabla propia, ``True`` si el idioma del ``locale`` está cubierto); si no, ``en`` y ``False``."""
    base = locale.split("-")[0].lower()
    return (base, True) if base in IDIOMAS else ("en", False)


def rotulos(locale: str) -> dict[str, str]:
    """Rótulos fijos de la interfaz para el idioma del ``locale``."""
    return dict(_ROTULOS[idioma_de(locale)[0]])


def titulos_legales(locale: str) -> dict[str, str]:
    """Título de cada una de las siete páginas legales en el idioma del ``locale``."""
    return dict(_TITULOS[idioma_de(locale)[0]])


def cuerpo_legal(nombre: str, locale: str, *, marca: str, dominio: str, garantia_dias: int) -> tuple[str, ...]:
    """Párrafos (texto plano, sin escapar) de una página legal genérica con los datos de la marca."""
    return tuple(
        p.replace("{marca}", marca).replace("{dominio}", dominio).replace("{garantia_dias}", str(int(garantia_dias)))
        for p in _CUERPOS[idioma_de(locale)[0]][nombre]
    )


def etiqueta_metodo(metodo: str, locale: str) -> str:
    """Nombre visible de un método de pago de ``checkout.metodos``."""
    idioma = idioma_de(locale)[0]
    return _METODOS_MARCA.get(metodo) or _METODOS[idioma].get(metodo) or metodo.replace("_", " ").capitalize()


# ----------------------------------------------------------------------------------------------
# Importes
# ----------------------------------------------------------------------------------------------
_FORMATO_NUMERO = {  # idioma -> (decimal, millares, dígitos mínimos para agrupar)
    "es": (",", ".", 5), "it": (",", ".", 4), "pl": (",", NBSP, 5), "en": (".", ",", 4),
}
_SIMBOLO = {"EUR": "€", "USD": "$", "GBP": "£", "PLN": "zł"}


def formatear_importe(monto_minor: int, moneda: str, locale: str) -> str:
    """Importe legible con enteros: ``1990, EUR, es-ES`` -> ``19,90 €`` (espacio duro); ``en`` lleva el símbolo delante."""
    exponente = V.EXPONENTE_ISO4217.get(moneda, 2)
    entero, resto = divmod(int(monto_minor), 10 ** exponente)
    idioma = locale.split("-")[0].lower()
    decimal, millares, minimo = _FORMATO_NUMERO.get(idioma, (",", ".", 4))
    digitos = str(entero)
    if len(digitos) >= minimo:
        grupos: list[str] = []
        while digitos:
            grupos.insert(0, digitos[-3:])
            digitos = digitos[:-3]
        digitos = millares.join(grupos)
    numero = digitos + (decimal + str(resto).zfill(exponente) if exponente else "")
    simbolo = _SIMBOLO.get(moneda)
    if idioma == "en" and simbolo:
        return f"{simbolo}{numero}"
    return f"{numero}{NBSP}{simbolo or moneda}"


def formatear_rango(desde: int, hasta: int | None, moneda: str, locale: str) -> str:
    """Rango o importe de mercado SIN decimales superfluos: ``1200, 3300, PLN, pl-PL`` -> ``12–33 zł``; ``12900, None`` -> ``129 zł``; ``en`` -> ``$12–$33``.
    Enteros en unidad menor (nunca ``float``); lo usa la comparación con el mercado, cuyas cifras ajenas se marcan y se citan con su fuente."""
    exponente = V.EXPONENTE_ISO4217.get(moneda, 2)
    idioma = locale.split("-")[0].lower()
    decimal, millares, minimo = _FORMATO_NUMERO.get(idioma, (",", ".", 4))

    def numero(m: int) -> str:
        entero, resto = divmod(int(m), 10 ** exponente)
        digitos = str(entero)
        if len(digitos) >= minimo:
            grupos: list[str] = []
            while digitos:
                grupos.insert(0, digitos[-3:])
                digitos = digitos[:-3]
            digitos = millares.join(grupos)
        return digitos + (decimal + str(resto).zfill(exponente) if resto and exponente else "")

    a = numero(desde)
    b = numero(hasta) if hasta is not None and int(hasta) != int(desde) else None
    simbolo = _SIMBOLO.get(moneda)
    if idioma == "en" and simbolo:
        return f"{simbolo}{a}" + (f"–{simbolo}{b}" if b else "")
    return f"{a}" + (f"–{b}" if b else "") + f"{NBSP}{simbolo or moneda}"


# ----------------------------------------------------------------------------------------------
# Fechas y números
# ----------------------------------------------------------------------------------------------
_MESES: Mapping[str, tuple[str, ...]] = {
    "es": ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"),
    "en": ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"),
    "it": ("gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"),
    "pl": ("stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca", "lipca", "sierpnia", "września", "października", "listopada", "grudnia"),
}


def formatear_fecha(iso: str, locale: str) -> str:
    """``2026-11-30`` -> ``30 de noviembre de 2026`` (es), ``November 30, 2026`` (en), ``30 novembre 2026`` (it), ``30 listopada 2026`` (pl)."""
    anio, mes, dia = (int(x) for x in iso.split("-"))
    idioma = idioma_de(locale)[0]
    nombre = _MESES[idioma][mes - 1]
    if idioma == "en":
        return f"{nombre} {dia}, {anio}"
    if idioma == "es":
        return f"{dia} de {nombre} de {anio}"
    return f"{dia} {nombre} {anio}"


def formatear_entero(n: int, locale: str) -> str:
    """Entero con separador de millares del idioma (``1234`` -> ``1.234`` es/it, ``1 234`` pl, ``1,234`` en); sin agrupar por debajo de 4 dígitos."""
    idioma = locale.split("-")[0].lower()
    _decimal, millares, _minimo = _FORMATO_NUMERO.get(idioma, (",", ".", 4))
    digitos, grupos = str(int(n)), []
    if len(digitos) < 4:
        return digitos
    while digitos:
        grupos.insert(0, digitos[-3:])
        digitos = digitos[:-3]
    return millares.join(grupos)


def formatear_decimal(entero: int, decimas: int, locale: str) -> str:
    """``4, 8`` -> ``4,8`` (es/it/pl) o ``4.8`` (en): una cifra decimal sin ``float``."""
    idioma = locale.split("-")[0].lower()
    return f"{entero}{_FORMATO_NUMERO.get(idioma, (',', '.', 4))[0]}{decimas}"


# ----------------------------------------------------------------------------------------------
# Solo VISTA PREVIA: opiniones de demostración (nunca en producción; ``landing.validar`` las bloquea con L1-DEMO)
# ----------------------------------------------------------------------------------------------
TEXTO_VISTA_PREVIA = {
    "barra": "VISTA PREVIA — contiene contenido de demostración",
    "aviso_opiniones": "Vista previa: opiniones de demostración, no son reales",
    "aviso_valoracion": "Vista previa: valoración de demostración, no es real",
    "marcador_imagen": "[vista previa: {que}]",
}

# (nombre, texto) por idioma. Textos genéricos y sin promesas de resultado; el nombre lleva «(demo)». Solo para pintar el diseño final en vista previa.
_DEMO_RESENAS: Mapping[str, tuple[tuple[str, str], ...]] = {
    "es": (("Ana M.", "Los mapas son claros y están bien ordenados. Se leen cómodos en el móvil y también impresos."),
           ("Marcos T.", "Me gustó empezar por el nivel que me tocaba. Cada mapa se estudia en una sesión corta."),
           ("Laura G.", "Se ve que está pensado con orden. Las frases de ejemplo ayudan a entender cada palabra en contexto."),
           ("Pablo R.", "La entrega fue inmediata y los archivos abren sin problema. Fácil de seguir.")),
    "en": (("Anna M.", "The maps are clear and well organised. They read comfortably on a phone and in print."),
           ("Mark T.", "I liked starting at my own level. Each map fits into one short session."),
           ("Laura G.", "It feels carefully put together. The example sentences help me see each word in context."),
           ("Paul R.", "Delivery was instant and the files open without any trouble. Easy to follow.")),
    "it": (("Anna M.", "Le mappe sono chiare e ben ordinate. Si leggono comodamente sul telefono e anche stampate."),
           ("Marco T.", "Mi è piaciuto iniziare dal livello giusto per me. Ogni mappa si studia in una sessione breve."),
           ("Laura G.", "Si vede che è pensato con ordine. Le frasi di esempio aiutano a capire ogni parola nel contesto."),
           ("Paolo R.", "La consegna è stata immediata e i file si aprono senza problemi. Facile da seguire.")),
    "pl": (("Anna K.", "Mapy są czytelne i dobrze uporządkowane. Wygodnie się z nich korzysta na telefonie i po wydrukowaniu."),
           ("Marek T.", "Spodobało mi się, że zaczynam od swojego poziomu. Każdą mapę da się przerobić w jednej krótkiej sesji."),
           ("Kasia W.", "Widać, że całość jest przemyślana. Zdania przykładowe pomagają zrozumieć słowa w kontekście."),
           ("Piotr S.", "Pliki dotarły od razu i otwierają się bez problemu. Łatwo się z nich korzysta.")),
}


def demo_resenas(locale: str) -> list[dict[str, str]]:
    """Cuatro opiniones de DEMOSTRACIÓN del idioma (solo vista previa): ``nombre`` (con «(demo)»), ``inicial`` y ``texto``."""
    return [{"nombre": f"{n} (demo)", "inicial": n[0], "texto": t} for n, t in _DEMO_RESENAS[idioma_de(locale)[0]]]


def rotulos_de_imagen(locale: str, personalizados: Mapping[str, str] | None = None) -> dict[str, str]:
    """Rótulos de las imágenes ilustrativas y de IA en el idioma del ``locale``: ``ilustrativa`` (insignia), ``ilustrativa_pie`` (pie de grupo) e ``ia``.

    ``personalizados`` (``copy.rotulos_imagen``: ``ilustrativa``, ``ilustrativa_pie``, ``ia``) sustituye al texto por defecto; solo cuenta lo que trae texto."""
    t = rotulos(locale)
    base = {"ilustrativa": t["rotulo_ilustrativa"], "ilustrativa_pie": t["rotulo_ilustrativa_pie"], "ia": t["rotulo_ia"]}
    for k in base:
        v = (personalizados or {}).get(k)
        if isinstance(v, str) and v.strip():
            base[k] = " ".join(v.split())
    return base
