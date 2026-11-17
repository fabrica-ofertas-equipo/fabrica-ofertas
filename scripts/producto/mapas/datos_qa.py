"""Listas de las capas automáticas de QA de idioma (J11): falsos amigos PL↔EN, marcas, sensibles, promesas, jerga y palabras elementales.

Son listas INTERINAS y deliberadamente cortas (solo lo que el equipo conoce con certeza): sirven para cazar lo evidente, no para
certificar un idioma. Crecen con cada defecto real que encuentre la revisión ciega (regla: un defecto repetido pasa a la lista).
Todo se compara en minúsculas y sin distinguir diacríticos solo donde se indica.
"""
from __future__ import annotations

# ── falsos amigos EN→PL ────────────────────────────────────────────────────────────────────────────────────────────────────
# en: palabra inglesa · falso: traducciones polacas que son el «amigo falso» (si aparecen como traducción = error) ·
# raiz_pl: raíces para cazar el calco en las frases polacas · correcto: lo que significa de verdad · nota_pl: texto sugerido para uwaga_pl
# (≤ 40 caracteres) · marcar: si True, la palabra DEBE llevar uwaga_pl cuando es palabra de una rama (el aprendiz polaco cae en la trampa).
FALSOS_AMIGOS: list[dict] = [
    {"en": "actual", "falso": ["aktualny"], "raiz_pl": ["aktualn"], "correcto": ["rzeczywisty", "faktyczny"], "nota_pl": "nie „aktualny”: rzeczywisty", "marcar": True},
    {"en": "actually", "falso": ["aktualnie"], "raiz_pl": ["aktualnie"], "correcto": ["właściwie", "naprawdę"], "nota_pl": "nie „aktualnie”: właściwie", "marcar": True},
    {"en": "eventually", "falso": ["ewentualnie"], "raiz_pl": ["ewentualn"], "correcto": ["w końcu", "ostatecznie"], "nota_pl": "nie „ewentualnie”: w końcu", "marcar": True},
    {"en": "eventual", "falso": ["ewentualny"], "raiz_pl": ["ewentualn"], "correcto": ["ostateczny"], "nota_pl": "nie „ewentualny”: ostateczny", "marcar": True},
    {"en": "sympathetic", "falso": ["sympatyczny"], "raiz_pl": ["sympatyczn"], "correcto": ["współczujący"], "nota_pl": "nie „sympatyczny”: współczujący", "marcar": True},
    {"en": "sympathy", "falso": ["sympatia"], "raiz_pl": ["sympati"], "correcto": ["współczucie"], "nota_pl": "nie „sympatia”: współczucie", "marcar": True},
    {"en": "pension", "falso": ["pensja"], "raiz_pl": ["pensj"], "correcto": ["emerytura"], "nota_pl": "nie „pensja”: emerytura", "marcar": True},
    {"en": "magazine", "falso": ["magazyn"], "raiz_pl": ["magazyn"], "correcto": ["czasopismo"], "nota_pl": "nie „magazyn”: czasopismo", "marcar": True},
    {"en": "lecture", "falso": ["lektura"], "raiz_pl": ["lektur"], "correcto": ["wykład"], "nota_pl": "nie „lektura”: wykład", "marcar": True},
    {"en": "fabric", "falso": ["fabryka"], "raiz_pl": ["fabryk"], "correcto": ["tkanina"], "nota_pl": "nie „fabryka”: tkanina", "marcar": True},
    {"en": "physician", "falso": ["fizyk"], "raiz_pl": ["fizyk"], "correcto": ["lekarz"], "nota_pl": "nie „fizyk”: lekarz", "marcar": True},
    {"en": "sensitive", "falso": ["sensowny"], "raiz_pl": ["sensown"], "correcto": ["wrażliwy"], "nota_pl": "nie „sensowny”: wrażliwy", "marcar": True},
    {"en": "genial", "falso": ["genialny"], "raiz_pl": ["genialn"], "correcto": ["serdeczny"], "nota_pl": "nie „genialny”: serdeczny", "marcar": True},
    {"en": "novel", "falso": ["nowela"], "raiz_pl": ["nowel"], "correcto": ["powieść"], "nota_pl": "nie „nowela”: powieść", "marcar": True},
    {"en": "agenda", "falso": ["agenda"], "raiz_pl": ["agend"], "correcto": ["porządek obrad"], "nota_pl": "agenda = porządek obrad", "marcar": True},
    {"en": "accurate", "falso": ["akuratny"], "raiz_pl": ["akuratn"], "correcto": ["dokładny"], "nota_pl": "nie „akuratny”: dokładny", "marcar": True},
    {"en": "ordinary", "falso": ["ordynarny"], "raiz_pl": ["ordynarn"], "correcto": ["zwyczajny"], "nota_pl": "nie „ordynarny”: zwyczajny", "marcar": True},
    {"en": "dress", "falso": ["dres"], "raiz_pl": ["dres"], "correcto": ["sukienka"], "nota_pl": "nie „dres”: sukienka", "marcar": True},
    {"en": "pretend", "falso": ["pretendować"], "raiz_pl": ["pretendu"], "correcto": ["udawać"], "nota_pl": "nie „pretendować”: udawać", "marcar": True},
    {"en": "billion", "falso": ["bilion"], "raiz_pl": ["bilion"], "correcto": ["miliard"], "nota_pl": "billion = miliard, nie bilion", "marcar": True},
    {"en": "gymnasium", "falso": ["gimnazjum"], "raiz_pl": ["gimnazj"], "correcto": ["sala gimnastyczna"], "nota_pl": "nie „gimnazjum”: sala gimnastyczna", "marcar": True},
    {"en": "recipe", "falso": ["recepta"], "raiz_pl": ["recept"], "correcto": ["przepis"], "nota_pl": "nie „recepta”: przepis", "marcar": True},
    {"en": "receipt", "falso": ["recepta"], "raiz_pl": ["recept"], "correcto": ["paragon"], "nota_pl": "nie „recepta”: paragon", "marcar": True},
    {"en": "evidence", "falso": ["ewidencja"], "raiz_pl": ["ewidencj"], "correcto": ["dowód"], "nota_pl": "nie mylić z „ewidencją”", "marcar": True},
    {"en": "pathetic", "falso": ["patetyczny"], "raiz_pl": ["patetyczn"], "correcto": ["żałosny"], "nota_pl": "nie „patetyczny”: żałosny", "marcar": True},
    {"en": "affair", "falso": ["afera"], "raiz_pl": ["afer"], "correcto": ["sprawa"], "nota_pl": "nie „afera”: sprawa", "marcar": True},
    {"en": "chef", "falso": ["szef"], "raiz_pl": ["szef"], "correcto": ["szef kuchni"], "nota_pl": "chef = szef kuchni", "marcar": True},
    {"en": "resort", "falso": ["resort"], "raiz_pl": ["resort"], "correcto": ["kurort"], "nota_pl": "nie „resort”: kurort", "marcar": True},
    {"en": "sale", "falso": ["sala"], "raiz_pl": ["sala"], "correcto": ["wyprzedaż"], "nota_pl": "nie „sala”: wyprzedaż", "marcar": False},
    {"en": "promotion", "falso": ["promocja"], "raiz_pl": ["promocj"], "correcto": ["awans"], "nota_pl": "w pracy: awans, nie „promocja”", "marcar": False},
    {"en": "dispute", "falso": ["dysputa"], "raiz_pl": ["dysput"], "correcto": ["spór"], "nota_pl": "nie „dysputa”: spór", "marcar": True},
    {"en": "colleague", "falso": ["kolega"], "raiz_pl": ["koleg"], "correcto": ["współpracownik"], "nota_pl": "kolega (znajomy) = friend, nie colleague", "marcar": True},
    {"en": "data", "falso": ["data"], "raiz_pl": ["dat"], "correcto": ["dane"], "nota_pl": "data = dane; „date” = data", "marcar": True},
    {"en": "list", "falso": ["list"], "raiz_pl": ["list"], "correcto": ["lista"], "nota_pl": "list = lista, nie polski „list”", "marcar": True},
    {"en": "pasta", "falso": ["pasta"], "raiz_pl": ["past"], "correcto": ["makaron"], "nota_pl": "pasta = makaron, nie „pasta”", "marcar": True},
]

