# infra/maquina — la máquina principal, siempre prendida y manejable desde cualquier lado

La iMac (`iMac de el dueño`) es el **cómputo** de la fábrica: corre las sesiones de Claude Code,
los workers locales (`com.fabrica.*`), los renders y todo lo pesado. Queda prendida en casa y
se maneja desde la laptop, esté donde esté, mientras tenga corriente e internet. La laptop
queda para el uso personal y no se traba.

El armado copia el de Claudio Conde, que en su video («Así corro Claude Code y Codex en 2 Macs»,
YouTube `F-3HuWcP36s`) maneja con Tailscale desde una MacBook Air una M4 Pro que queda en su casa.
Se armó el 16 y el 17 de noviembre de 2026.

**La regla general** (los 8 puntos que tiene que cumplir cualquier máquina así, Mac o Windows,
paso a paso): [`REGLA.md`](REGLA.md).

## Cómo funciona

| Pieza | Para qué | Estado |
|---|---|---|
| **Tailscale** (app de la App Store) | Red privada entre la iMac y la laptop; anda desde cualquier red sin abrir puertos. | Cuenta Gmail de el dueño. La iMac es `imac-de-lucas` (`imac-de-lucas.tail56e8c6.ts.net`, 100.92.191.94). |
| **Compartir pantalla** (de macOS) | Ver y manejar la iMac. | Activo, sólo administradores. *Administración remota* apagada (choca). |
| **Sesión remota (SSH)** | Terminal de la iMac desde la laptop. | Activa, sólo administradores, sin acceso total al disco. |
| **Energía** | Que no se duerma y vuelva sola después de un corte de luz. | Sin reposo, «Arrancar al conectarse a la corriente: Siempre», red la despierta. |
| **FileVault** | Si está activo, tras un reinicio el disco pide la clave en la máquina. | Apagado: vuelve sola a estar disponible. |
| **Inicio de sesión automático** | Tras un reinicio, la sesión se abre sola y arrancan Tailscale y las apps. | Activo. |
| **Ítems de inicio** | Apps que se abren solas. | Tailscale (agregado el 17-nov: estaba apagado y tras un corte de luz no hubiera habido acceso remoto), Claude, Fathom. |
| **Bloqueo y actualizaciones** | Que no pida clave ni se reinicie sola. | Bloqueo de pantalla apagado; macOS no se instala solo. |
| **Vigilante de Wi-Fi** (`vigilante_wifi.sh`) | Que no quede trabada en otra red sin internet. | LaunchAgent `com.fabrica.vigilante-wifi`, cada 60 s. |

## El incidente que originó el vigilante (noche del 16 al 17-nov-2026)

La iMac estaba en **tuotroproyecto** (la red buena) y se pasó sola a **«TeleCentro Wifi»**: una red
pública del proveedor de internet que aparece en casi cualquier casa, conecta sola y no da
internet hasta hacer login. Quedó «conectada» sin internet, Tailscale se cayó y no hubo forma de
entrar desde afuera.

La causa: la iMac tenía **64 redes guardadas** que llegan por iCloud desde el celular y la laptop
(bares, hoteles, celulares ajenos), y «TeleCentro Wifi» y «Personal Wifi Zone» estaban 2ª y 3ª en
prioridad. Arreglo:

1. Se olvidaron «TeleCentro Wifi» y «Personal Wifi Zone» (`networksetup -removepreferredwirelessnetwork`,
   no pide clave). Ojo: el olvido viaja por iCloud a los otros equipos.
2. **Vigilante**: cada minuto pide `http://captive.apple.com/hotspot-detect.html`, que dice
   «Success» sólo con internet real (un portal con login devuelve otra cosa). Si falla **2 veces
   seguidas**, apaga y prende el Wi-Fi y macOS vuelve a la red conocida de mayor prioridad, que es
   tuotroproyecto. Si sigue sin internet (por ejemplo, porque se cayó tuotroproyecto), vuelve a probar al minuto.
3. Probado de verdad: en una caída real, volvió con internet en **15 segundos**.

Por qué no fuerza «tuotroproyecto» por nombre: `networksetup -setairportnetwork en1 tuotroproyecto` sin la
clave falla con `-3900`, y el vigilante no guarda ni lee contraseñas. Por eso reinicia el Wi-Fi.

**Lo definitivo es un cable Ethernet** al router (el puerto `en0` está libre): con cable no
depende del Wi-Fi. El vigilante queda igual, como respaldo.

## Uso diario (desde la laptop)

- **Una sola vez:** instalar Tailscale (App Store) con **la misma cuenta**, abrir la app
  *Compartir pantalla*, dejarla en el Dock y tildar «Recordar contraseña» la primera vez.
- **Entrar:** *Compartir pantalla* → doble clic en `imac-de-lucas`, o en el Finder, Cmd+K →
  `vnc://imac-de-lucas`. Elegir **Alto rendimiento** con **una pantalla virtual** (dos sólo con
  monitor externo). El monitor de la iMac queda negro mientras tanto: es normal y todo sigue
  corriendo.
- **Terminal:** `ssh usuario@imac-de-lucas`.
- **Salir:** Cmd+Q en *Compartir pantalla*, o cerrar la tapa de la laptop. En la iMac se vuelve a
  entrar con la clave y todo sigue como estaba.
- **Nunca apagar la iMac** desde el menú: para que no gaste, alcanza con apagar el monitor.

## Comandos

```bash
zsh infra/maquina/verificar.sh   # chequeo completo, sólo lectura; sale ≠ 0 si falta algo
zsh infra/maquina/instalar.sh    # (re)instala el vigilante como LaunchAgent; no pide clave
tail -f ~/Library/Logs/fabrica-vigilante-wifi.log   # qué hizo el vigilante
```

Variables para probarlo sin tocar nada real: `VIGILANTE_URL` (forzar una falla con una URL
muerta), `VIGILANTE_LOG`, `VIGILANTE_ESTADO`, `VIGILANTE_RED`, `VIGILANTE_INTERFAZ`.

## Si algún día no se puede entrar desde afuera

1. ¿La laptop tiene Tailscale en **Connected**? Si no, prenderlo.
2. En la app de Tailscale de la laptop, ¿aparece `imac-de-lucas` y **en línea**? Si figura
   desconectada, la iMac perdió internet o corriente: el vigilante la reconecta en 1–2 minutos;
   si no vuelve, hay que estar ahí (o pedirle a alguien en casa que mire el Wi-Fi).
3. Al volver, correr `verificar.sh` y leer el log del vigilante para saber qué pasó.

## Pasos que sólo puede hacer el dueño

Instalar Tailscale e iniciar sesión, aprobar el permiso de VPN, activar Compartir pantalla y
Sesión remota en Ajustes del Sistema y los ajustes de Energía: piden su clave o sus clics, y
Claude no los toca.
