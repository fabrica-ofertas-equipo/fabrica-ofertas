"""Patrones léxicos de los linters de D4 (L1-05, L1-09, L1-13, L1-14, L1-15, L1-17). SOLO biblioteca estándar.

ESTADO: INTERINO [SUPUESTO]. La fuente definitiva de «términos sensibles por idioma» es ``empresa/compliance/terminos_sensibles/<locale>.yaml``
(propietario X1, aún no existe) y la de las líneas de ayuda, ``empresa/compliance/ayuda_por_pais.yaml``. Estas listas parten de la nota
22f §8 (``palabras_vetadas``, ``patrones_diagnostico``) y de la nota 25; son aproximaciones por idioma y NO sustituyen a la lectura del QA
(un léxico no atrapa eufemismos ni variantes). Las líneas conocidas son las verificadas el 2026-11-06 en 22f/25 y llevan ``[VERIFICAR]``
de vigencia: la fuente de verdad para IMPRIMIR un número es ``ayuda_por_pais.yaml``, nunca esta tabla.
"""
from __future__ import annotations

import re

I = re.IGNORECASE

# Placeholders que el MAKER dejó sin completar. Los campos que el COMPRADOR rellena en una plantilla («[Nombre y apellidos]») son legítimos y NO se marcan:
# por eso no hay patrones genéricos de corchetes. PLACEHOLDERS_CS distingue mayúsculas (TODO ≠ «todo»).
PLACEHOLDERS = [
    r"\[(?:INSERTAR|INSERT|TODO|LOREM|TBD|PENDIENTE DE REDACTAR)\b[^\]]*\]", r"lorem\s+ipsum", r"\{\{[^}]{1,60}\}\}", r"<<[^>]{1,60}>>", r"\bINSERTAR\s+(?:TEMA|NOMBRE|LOGO)\b",
]
PLACEHOLDERS_CS = [r"\bTODO\b", r"\bFIXME\b", r"\bXXX+\b", r"\bTBD\b"]
MARCAS_PENDIENTES = [r"\[VERIFICAR[^\]]*\]", r"\[SUPUESTO[^\]]*\]", r"\[DUEÑO[^\]]*\]", r"\[HIPÓTESIS[^\]]*\]", r"\[PENDIENTE[^\]]*\]"]

CHATBOT = {
    "es": [r"como\s+(un\s+)?modelo\s+de\s+lenguaje", r"claro,?\s+aqu[ií]\s+tienes", r"¡?por\s+supuesto!", r"espero\s+que\s+esto\s+(te\s+)?(ayude|sirva)",
           r"si\s+necesitas\s+(algo\s+m[aá]s|que\s+(ajuste|modifique))", r"aqu[ií]\s+tienes\s+(una|un|el|la)\s+(gu[ií]a|versi[oó]n|resumen)"],
    "en": [r"as\s+an\s+ai(\s+language\s+model)?", r"certainly!?\s+here", r"here\s+is\s+(a|an|the)\s+(guide|version|summary)", r"i\s+hope\s+this\s+helps",
           r"let\s+me\s+know\s+if\s+you\s+(need|would\s+like)", r"sure!?\s+here"],
    "it": [r"come\s+modello\s+linguistico", r"certo!?\s+ecco", r"ecco\s+(una|un|la|il)\s+(guida|versione|riassunto)", r"spero\s+che\s+(questo\s+)?(ti\s+)?aiut"],
    "pl": [r"jako\s+model\s+j[ęe]zykowy", r"oczywi[śs]cie!?\s+oto", r"oto\s+(przewodnik|wersja|podsumowanie)", r"mam\s+nadziej[ęe],?\s+[żz]e\s+to\s+pomo[żz]e"],
    "fr": [r"en\s+tant\s+que\s+mod[èe]le\s+de\s+langage", r"bien\s+s[ûu]r\s*!?\s+voici", r"voici\s+(un|une|le|la)\s+(guide|version|r[ée]sum[ée])", r"j'esp[èe]re\s+que\s+cela"],
    "ro": [r"ca\s+model\s+de\s+limbaj", r"desigur!?\s+iat[ăa]", r"sper\s+c[ăa]\s+aceasta\s+te\s+ajut"],
    "de": [r"als\s+sprachmodell", r"nat[üu]rlich!?\s+hier\s+ist", r"ich\s+hoffe,?\s+das\s+hilft"],
    "pt": [r"como\s+um\s+modelo\s+de\s+linguagem", r"claro!?\s+aqui\s+est[áa]", r"espero\s+que\s+isso\s+ajude"],
}

