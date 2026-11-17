# Respuestas tipo de soporte (M01-M12) en polaco, español e inglés

> v0.1 sin pulir. Punto de partida: cada oferta las copia a `soporte/macros.<locale>.md`, las adapta con su KB y su glosario, pasan por QA, retraducción y segunda lectura de IA (J11; **polaco sin revisor nativo**) y X1 las sella por hash. Una macro sellada no se edita (un cambio es una versión nueva).
> Los campos entre dobles llaves son los de la lista cerrada `CAMPOS` de `../scripts/d10.py`; el código los rellena con datos validados y escapados. El Maker **no** escribe importes, plazos ni números a mano. Firma: la marca, nunca una persona. `{{aviso_ia}}` sale de `limites.politica_divulgacion_ia` (texto sugerido al final).
> Cada macro dice su categoría (C1-C10), la orden que acompaña (`validar-orden`) y si puede salir sola. **Toda respuesta que afirma una acción se envía solo si el código aceptó la orden; si no, sale M07.** Tono: breve, sin emoji, sin exclamaciones, sin discutir ni disuadir.

---

## M01 · No me llegó el correo con los enlaces (C1)
**Orden:** `reenviar_entrega` (al correo del pedido; si piden otro destino, la respuesta lo explica y la orden no lleva destinatario). **Auto-envío:** sí, si el código aceptó la orden; si no, M07.

**pl** — Dzień dobry,

dziękujemy za wiadomość. Linki do materiałów wysyłamy wyłącznie na adres e-mail podany przy zakupie. Sprawdź proszę foldery SPAM i „Oferty”: wiadomość ma temat „Twój dostęp do materiałów – zamówienie {{pedido_ref}}”.

Wysłaliśmy ją ponownie na ten sam adres; powinna dotrzeć w ciągu kilku minut. Jeśli nadal jej nie zobaczysz, odpisz na tę wiadomość.

Zespół {{marca}}
{{aviso_ia}}

**es** — Hola,

gracias por tu mensaje. Enviamos los enlaces únicamente al correo que indicaste al comprar. Revisa por favor las carpetas de spam y de promociones: el asunto es «Tu acceso a los materiales – pedido {{pedido_ref}}».

Te lo hemos vuelto a enviar a esa misma dirección; debería llegar en unos minutos. Si sigues sin verlo, responde a este mensaje.

Equipo {{marca}}
{{aviso_ia}}

**en** — Hello,

thank you for your message. We send the links only to the email address you gave when you bought. Please check your spam and promotions folders: the subject is "Your access to the materials – order {{pedido_ref}}".

We have sent it again to that same address; it should arrive within a few minutes. If you still do not see it, reply to this message.

The {{marca}} team
{{aviso_ia}}

---

## M02 · No puedo abrir el archivo (C2)
**Orden:** ninguna. **Auto-envío:** sí. Formato concreto de cada línea: de la KB (`[KB: formato]`), no inventar.

**pl** — Dzień dobry,

dziękujemy za wiadomość. Plik otworzysz w przeglądarce albo w dowolnym czytniku PDF; archiwum ZIP trzeba najpierw rozpakować. Jeśli to nie pomaga, odpisz, na jakim urządzeniu próbujesz (telefon, komputer) i co dokładnie widzisz na ekranie.

Zespół {{marca}}
{{aviso_ia}}

**es** — Hola,

gracias por tu mensaje. El archivo se abre en el navegador o en cualquier lector de PDF; el ZIP hay que descomprimirlo antes. Si no te ayuda, dinos desde qué dispositivo lo intentas (móvil, ordenador) y qué ves exactamente en pantalla.

Equipo {{marca}}
{{aviso_ia}}

**en** — Hello,

thank you for your message. The file opens in your browser or in any PDF reader; a ZIP archive must be unpacked first. If that does not help, tell us which device you are using (phone, computer) and what exactly you see on the screen.

The {{marca}} team
{{aviso_ia}}

---

## M03 · El enlace venció o se agotaron las descargas (C1)
**Orden:** `reenviar_entrega`. **Auto-envío:** sí, si el código aceptó la orden; si no, M07.

**pl** — Dzień dobry,

dziękujemy za wiadomość. Linki są ważne przez {{vence_dias}} dni, a każdy z nich pozwala pobrać plik maksymalnie {{max_descargas}} razy. Wysłaliśmy nowe linki na adres podany przy zakupie; zapisz pliki na swoim urządzeniu.

Zespół {{marca}}
{{aviso_ia}}

**es** — Hola,

