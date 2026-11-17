"""Reglas de palabras del control de calidad de 6 puntos (qc6.py): red mínima, multi-idioma, sin red.

Qué es: una lista de patrones sobre texto **plegado** (minúsculas, sin tildes, ł→l, ß→ss) para los puntos
«nada de material ajeno» y «sin precios ni promesas prohibidas» de la fábrica de creativos (D6). Sale de
`references/lista-rojo-amarillo.md`, de la lista de claims rojos de D5 (`d5-landing-checkout/references/claims-rojos.md`
y su `lint_copy.py`) y de las semillas por idioma de D6. **No sustituye** a `compliance.lint_claims` ni al veto de X1:
es una red adicional que cubre los idiomas y los patrones que el lint oficial todavía no cubre (it, pl, fr, de, ro,
verbos de cambio, atributo del espectador en pregunta) y que corre aunque `compliance` no esté en el PYTHONPATH.
Todos los patrones son `[HIPÓTESIS]` sin revisión de un nativo; un hallazgo ROJO nunca se «arregla» cambiando palabras
(regla LM-08): se corrige el claim.

Niveles: ``rojo`` → el punto da «falla»; ``amarillo`` → «revisar» (decide una persona o el QA).
"""
from __future__ import annotations

import re
import unicodedata

VERSION_REGLAS = "0.1.0"

# --------------------------------------------------------------------------------------- plegado de texto
_ESPECIALES = str.maketrans({"ł": "l", "Ł": "l", "đ": "d", "ø": "o", "æ": "ae", "œ": "oe", "ß": "ss", "ı": "i"})


def plegar(texto: str) -> str:
    """Minúsculas, sin marcas diacríticas, ł→l, ß→ss, espacios colapsados. Conserva símbolos (€, $, ★, ™, ©)."""
    t = unicodedata.normalize("NFKD", texto.lower().translate(_ESPECIALES))
    t = "".join(c for c in t if not unicodedata.combining(c))
    return " ".join(t.split())


# --------------------------------------------------------------------------------------- promesas prohibidas
_VERBOS_ES = r"(?:aprend|habl|domin|baj|perd|gan|consegu|logr|ahorr|elimin|recuper|adelgaz|sal[gi]|cur)\w*"
_VERBOS_EN = r"(?:learn|speak|lose|gain|earn|make|master|fix|get|save|reach|become|cure|heal)\w*"
_VERBOS_IT = r"(?:impar|parl|perd|guadagn|ottien|risolv|dimagr|elimin)\w*"
_VERBOS_PL = r"(?:naucz|mow|schudn|zarob|opanuj|osiagn|wyleczy|pozbad|odzysk)\w*"
_VERBOS_FR = r"(?:apprenez|parlez|perdez|gagnez|maitrisez|sortez|maigrissez|economisez|guerissez)\w*"
_VERBOS_DE = r"(?:lern|sprech|verlier|verdien|abnehm|meistern)\w*"
_VERBOS_RO = r"(?:invata|vorbeste|slabeste|castiga|elimina)\w*"
_UNID = r"(?:dias?|semanas?|meses|horas?|days?|weeks?|months?|hours?|giorni|settimane|mesi|ore|dni|dzien|tygodni\w*|miesiac\w*|godzin\w*|jours?|semaines?|mois|heures?|tagen?|wochen?|monaten?|stunden?|zile|saptamani|luni)"
_N = r"\d+\s*"


def _cambio(verbos: str, prep: str) -> str:
    """Verbo de cambio + hasta 5 palabras + «en/in/w N unidad»: plazo de RESULTADO."""
    return rf"{verbos}\W+(?:\w+\W+){{0,5}}?{prep}\s+{_N}{_UNID}\b"


