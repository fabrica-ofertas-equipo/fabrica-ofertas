# Regla: máquina de cómputo siempre prendida (Mac o Windows)

Toda computadora que quede como **cómputo** de la fábrica (corre sesiones, workers y renders y se
maneja desde otra) tiene que cumplir **los 8 puntos** de abajo. La pregunta que responden es:
*si se corta la luz o el Wi-Fi a las 3 de la mañana y nadie está en casa, ¿vuelve sola a estar
manejable desde afuera, con todo corriendo?*

La iMac de el dueño cumple todo (ver [`README.md`](README.md)); se comprueba con
`zsh infra/maquina/verificar.sh`. La parte de Windows no se probó en una máquina real todavía:
seguirla y marcar acá lo que difiera.

| # | Punto | Por qué |
|---|---|---|
| 1 | Nunca se duerme ni hiberna | Dormida no corre nada ni se puede entrar. |
| 2 | Pantalla sin bloqueo | Que no haga falta la clave en la máquina para seguir. |
| 3 | Vuelve a prender sola tras un corte de luz | Si no, queda apagada hasta que alguien llegue. |
| 4 | Inicia sesión sola | Tras un reinicio, las apps y el acceso remoto arrancan recién con la sesión abierta. |
| 5 | Abre sola las apps que tienen que correr | Tailscale primero; después lo de la fábrica. |
| 6 | No se reinicia por actualizaciones | Un reinicio sorpresa corta las sesiones. Actualizar a mano. |
| 7 | Acceso remoto desde cualquier red | Tailscale + pantalla remota + terminal. |
| 8 | Internet que no se cae solo | Cable si se puede; si no, red buena primero, sin redes públicas, y vigilante. |

**Cifrado de disco**: en Mac, FileVault activo choca con los puntos 3 y 4 (pide la clave en la
máquina después de cada reinicio): **apagado**. En Windows, BitLocker con TPM arranca solo y no
choca; si pide clave de recuperación al arrancar, apagarlo.

**Seguridad**: sin bloqueo y con inicio de sesión automático, cualquiera que esté **físicamente**
frente a la máquina la usa. Por eso queda en casa, y el acceso remoto va sólo por Tailscale (nunca
abrir puertos del router ni usar herramientas de acceso remoto con link público).

---

## Mac

| # | Dónde | Qué poner |
|---|---|---|
| 1 | Ajustes del Sistema → **Energía** (iMac/Mac mini/Studio) o **Batería → Opciones** (notebook) | Activar «Impedir entrar en reposo automáticamente cuando se apaga la pantalla» y «Activar para acceso a la red». En terminal: `sudo pmset -a sleep 0 standby 0 womp 1`. Notebook: siempre enchufada; con la tapa cerrada sólo no se duerme si tiene monitor externo. |
| 2 | **Pantalla bloqueada** | «Requerir contraseña tras activar el salvapantallas o apagar la pantalla»: **Nunca**. Salvapantallas: Nunca. Apagar la pantalla sí se puede: ahorra y no molesta. |
| 3 | **Energía** | «Arrancar al conectarse a la corriente»: **Siempre** (o `sudo pmset -a autorestart 1`). Notebooks Apple silicon: prenden solas al abrir la tapa o enchufar; no hay ajuste equivalente. |
| 4 | **Usuarios y grupos** | «Iniciar sesión automáticamente como»: tu usuario. Sólo aparece con **FileVault apagado** (Privacidad y seguridad → FileVault). |
| 5 | General → **Ítems de inicio y extensiones** | Agregar con «+»: **Tailscale** (imprescindible), Claude y lo que tenga que estar abierto. Los procesos sin ventana (workers, vigilante) van como LaunchAgent en `~/Library/LaunchAgents/` con `RunAtLoad`. En Tailscale, además: Ajustes → «Iniciar al iniciar sesión». |
| 6 | General → **Actualización de software** → «Actualizaciones automáticas» (ⓘ) | Apagar «Instalar actualizaciones de macOS». Dejar las de seguridad («Instalar respuestas de seguridad y archivos del sistema»): no reinician. |
| 7 | **Tailscale** (App Store) + General → **Compartir** | Tailscale con la misma cuenta que la laptop. En Compartir: **Compartir pantalla** y **Sesión remota** (SSH) activos, sólo administradores; *Administración remota* apagada. Desde la laptop: `vnc://nombre-de-la-mac` en Alto rendimiento con pantalla virtual, o `ssh usuario@nombre-de-la-mac`. La versión de Tailscale de la App Store sólo corre con la sesión abierta: por eso el punto 4 es obligatorio. |
| 8 | **Wi-Fi** → Redes conocidas | Cable Ethernet si se puede. Si no: la red buena primera, «Unirse automáticamente» apagado (o red olvidada) en las públicas con login (TeleCentro Wifi, Personal Wifi Zone, Fibertel Zone…) y el vigilante: `zsh infra/maquina/instalar.sh` (cambiar `VIGILANTE_RED` si la red buena no es «tuotroproyecto»). |