# Palabras vetadas (claims de cura, resultado, ingresos). 22f §8 palabras_vetadas + nota 25 §2.2 (P2n). «rojo» = BLOQUEANTE; «aviso» = MAYOR (puede ser legítimo en contexto).
VETADAS = {
    "es": {"rojo": [r"\bcura(?:r|rte|rse|mos|r[áa]|r[áa]s)?\b", r"\bsana(?:r|rte|rse)\b", r"\brevierte(?:s|n)?\b", r"\brevertir\b",
                    r"\belimina(?:r|r[áa]|s)?\s+(?:tu|tus|la|el|los|las)\b", r"\bdetox\b", r"\bdesintoxica\w*", r"\bacelera\w*\s+(?:tu\s+)?metabolismo",
                    r"\bmetabolismo\s+acelerad\w*", r"\bquema\s*grasas?\b|\bquemagrasas?\b|\bquemar\s+grasa", r"\bgarantizad[oa]s?\b|\bgarantizamos\b",
                    r"\bsin\s+esfuerzo\b", r"\bsin\s+experiencia\b", r"\bingresos?\s+pasivos?\b", r"\bhazte\s+ric[oa]\b|\bhacerse\s+ric[oa]\b",
                    r"\bahorra(?:r|r[áa]s)?\s+\d[\d.,]*\s*(?:€|eur|euros|usd|\$)?\s*(?:al|por|/)\s*(?:mes|d[ií]a|semana|a[ñn]o)\b",
                    r"\bpierde\s+\d+\s*(?:kilos?|kg)\b", r"\bresultados?\s+(?:r[aá]pidos?|inmediatos?)\b"],
           "aviso": [r"\bresultados?\s+reales?\b", r"\bsin\s+riesgo\b", r"\bf[aá]cil(?:mente)?\s+y\s+r[aá]pid\w*"]},
    "en": {"rojo": [r"\bcure[sd]?\b", r"\bcuring\b", r"\bheal(?:s|ing|ed)?\b", r"\breverse(?:s|d)?\s+(?:your\s+)?(?:diabetes|disease|aging|ageing)\b", r"\bdetox\b",
                    r"\bburn(?:s|ing)?\s+fat\b|\bfat[- ]burn\w*", r"\bboost(?:s|ing)?\s+(?:your\s+)?metabolism", r"\bguaranteed\s+(?:results?|income|returns?|success|savings)\b",
                    r"\beffortless(?:ly)?\b", r"\bpassive\s+income\b", r"\bget\s+rich\b", r"\bno\s+experience\s+(?:needed|required)\b", r"\bwithout\s+(?:any\s+)?experience\b",
                    r"\b(?:save|earn|make)\s+[$€£]?\d[\d.,]*\s*(?:a|per|/)\s*(?:month|day|week|year)\b", r"\blose\s+\d+\s*(?:kg|kilos?|lbs?|pounds)\b"],
           "aviso": [r"\bguarantee[sd]?\b", r"\bproven\b", r"\bno\s+risk\b"]},
    "it": {"rojo": [r"\bcura(?:re|rti)?\b", r"\bguarisc\w*|\bguarire\b", r"\bdisintossic\w*", r"\bdetox\b", r"\baccelera\w*\s+(?:il\s+)?metabolismo", r"\bbrucia\s+grassi\b",
                    r"\bgarantit[oiae]\b", r"\bsenza\s+sforzo\b", r"\bsenza\s+esperienza\b", r"\b(?:rendita|reddito)\s+passiv[oa]\b", r"\bdiventa\s+ricco\b",
                    r"\brisparmia\s+\d[\d.,]*\s*(?:€|euro)?\s*(?:al|ogni)\s*(?:mese|giorno|settimana|anno)\b"],
           "aviso": [r"\brisultati\s+(?:reali|rapidi|immediati)\b"]},
    "pl": {"rojo": [r"\bwylecz\w*", r"\bleczy\w*", r"\blek\s+na\b", r"\bdetoks\w*", r"\bprzyspiesz\w*\s+metabolizm", r"\bspala\w*\s+t[łl]uszcz", r"\bgwarantowan\w*",
                    r"\bbez\s+wysi[łl]ku\b", r"\bbez\s+do[śs]wiadczenia\b", r"\bdoch[óo]d\s+pasywny\b", r"\bzosta[ńn]\s+bogaczem\b",
                    r"\boszcz[ęe]dzisz\s+\d[\d\s.,]*\s*(?:z[łl]|pln)\s+(?:miesi[ęe]cznie|na\s+miesi[ąa]c)\b"],
           "aviso": [r"\bwyniki\s+(?:natychmiastowe|b[łl]yskawiczne)\b"]},
    "fr": {"rojo": [r"\bgu[ée]ri\w*", r"\bgu[ée]rison\b", r"\bd[ée]tox\b", r"\bacc[ée]l[èe]r\w*\s+(?:le\s+)?m[ée]tabolisme", r"\bbr[ûu]le\w*\s+(?:les\s+)?graisses\b",
                    r"\b(?:r[ée]sultats?|revenus?|succ[èe]s)\s+garanti\w*|\bgaranti\w*\s+(?:r[ée]sultats?|revenus?|succ[èe]s)\b", r"\bsans\s+effort\b", r"\bsans\s+exp[ée]rience\b",
                    r"\brevenu\s+passif\b", r"\bdevenez?\s+riche\b"],
           "aviso": [r"\br[ée]sultats?\s+(?:rapides?|imm[ée]diats?)\b"]},
    "ro": {"rojo": [r"\bvindec\w*", r"\bdetox\b", r"\baccelereaz[ăa]\s+metabolismul", r"\barde\s+gr[ăa]simi\b", r"\bgarantat\w*", r"\bf[ăa]r[ăa]\s+efort\b",
                    r"\bf[ăa]r[ăa]\s+experien[țt][ăa]\b", r"\bvenit\s+pasiv\b"], "aviso": []},
    "de": {"rojo": [r"\bheilt\b|\bheilen\b|\bheilung\b", r"\bdetox\b|\bentgiftung\b", r"\bstoffwechsel\s+an(?:ku|k)rbeln", r"\bfett\s*verbrenn\w*", r"\bgarantiert\w*",
                    r"\bohne\s+anstrengung\b", r"\bohne\s+erfahrung\b", r"\bpassives\s+einkommen\b", r"\breich\s+werden\b"], "aviso": []},
    "pt": {"rojo": [r"\bcura(?:r|rte)?\b", r"\bdesintoxic\w*", r"\bdetox\b", r"\bgarantid[oa]s?\b", r"\bsem\s+esfor[çc]o\b", r"\brenda\s+passiva\b", r"\bfique\s+rico\b"], "aviso": []},
}