# ── marcas y nombres comerciales (BLOQUEANTE: no hay marcas en el producto) ───────────────────────────────────────────────────
MARCAS = [
    "google", "facebook", "instagram", "whatsapp", "tiktok", "youtube", "netflix", "spotify", "iphone", "microsoft",
    "coca-cola", "coca cola", "pepsi", "mcdonald", "adidas", "ikea", "allegro", "lego", "skype",
    "twitter", "linkedin", "wikipedia", "chatgpt", "openai", "duolingo", "pinterest", "snapchat", "photoshop",
]
# nombres de marca que también son palabras comunes: solo se marcan escritos con mayúscula y fuera de inicio de frase (MAYOR)
MARCAS_AMBIGUAS = ["Apple", "Amazon", "Windows", "Zoom", "Word", "Excel", "Tesla", "Nike", "Android", "Uber", "Bluetooth"]
MARCAS_DUDOSAS = ["wi-fi", "wifi", "post-it", "jacuzzi", "tipp-ex", "velcro", "hoover", "kleenex", "sellotape", "tannoy"]  # nombres de marca de uso común: MAYOR

# ── contenido sensible (para revisión humana/de segundo agente; no se prohíbe el vocabulario general) ────────────────────────────
SENSIBLES_BLOQUEANTES = [
    "porn", "porno", "nude", "naked", "sexy", "erotic", "erotyczn", "seks", "nagi", "nagość", "rape", "gwałt", "suicide", "samobójstw", "self-harm",
    "nigger", "faggot", "retard", "whore", "slut", "kurwa", "pierdol", "chuj", "jebać", "pizda", "spierdalaj",
]
SENSIBLES_REVISAR = [
    "kill", "murder", "weapon", "gun", "bomb", "terror", "cocaine", "heroin", "marijuana", "weed", "drunk", "alcohol", "cigarette", "smoking",
    "zabić", "morderstwo", "broń", "bomba", "terroryzm", "kokaina", "heroina", "narkotyk", "pijany", "alkohol", "papieros",
    "partia", "election", "wybory", "religion", "religia", "god", "bóg", "church", "kościół",
]