gracias por tu mensaje. Los enlaces son válidos {{vence_dias}} días y cada uno permite descargar el archivo hasta {{max_descargas}} veces. Hemos enviado enlaces nuevos al correo que indicaste al comprar; guarda los archivos en tu dispositivo.

Equipo {{marca}}
{{aviso_ia}}

**en** — Hello,

thank you for your message. The links are valid for {{vence_dias}} days and each one lets you download its file up to {{max_descargas}} times. We have sent new links to the address you gave when you bought; please save the files on your device.

The {{marca}} team
{{aviso_ia}}

---

## M04 · ¿Por dónde empiezo? (C3)
**Orden:** ninguna. **Auto-envío:** sí. Los pasos salen de la KB / `producto.pasos`; solo hechos de la ficha.

**pl** — Dzień dobry,

dziękujemy za wiadomość. Najlepiej zacząć od jednego kroku: {{primer_paso}}

Jeśli utkniesz, napisz, w którym miejscu, a podpowiemy, co dalej.

Zespół {{marca}}
{{aviso_ia}}

**es** — Hola,

gracias por tu mensaje. Lo mejor es empezar por un solo paso: {{primer_paso}}

Si te atascas, dinos en qué punto y te orientamos.

Equipo {{marca}}
{{aviso_ia}}

**en** — Hello,

thank you for your message. The best way to start is with one step: {{primer_paso}}

If you get stuck, tell us where and we will point you in the right direction.

The {{marca}} team
{{aviso_ia}}

---

## M05 · Pregunta antes de comprar (C9)
**Orden:** ninguna. **Auto-envío:** sí. La respuesta sale **solo** de la KB (`[KB: respuesta]`); si la pregunta no está en la KB, borrador para una persona. Sin claims, sin comparaciones, sin precios que no estén en el contrato.

**pl** — Dzień dobry,

dziękujemy za pytanie o {{producto}}. [KB: odpowiedź oparta wyłącznie na opisie produktu.]

Na stronie zakupu piszemy też o gwarancji: „{{garantia_texto}}”

Zespół {{marca}}
{{aviso_ia}}

**es** — Hola,

gracias por tu pregunta sobre {{producto}}. [KB: respuesta basada solo en la ficha del producto.]

En la página de compra también explicamos la garantía: «{{garantia_texto}}»

Equipo {{marca}}
{{aviso_ia}}

**en** — Hello,

thank you for your question about {{producto}}. [KB: answer based only on the product description.]

The purchase page also explains the guarantee: "{{garantia_texto}}"

The {{marca}} team
{{aviso_ia}}

---

## M06 · Quiero el reembolso, dentro del plazo (C5)
**Orden:** `reembolsar` (`motivo: dentro_de_garantia`; sin importe). **Auto-envío:** solo si el código aceptó la orden (`ejecutado` o `aprobado`); si no, M07. **Cita literal** de la garantía publicada; no pide motivo como condición.

**pl** — Dzień dobry,

dziękujemy za wiadomość. Zgodnie z tym, co obiecaliśmy na stronie zakupu („{{garantia_texto}}”), zleciliśmy zwrot płatności za zamówienie {{pedido_ref}}. Pieniądze wrócą na tę samą metodę płatności, której użyto przy zakupie; potwierdzenie dostaniesz osobnym e-mailem.

Nie musisz nic więcej robić ani podawać powodu. Jeśli chcesz, napisz, co nie zadziałało – pomoże nam to poprawić materiały, ale nie jest warunkiem zwrotu.

Zespół {{marca}}
{{aviso_ia}}

**es** — Hola,

gracias por tu mensaje. Tal como prometimos en la página de compra («{{garantia_texto}}»), hemos ordenado el reembolso del pedido {{pedido_ref}}. El dinero vuelve al mismo método de pago que usaste al comprar; recibirás la confirmación en un correo aparte.

No tienes que hacer nada más ni dar ningún motivo. Si quieres, cuéntanos qué no funcionó: nos ayuda a mejorar el material, pero no es condición para el reembolso.

Equipo {{marca}}
{{aviso_ia}}

**en** — Hello,

thank you for your message. As we promised on the purchase page ("{{garantia_texto}}"), we have ordered a refund for order {{pedido_ref}}. The money goes back to the same payment method you used to buy; you will get confirmation in a separate email.

You do not need to do anything else or give a reason. If you like, tell us what did not work: it helps us improve the material, but it is not a condition for the refund.

The {{marca}} team
{{aviso_ia}}

---

