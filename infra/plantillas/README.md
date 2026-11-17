# infra/plantillas
Plantillas de configuración (sin secretos): catálogo de preflight, manifiesto de variables de
entorno, permisos de tokens, registro de verificación de conexiones, eventos de webhook de Stripe y
los 11 pasos de alta de oferta (N01b).
Propietario: **B8** (ola 1), continuado por **B8b** (segunda sesión, 2026-11-06).
Los valores sensibles se referencian como variables de entorno, nunca en claro.
Probar: python3 -m unittest discover -s tests/infra -t .

## Archivos

- `preflight-items.yaml` (B8) — catálogo normativo de 44 ítems que consume `infra.preflight`.
- `variables-entorno.yaml` (B8, ampliado por B8b) — manifiesto normativo de TODAS las variables de
  entorno de toda plataforma/servicio; `infra.variables` regenera `.env.example` desde aquí.
- `permisos-tokens.yaml`, `registro-verificacion-conexiones.yaml`, `stripe-eventos-webhook.yaml` (B8).
- `estado.ejemplo.json` (B8) — **ilustrativo**, no normativo: su forma es más vieja que
  `contratos/infra_estado.schema.json` vigente (campos `version_esquema`/`resumen` que ya no existen
  en el esquema real); no se usa para validar nada, solo para que un humano entienda el semáforo.
- `alta-oferta.yaml` (B8b) — los 11 pasos de N01b («quién», «cómo se comprueba», ítem de preflight)
  que consume `infra.alta_oferta`.

## Decisiones (B8b)

- `alta-oferta.yaml` usa el mismo estilo plano `{clave: valor, ...}` por línea que
  `registro-verificacion-conexiones.yaml` (consistencia con lo que ya escribió B8), en vez de bloques
  YAML anidados más largos.
- Todos los 11 pasos son `quien: dueno` (acción humana que cuesta dinero, exige 2FA o un panel sin
  API de lectura adecuada): ningún agente ejecuta ninguno; `infra.alta_oferta` solo lista y verifica
  en solo lectura lo que un `Transporte`/cliente inyectado le permita.