CATEGORIAS: dict[str, dict[str, object]] = {
    "ingresos": {"nivel": "rojo", "p07": "X1-P01/P02", "patrones": [
        r"\bgan(?:a|e|ar|as|ando|arte|aras)\s+(?:dinero|plata|\$|€|\d)", r"\bingresos?\s+(?:pasivos?|extra|garantizados?|mensuales?)",
        r"\bdinero\s+(?:mientras|extra|facil)", r"libertad\s+financiera", r"\bfactur\w+\s+\d", r"vivir\s+de\s+(?:esto|tu\s+pasion)",
        r"deja\s+tu\s+empleo", r"\bahorr\w+\s+(?:\$|€|\d)",
        r"\bmake\s+(?:money|\$|€|£|\d)", r"\bearn\s+(?:money|\$|€|£|\d)", r"passive\s+income", r"financial\s+freedom", r"quit\s+your\s+job",
        r"\bsave\s+(?:\$|€|£)\s?\d",
        r"\bguadagn\w+\s+(?:\d|\$|€|soldi)", r"liberta\s+finanziaria", r"reddito\s+passivo", r"\brisparmi\w+\s+(?:\d|€)",
        r"\bzarabi\w+\s+(?:\d|pieniadze|na\s)", r"\d+\s*(?:zl|pln)\s+(?:miesiecznie|dziennie|tygodniowo)", r"pasywny\s+dochod|dochod\s+pasywny",
        r"wolnosc\s+finansowa", r"\boszczedz\w+\s+\d",
        r"\bgagnez\s+(?:\d|de\s+l.argent)", r"revenus?\s+passifs?", r"liberte\s+financiere", r"\beconomisez\s+\d",
        r"\bverdien\w+\s+(?:sie\s+)?\d", r"passives\s+einkommen", r"finanzielle\s+freiheit", r"\bsparen\s+sie\s+\d",
        r"\bcastiga\s+\d", r"venit\s+pasiv", r"libertate\s+financiara", r"\beconomiseste\s+\d",
    ]},
    "plazo_resultado": {"nivel": "rojo", "p07": "X1-P02/P07", "patrones": [
        _cambio(_VERBOS_ES, "en"), _cambio(_VERBOS_EN, "in"), _cambio(_VERBOS_IT, "in"),
        _cambio(_VERBOS_PL, r"(?:w|za)"), _cambio(_VERBOS_FR, "en"), _cambio(_VERBOS_DE, "in"), _cambio(_VERBOS_RO, "in"),
        r"\b(?:perder|perdi|lose|schudnij|perdez)\s+\d+\s*(?:kg|kilos?|libras|lbs|pounds)",
        r"\bplynnie\b", r"\bfluently\b", r"\bfluidamente\b", r"\bcon\s+fluidez\b", r"\bsekret\w*\s+poliglot", r"\bcud(?:owny|owna|ow\w+)?\b", r"metoda\s+cudown",
    ]},
    "plazo_ambiguo": {"nivel": "amarillo", "p07": "X1-P02", "patrones": [
        rf"\b(?:en|in|w|za|dans)\s+{_N}{_UNID}\b",
    ]},
    "garantia_resultado": {"nivel": "rojo", "p07": "X1-P03", "patrones": [
        r"\bgarantiz\w+", r"resultados?\s+garantizados?", r"100\s?%\s+(?:garantiz|seguro|efectiv)",
        r"si\s+no\s+(?:consigues|logras|ahorras|bajas|adelgazas|recuperas|ganas|encuentras|aprendes|hablas)",
        r"\bguaranteed\b", r"money.back\s+if\s+you", r"if\s+you\s+(?:don.?t|do\s+not)\s+(?:get|lose|save|earn|find|land|learn)",
        r"\bgarantit\w+", r"se\s+non\s+(?:ottieni|risparmi|perdi|guadagni|impari)", r"\bgwarantowan\w+|\bgwarantujemy",
        r"jesli\s+nie\s+(?:schudniesz|zaoszczedzisz|zarobisz|nauczysz)", r"resultats?\s+garantis?\b|\bgarantissons",
        r"si\s+vous\s+ne\s+(?:perdez|gagnez|economisez|parlez)", r"\bgarantiert\b", r"garantat\w*\s+(?:rezultat|castig)",
    ]},
    "facilidad": {"nivel": "rojo", "p07": "X1-P07", "patrones": [
        r"\bsin\s+(?:experiencia|inversion|esfuerzo|conocimientos)", r"a\s+prueba\s+de\s+tontos", r"\bno\s+(?:experience|investment)\s+(?:needed|required)?",
        r"\beffortless\b", r"\bsenza\s+(?:esperienza|investimento|sforzo)", r"\bbez\s+(?:doswiadczenia|inwestycji|wysilku)",
        r"\bsans\s+(?:experience|investissement|effort)", r"\bohne\s+(?:erfahrung|investition|aufwand)", r"\bfara\s+(?:experienta|investitie|efort)",
    ]},
    "facilidad_ambigua": {"nivel": "amarillo", "p07": "X1-P07", "patrones": [
        r"\b(?:facil|facilmente|rapido|rapida|automatico|automatica|easy|easily|quick|quickly|facile|veloce|latwo|szybko|rapide|einfach|schnell|usor)\b",
    ]},
    "salud": {"nivel": "rojo", "p07": "X1-P01/LP-01", "patrones": [
        r"\bcur(?:a|ar|arte|arse|ado|amos|ate)\b", r"\bsana(?:r|rte|rse)\b", r"\brevert\w+", r"adelgaz\w+", r"bajar\s+de\s+peso",
        r"\bdetox\b", r"quema\w*\s+grasa", r"sin\s+dieta", r"metabolismo", r"cortisol", r"\b(?:cure|heal|reverse)s?\b",
        r"lose\s+\d+\s*(?:kg|lbs|pounds)", r"burn\s+fat", r"weight\s+loss", r"\bguarisc\w+", r"dimagr\w+", r"senza\s+dieta",
        r"\bleczy\b|leczeni\w+|\bschudn\w+|\bodchudz\w+", r"\bguerir\b|\bguerison", r"perdre\s+du\s+poids|\bmaigrir\b|\bminceur\b",
        r"\bheilt\b|\bheilen\b|\babnehmen\b", r"\bvindec\w+|\bslabi\w+",
    ]},
    "atributo_espectador": {"nivel": "rojo", "p07": "X1-E01", "patrones": [
        r"\b(?:estas|eres|sos|sufres|padeces|tienes|tenes)\s+(?:endeudad|obes|deprimid|ansios|gord|solter|divorciad|viud|cansad|agotad|desemplead|arruinad|sin\s+trabajo)\w*",
        r"\btu\s+ex\b", r"\bmadres?\s+(?:solteras?|agotadas?)", r"\bmamas?\s+agotadas?", r"\btu\s+(?:hijo|hija)\s+con\b",
        r"\bsi\s+(?:estas|eres|sos|sufres|padeces)\s+\w+", r"\b(?:mas\s+de|tras\s+los|despues\s+de\s+los)\s+\d{2}\b",
        r"\b(?:are|r)\s+you\s+(?:broke|fat|depressed|anxious|in\s+debt|lonely|single|overweight)", r"\byour\s+ex\b",
        r"\bif\s+you\s+(?:are|struggle|suffer)\s+(?:from|with|a|an|in)\b",
        r"\bsei\s+(?:indebitat|obes|depress|ansios|single|stanc)\w*", r"\til\s+tuo\s+ex\b",
        r"\bjestes\s+(?:zadluzon|otyl|zdolowan|samotn|zmeczon|bezrobotn)\w*", r"\btwoj\s+byly\b", r"\bmasz\s+(?:dlugi|depresje|nadwage)\b",
        r"\bvous\s+etes\s+(?:surendett|obes|deprim|anxieu|fatigu)\w*", r"\bton\s+ex\b|\bvotre\s+ex\b",
        r"\bsind\s+sie\s+(?:verschuldet|ubergewichtig|depressiv|erschopft)", r"\bdein\s+ex\b",
        r"\besti\s+(?:indatorat|obez|deprimat)\w*", r"te\s+insala\s+partenerul",
    ]},
    "autopercepcion_negativa": {"nivel": "rojo", "p07": "X1-E01", "patrones": [
        r"\b(?:inutil|insuficiente|fracasad[oa]|verguenza|worthless|ashamed|inutile|insufficiente|vergogna|beznadziejn\w+|wstyd|honte|wertlos|scham|rusine)\b",
        r"not\s+good\s+enough", r"deja\s+de\s+sentirte",
    ]},
    "escasez_urgencia": {"nivel": "rojo", "p07": "X1-P05", "patrones": [
        r"\bquedan?\s+\d+", r"\bultim[oa]s?\s+(?:plazas?|cupos?|unidades|\d+)", r"\bcupos?\b", r"plazas?\s+limitadas", r"solo\s+(?:por\s+)?hoy",
        r"cuenta\s+regresiva", r"oferta\s+(?:termina|finaliza|vence)", r"stock\s+limitado", r"se\s+agota(?:n)?\b",
        r"\bonly\s+\d+\s+(?:left|remaining|spots)", r"\bcountdown\b", r"limited\s+(?:time|spots|stock|offer)", r"today\s+only", r"offer\s+ends",
        r"selling\s+fast", r"last\s+chance", r"solo\s+\d+\s+(?:posti|rimast)", r"\bultimi\s+\d+", r"solo\s+oggi", r"offerta\s+limitata",
        r"posti\s+limitati", r"conto\s+alla\s+rovescia", r"zostalo\s+(?:tylko\s+)?\d+", r"ostatnie\s+(?:sztuki|miejsca)", r"tylko\s+dzis",
        r"ograniczona\s+(?:oferta|liczba)", r"\bodliczanie\b", r"il\s+reste\s+\d+", r"derni[e]res?\s+places", r"offre\s+limitee",
        r"aujourd.hui\s+seulement", r"compte\s+a\s+rebours", r"nur\s+noch\s+\d+", r"nur\s+heute", r"begrenzte\s+(?:anzahl|platze|angebot)",
        r"letzte\s+chance", r"doar\s+astazi", r"stoc\s+limitat", r"au\s+mai\s+ramas\s+\d+",
    ]},
    "prueba_social_inventada": {"nivel": "rojo", "p07": "X1-P08", "patrones": [
        r"(?:miles|cientos)\s+de\s+(?:personas|alumnos|clientes|estudiantes|compradores)",
        r"\+\s?\d[\d.,]*\s*(?:alumnos|clientes|compradores|estudiantes|students|customers|buyers|studenti|clienti|uczni\w*|kursant\w*|klient\w*|eleves|clients|schueler|kunden|elevi)",
        r"\d[\d.,]*\s*(?:alumnos|clientes|compradores|estudiantes|students|customers|buyers)\s+(?:satisfech|felices|happy|satisfied)",
        r"tysiac\w*\s+(?:zadowolonych|klientow|uczniow)", r"(?:clientes?|customers?|klienci)\s+(?:satisfech|satisfied|zadowolon)",
        r"\btestimonios?\b|\btestimonials?\b|\brecensioni\b|opinie\s+klientow|\bavis\s+clients?\b|\bbewertungen\b",
        r"resenas?\s+(?:verificadas|reales|de\s+clientes)", r"\b[1-5][.,][0-9]\s*/\s*5\b",
        r"\b[1-5][.,][0-9]\s*(?:estrellas|stars|stelle|gwiazd\w*|etoiles|sterne|stele)", r"[★⭐]",
    ]},
    "testimonio_en_primera_persona": {"nivel": "rojo", "p07": "X1-P04/P08", "patrones": [
        r"\b(?:consegui|logre|baje|perdi|ahorre|recupere|aprendi|gane|encontre)\s+\w+", r"\bi\s+(?:got|lost|made|earned|saved|learned|finally|went)\b",
        r"\bho\s+(?:perso|guadagnato|imparato|risparmiato|ottenuto)\b", r"\b(?:schudlem|schudlam|zarobilem|zarobilam|nauczylem|nauczylam|oszczedzilem|oszczedzilam)\b",
        r"\bj.ai\s+(?:perdu|gagne|appris|economise|obtenu)\b", r"\bich\s+habe\s+(?:\w+\s+)?(?:verloren|verdient|gelernt|gespart)\b", r"\bam\s+(?:slabit|castigat|invatat|economisit)\b",
        r"\w,\s*\d{2}\s*(?:anos|anni|lat|ans|jahre|ani|years?)\b",
    ]},
    "aviso_compra_falso": {"nivel": "rojo", "p07": "X1-P08", "patrones": [
        r"acaba\s+de\s+(?:comprar|adquirir)", r"(?:compro|compraron)\s+hace\s+\d+", r"\bjust\s+(?:bought|purchased)",
        r"\d+\s+(?:people|others)\s+(?:are\s+)?(?:viewing|watching|buying)", r"\d+\s+personas?\s+(?:viendo|mirando|comprando)",
        r"ktos\s+wlasnie\s+kupil", r"qualcuno\s+ha\s+appena\s+acquistato", r"vient\s+d.acheter", r"hat\s+gerade\s+gekauft",
    ]},
    "autoridad_falsa": {"nivel": "rojo", "p07": "LP-08", "patrones": [
        r"aprobad[oa]\s+por", r"recomendad[oa]\s+por", r"visto\s+en\s+(?:tv|forbes|cnn)", r"as\s+seen\s+(?:on|in)", r"featured\s+(?:on|in)",
        r"approved\s+by", r"endorsed\s+by", r"raccomandato\s+da|approvato\s+da", r"polecan\w+\s+przez|zatwierdzon\w+\s+przez",
        r"recommande\s+par|approuve\s+par", r"empfohlen\s+von", r"recomandat\s+de",
    ]},
    "credenciales": {"nivel": "amarillo", "p07": "LP-08", "patrones": [
        r"\b(?:medico|doctor|doctora|psicolog[oa]|abogad[oa]|nutricionista|certificad[oa]|certified|expert[oa]?|experts?|psycholog\w+|lekarz|terapeut\w+)\b",
    ]},
    "antes_despues": {"nivel": "rojo", "p07": "X1-P04", "patrones": [
        r"\bantes\s*(?:y|/|vs\.?|&)\s*despues", r"\bbefore\s*(?:and|/|&|vs\.?)\s*after", r"\bprima\s*(?:e|/)\s*dopo", r"\bprzed\s*(?:i|/)\s*po\b",
        r"\bavant\s*(?:/|et)\s*apres", r"\bvorher\s*(?:/|-|und)\s*nachher", r"\binainte\s*(?:si|/)\s*dupa", r"\bdia\s+1\s+(?:vs|contra)\s+dia\s+\d+",
    ]},
    "relaciones_manipulacion": {"nivel": "rojo", "p07": "LP-04", "patrones": [
        r"recupera\w*\s+a\s+tu\s+ex", r"get\s+your\s+ex\s+back", r"hace(?:r|le)?\s+que\s+(?:te|se)\s+(?:ame|enamore)", r"make\s+(?:him|her|them)\s+(?:love|fall)",
        r"descubre\s+si\s+te\s+(?:enganya|engana|miente)", r"narcisista", r"fai\s+in\s+modo\s+che\s+si\s+innamori", r"odzyskaj\s+byl\w+", r"te\s+insala",
    ]},
    "plataforma": {"nivel": "rojo", "p07": "localizacion.md regla 6", "patrones": [
        r"(?:link|enlace)\s+en\s+(?:la\s+|mi\s+)?bio", r"en\s+mi\s+bio", r"link\s+in\s+(?:my\s+|der\s+)?bio", r"link\s+w\s+bio", r"lien\s+en\s+bio",
    ]},
    "pago_local": {"nivel": "amarillo", "p07": "localizacion.md regla 5", "patrones": [
        r"\b(?:bizum|blik|satispay|przelewy\s?24|mbway|mercado\s?pago|paypal)\b",
    ]},
    "menores": {"nivel": "amarillo", "p07": "X1-E03", "patrones": [
        r"\b(?:ninos?|ninas?|bebes?|menores|kids?|children|bambini|dzieci|enfants|kinder|copii)\b",
    ]},
    "marcador_sin_resolver": {"nivel": "rojo", "p07": "render", "patrones": [
        r"lorem\s+ipsum", r"\{\{|\}\}", r"\[(?:supuesto|verificar|pendiente)", r"\bplaceholder\b", r"\bxxx+\b", r"\btodo:",
    ]},
}