## M07 · Lo revisa una persona (alternativa universal; C4, C5, C7, C8)
**Orden:** `escalar_humano`. **Auto-envío:** sí (no promete nada). Es la `respuesta_alternativa` de toda macro que afirma una acción y la respuesta a: reembolso fuera de plazo, método sin reembolso automático, disputa abierta, `PAUSA`, abuso, amenaza legal o de prensa, idioma sin glosario, confianza baja.

**pl** — Dzień dobry,

dziękujemy za wiadomość. Przekazaliśmy Twoją sprawę (zamówienie {{pedido_ref}}) do sprawdzenia przez osobę z zespołu; odpiszemy w ciągu 24 godzin.

Zespół {{marca}}
{{aviso_ia}}

**es** — Hola,

gracias por tu mensaje. Hemos pasado tu caso (pedido {{pedido_ref}}) a una persona del equipo para que lo revise; te responderemos en un máximo de 24 horas.

Equipo {{marca}}
{{aviso_ia}}

**en** — Hello,

thank you for your message. We have passed your case (order {{pedido_ref}}) to a member of the team to review; we will reply within 24 hours.

The {{marca}} team
{{aviso_ia}}

---

## M08 · No me funcionó / estoy insatisfecho (C4)
**Orden:** `reembolsar` solo si lo pide; si no, ninguna. **Auto-envío:** no (borrador, lo envía una persona). Ayuda **y** garantía a la vista, sin condicionar.

**pl** — Dzień dobry,

dziękujemy za informację. Szkoda, że materiały nie sprawdziły się u Ciebie. Jeśli napiszesz, co dokładnie nie działa, postaramy się pomóc; nie jest to jednak warunkiem zwrotu.

Przypominamy, co obiecaliśmy: „{{garantia_texto}}” Jeśli wolisz zwrot, wystarczy, że odpiszesz na tę wiadomość; numer zamówienia mamy: {{pedido_ref}}.

Zespół {{marca}}
{{aviso_ia}}

**es** — Hola,

gracias por avisarnos. Lamentamos que el material no te haya servido como esperabas. Si nos cuentas qué falla exactamente, intentaremos ayudarte; no es una condición para el reembolso.

Te recordamos lo que prometimos: «{{garantia_texto}}» Si prefieres el reembolso, basta con que respondas a este mensaje; ya tenemos tu número de pedido: {{pedido_ref}}.

Equipo {{marca}}
{{aviso_ia}}

**en** — Hello,

thank you for letting us know. We are sorry the material did not work out as you expected. If you tell us what exactly is not working, we will try to help; this is not a condition for a refund.

As a reminder, we promised: "{{garantia_texto}}" If you prefer a refund, just reply to this message; we already have your order number: {{pedido_ref}}.

The {{marca}} team
{{aviso_ia}}

---

## M09 · Factura o comprobante (C6)
**Orden:** ninguna (si piden un documento contable: `escalar_humano`, C6). **Auto-envío:** sí. `[VERIFICAR con el contador]` si se emiten facturas y cómo; esta macro no promete ninguna.

**pl** — Dzień dobry,

dziękujemy za wiadomość. Potwierdzenie płatności otrzymujesz od operatora płatności na adres e-mail podany przy zakupie (zamówienie {{pedido_ref}}). Jeśli potrzebujesz dokumentu księgowego, odpisz, a przekażemy sprawę osobie, która się tym zajmuje.

Zespół {{marca}}
{{aviso_ia}}

**es** — Hola,

gracias por tu mensaje. El comprobante de pago te llega del procesador de pagos al correo que indicaste al comprar (pedido {{pedido_ref}}). Si necesitas un documento contable, responde y pasaremos tu caso a la persona que se ocupa de ello.

Equipo {{marca}}
{{aviso_ia}}

**en** — Hello,

thank you for your message. You receive the payment receipt from the payment processor at the email address you gave when you bought (order {{pedido_ref}}). If you need an accounting document, reply and we will pass your case to the person who handles it.

The {{marca}} team
{{aviso_ia}}

---

## M10 · Crisis o incidente de seguridad (C7) — PLANTILLA FIJA, la sella X1
**Orden:** `escalar_humano` (C7) y el código emite `senal_pausa` con `motivo = incidente_seguridad`. **Auto-envío:** solo este texto, sin añadir ni quitar. Sin consejo, sin discutir causalidad, sin diagnóstico. `{{ayuda_pais}}` sale de `ayuda_por_pais.yaml` verificada (X1). El reembolso inmediato y sin condiciones lo ejecuta una persona.

**pl** — Dzień dobry,

