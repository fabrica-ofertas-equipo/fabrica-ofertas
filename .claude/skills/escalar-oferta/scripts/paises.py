"""Mercados con bandera y nombre completo del país (pedido del dueño, 17-nov-2026).

Regla: cada vez que se nombra un mercado por su código, va con la bandera y el nombre entre paréntesis: «IE (🇮🇪 Irlanda)».

Uso como módulo:
  from paises import pais_largo, con_paises
  pais_largo("IE")                    → «IE (🇮🇪 Irlanda)»
  con_paises("Oferta: …")    → «Oferta (🇮🇪 Irlanda): …»
Uso suelto (prueba):
  python3 paises.py "texto con IE y NZ"

`con_paises` solo toca códigos de la tabla y deja afuera los que en un texto en español suelen ser otra cosa (NO, SI, SE, CR de
«tasa de conversión», AM/PM…). No toca «US$», ni un código que ya tiene su paréntesis, ni letras dentro de otra palabra o
identificador (B08, R16, VB-D4).
"""
from __future__ import annotations

import re
import sys

NOMBRES = {
    # América
    "AR": "Argentina", "BO": "Bolivia", "BR": "Brasil", "CA": "Canadá", "CL": "Chile", "CO": "Colombia", "CR": "Costa Rica",
    "DO": "República Dominicana", "EC": "Ecuador", "GT": "Guatemala", "HN": "Honduras", "JM": "Jamaica", "MX": "México",
    "NI": "Nicaragua", "PA": "Panamá", "PE": "Perú", "PR": "Puerto Rico", "PY": "Paraguay", "SV": "El Salvador",
    "TT": "Trinidad y Tobago", "US": "Estados Unidos", "UY": "Uruguay", "VE": "Venezuela",
    # Europa
    "AT": "Austria", "BE": "Bélgica", "BG": "Bulgaria", "CH": "Suiza", "CY": "Chipre", "CZ": "Chequia", "DE": "Alemania",
    "DK": "Dinamarca", "EE": "Estonia", "ES": "España", "FI": "Finlandia", "FR": "Francia", "GB": "Reino Unido",
    "UK": "Reino Unido", "GR": "Grecia", "HR": "Croacia", "HU": "Hungría", "IE": "Irlanda", "IS": "Islandia", "IT": "Italia",
    "LT": "Lituania", "LU": "Luxemburgo", "LV": "Letonia", "MT": "Malta", "NL": "Países Bajos", "NO": "Noruega",
    "PL": "Polonia", "PT": "Portugal", "RO": "Rumania", "RS": "Serbia", "SE": "Suecia", "SI": "Eslovenia", "SK": "Eslovaquia",
    "TR": "Turquía", "UA": "Ucrania",
    # Asia y Medio Oriente
    "AE": "Emiratos Árabes Unidos", "HK": "Hong Kong", "ID": "Indonesia", "IL": "Israel", "IN": "India", "JP": "Japón",
    "KR": "Corea del Sur", "KW": "Kuwait", "MY": "Malasia", "PH": "Filipinas", "QA": "Catar", "SA": "Arabia Saudita",
    "SG": "Singapur", "TH": "Tailandia", "TW": "Taiwán", "VN": "Vietnam",
    # Oceanía
    "AU": "Australia", "NZ": "Nueva Zelanda",
    # África
    "BW": "Botsuana", "EG": "Egipto", "GH": "Ghana", "KE": "Kenia", "MA": "Marruecos", "MU": "Mauricio", "NG": "Nigeria",
    "ZA": "Sudáfrica",
}
# En un texto suelto estos códigos suelen ser palabras o siglas en español; se expanden solo con pais_largo().
AMBIGUOS = {"NO", "SI", "SE", "CR", "IS", "IN", "ID", "MA", "PA", "AM", "PM"}
_CODIGO = re.compile(r"(?<![A-Za-z0-9\-_/.#])([A-Z]{2})(?![A-Za-z0-9$\-_])")


def bandera(cod: str) -> str:
    """«IE» → «🇮🇪» («UK» → la de GB)."""
    c = "GB" if cod.upper() == "UK" else cod.upper()
    if not re.fullmatch(r"[A-Z]{2}", c):
        return ""
    return "".join(chr(0x1F1E6 + ord(x) - 65) for x in c)


def nombre(cod: str) -> str:
    return NOMBRES.get(str(cod).upper(), str(cod))


def pais_largo(cod: str | None) -> str:
    """«IE» → «IE (🇮🇪 Irlanda)». Acepta varios separados por «/» o «,»: «MX/BR» → «MX (🇲🇽 México) y BR (🇧🇷 Brasil)»."""
    cods = [c for c in re.split(r"[^A-Za-z]+", str(cod or "").upper()) if c]
    if not cods:
        return str(cod or "")
    partes = [f"{c} ({bandera(c)} {nombre(c)})" if c in NOMBRES else c for c in cods]
    return " y ".join(partes)


def con_paises(texto: str | None) -> str:
    """Agrega «(🇮🇪 Irlanda)» después de cada código de mercado del texto que todavía no lo tenga."""
    if not texto:
        return texto or ""

    def cambio(m: re.Match) -> str:
        c = m.group(1)
        if c not in NOMBRES or c in AMBIGUOS:
            return c
        resto = texto[m.end():m.end() + 4]
        if resto.lstrip().startswith("(") and bandera(c) in texto[m.end():m.end() + 8]:
            return c   # ya tiene su paréntesis
        return f"{c} ({bandera(c)} {nombre(c)})"

    def grupo(m: re.Match) -> str:
        cods = re.split(r"[/,]\s*", m.group(1))
        if all(c in NOMBRES and c not in AMBIGUOS for c in cods):
            return pais_largo(m.group(1))
        return m.group(0)

    # «(TR)» → «TR (🇹🇷 Turquía)» y «MX/BR» → «MX (🇲🇽 México) y BR (🇧🇷 Brasil)», antes que los sueltos.
    texto = re.sub(r"\(([A-Z]{2}(?:[/,]\s*[A-Z]{2})*)\)", grupo, texto)
    texto = re.sub(r"(?<![A-Za-z0-9\-_/.#])([A-Z]{2}(?:/[A-Z]{2})+)(?![A-Za-z0-9$\-_/])", grupo, texto)
    return _CODIGO.sub(cambio, texto)


if __name__ == "__main__":
    print(con_paises(" ".join(sys.argv[1:])))