# Diagnóstico y atributos del lector (L1-S09; HC-19 de Meta en la nota 22f). «rojo»: atribuye una condición al lector.
DIAGNOSTICO = {
    "es": {"rojo": [r"\b(?:tienes|sufres\s+de|padeces|eres)\s+(?:una\s+|un\s+)?(?:diabet\w*|depresi[oó]n|ansiedad|obes\w*|anorex\w*|bulimi\w*|hipertens\w*|tdah|autis\w*)",
                    r"\bsi\s+(?:eres|est[aá]s|tienes)\s+(?:diab[eé]tic\w*|deprimid\w*|endeudad\w*|ansios\w*|obes\w*)"],
           "aviso": [r"\bdiagn[oó]stic\w*", r"\bs[ií]ntomas\s+de\b"]},
    "en": {"rojo": [r"\b(?:you\s+have|you\s+suffer\s+from)\s+(?:diabetes|depress\w*|anxiety|obesity|anorexia|bulimia|adhd|autism)\b",
                    r"\bif\s+you\s+are\s+(?:diabetic|depressed|in\s+debt|obese|anxious)\b"],
           "aviso": [r"\bdiagnos\w*", r"\bsymptoms\s+of\b"]},
    "it": {"rojo": [r"\b(?:hai|soffri\s+di)\s+(?:diabete|depressione|ansia|obesit[àa]|anoressia|bulimia)\b", r"\bse\s+sei\s+(?:diabetic\w*|depress\w*|indebitat\w*|obes\w*)\b"],
           "aviso": [r"\bdiagnos\w*", r"\bsintomi\s+di\b"]},
    "pl": {"rojo": [r"\b(?:masz|cierpisz\s+na)\s+(?:cukrzyc\w*|depresj\w*|l[ęe]k\w*|oty[łl]o[śs][ćc]\w*|anoreksj\w*)\b", r"\bje[śs]li\s+jeste[śs]\s+(?:zadłu[żz]on\w*|w\s+depresji)\b"],
           "aviso": [r"\bdiagnoz\w*", r"\bobjawy\s+(?:depresji|cukrzycy)\b"]},
    "fr": {"rojo": [r"\b(?:vous\s+avez|tu\s+as|vous\s+souffrez\s+de)\s+(?:du\s+|de\s+la\s+|de\s+l')?(?:diab[èe]te|d[ée]pression|anxi[ée]t[ée]|ob[ée]sit[ée]|anorexie|boulimie)\b",
                    r"\bsi\s+vous\s+[êe]tes\s+(?:diab[ée]tique|d[ée]prim[ée]\w*|endett[ée]\w*)\b"],
           "aviso": [r"\bdiagnostic\w*", r"\bsympt[ôo]mes\s+de\b"]},
    "ro": {"rojo": [r"\b(?:ai|suferi\s+de)\s+(?:diabet|depresie|anxietate|obezitate)\b"], "aviso": [r"\bdiagnostic\w*"]},
    "de": {"rojo": [r"\b(?:du\s+hast|sie\s+haben|du\s+leidest\s+an)\s+(?:diabetes|depression|angst\w*|adipositas|magersucht|bulimie)\b"], "aviso": [r"\bdiagnose\w*"]},
    "pt": {"rojo": [r"\b(?:voc[êe]\s+tem|sofre\s+de)\s+(?:diabetes|depress[ãa]o|ansiedade|obesidade)\b"], "aviso": [r"\bdiagn[óo]stic\w*"]},
}

