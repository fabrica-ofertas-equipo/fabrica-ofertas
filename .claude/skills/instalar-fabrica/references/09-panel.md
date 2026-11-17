# 9 · Panel

El panel muestra todo: ofertas, ventas, gasto, avisos y «Lo que espera tus manos».

1. `.venv/bin/python scripts/kit/servicios.py panel` → queda prendido siempre (arranca solo con la Mac).
2. La dirección con la clave aparece en `~/Library/Logs/fabrica-panel.log` (línea que empieza con `http://127.0.0.1:8790`). Abrila en Chrome y pedile a la persona que la guarde como marcador.
3. **Meta en vivo (opcional):** para ver el gasto de Meta cada 10 minutos sin Claude hace falta un token de «usuario del sistema» con permiso `ads_read` (Business → Configuración → Usuarios del sistema → Generar token, con una app propia de Meta para desarrolladores). Lo genera y pega la persona en `.env` como `META_ACCESS_TOKEN`; después `servicios.py meta-vivo`. Sin esto, la vigilancia igual lee Meta cada hora con el conector.
4. **Panel desde el celular o capa en la nube (opcional, avanzado):** `infra/workers/vivo/` y el túnel de Cloudflare. Necesita su propio Cloudflare y dominio; dejalo para después de la primera oferta.

Hecho cuando el estado marca ✓ en `panel`.
