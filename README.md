# minipantalla

Linux support for the cheap **2.1" round USB mini screen** sold as
QTKeJi / "SmatCool" / AX206 (480×480). The vendor only ships a
Windows app. This repo gives you:

- a CLI, `minipantalla`, to show GIFs, images and videos on the screen and to rotate them
- a user service that streams to the screen live, at full color and smooth framerate.
  The screen turns off when the PC shuts down or suspends.
- an [Omarchy](https://omarchy.org/) bar plugin to pick a file and rotate it with one click

*[Leer en español](README.es.md)*

## Is my screen supported?

Plug it in and run:

```bash
lsusb | grep 2a55:9990
```

If a line shows up, it is the same chip this was tested on. Other AX206
screens (other sizes or USB IDs) are **untested** and probably need changes.

## Install

Requires Arch Linux. The bar plugin also requires Omarchy; without it, the CLI and the service still work.

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
- copies the bar plugin to `~/.config/omarchy/plugins/corico.minipantalla` and enables it
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
