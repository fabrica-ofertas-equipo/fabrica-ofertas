<!-- Plantilla del informe de /o0-lanzar-oferta (≤ 25 líneas). Sustituye lo que está entre <…>; borra lo que no aplique. -->
LANZAR OFERTA · <OF-AAAAMM-NN | nueva> · <AAAA-MM-DD> · nivel <Nx>

**1. Bloqueos del dueño (<n> abiertos)**
- <titulo> — <estado>: bloquea <qué>. Se cierra con <acción del dueño> (<comando o [PENDIENTE]>).

**2. Dónde estoy**
Fase <fase>. Etapas: D1 <estado/gate> · M1 … · D7 <estado/gate> · D8/D9/D10 <si la oferta ya está en test>. Modelado (solo ofertas del Modo D, no es etapa del motor): <plan v0 | inmersión | plan v1 pendiente de tu firma | tarjeta en el gate de D3>.
Dinero: gasto acumulado <monto moneda> (<archivo>, <actualizado_en>); hoy <monto>; costo de IA <monto>. <«dato ausente o viejo: …» si corresponde>

**3. Qué falta**
- <lo concreto que falta>

**4. Qué espera tu firma**
<Sí/No>. <Qué se aprueba en una frase> · hash <sha256:abcd…> · mira `ofertas/<id>/qa/<archivo>`. Si dices no: <qué pasa>.

**5. Comando exacto** (lo corres tú en tu terminal; efecto: <lectura | escribe local | firma | mueve dinero>)
`<.venv/bin/python -m engine.orq …>`  <[PENDIENTE: …] si el comando usa algo que la CLI aún no tiene (`ejecutar` dry-run/live, `activar --live`, `reanudar`, `orq validar`); un `firmar` lleva `--hash-objetivo <hash>` y `--clave-privada <RUTA_DE_TU_CLAVE_PRIVADA>`, nunca una ruta real>

**6. Avisos**
- <excepción que fuerza H / C-04 abierta (gate efectivo H hasta que el dueño decida D-02) / requiere sesión interactiva / PAUSA>
- No ejecuto etapas, no firmo, no activo.
