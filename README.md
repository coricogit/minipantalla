# minipantalla — now for KDE Plasma 6 too

Linux support for the cheap **2.1" round USB mini screen** sold as
QTKeJi / "SmatCool" / AX206 (480×480). The vendor only ships a
Windows app. This repo gives you:

- a CLI, `minipantalla`, to show GIFs, images and videos on the screen and to rotate them
- a user service that streams to the screen live, at full color and smooth framerate.
  The screen turns off when the PC shuts down or suspends.
- an [Omarchy](https://omarchy.org/) bar plugin, **Mini Screen**, to pick a file and rotate it with one click ([also on its own repo](https://github.com/coricogit/omarchy-mini-screen))
- the same widget for **KDE Plasma 6** (CachyOS, Arch + Plasma...)
- a **Windows 11** version (`windows` branch): a tray app and the same CLI. See [Windows 11](#windows-11)

*[Leer en español](README.es.md)*

## Is my screen supported?

Plug it in and run:

```bash
lsusb | grep 2a55:9990
```

If a line shows up, it is the same chip this was tested on. Other AX206
screens (other sizes or USB IDs) are **untested** and probably need changes.

## Install

Requires an Arch-based distro (Arch, Omarchy, CachyOS...). The bar widget needs
Omarchy or KDE Plasma 6; without either, the CLI and the service still work.

```bash
git clone https://github.com/coricogit/minipantalla.git ~/minipantalla
cd ~/minipantalla
./install.sh
```

The installer asks for `sudo` to install the missing packages
(`python-pyusb python-pillow ffmpeg python-dbus python-gobject`) and the udev rule
that lets your user talk to the screen. It also:

- links `~/.local/bin/minipantalla` to this folder (keep the folder where you cloned it)
- creates `~/Pictures/minipantalla` for your media (override it with `MINIPANTALLA_DIR`)
- on Omarchy, copies the bar plugin to `~/.config/omarchy/plugins/corico.minipantalla` and enables it
- on KDE Plasma, installs the **Mini Screen** widget. Add it with right-click on the panel > *Add Widgets*
- installs and starts `minipantalla.service` (systemd user unit)

Update with `git pull && ./install.sh`. Remove it with `./install.sh --uninstall`.

## Usage

The CLI messages are in Spanish. The commands:

| Command | What it does |
|---|---|
| `minipantalla poner <file>` | Show a GIF, image or video (streamed live by the service) |
| `minipantalla rotar 0\|90\|180\|270` | Rotate the picture |
| `minipantalla estado` | Service status |
| `minipantalla iniciar` / `parar` | Start / stop the service (stopping turns the screen off) |
| `minipantalla guardar <file>` | Store the file in the screen's own memory so it plays without a PC |
| `minipantalla transmitir <file>` | Stream manually in the terminal (service must be stopped) |
| `minipantalla info` | Show the resolution (connection test) |

`--fit cover|contain|stretch` chooses how a file that isn't 480×480 is fitted.

## Windows 11

On Windows, a **system tray** app does what the service does on Linux. It uses the
same streaming code (`servicio.py`, `acciones.py` and `vendor/`).

### Install

You need [Python 3.9+](https://www.python.org/downloads/windows/) (tick
**Add python.exe to PATH**) or `winget install Python.Python.3.12`. Then:

```powershell
git clone -b windows https://github.com/coricogit/minipantalla.git $HOME\src\minipantalla
py $HOME\src\minipantalla\windows\install.py
```

Or double-click `windows\instalar.bat`, which saves the output to `windows\install.log`.

The installer:

- installs whatever that Python is missing: pyusb, libusb, Pillow, ffmpeg (through
  imageio-ffmpeg) and PySide6
- checks that the screen uses the **WinUSB** driver and explains how to set it if not
- creates `Pictures\minipantalla` (follows Pictures into OneDrive; override with `MINIPANTALLA_DIR`)
- adds the `minipantalla` command (in `%LOCALAPPDATA%\minipantalla\bin`, added to your PATH)
- starts the app when you sign in (`--no-autostart` to skip) and opens it (`--no-start`)

To update: `git pull` and run `install.py` again. To remove it:
`py windows\install.py --uninstall` (your files and settings are left alone).

### WinUSB driver

Windows has no driver for this chip. The screen has to use **WinUSB** (once):

1. Download [Zadig](https://zadig.akeo.ie) and open it.
2. *Options > List All Devices* and pick the device with USB ID `2A55 9990`.
3. Choose **WinUSB** and click *Replace Driver*.

With WinUSB, the vendor app no longer sees the screen.

### Usage

**The tray icon** is a little round screen with a colored dot: green while streaming,
amber while it waits for a file and red when the screen isn't connected.

- **click**: opens the panel with your files (round thumbnails, like the screen).
  Click one to stream it; rotation and fit are at the bottom.
- **middle click**: turn the screen off or on
- **right click**: open the panel, turn off or on, open the folder, start with Windows, quit

The screen turns off when you quit the app, sign out, shut down or suspend the PC.
When the PC wakes up, streaming resumes.

The CLI has the same commands as on Linux (`poner`, `rotar`, `estado`, `iniciar`,
`parar`, `guardar`, `transmitir`, `mostrar`, `info`). `iniciar` and `parar` turn the
screen on and off through the tray app; `guardar`, `transmitir` and `info` need the
screen free (`minipantalla parar`).

State and log live in `%LOCALAPPDATA%\minipantalla` (`estado.json` and
`minipantalla.log`); settings in `%APPDATA%\AppotechLCD\settings.ini`.

## Known limits

- **Stored media (`guardar`) is choppy for heavy GIFs.** The chip decodes them in
  software. Simple GIFs (≈15–20 KB per frame) play fine; photo-like ones don't.
  `--colores N` reduces the palette to help. Live streaming (the default) has no such limit.
- **AVI does not play** from the screen's memory. The exact format the firmware
  expects is unknown, so `--avi` is experimental.
- While the service is running it owns the USB device, so `info` and `transmitir`
  ask you to stop it first.

## Credits and license

The USB protocol code in [`vendor/`](vendor/) is a reviewed copy of
[caioklein/AX206-LCD-Screen](https://github.com/caioklein/AX206-LCD-Screen)
(see `vendor/UPSTREAM` for the exact commit). Thanks to its author for
reverse-engineering the screen.

Because of that, the whole project is released under the
[GNU GPL v3](LICENSE).