TESTIMONIO = {
    "es": [r"\b(?:yo\s+)?(?:perd[ií]|ahorr[eé]|gan[eé]|baj[eé])\s+\d", r"\b[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+\s+(?:perdi[oó]|ahorr[oó]|gan[oó]|baj[oó])\s+\d",
           r"\bantes\s+y\s+despu[eé]s\b", r"\btestimonios?\s+(?:reales|verificados)\b"],
    "en": [r"\bI\s+(?:lost|saved|made|earned|gained)\s+[$€£]?\d", r"\b[A-Z][a-z]+\s+(?:lost|saved|made|earned)\s+[$€£]?\d", r"\bbefore\s+and\s+after\b",
           r"\bverified\s+(?:testimonials?|reviews?)\b"],
    "it": [r"\bho\s+(?:perso|risparmiato|guadagnato)\s+\d", r"\b[A-Z][a-z]+\s+ha\s+(?:perso|risparmiato|guadagnato)\s+\d", r"\bprima\s+e\s+dopo\b"],
    "pl": [r"\b(?:schud[łl]em|schud[łl]am|zaoszcz[ęe]dzi[łl]em|zaoszcz[ęe]dzi[łl]am|zarobi[łl]em|zarobi[łl]am)\s+\d", r"\bprzed\s+i\s+po\b"],
    "fr": [r"\bj'ai\s+(?:perdu|[ée]conomis[ée]|gagn[ée])\s+\d", r"\bavant\s+et\s+apr[èe]s\b"],
    "ro": [r"\bam\s+(?:sl[ăa]bit|economisit|c[âa][șs]tigat)\s+\d"],
    "de": [r"\bich\s+habe\s+\d[\d.,]*\s*(?:kg|kilo|euro|€)\s+(?:abgenommen|gespart|verdient)\b", r"\bvorher\s+und\s+nachher\b"],
    "pt": [r"\beu\s+(?:perdi|economizei|ganhei)\s+\d"],
}