# ── promesas de resultado, plazos y urgencia (claims_prohibidos de la oferta) ────────────────────────────────────────────────────
PROMESAS_PL = [
    r"płynnie", r"gwarantowan", r"gwarancj", r"w\s+\d+\s+(?:dni|dzień|tygodni|miesięcy|miesiąc)", r"w\s+(?:miesiąc|rok|tydzień)\b", r"szybko\s+(?:nauczysz|opanujesz)",
    r"bez\s+wysiłku", r"sekret", r"cudown", r"nigdy\s+nie\s+zapomnisz", r"na\s+pewno\s+(?:zdasz|nauczysz)", r"certyfikat", r"zdasz\s+egzamin", r"efekt\s+gwarantowany",
    r"tylko\s+dziś", r"ostatnie\s+sztuki", r"najlepszy\s+(?:kurs|sposób)",
]
PROMESAS_EN = [
    r"\bfluent\s+in\b", r"\bguarantee[sd]?\b.*\b(?:result|success|fluency)\b", r"\bin\s+\d+\s+days?\b", r"\bovernight\b", r"\beffortless(?:ly)?\b", r"\bsecret\s+method\b",
    r"\bnever\s+forget\b", r"\bpass\s+the\s+exam\b", r"\bcertificate\b",
]

# ── jerga y vulgarismos (no entran en una hoja de aprendizaje; el registro es neutro, «ty») ──────────────────────────────────────
JERGA_PL = ["zajebiście", "kurde", "cholera", "do bani", "dupa", "debil", "idiot", "głupek", "zdechł", "ogarnąć", "spoko", "xd", "nwm", "apka", "pierdu"]
JERGA_EN = ["damn", "crap", "sucks", "bloody", "wtf", "omg", "lol", "stupid", "idiot", "dumb", "shit", "fuck"]

# ── palabras elementales (A1/A2): no deben ser palabra de rama en C1/C2 ───────────────────────────────────────────────────────────
ELEMENTALES = set("""
a about after again all also always and any apple arm as ask at baby bad bag ball bank be beautiful because bed before big bike bird black blue boat body book boy bread
breakfast brother brown bus buy by cake call can car cat chair child city class clean close clothes cold color colour come cook cool country cup cut dad dance day dinner
dog door down draw dress drink drive eat egg eight email english evening every eye face family far farm fast father favourite feel find fine fish five floor flower food foot
for four friend fruit game garden get girl give glass go good green hair hand happy hat have he head hear help her here his home horse hot hotel house how hungry husband
ice idea in is it job juice key kitchen know lamp large late learn leg like listen little live long look love lunch make man many map meat milk mom money month morning mother
mouth music name near new nice night nine no nose not now number old on one open orange out page paper parent park pen people phone photo piano pink place plane play please
quick rain read red rice rich right river road room run sad salt same school sea see seven shirt shoe shop short sing sister six sit sleep slow small snow sock son soup speak
spring star stop street sugar summer sun swim table tea teacher ten that the thin three time tired to today tomorrow town train tree two under up use very walk wall want warm
wash watch water we week wet what white who wife wind window winter woman work write wrong year yellow yes young zoo
""".split())

# ── umbrales de longitud de frase por nivel (palabras EN): (máximo por frase, media mínima, media máxima) ────────────────────────────
LONGITUD_FRASE = {
    "A1": (11, 0.0, 8.5), "A2": (14, 0.0, 10.5), "B1": (18, 6.0, 14.0), "B2": (22, 7.0, 99.0), "C1": (28, 8.0, 99.0), "C2": (32, 9.0, 99.0),
}
LARGO_MAX_PALABRA = {"A1": 13, "A2": 15}  # caracteres: una palabra de rama más larga es probablemente de otro nivel