Chequeo: `zsh infra/maquina/verificar.sh` revisa los 8 puntos y sale distinto de 0 si falta algo.

---

## Windows (10 y 11)

Los comandos van en **PowerShell como administrador** (clic derecho en Inicio → Terminal (Administrador)).

**1 · Nunca se duerme ni hiberna**
- Configuración → Sistema → **Inicio/apagado y batería** (o Energía): con corriente, «Suspender» →
  **Nunca**. La pantalla puede apagarse.
- ```powershell
  powercfg /change standby-timeout-ac 0
  powercfg /change hibernate-timeout-ac 0
  powercfg /hibernate off
  ```
- Administrador de dispositivos → Adaptadores de red → la placa (Wi-Fi y Ethernet) → Propiedades →
  **Administración de energía** → destildar «Permitir que el equipo apague este dispositivo para
  ahorrar energía». Si no, la red se duerme aunque la PC no.

**2 · Pantalla sin bloqueo**
- Configuración → Cuentas → **Opciones de inicio de sesión** → «Si estuviste ausente, ¿cuándo
  debería Windows pedirte que vuelvas a iniciar sesión?» → **Nunca**. Apagar «Bloqueo dinámico».
- Protector de pantalla: Ninguno, o destildar «Mostrar la pantalla de inicio de sesión al reanudar».

**3 · Vuelve a prender sola tras un corte de luz** — esto **no está en Windows**, está en la BIOS/UEFI:
- Reiniciar entrando a la BIOS (Configuración → Sistema → Recuperación → Inicio avanzado → Opciones
  avanzadas → Configuración de firmware UEFI, o tecla Supr/F2 al prender).
- Buscar **«Restore on AC Power Loss»**, «AC Recovery», «After Power Failure» o «AC Back»
  (suele estar en Power / Advanced / Chipset) → **Power On** (o «Last State»). Guardar y salir.
- Si existe, activar también **Wake on LAN** (para prenderla desde otra máquina de la red).

**4 · Inicia sesión sola**
- Configuración → Cuentas → Opciones de inicio de sesión → apagar «Para mejorar la seguridad, permitir
  sólo el inicio de sesión de Windows Hello…».
- Win+R → `netplwiz` → destildar «Los usuarios deben escribir su nombre y contraseña para usar el
  equipo» → Aplicar → poner la clave una vez. Si la casilla no aparece:
  ```powershell
  reg add "HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\PasswordLess\Device" /v DevicePasswordLessBuildVersion /t REG_DWORD /d 0 /f
  ```
  y volver a abrir `netplwiz`. Alternativa: **Autologon** de Microsoft Sysinternals (guarda la clave cifrada).

**5 · Abre sola las apps**
- Configuración → Aplicaciones → **Inicio**: prender Tailscale y lo que tenga que correr.
- Para lo que no aparezca ahí: Win+R → `shell:startup` y pegar un acceso directo.
- Scripts o procesos sin ventana: **Programador de tareas** → Crear tarea → Desencadenador «Al
  iniciar sesión» → en Configuración, «Si la tarea no se ejecuta, reiniciar cada: 1 minuto».

**6 · No se reinicia por actualizaciones**
- Configuración → Windows Update → Opciones avanzadas → **Horas activas**: manual, el rango máximo;
  apagar «Reiniciar este dispositivo lo antes posible…». Usar «Pausar actualizaciones» y actualizar a mano.