CREDENCIALES = {
    "es": [r"\b(?:dise[ñn]ad[oa]|elaborad[oa]|cread[oa]|revisad[oa]|avalad[oa]|aprobad[oa]|recomendad[oa])\s+por\s+(?:nutricionistas|m[ée]dicos|expertos|psic[óo]logos|abogados|profesionales|economistas|asesores|terapeutas)\b"],
    "en": [r"\b(?:designed|created|reviewed|approved|endorsed|recommended)\s+by\s+(?:nutritionists|doctors|physicians|experts|psychologists|lawyers|professionals|economists|advisors|therapists)\b"],
    "it": [r"\b(?:progettat[oa]|creat[oa]|rivist[oa]|approvat[oa]|consigliat[oa])\s+da\s+(?:nutrizionisti|medici|esperti|psicologi|avvocati|professionisti|economisti|consulenti|terapeuti)\b"],
    "pl": [r"\b(?:opracowan\w+|zatwierdzon\w+|sprawdzon\w+|polecan\w+)\s+przez\s+(?:dietetyk\w+|lekarz\w+|ekspert\w+|psycholog\w+|prawnik\w+|doradc\w+|terapeut\w+)\b"],
    "fr": [r"\b(?:con[çc]u|cr[ée]{1,2}|r[ée]vis[ée]|approuv[ée]|recommand[ée])e?s?\s+par\s+(?:des\s+)?(?:nutritionnistes|m[ée]decins|experts|psychologues|avocats|professionnels|conseillers|th[ée]rapeutes)\b"],
    "ro": [r"\b(?:conceput|creat|revizuit|aprobat|recomandat)\s+de\s+(?:nutri[țt]ioni[șs]ti|medici|exper[țt]i|psihologi|avoca[țt]i)\b"],
    "de": [r"\b(?:entwickelt|erstellt|gepr[üu]ft|gepr\wft|empfohlen)\s+von\s+(?:ern[äa]hrungsberater\w*|[äa]rzt\w*|experten|psycholog\w*|anw[äa]lt\w*|therapeut\w*)\b"],
    "pt": [r"\b(?:desenhad[oa]|criad[oa]|revisad[oa]|aprovad[oa])\s+por\s+(?:nutricionistas|m[ée]dicos|especialistas|psic[óo]logos|advogados)\b"],
}