# --------------------------------------------------------------------------------------- material ajeno
MARCAS = (
    "facebook", "instagram", "meta ads", "whatsapp", "tiktok", "youtube", "google", "amazon", "netflix", "spotify", "apple", "microsoft",
    "duolingo", "babbel", "busuu", "memrise", "rosetta stone", "coursera", "udemy", "skillshare", "hotmart", "gumroad", "canva", "chatgpt",
    "openai", "ikea", "nike", "adidas", "coca-cola", "disney", "pixar", "marvel", "harry potter",
)
MEDIOS = (
    r"as seen on", r"visto en", r"featured in", r"\bforbes\b", r"\bcnn\b", r"\bbbc\b", r"new york times", r"\bel pais\b", r"\brtve\b", r"\bbloomberg\b",
    r"\btechcrunch\b",
)
MARCAS_AGUA = (
    r"shutterstock", r"getty\s*images", r"istock", r"adobe\s*stock", r"freepik", r"depositphotos", r"alamy", r"dreamstime", r"123rf",
    r"\bpexels\b", r"\bunsplash\b", r"\bpixabay\b", r"stock\s+photo", r"©",
)
SIMBOLOS_MARCA = r"[™®]"
ENLACES = (
    r"https?://\S+", r"\bwww\.\S+", r"\b[a-z0-9][a-z0-9-]*\.(?:com|net|org|pl|es|it|fr|de|ro|io|store|app|shop|me|co)\b",
)
ARROBAS = r"(?<![\w.])@[a-z0-9_.]{3,}"