- Windows Pro: `gpedit.msc` → Configuración del equipo → Plantillas administrativas → Componentes de
  Windows → Windows Update → «No reiniciar automáticamente con usuarios que hayan iniciado sesión» →
  Habilitada. En Home, por registro:
  ```powershell
  reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU" /v NoAutoRebootWithLoggedOnUsers /t REG_DWORD /d 1 /f
  ```

**7 · Acceso remoto desde cualquier red**
- **Tailscale** (tailscale.com/download) con la misma cuenta. En el ícono de la bandeja →
  Preferences → activar **«Run unattended»**: así queda conectada aunque no haya sesión abierta.
- **Pantalla**, según la edición:
  - Windows **Pro**: Configuración → Sistema → **Escritorio remoto** → Activado. Desde la Mac, la app
    *Windows App* (ex Microsoft Remote Desktop) al nombre de Tailscale. Ojo: al entrar por Escritorio
    remoto, la pantalla física se bloquea; las apps siguen corriendo.
  - Windows **Home** (no trae Escritorio remoto): **RustDesk** apuntando a la IP de Tailscale (con
    «Acceso directo por IP» activado y clave permanente), o Parsec / Chrome Remote Desktop.
- **Terminal**: Configuración → Sistema → Características opcionales → agregar **Servidor OpenSSH**, y:
  ```powershell
  Start-Service sshd; Set-Service sshd -StartupType Automatic
  ```

**8 · Internet que no se cae solo**
- Cable si se puede.
- Ver las redes guardadas, olvidar las públicas y dejar la buena primera:
  ```powershell
  netsh wlan show profiles
  netsh wlan delete profile name="TeleCentro Wifi"
  netsh wlan set profileorder name="tuotroproyecto" interface="Wi-Fi" priority=1
  netsh wlan set profileparameter name="OTRA RED" connectionmode=manual   # las que no se borran
  ```
- Vigilante (sin probar todavía en Windows): guardarlo como `C:\fabrica\vigilante_wifi.ps1` y crear
  la tarea del final. A diferencia de la Mac, Windows sí se puede reconectar por nombre sin la clave
  (`netsh wlan connect`), porque el perfil la guarda.
  ```powershell
  # vigilante_wifi.ps1 — cada minuto; con 2 fallas seguidas reconecta a la red buena
  $red = "tuotroproyecto"; $estado = "$env:ProgramData\vigilante-wifi.fallas"; $log = "$env:ProgramData\vigilante-wifi.log"
  function HayInternet { try { (Invoke-WebRequest "http://www.msftconnecttest.com/connecttest.txt" -UseBasicParsing -TimeoutSec 6).Content -eq "Microsoft Connect Test" } catch { $false } }
  function Anotar($m) { Add-Content $log "$(Get-Date -f 'yyyy-MM-dd HH:mm:ss') $m" }
  if (HayInternet) { if (Test-Path $estado) { Anotar "internet de vuelta"; Remove-Item $estado }; exit 0 }
  $f = 1 + [int](Get-Content $estado -ErrorAction SilentlyContinue); Set-Content $estado $f; Anotar "sin internet (falla $f)"
  if ($f -lt 2) { exit 0 }
  Anotar "reconecto a $red"; netsh wlan connect name="$red" | Out-Null; Start-Sleep 15
  if (HayInternet) { Anotar "ok"; Remove-Item $estado } else { Anotar "sigue sin internet; reintento en el próximo minuto" }
  ```
  ```powershell
  schtasks /create /tn "Vigilante Wi-Fi" /sc minute /mo 1 /ru SYSTEM /rl HIGHEST /tr "powershell -NoProfile -ExecutionPolicy Bypass -File C:\fabrica\vigilante_wifi.ps1"
  ```

---

## Prueba final (en las dos)

1. Desde la laptop, en otra red (el hotspot del celular), entrar a la pantalla y a la terminal.
2. **Simulacro de corte**: desenchufar la máquina 10 segundos y volver a enchufar, sin tocar nada
   más. En unos minutos tiene que volver a aparecer en línea en Tailscale y dejar entrar, con las
   apps del punto 5 abiertas.
3. **Simulacro de Wi-Fi**: conectarla a mano a otra red sin internet; en 1–2 minutos el vigilante
   la tiene que devolver a la red buena (Mac: mirar `~/Library/Logs/fabrica-vigilante-wifi.log`).
