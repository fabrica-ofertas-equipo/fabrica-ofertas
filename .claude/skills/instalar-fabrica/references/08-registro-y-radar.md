# 8 · Registro compartido y orden propio del radar

Varias fábricas comparten el mismo método. Para que no modelen la misma oferta:

- **Registro compartido:** cada oferta que entra al banco se reserva; antes de modelarla se confirma. El primero que la reserva se la queda y las demás la ven «tomada» y la saltean. Viajan solo huellas cifradas (sha256): nadie ve qué ofertas tiene otra instalación. Lo usan solos `banco_candidatos.py importar` y la skill `modelar-y-lanzar-oferta`.
- **Semilla propia:** el radar de esta instalación recorre las búsquedas en otro orden (ya quedó en `empresa/instalacion.json` en el paso 3).
- **Términos propios:** cada fábrica busca además con palabras que las otras no usan.

Pasos:
1. La persona pega en `.env` la línea `REGISTRO_TOKEN=<token que le dio el dueño>`.
2. `.venv/bin/python .claude/skills/buscar-ofertas/scripts/territorio.py estado` → tiene que decir «registro: responde». Si dice que no responde: revisá la URL en `empresa/instalacion.json` y que el token esté bien pegado (sin espacios).
3. **Términos propios:** preguntale a la persona en qué idiomas y nichos le gustaría buscar (o, si no sabe, elegí vos). Leé `buscar-ofertas/scripts/radar_terminos.json` para ver el estilo (frases de entrega o de pago de producto digital: «descarga inmediata», «acceso de por vida», «PDF»…), y escribí `empresa/barrido/radar/terminos_propios.json` con 4-6 frases nuevas por idioma principal que NO estén en el catálogo, con la forma `{"entrega": {"es": [...], "pt": [...], "en": [...]}, "ingles_en_cada_mercado": []}`. Después `python3 .claude/skills/buscar-ofertas/scripts/radar.py cola generar`.

Marcá `terminos-propios`.