dziękujemy za wiadomość i bardzo przykro nam z powodu tego, co opisujesz. Twoją wiadomość przeczyta osoba z naszego zespołu i odpisze w ciągu 24 godzin. Jeśli chcesz, zwrócimy pieniądze bez żadnych warunków.

Nie jesteśmy w stanie udzielać porad ani pomocy specjalistycznej. Jeśli potrzebujesz wsparcia już teraz: {{ayuda_pais}}

Zespół {{marca}}

**es** — Hola,

gracias por tu mensaje; lamentamos mucho lo que describes. Una persona de nuestro equipo leerá tu mensaje y te responderá en un máximo de 24 horas. Si quieres, te devolvemos el dinero sin ninguna condición.

No podemos dar consejos ni ayuda especializada. Si necesitas apoyo ahora mismo: {{ayuda_pais}}

Equipo {{marca}}

**en** — Hello,

thank you for your message; we are very sorry about what you describe. A member of our team will read your message and reply within 24 hours. If you like, we will refund your money with no conditions.

We cannot give advice or specialist help. If you need support right now: {{ayuda_pais}}

The {{marca}} team

---

## M11 · Datos personales, baja o borrado (C8)
**Orden:** `escalar_humano` (C8, plazo legal). **Auto-envío:** acuse automático; la resolución es humana. La baja de las peticiones de reseña es automática por el enlace.

**pl** — Dzień dobry,

dziękujemy za wiadomość. Prośbę dotyczącą Twoich danych przekazaliśmy osobie odpowiedzialnej za ich ochronę; odpiszemy w terminie wymaganym przepisami. Nie prosimy Cię o dokumenty ani dodatkowe dane. Jeśli chodzi tylko o wiadomości z prośbą o ocenę, możesz się wypisać tutaj: {{baja_url}}

Zespół {{marca}}
{{aviso_ia}}

**es** — Hola,

gracias por tu mensaje. Hemos pasado tu solicitud sobre tus datos a la persona responsable de su protección; te responderemos en el plazo que exige la normativa. No te pedimos documentos ni datos adicionales. Si solo quieres dejar de recibir las peticiones de valoración, puedes darte de baja aquí: {{baja_url}}

Equipo {{marca}}
{{aviso_ia}}

**en** — Hello,

thank you for your message. We have passed your request about your data to the person responsible for data protection; we will reply within the time the rules require. We do not ask you for documents or extra data. If you only want to stop receiving rating requests, you can unsubscribe here: {{baja_url}}

The {{marca}} team
{{aviso_ia}}

---

## M12 · No reconozco este cargo (C4/C5)
**Orden:** `reembolsar` solo si lo pide; si el cargo no se identifica con ningún pedido o hay disputa abierta: `escalar_humano` (C7). **Auto-envío:** no (borrador). No se desaconseja acudir al banco; se ofrece la solución más rápida.

**pl** — Dzień dobry,

dziękujemy za wiadomość. Płatność widnieje na wyciągu jako „{{descriptor}}” i dotyczy zamówienia {{pedido_ref}} w sklepie {{marca}}. Jeśli jej nie rozpoznajesz albo wolisz zwrot, odpisz na tę wiadomość, a zwrócimy pieniądze na tę samą metodę płatności.

Zespół {{marca}}
{{aviso_ia}}

**es** — Hola,

gracias por tu mensaje. El pago aparece en tu extracto como «{{descriptor}}» y corresponde al pedido {{pedido_ref}} de {{marca}}. Si no lo reconoces o prefieres el reembolso, responde a este mensaje y devolveremos el dinero al mismo método de pago.

Equipo {{marca}}
{{aviso_ia}}

**en** — Hello,

thank you for your message. The payment appears on your statement as "{{descriptor}}" and belongs to order {{pedido_ref}} at {{marca}}. If you do not recognise it or would rather have a refund, reply to this message and we will return the money to the same payment method.

The {{marca}} team
{{aviso_ia}}

---

## Aviso de IA (texto sugerido para `{{aviso_ia}}`; lo fija `limites.politica_divulgacion_ia`, decisión del dueño)
**pl** — Ta odpowiedź została przygotowana z pomocą automatycznego asystenta. Jeśli wolisz rozmawiać z człowiekiem, napisz o tym w odpowiedzi.
**es** — Esta respuesta se ha preparado con ayuda de un asistente automático. Si prefieres hablar con una persona, indícalo en tu respuesta.
**en** — This reply was prepared with the help of an automated assistant. If you would rather speak to a person, say so in your reply.
