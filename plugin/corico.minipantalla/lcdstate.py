#!/usr/bin/env python3
"""Estado de la mini pantalla para el panel, sin tocar el USB.

    lcdstate.py state   -> JSON: conectada, carpeta, archivos, actual, rotación

Solo lee sysfs y los ajustes que guarda `minipantalla`; nunca abre el
dispositivo, así que es seguro llamarlo a menudo y mientras se guarda algo.
"""
import configparser
import glob
import json
import os
import subprocess
import sys

VID, PID = "2a55", "9990"
HOME = os.path.expanduser("~")
FOLDER = os.environ.get("MINIPANTALLA_DIR") or os.path.join(HOME, "Pictures", "minipantalla")
SETTINGS = os.path.join(HOME, ".config", "AppotechLCD", "settings.ini")
EXTS = {".gif", ".png", ".jpg", ".jpeg", ".bmp", ".mp4", ".mkv", ".webm", ".mov", ".avi"}
VIDEO = {".mp4", ".mkv", ".webm", ".mov", ".avi"}


def connected():
    for vendor in glob.glob("/sys/bus/usb/devices/*/idVendor"):
        base = os.path.dirname(vendor)
        try:
            with open(vendor) as f, open(os.path.join(base, "idProduct")) as g:
                if f.read().strip() == VID and g.read().strip() == PID:
                    return True
        except OSError:
            continue
    return False


def streaming():
    """¿Está en marcha el servicio que transmite a la pantalla?"""
    try:
        r = subprocess.run(["systemctl", "--user", "-q", "is-active", "minipantalla.service"],
                           stdin=subprocess.DEVNULL, capture_output=True, timeout=3)
        return r.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def settings():
    cp = configparser.ConfigParser()
    cp.optionxform = str
    try:
        cp.read(SETTINGS, encoding="utf-8")
    except (OSError, configparser.Error):
        return {}
    return dict(cp["settings"]) if cp.has_section("settings") else {}


def media_files():
    try:
        os.makedirs(FOLDER, exist_ok=True)
        entries = list(os.scandir(FOLDER))
    except OSError:
        return []
    out = []
    for e in entries:
        ext = os.path.splitext(e.name)[1].lower()
        if ext in EXTS and e.is_file():
            st = e.stat()
            out.append({"path": e.path, "name": e.name, "video": ext in VIDEO,
                        "size": st.st_size, "mtime": st.st_mtime})
    out.sort(key=lambda f: f["mtime"], reverse=True)
    return out


def state():
    s = settings()
    try:
        rotation = int(s.get("LcdDir", 0)) & 3
    except ValueError:
        rotation = 0
    return {
        "connected": connected(),
        "folder": FOLDER,
        "files": media_files(),
        "current": s.get("ResPath", ""),
        "rotation": rotation,
        "streaming": streaming(),
    }


if __name__ == "__main__":
    if sys.argv[1:] != ["state"]:
        print("uso: lcdstate.py state", file=sys.stderr)
        sys.exit(2)
    print(json.dumps(state()))
