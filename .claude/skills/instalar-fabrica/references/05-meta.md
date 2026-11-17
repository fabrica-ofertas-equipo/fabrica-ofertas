# 5 · Meta

Todo lo de Meta lo crea la persona (son sus datos y su tarjeta). Vos le abrís cada pantalla en el navegador integrado y comprobás con el conector.

1. **Facebook en el navegador integrado:** abrí `https://www.facebook.com` y pedile que inicie sesión con su cuenta personal de siempre. Debe ser una cuenta real con antigüedad; con una recién creada Meta suele bloquear la publicidad.
2. **Portafolio de negocios (Business):** `https://business.facebook.com` → crear un portafolio a su nombre (o usar el que tenga). Pedile que active la verificación en dos pasos en Facebook si no la tiene (Meta la exige para administrar anuncios).
3. **Cuenta publicitaria:** dentro del portafolio → Configuración → Cuentas publicitarias → Agregar → Crear. **Moneda USD** (todo el sistema calcula en dólares) y su zona horaria. Anotá el número (sin «act_»).
4. **Medio de pago:** en esa cuenta → Facturación → agregar tarjeta. Lo hace la persona; vos no ves ni escribís datos de la tarjeta.
5. **Conector de Meta en Claude:** Configuración → Conectores → el conector de Meta para anuncios → conectar con la misma cuenta de Facebook y darle acceso a esa cuenta publicitaria. Comprobá con `ads_get_ad_accounts`: tiene que aparecer la cuenta, activa (`account_status` 1) y con medio de pago.
6. Corré `personalizar.py` otra vez agregando `--cuenta-meta <número>` (con el mismo id, dominio y correo).
7. **Las fan pages y los píxeles NO se crean ahora:** cada oferta tiene los suyos y los arma `modelar-y-lanzar-oferta` (fase 5). Avisale que en cada oferta nueva le vas a pedir que genere y pegue el token de la API de conversiones del píxel (lo pega en Impultienda, no en el chat).

Marcá `conector-meta`, `cuenta-meta-activa` y `navegador-facebook`.

Si la cuenta queda «restringida» o pide verificación de identidad: es entre la persona y Meta (Centro de calidad de la cuenta); no intentes rodearlo. Mientras tanto, seguí con los pasos 6 y 7.