# Servicio humano, comunidad, vivo, suscripción o mantenimiento continuo (L1-14; se lee también en bonus y bump).
SERVICIO = {
    "es": [r"\b(?:sesi[oó]n|llamada|consulta|reuni[oó]n|videollamada)\s+(?:1\s*[:a]\s*1|uno\s+a\s+uno|individual|personal(?:izada)?|privada)\b", r"\bcoaching\b", r"\bmentor[ií]a\b",
           r"\bgrupo\s+(?:privado|de\s+whatsapp|de\s+telegram)\b", r"\bcomunidad\s+(?:privada|exclusiva|de\s+miembros)\b", r"\ben\s+vivo\b", r"\bwebinar\b",
           r"\bclases?\s+en\s+directo\b", r"\bsuscripci[oó]n\b", r"\bsoporte\s+(?:personalizado|por\s+(?:whatsapp|email|correo))\b", r"\bactualizaciones?\s+(?:mensuales|semanales|de\s+por\s+vida)\b",
           r"\brespuesta\s+personalizada\b", r"\bseguimiento\s+(?:personal|individual)\b"],
    "en": [r"\b1\s*[:-]\s*1\b", r"\bone[- ]on[- ]one\b", r"\bprivate\s+(?:group|community|session|call)\b", r"\blive\s+(?:call|session|q&a|webinar|class)\b", r"\bcoaching\b", r"\bmentoring\b",
           r"\bsubscription\b", r"\bmembership\b", r"\blifetime\s+updates\b", r"\bpersonali[sz]ed\s+(?:feedback|support|plan|advice)\b", r"\bfacebook\s+group\b"],
    "it": [r"\bsessione\s+(?:1\s*[:a]\s*1|individuale|privata)\b", r"\bgruppo\s+privato\b", r"\bcommunity\s+privata\b", r"\bdal\s+vivo\b", r"\bwebinar\b", r"\bcoaching\b",
           r"\babbonamento\b", r"\bsupporto\s+personalizzato\b", r"\baggiornamenti\s+a\s+vita\b"],
    "pl": [r"\bsesja\s+(?:1\s*[:na]\s*1|indywidualna)\b", r"\bprywatna\s+grupa\b", r"\bspo[łl]eczno[śs][ćc]\b", r"\bna\s+[żz]ywo\b", r"\bwebinar\w*", r"\bcoaching\b", r"\bsubskrypcj\w+",
           r"\bwsparcie\s+(?:osobiste|indywidualne)\b", r"\baktualizacje\s+do[żz]ywotnie\b"],
    "fr": [r"\bs[ée]ance\s+(?:individuelle|priv[ée]e|1\s*[:à]\s*1)\b", r"\bgroupe\s+priv[ée]\b", r"\bcommunaut[ée]\s+priv[ée]e\b", r"\ben\s+direct\b", r"\bwebinaire\b", r"\bcoaching\b",
           r"\babonnement\b", r"\baccompagnement\s+personnalis[ée]\b", r"\bmises?\s+[àa]\s+jour\s+[àa]\s+vie\b"],
    "ro": [r"\bsesiune\s+(?:1\s*[:la]\s*1|individual[ăa])\b", r"\bgrup\s+privat\b", r"\bcomunitate\s+privat[ăa]\b", r"\bîn\s+direct\b", r"\bwebinar\b", r"\bcoaching\b", r"\babonament\b"],
    "de": [r"\b1\s*[:zu]\s*1\b", r"\beinzelsitzung\b", r"\bprivate\s+gruppe\b", r"\bcommunity\b", r"\blive[- ]?(?:call|webinar|sitzung)\b", r"\bcoaching\b", r"\babonnement\b", r"\bpers[öo]nliche\s+betreuung\b"],
    "pt": [r"\bsess[ãa]o\s+(?:1\s*[:a]\s*1|individual)\b", r"\bgrupo\s+privado\b", r"\bcomunidade\s+privada\b", r"\bao\s+vivo\b", r"\bwebinar\b", r"\bcoaching\b", r"\bassinatura\b"],
}

