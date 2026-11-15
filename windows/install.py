"""Instala minipantalla en Windows 11.

    py windows\\install.py              instala (o actualiza) y abre la app
    py windows\\install.py --uninstall  quita el comando, el inicio automático y cierra la app

Qué hace:
  - instala para este Python lo que falte (pyusb, libusb, Pillow, ffmpeg, PySide6)
  - comprueba que la pantalla use el driver WinUSB (si no, explica cómo ponerlo con Zadig)
  - crea la carpeta Imágenes\\minipantalla para tus GIFs, imágenes y videos
  - añade el comando `minipantalla` (en %LOCALAPPDATA%\\minipantalla\\bin, que se añade al PATH)
  - hace que la app arranque al iniciar sesión (HKCU ...\\CurrentVersion\\Run)
  - abre la app (icono en la bandeja)
"""
import argparse
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import common  # noqa: E402

APP = os.path.join(HERE, "minipantalla.pyw")
CLI = os.path.join(HERE, "minipantalla.py")
REQUIREMENTS = os.path.join(HERE, "requirements.txt")
BIN = os.path.join(common.DATA, "bin")
SHIM = os.path.join(BIN, "minipantalla.cmd")
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_NAME = "Minipantalla"
NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def step(msg):
    print("\n==> " + msg, flush=True)


def console_python():
    exe = sys.executable
    if os.path.basename(exe).lower() == "pythonw.exe":
        exe = os.path.join(os.path.dirname(exe), "python.exe")
    return exe


def gui_python():
    w = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    return w if os.path.exists(w) else sys.executable


# ---------- dependencias ----------

def ensure_requirements():
    missing = []
    for mod in ("usb", "libusb_package", "PIL", "imageio_ffmpeg", "PySide6"):
        try:
            __import__(mod)
        except ImportError:
            missing.append(mod)
    if not missing:
        print("Ya está todo instalado.")
        return
    print("Instalando para", sys.executable)
    in_venv = sys.prefix != getattr(sys, "base_prefix", sys.prefix)
    user = [] if in_venv else ["--user"]
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--disable-pip-version-check", *user,
                           "-r", REQUIREMENTS])


# ---------- driver ----------

def pnp_driver():
    """(nombre, servicio) del dispositivo 2a55:9990 según Windows, o None si no está enchufado."""
    ps = ("Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -match 'VID_2A55&PID_9990' } | "
          "Select-Object -First 1 | ForEach-Object { $_.FriendlyName + '|' + $_.Service }")
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True,
                             timeout=30, creationflags=NOWIN).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None
    return tuple(out.split("|", 1)) if "|" in out else None


def check_driver():
    if common.usb_present():
        print("Pantalla encontrada y con un driver compatible (WinUSB).")
        return
    dev = pnp_driver()
    if dev is None:
        print("La pantalla no está enchufada. Puedes conectarla después: la app la detecta sola.")
        return
    print("Windows ve la pantalla como «%s» (driver: %s), pero minipantalla necesita WinUSB." % dev)
    print("""Para cambiarlo (una sola vez):
  1. Descarga Zadig de https://zadig.akeo.ie y ábrelo.
  2. Options > List All Devices, y elige el dispositivo con USB ID 2A55 9990.
  3. A la derecha elige WinUSB y pulsa Replace Driver (o Install Driver).
  4. Vuelve a ejecutar este instalador.
Ojo: con WinUSB el programa del fabricante deja de ver la pantalla.""")


# ---------- comando y PATH ----------

def write_shim():
    os.makedirs(BIN, exist_ok=True)
    with open(SHIM, "w", encoding="utf-8", newline="\r\n") as f:
        f.write('@echo off\n"%s" "%s" %%*\n' % (console_python(), CLI))
    print("Comando:", SHIM)


def _user_path():
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
        try:
            value, kind = winreg.QueryValueEx(k, "Path")
        except FileNotFoundError:
            value, kind = "", winreg.REG_EXPAND_SZ
    return value, kind


def _set_user_path(value, kind):
    import ctypes
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k, "Path", 0, kind, value)
    # Avisar a Windows para que las terminales nuevas vean el PATH nuevo.
    ctypes.windll.user32.SendMessageTimeoutW(0xFFFF, 0x1A, 0, "Environment", 0x2, 3000, None)


def _same(a, b):
    return os.path.normcase(os.path.normpath(os.path.expandvars(a))) == os.path.normcase(os.path.normpath(b))


def add_to_path():
    value, kind = _user_path()
    parts = [p for p in value.split(";") if p]
    if any(_same(p, BIN) for p in parts):
        print("Ya está en el PATH.")
        return
    _set_user_path(";".join(parts + [BIN]), kind)
    print("Añadido al PATH de tu usuario. Abre una terminal nueva para usar `minipantalla`.")


def remove_from_path():
    value, kind = _user_path()
    parts = [p for p in value.split(";") if p]
    keep = [p for p in parts if not _same(p, BIN)]
    if keep != parts:
        _set_user_path(";".join(keep), kind)


# ---------- inicio automático y app ----------

def set_autostart(on):
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if on:
            winreg.SetValueEx(k, RUN_NAME, 0, winreg.REG_SZ, '"%s" "%s"' % (gui_python(), APP))
        else:
            try:
                winreg.DeleteValue(k, RUN_NAME)
            except FileNotFoundError:
                pass


def stop_app():
    """Cierra la copia abierta (para actualizar o desinstalar): primero apaga la pantalla."""
    st = common.read_status()
    if not st:
        return
    common.set_paused(True)
    end = time.time() + 8
    while time.time() < end:
        s = common.read_status()
        if not s or s.get("state") in ("paused", "sleeping"):
            break
        time.sleep(0.2)
    subprocess.run(["taskkill", "/PID", str(st["pid"]), "/F"], capture_output=True, creationflags=NOWIN)
    time.sleep(0.5)
    print("App anterior cerrada.")


def start_app():
    flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    subprocess.Popen([gui_python(), APP], cwd=HERE, creationflags=flags, close_fds=True)


def main():
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description="Instala minipantalla para Windows.")
    ap.add_argument("--uninstall", action="store_true", help="quita el comando, el inicio automático y cierra la app")
    ap.add_argument("--no-autostart", action="store_true", help="no abrir la app al iniciar sesión")
    ap.add_argument("--no-start", action="store_true", help="no abrir la app ahora")
    args = ap.parse_args()

    if args.uninstall:
        step("Cerrando la app")
        stop_app()
        step("Quitando el inicio automático y el comando")
        set_autostart(False)
        remove_from_path()
        try:
            os.remove(SHIM)
        except FileNotFoundError:
            pass
        print("Listo. Tus archivos de Imágenes\\minipantalla y los ajustes no se han tocado.")
        return

    if sys.version_info < (3, 9):
        raise SystemExit("minipantalla necesita Python 3.9 o más nuevo.")

    step("Dependencias de Python")
    ensure_requirements()

    step("Pantalla y driver")
    check_driver()

    step("Carpeta de archivos")
    folder = common.media_folder()
    os.makedirs(folder, exist_ok=True)
    print("Copia aquí tus GIFs, imágenes y videos:", folder)

    step("Comando minipantalla")
    write_shim()
    add_to_path()

    step("Inicio automático")
    set_autostart(not args.no_autostart)
    print("La app se abre al iniciar sesión." if not args.no_autostart else "Inicio automático desactivado.")

    if not args.no_start:
        step("Abriendo la app")
        stop_app()
        start_app()
        print("Busca el icono redondo en la bandeja (puede estar bajo la flecha ^).")


if __name__ == "__main__":
    main()
