# 6 · Impultienda

> Antes de esto: si la persona no puede o no quiere usar Impultienda, este paso se hace con la skill `conectar-tienda` (tienda propia con Stripe u otra plataforma) y esta guía se saltea.

Impultienda es donde viven las tiendas: producto en PDF, checkout, cobros, landing y ofertas post-compra.

1. **Cuenta:** abrí `https://impultienda.ar` en el navegador integrado; la persona crea la cuenta e inicia sesión (queda iniciada para cuando la fábrica necesite el panel de Impultienda).
2. **Plan:** que elija un plan que incluya webhooks y el conector para IA (MCP). Las condiciones y el precio los lee la persona en la página; no recomiendes uno por el precio.
3. **Conector de Impultienda en Claude:** Configuración → Conectores → Agregar conector personalizado → URL `https://mcp.impultienda.ar/mcp` → conectar (se autoriza con la cuenta de Impultienda). Comprobá cargando sus herramientas con ToolSearch («impultienda») y llamando `resumen_cuenta`.
4. **Cobros:** activar Impul Pay y/o Stripe en Impultienda. Pide datos personales, de empresa y de banco: lo completa la persona, de punta a punta. Vos solo le abrís la pantalla y le decís qué medios conviene tener activos (tarjeta como mínimo; los locales de cada país los suma la fábrica al lanzar en ese mercado si Impultienda los ofrece).
5. **Configuración que la fábrica espera en cada tienda** (la aplica sola al crear tiendas; acá solo se lee): plantilla de checkout clásica, sellos con garantía de 7 días, imagen de producto siempre, precio original ≈ 2,9 × el precio, correo de contacto = el de soporte. Detalle en `REGLAS-DEL-METODO.md` §Modelado.

Marcá `conector-impultienda`, `navegador-impultienda` e `impul-pay`.
