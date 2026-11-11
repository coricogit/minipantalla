# Mini Screen

An Omarchy bar widget for the cheap **2.1" round USB mini screen** sold as
QTKeJi / "SmatCool" / AX206 (USB `2a55:9990`, 480×480).

Click the icon to open the panel. It lists the GIFs, images and videos in
`~/Pictures/minipantalla`. Click one to show it on the screen, or pick a
rotation (0°, 90°, 180°, 270°). The panel also shows whether the screen is
plugged in and whether it is streaming.

## Requirements

This widget is only the bar front end. The USB work is done by the
**[minipantalla](https://github.com/coricogit/minipantalla)** CLI and its user
service, which need:

- Arch Linux / Omarchy
- the packages `python-pyusb python-pillow ffmpeg python-dbus python-gobject`
- a udev rule so your user can access the screen (installed with `sudo`)

Without the CLI, the panel still opens but tells you it's missing.

## Install

1. Add the widget:

   ```bash
   omarchy plugin add https://github.com/coricogit/omarchy-mini-screen --enable
   ```

2. Install the CLI and service, pinned to the reviewed commit. This also installs the dependencies and the udev rule, and leaves the widget from step 1 untouched:

   ```bash
   git clone https://github.com/coricogit/minipantalla.git ~/minipantalla && git -C ~/minipantalla checkout --detach e202cf9735ca292ad091077ffcb8e7a23b040c5e && ~/minipantalla/install.sh
   ```

Put your media in `~/Pictures/minipantalla`, or set `MINIPANTALLA_DIR` to use another folder.

## Remove

```bash
omarchy plugin remove corico.minipantalla
~/minipantalla/install.sh --uninstall   # removes the CLI, the service and the udev rule
```

Your pictures folder is never deleted.

## Notes

- The widget never opens the USB device itself. `lcdstate.py` only reads sysfs,
  `systemctl --user is-active minipantalla.service` and the CLI's
  `~/.config/AppotechLCD/settings.ini`.
- Clicking a file runs `~/.local/bin/minipantalla poner <file>`. Picking a
  rotation runs `minipantalla rotar <degrees>`.
- Only the `2a55:9990` model has been tested.

## License

GPL-3.0, same as the [minipantalla](https://github.com/coricogit/minipantalla) project.