SECRETOS = [r"\bsk_(?:live|test)_[A-Za-z0-9]{10,}", r"\bAKIA[0-9A-Z]{16}\b", r"-----BEGIN [A-Z ]*PRIVATE KEY-----", r"\bxox[baprs]-[A-Za-z0-9-]{10,}", r"\bghp_[A-Za-z0-9]{20,}",
            r"\beyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}"]
RUTAS_PERSONALES = [r"/Users/[A-Za-z0-9._-]+", r"[A-Za-z]:\\Users\\[A-Za-z0-9._-]+", r"/home/[a-z0-9._-]+"]
RX_EMAIL = r"[\w.+-]+@(?!(?:[\w-]+\.)*(?:invalid|example|test)\b)[\w-]+(?:\.[\w-]+)+"

# Líneas de ayuda ya verificadas (22f §8 y nota 25 §7, 2026-11-06), por dígitos. [VERIFICAR] vigencia: la fuente es ayuda_por_pais.yaml.
LINEAS_CONOCIDAS: dict[str, set[str]] = {
    "988": {"US"}, "18007997233": {"US"}, "116123": {"GB", "PL"}, "08082000247": {"GB"}, "08088010677": {"GB"},
    "3114": {"FR"}, "3919": {"FR"}, "1522": {"IT"}, "0223272327": {"IT"}, "800702222": {"PL"}, "800120002": {"PL"},
    "0800500333": {"RO"}, "024": {"ES"}, "016": {"ES"},
}
CONTEXTO_LINEA = r"(?:l[ií]nea|linea|tel[eé]fono|telefono|llama|llame|call|hotline|helpline|chiama|numero|número|zadzwo[ńn]|numer|appelez|num[ée]ro|tel\.?|ayuda|help|aiuto|pomoc|aide)"

# Nombres de archivo o URL con condición, deuda o estado (BLOQUEANTE: neutralidad, X1-D01). INTERINO hasta terminos_sensibles/<locale>.yaml.
NOMBRES_SENSIBLES = [
    r"diabet", r"diabetes", r"deuda", r"endeud", r"ansied", r"depres", r"obes", r"adelgaz", r"bajar-?peso", r"cancer", r"tdah", r"autis", r"divorci", r"ruptura",
    r"anorex", r"bulim", r"insulin", r"hipertens", r"colesterol", r"embaraz", r"menopaus", r"suicid", r"maltrat", r"debito", r"depressione", r"ansia", r"obesit",
    r"rozwod", r"cukrzyc", r"depresj", r"dette", r"depression", r"anxiety", r"weight-?loss", r"overweight", r"debt-?relief", r"bankrupt", r"quiebra", r"pcos", r"sop-",
]

# Palabras de estado que una fórmula de hoja no debe producir sobre el comprador (L1-17: «hoja que puntúa salud o deuda»).
ESTADOS_HOJA = [
    r"depresi", r"ansiedad", r"obes", r"sobrepeso", r"bajo\s+peso", r"riesgo\s+(?:alto|medio|bajo)", r"endeudad", r"deuda\s+(?:alta|cr[ií]tica|peligrosa)", r"diab", r"trastorno",
    r"anorex", r"depress", r"anxiety", r"obese", r"overweight", r"underweight", r"(?:high|low|medium)\s+risk", r"in\s+debt", r"disorder", r"sovrappeso", r"rischio\s+(?:alto|medio|basso)",
    r"nadwag", r"oty[łl]o", r"ryzyko\s+(?:wysokie|[śs]rednie|niskie)", r"d[ée]pression", r"surpoids", r"risque\s+(?:[ée]lev[ée]|moyen|faible)",
]


def idioma(locale: str) -> str:
    return locale.split("-")[0].lower()


def pais(locale: str) -> str:
    return locale.split("-")[1].upper() if "-" in locale else ""


def compilar(patrones: list[str]) -> list[re.Pattern]:
    return [re.compile(p, I) for p in patrones]
