"""Lo que comparten la app de la bandeja (minipantalla.pyw) y el CLI (minipantalla.py).

    %LOCALAPPDATA%\\minipantalla\\estado.json   lo escribe la app: qué está haciendo
    %LOCALAPPDATA%\\minipantalla\\pausa         si existe, la app suelta el USB y apaga la pantalla

Los ajustes (archivo, encaje, rotación) siguen en %APPDATA%\\AppotechLCD\\settings.ini,
el mismo archivo que usan vendor/core.py y acciones.py.
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for p in (os.path.join(ROOT, "vendor"), ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)

VID, PID = 0x2A55, 0x9990
EXTS = {".gif", ".png", ".jpg", ".jpeg", ".bmp", ".mp4", ".mkv", ".webm", ".mov", ".avi", ".wmv", ".flv"}
VIDEO = {".mp4", ".mkv", ".webm", ".mov", ".avi", ".wmv", ".flv"}

DATA = os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "minipantalla")
STATUS = os.path.join(DATA, "estado.json")
PAUSE = os.path.join(DATA, "pausa")
THUMBS = os.path.join(DATA, "miniaturas")
LOG = os.path.join(DATA, "minipantalla.log")


def ensure_data():
    os.makedirs(DATA, exist_ok=True)


def media_folder():
    """%MINIPANTALLA_DIR%, o Imágenes\\minipantalla (respeta Imágenes movida a OneDrive u otro disco)."""
    env = os.environ.get("MINIPANTALLA_DIR")
    if env:
        return env
    pictures = os.path.join(os.path.expanduser("~"), "Pictures")
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders") as k:
            pictures = os.path.expandvars(winreg.QueryValueEx(k, "My Pictures")[0])
    except (ImportError, OSError):
        pass
    return os.path.join(pictures, "minipantalla")


def spanish():
    """Idioma de la interfaz de Windows (no el formato regional, que puede estar en inglés)."""
    for var in ("MINIPANTALLA_LANG", "LANG"):
        if os.environ.get(var):
            return os.environ[var].startswith("es")
    try:
        import ctypes
        return ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF == 0x0A
    except (AttributeError, OSError):
        return False


def process_started(pid):
    """Hora de creación (FILETIME) del proceso `pid` si sigue vivo, o None."""
    if not pid:
        return None
    try:
        import ctypes
        k = ctypes.windll.kernel32
        h = k.OpenProcess(0x1000, False, int(pid))        # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return None
        try:
            code = ctypes.c_ulong()
            if not k.GetExitCodeProcess(h, ctypes.byref(code)) or code.value != 259:     # STILL_ACTIVE
                return None
            t = [ctypes.c_ulonglong() for _ in range(4)]
            if not k.GetProcessTimes(h, *[ctypes.byref(x) for x in t]):
                return None
            return t[0].value
        finally:
            k.CloseHandle(h)
    except (AttributeError, OSError):
        return None


def read_status():
    """Estado que publica la app, o None si no está abierta.

    Comprueba el PID y también la hora a la que arrancó ese proceso: si la app se
    cerró de golpe, Windows puede haber dado su PID a otro programa."""
    try:
        with open(STATUS, encoding="utf-8") as f:
            st = json.load(f)
    except (OSError, ValueError):
        return None
    started = process_started(st.get("pid"))
    return st if started is not None and started == st.get("started") else None


def write_status(st):
    ensure_data()
    tmp = STATUS + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False)
    for _ in range(20):                                   # el CLI puede estar leyéndolo justo ahora
        try:
            os.replace(tmp, STATUS)
            return
        except PermissionError:
            time.sleep(0.05)


def paused():
    return os.path.exists(PAUSE)


def set_paused(on):
    ensure_data()
    if on:
        open(PAUSE, "w").close()
    else:
        try:
            os.remove(PAUSE)
        except FileNotFoundError:
            pass


def usb_present():
    """¿Está la pantalla enchufada? Solo enumera el USB, no la abre (seguro mientras otro la usa)."""
    try:
        import usb.core
        import libusb_package
        return usb.core.find(idVendor=VID, idProduct=PID, backend=libusb_package.get_libusb1_backend()) is not None
    except Exception:  # noqa: BLE001
        return False


def media_files(folder=None):
    """(archivos válidos más recientes primero, nombres ignorados por extensión)."""
    folder = folder or media_folder()
    try:
        os.makedirs(folder, exist_ok=True)
        entries = list(os.scandir(folder))
    except OSError:
        return [], []
    out, ignored = [], []
    for e in entries:
        if not e.is_file() or e.name.startswith("."):
            continue
        ext = os.path.splitext(e.name)[1].lower()
        if ext not in EXTS:
            if ext not in (".ini", ".db", ".lnk"):        # desktop.ini, Thumbs.db...
                ignored.append(e.name)
            continue
        st = e.stat()
        out.append({"path": e.path, "name": e.name, "video": ext in VIDEO, "size": st.st_size, "mtime": st.st_mtime})
    out.sort(key=lambda f: f["mtime"], reverse=True)
    return out, sorted(ignored)