# --------------------------------------------------------------------------------------- precios
MONEDA = r"(?:€|\$|£|eur\b|usd\b|gbp\b|pln\b|zl\b|lei\b|ron\b|chf\b|us\$)"
NUM_PRECIO = r"\d{1,3}(?:[ . ]\d{3})*(?:[.,]\d{1,2})?|\d+(?:[.,]\d{1,2})?"
PRECIO_RX = re.compile(rf"(?:(?:{MONEDA})\s?(?P<a>{NUM_PRECIO}))|(?:(?P<b>{NUM_PRECIO})\s?{MONEDA})")

# --------------------------------------------------------------------------------------- pruebas integradas
# Frases que DEBEN dar rojo y frases que NO deben dar rojo (aprobables y dorados de la skill). Las usa tests/creativos.
PRUEBAS_ROJO = (
    "Ganá 3.000 al mes trabajando desde casa", "Ahorrá 1.378 € en un año", "Aprende inglés en 30 días", "¿Estás endeudado? Sal en 90 días",
    "Recupera a tu ex en 7 días", "Resultados garantizados", "Sin experiencia y sin inversión", "Solo hoy: quedan 3 plazas", "+3.482 alumnos ya lo usan",
    "4,9/5 ★★★★★", "Perdi 8 kg in 30 giorni senza dieta", "Guadagna 2.000 € al mese da casa", "Jesteś zadłużony? Pozbądź się długów w 3 miesiące",
    "Schudnij 10 kg w miesiąc", "Odzyskaj byłego w 7 dni", "Mów płynnie po angielsku", "Poznaj sekret poliglotów", "Zostało tylko 3 miejsc",
    "Tysiące zadowolonych klientów", "Vous êtes surendetté ? Sortez-en en 90 jours", "Sind Sie verschuldet?", "Câștigă 3.000 de lei pe lună",
    "Te înșală partenerul?", "Lose 15 lbs in 2 weeks", "Is your partner cheating? Make money fast", "Link en la bio", "Someone just bought this",
    "Antes y después de tu cuerpo", "Aprobado por Meta", "«Con esta guía conseguí tres entrevistas», cuenta Marta, 34 años", "I finally lost the weight, says Anna",
)
PRUEBAS_VERDE = (
    "Recetario con tabla de azúcar añadida y fibra por porción", "10 preguntas para ordenar tus ideas antes de decidir si escribir a un ex",
    "Método de 4 pasos para ordenar pagos pendientes en una hoja", "Planner settimanale dei pasti", "Quaderno di 20 domande per conoscersi in coppia",
    "Modello Excel per costi, prezzo e margine", "Tygodniowy planer posiłków", "Arkusz 10 pytań przed decyzją",
    "Metoda w 4 krokach do uporządkowania zobowiązań", "Weekly meal-prep planner with grocery lists", "Checklist to prepare a hard conversation",
    "Zero-based budget template", "Méthode en 4 étapes pour ordonner des échéances de paiement", "Fristenkalender und Belegordner",
    "Costo por vela, precio mínimo y margen en una sola hoja.", "Un planner settimanale dei pasti con la lista della spesa già pronta.",
    "Arkusz: koszt, cena minimalna i marża w jednej tabeli.", "Twenty conversation cards for a quiet evening together.",
    "Des fiches de mobilité de 10 minutes pour les pauses.", "Un tabel pentru costurile unui produs handmade.",
    "Arbeitsmappe als PDF: Fragen vor einem schwierigen Gespräch.", "Garantía de devolución de 14 días", "Plan de 14 días",
    "Plantilla lista para completar", "Una pausa laboral no es un hueco: es un relato que se puede contar.",
    "Gwarancja 14 dni · Pobierz jedną mapę za darmo", "Mapy myśli, poziom po poziomie: A1, A2, B1, B2, C1, C2",
)

COMPILADAS = {
    nombre: {"nivel": datos["nivel"], "p07": datos.get("p07", ""), "rx": [re.compile(p) for p in datos["patrones"]]}  # type: ignore[index]
    for nombre, datos in CATEGORIAS.items()
}


def buscar(texto_plegado: str) -> list[dict[str, str]]:
    """Hallazgos de las categorías de promesas sobre un texto ya plegado: [{categoria, nivel, evidencia, ref}]."""
    salida: list[dict[str, str]] = []
    for nombre, c in COMPILADAS.items():
        for rx in c["rx"]:  # type: ignore[union-attr]
            m = rx.search(texto_plegado)
            if m:
                desde, hasta = max(0, m.start() - 20), min(len(texto_plegado), m.end() + 20)
                salida.append({"categoria": nombre, "nivel": str(c["nivel"]), "evidencia": texto_plegado[desde:hasta].strip(), "ref": str(c["p07"])})
                break  # una coincidencia por categoría basta para el semáforo; el detalle sale de la evidencia
    return salida
