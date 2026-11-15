# minipantalla — ahora también para KDE Plasma 6

Soporte en Linux para la **mini pantalla USB redonda de 2.1"** que se vende como
QTKeJi / "SmatCool" / AX206 (480×480). El fabricante solo trae
programa para Windows. Este repo incluye:

- un CLI, `minipantalla`, para poner GIFs, imágenes y videos en la pantalla y girarlos
- un servicio de usuario que transmite en vivo, a todo color y fluido. La pantalla
  se apaga cuando apagas o suspendes el PC.
- un plugin para la barra de [Omarchy](https://omarchy.org/), **Mini Screen**, para elegir el archivo y girarlo con un clic
- el mismo widget para **KDE Plasma 6** (CachyOS, Arch + Plasma...)
- una versión para **Windows 11** (rama `windows`): app en la bandeja y el mismo CLI. Mira [Windows 11](#windows-11)

## ¿Es compatible mi pantalla?

Conéctala y ejecuta:

```bash
lsusb | grep 2a55:9990
```

Si sale una línea, es el mismo chip con el que se probó. Otras pantallas AX206
(otro tamaño u otro ID USB) **no están probadas** y seguramente necesiten cambios.

## Instalación

Necesitas una distro basada en Arch (Arch, Omarchy, CachyOS...). El widget de la barra
necesita Omarchy o KDE Plasma 6; sin ninguno, el CLI y el servicio funcionan igual.

```bash
git clone https://github.com/coricogit/minipantalla.git ~/minipantalla
cd ~/minipantalla
./install.sh
```

El instalador pide `sudo` para instalar los paquetes que falten
(`python-pyusb python-pillow ffmpeg python-dbus python-gobject`) y la regla udev
que deja a tu usuario usar la pantalla. Además:

- enlaza `~/.local/bin/minipantalla` a esta carpeta (no la muevas después de clonarla)
- crea `~/Pictures/minipantalla` para tus archivos (se cambia con `MINIPANTALLA_DIR`)
- en Omarchy, copia el plugin a `~/.config/omarchy/plugins/corico.minipantalla` y lo activa
- en KDE Plasma, instala el widget **Mini pantalla**. Añádelo con clic derecho en el panel > *Añadir widgets*
- instala y arranca `minipantalla.service` (unidad de usuario de systemd)

Para actualizar: `git pull && ./install.sh`. Para quitarlo: `./install.sh --uninstall`.

## Uso

| Comando | Qué hace |
|---|---|
| `minipantalla poner <archivo>` | Muestra un GIF, imagen o video (lo transmite el servicio) |
| `minipantalla rotar 0\|90\|180\|270` | Gira la imagen |
| `minipantalla estado` | Estado del servicio |
| `minipantalla iniciar` / `parar` | Arranca o para el servicio (al parar, la pantalla se apaga) |
| `minipantalla guardar <archivo>` | Graba el archivo en la memoria de la pantalla para que se vea sin PC |
| `minipantalla transmitir <archivo>` | Transmite a mano en la terminal (con el servicio parado) |
| `minipantalla info` | Muestra la resolución (prueba la conexión) |

`--fit cover|contain|stretch` elige cómo encajar un archivo que no sea de 480×480.

## Windows 11

En Windows, lo que en Linux hace el servicio lo hace una app en la **bandeja del
sistema**. Usa el mismo código de transmisión (`servicio.py`, `acciones.py` y
`vendor/`).

### Instalación

Necesitas [Python 3.9+](https://www.python.org/downloads/windows/) (marca
**Add python.exe to PATH**) o `winget install Python.Python.3.12`. Después:

```powershell
git clone -b windows https://github.com/coricogit/minipantalla.git $HOME\src\minipantalla
py $HOME\src\minipantalla\windows\install.py
```

También puedes hacer doble clic en `windows\instalar.bat`, que deja el resultado en
`windows\install.log`.

El instalador:

- instala lo que falte para ese Python: pyusb, libusb, Pillow, ffmpeg (vía
  imageio-ffmpeg) y PySide6
- comprueba que la pantalla use el driver **WinUSB** y, si no, explica cómo ponerlo
- crea `Imágenes\minipantalla` (respeta Imágenes en OneDrive; se cambia con `MINIPANTALLA_DIR`)
- añade el comando `minipantalla` (en `%LOCALAPPDATA%\minipantalla\bin`, que se añade a tu PATH)
- hace que la app se abra al iniciar sesión (`--no-autostart` para evitarlo) y la abre (`--no-start`)

Para actualizar: `git pull` y vuelve a ejecutar `install.py`. Para quitarlo:
`py windows\install.py --uninstall` (no toca tus archivos ni tus ajustes).

### Driver WinUSB

Windows no trae driver para este chip. La pantalla tiene que usar **WinUSB**
(una sola vez):

1. Descarga [Zadig](https://zadig.akeo.ie) y ábrelo.
2. *Options > List All Devices* y elige el dispositivo con USB ID `2A55 9990`.
3. Elige **WinUSB** y pulsa *Replace Driver*.

Con WinUSB, el programa del fabricante deja de ver la pantalla.

### Uso

**El icono de la bandeja** es una pantallita redonda con un punto de color: verde
si transmite, ámbar si espera un archivo y rojo si la pantalla no está conectada.

- **clic**: abre el panel con tus archivos (las miniaturas son redondas, como la
  pantalla). Clic en uno para transmitirlo; abajo están la rotación y el encaje.
- **clic central**: apagar o encender la pantalla
- **clic derecho**: abrir el panel, apagar o encender, abrir la carpeta, iniciar con Windows, salir

La pantalla se apaga al salir de la app, al cerrar sesión, al apagar el PC y al
suspenderlo. Al despertar, vuelve a transmitir.

El CLI tiene los mismos comandos que en Linux (`poner`, `rotar`, `estado`,
`iniciar`, `parar`, `guardar`, `transmitir`, `mostrar`, `info`). `iniciar` y `parar`
encienden y apagan la pantalla desde la app de la bandeja; `guardar`, `transmitir`
e `info` necesitan la pantalla libre (`minipantalla parar`).

El estado y el registro están en `%LOCALAPPDATA%\minipantalla` (`estado.json` y
`minipantalla.log`), y los ajustes en `%APPDATA%\AppotechLCD\settings.ini`.

## Límites conocidos

- **Lo grabado con `guardar` se traba con GIFs pesados**, porque el chip los decodifica por
  software. Los GIFs sencillos (≈15–20 KB por fotograma) van bien; los de tipo foto, no.
  `--colores N` reduce la paleta para ayudar. La transmisión en vivo (lo normal) no tiene este límite.
- **El AVI no se reproduce** desde la memoria de la pantalla. No se sabe qué formato
  exacto espera el firmware, así que `--avi` es experimental.
- Mientras el servicio está activo, ocupa el USB: `info` y `transmitir` te piden pararlo antes.

## Créditos y licencia

El código del protocolo USB en [`vendor/`](vendor/) es una copia revisada de
[caioklein/AX206-LCD-Screen](https://github.com/caioklein/AX206-LCD-Screen)
(el commit exacto está en `vendor/UPSTREAM`). Gracias a su autor por
descifrar la pantalla.

Por eso todo el proyecto se publica bajo la [GNU GPL v3](LICENSE).
