"""Mini pantalla para Windows 11: transmite en vivo a la pantalla USB AX206 desde la bandeja.

    pythonw minipantalla.pyw        (o doble clic en este archivo)

Hace lo mismo que minipantalla.service en Linux, reutilizando servicio.py:
  * transmite el archivo elegido en %APPDATA%\\AppotechLCD\\settings.ini y cambia de
    archivo o rotación sin cortar cuando ese archivo cambia;
  * apaga el panel al salir, al cerrar sesión o apagar el PC, y al suspender
    (PowerRegisterSuspendResumeNotification); al despertar vuelve a transmitir;
  * si la pantalla se desconecta, reintenta cada pocos segundos.
El icono de la bandeja abre un panel para elegir archivo y rotación, como el widget
de KDE Plasma / Omarchy.
"""
import ctypes
import hashlib
import json
import os
import subprocess
import sys
import threading
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import common  # noqa: E402  (añade vendor/ y la raíz del repo al path)

common.ensure_data()

from PySide6.QtCore import QLockFile, QObject, Qt, QTimer, QUrl, Property, Signal, Slot  # noqa: E402
from PySide6.QtGui import QAction, QColor, QCursor, QDesktopServices, QGuiApplication, QIcon, QPainter, QPen, QPixmap  # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine  # noqa: E402
from PySide6.QtQuick import QQuickWindow, QSGRendererInterface  # noqa: E402
from PySide6.QtQuickControls2 import QQuickStyle  # noqa: E402
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon  # noqa: E402

import acciones  # noqa: E402
import servicio  # noqa: E402
from lcdproto import LcdError, MediaError  # noqa: E402

LANG = "es" if common.spanish() else "en"
TEXT = {
    "en": {
        "title": "Mini Screen", "open": "Open panel", "pause": "Turn screen off", "resume": "Turn screen on",
        "folder": "Open folder", "autostart": "Start with Windows", "quit": "Quit",
        "streaming": "Streaming {}", "paused": "Screen off", "nofile": "Connected · choose a file",
        "connecting": "Connecting…", "disconnected": "Not connected", "sleeping": "Suspended",
        "badfile": "Can't play {}", "already": "Mini Screen is already running (look in the tray).",
    },
    "es": {
        "title": "Mini pantalla", "open": "Abrir panel", "pause": "Apagar pantalla", "resume": "Encender pantalla",
        "folder": "Abrir carpeta", "autostart": "Iniciar con Windows", "quit": "Salir",
        "streaming": "Transmitiendo {}", "paused": "Pantalla apagada", "nofile": "Conectada · elige un archivo",
        "connecting": "Conectando…", "disconnected": "No conectada", "sleeping": "Suspendido",
        "badfile": "No se puede reproducir {}", "already": "Mini pantalla ya está abierta (búscala en la bandeja).",
    },
}

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_NAME = "Minipantalla"
MY_START = common.process_started(os.getpid())   # junto al PID, identifica a esta copia sin ambigüedad


def tr(key):
    return TEXT[LANG].get(key) or TEXT["en"][key]


def log(msg):
    """pythonw no tiene consola: todo va a %LOCALAPPDATA%\\minipantalla\\minipantalla.log."""
    try:
        if os.path.exists(common.LOG) and os.path.getsize(common.LOG) > 512 * 1024:
            os.replace(common.LOG, common.LOG + ".1")
        with open(common.LOG, "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + msg + "\n")
    except OSError:
        pass
    if sys.stdout:
        print(msg, flush=True)


servicio.log = log     # session() y watch() de servicio.py escriben aquí


# ---------------------------------------------------------------------------
# Transmisión (el bucle de servicio.main, sin systemd ni D-Bus)
# ---------------------------------------------------------------------------

class Streamer:
    def __init__(self, on_change):
        self.on_change = on_change
        self.quit = threading.Event()
        self.state, self.msg = "connecting", ""
        self.thread = threading.Thread(target=self.run, name="transmision", daemon=True)

    def set(self, state, msg=""):
        if (state, msg) != (self.state, self.msg):
            self.state, self.msg = state, msg
            self.on_change()

    def hook_log(self, msg):
        log(msg)
        if msg.startswith(("transmitiendo", "cambio a")):
            self.set("streaming")
        elif msg.startswith("aviso: "):
            self.set(self.state, msg[7:])

    def run(self):
        servicio.log = self.hook_log
        last = None
        while not self.quit.is_set():
            if common.paused() or servicio.sleeping.is_set():
                servicio.halt.set()
                self.set("sleeping" if servicio.sleeping.is_set() else "paused")
                time.sleep(0.3)
                last = None
                continue
            servicio.halt.clear()
            try:
                self.set("connecting")
                servicio.in_session.set()
                try:
                    why = servicio.session()
                finally:
                    servicio.in_session.clear()
                if servicio.halt.is_set():
                    continue
                if why:                              # "sin archivo"
                    self.set("nofile")
                    servicio.wait_change(3600)
                    continue
            except MediaError as e:
                log("no se puede reproducir: %s" % e)
                self.set("badfile", str(e))
                servicio.wait_change(3600)
                continue
            except LcdError as e:
                msg = str(e).split(".")[0]
                if msg != last:
                    log("pantalla no disponible: %s" % msg)
                last = msg
                self.set("disconnected", msg)
            except Exception as e:  # noqa: BLE001 - que la app no se quede sin transmitir por un fallo raro
                log("error: %s" % traceback.format_exc())
                self.set("disconnected", repr(e))
                last = None
            servicio.wait_change(servicio.RETRY_S)
        log("parado: pantalla apagada")

    def start(self):
        self.thread.start()

    def stop(self, timeout=6):
        """Corta la transmisión; do_play manda 'apagar panel' antes de soltar el USB."""
        self.quit.set()
        servicio.halt.set()
        self.thread.join(timeout)

    def wait_released(self, timeout):
        end = time.time() + timeout
        while servicio.in_session.is_set() and time.time() < end:
            time.sleep(0.05)


# ---------------------------------------------------------------------------
# Suspensión: Windows avisa antes de dormir; se apaga el panel y luego se deja dormir
# ---------------------------------------------------------------------------

PBT_APMSUSPEND, PBT_APMRESUMESUSPEND, PBT_APMRESUMEAUTOMATIC = 0x4, 0x7, 0x12
_PowerCallback = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p, ctypes.c_ulong, ctypes.c_void_p)


class _SubscribeParams(ctypes.Structure):
    _fields_ = [("Callback", _PowerCallback), ("Context", ctypes.c_void_p)]


class SleepGuard:
    def __init__(self, streamer):
        self.streamer = streamer
        self.cb = _PowerCallback(self.on_power)       # hay que guardar la referencia
        self.params = _SubscribeParams(self.cb, None)
        self.handle = ctypes.c_void_p()

    def start(self):
        try:
            r = ctypes.windll.powrprof.PowerRegisterSuspendResumeNotification(
                2, ctypes.byref(self.params), ctypes.byref(self.handle))    # DEVICE_NOTIFY_CALLBACK
            if r:
                log("aviso: no se podrá apagar la pantalla al suspender (error %d)" % r)
        except (AttributeError, OSError) as e:
            log("aviso: no se podrá apagar la pantalla al suspender (%r)" % e)

    def on_power(self, _ctx, kind, _setting):
        try:
            if kind == PBT_APMSUSPEND:
                log("suspendiendo: apago la pantalla")
                servicio.sleeping.set()
                servicio.halt.set()
                self.streamer.wait_released(2.0)       # Windows da unos 2 s a las apps
            elif kind in (PBT_APMRESUMESUSPEND, PBT_APMRESUMEAUTOMATIC) and servicio.sleeping.is_set():
                log("despertando")
                servicio.sleeping.clear()
        except Exception:  # noqa: BLE001 - nunca lanzar dentro de un callback de Windows
            pass
        return 0


# ---------------------------------------------------------------------------
# Lo que ve el panel (QML)
# ---------------------------------------------------------------------------

class Backend(QObject):
    stateChanged = Signal()
    _changed = Signal()               # desde otros hilos
    _thumbReady = Signal()

    def __init__(self):
        super().__init__()
        self._state = "{}"
        self._busy = ""
        self.connected = False
        self.streamer = Streamer(self._changed.emit)
        self._changed.connect(self.refresh)
        self._thumbReady.connect(self.refresh)
        self._thumbs_pending = set()
        self._usb_checked = 0.0

    # ----- estado -----
    @Slot()
    def refresh(self):
        s = self.streamer
        now = time.time()
        if s.state in ("streaming", "nofile", "badfile"):
            self.connected = True
        elif now - self._usb_checked > 2.5 or s.state == "disconnected":
            self.connected = common.usb_present()
            self._usb_checked = now
        cfg = servicio.core.load_cfg()
        folder = common.media_folder()
        files, ignored = common.media_files(folder)
        for f in files:
            f["thumb"] = self.thumb_url(f)
        current = cfg.get("ResPath") or ""
        st = {
            "lang": LANG,
            "state": s.state,
            "msg": s.msg,
            "connected": self.connected,
            "paused": common.paused(),
            "current": current,
            "currentName": os.path.basename(current),
            "rotation": cfg["LcdDir"] & 3,
            "fit": cfg.get("Fit") or "cover",
            "folder": folder,
            "files": files,
            "ignored": ignored,
            "busy": self._busy,
        }
        text = json.dumps(st, ensure_ascii=False)
        if text != self._state:
            self._state = text
            self.stateChanged.emit()
        common.write_status({"pid": os.getpid(), "started": MY_START, "state": s.state, "msg": s.msg, "connected": self.connected,
                             "paused": st["paused"], "file": current, "rotation": st["rotation"] * 90,
                             "folder": folder, "time": now})

    def _get_state(self):
        return self._state

    stateText = Property(str, _get_state, notify=stateChanged)

    # ----- miniaturas: imágenes tal cual, videos con un fotograma de ffmpeg en caché -----
    def thumb_url(self, f):
        if not f["video"]:
            return QUrl.fromLocalFile(f["path"]).toString()
        key = hashlib.sha1(("%s|%s|%s" % (f["path"], f["size"], f["mtime"])).encode("utf-8")).hexdigest()[:16]
        png = os.path.join(common.THUMBS, key + ".png")
        if os.path.exists(png):
            return QUrl.fromLocalFile(png).toString()
        if key not in self._thumbs_pending:
            self._thumbs_pending.add(key)
            threading.Thread(target=self._make_thumb, args=(f["path"], png), daemon=True).start()
        return ""

    def _make_thumb(self, path, png):
        try:
            import media
            img = media.thumbnail(path, 192)
            if img is not None:
                os.makedirs(common.THUMBS, exist_ok=True)
                img.convert("RGB").save(png)
        except Exception:  # noqa: BLE001
            pass
        self._thumbReady.emit()

    # ----- acciones desde el panel -----
    @Slot(str)
    def choose(self, path):
        try:
            acciones.elegir(path, servicio.core.load_cfg().get("Fit") or "cover")
            common.set_paused(False)                     # elegir un archivo enciende la pantalla
            self.streamer.set(self.streamer.state, "")
        except LcdError as e:
            self.streamer.set(self.streamer.state, str(e))
        self.refresh()

    @Slot(int)
    def rotate(self, r):
        acciones.rotar(r)
        self.refresh()

    @Slot(str)
    def setFit(self, fit):
        cfg = servicio.core.load_cfg()
        path = cfg.get("ResPath") or ""
        if os.path.isfile(path):
            acciones.elegir(path, fit)
        else:
            cfg["Fit"] = fit
            servicio.core.save_cfg(cfg)
        self.refresh()

    @Slot()
    def togglePause(self):
        on = not common.paused()
        common.set_paused(on)
        if on:
            servicio.halt.set()
        self.refresh()

    @Slot()
    def openFolder(self):
        folder = common.media_folder()
        os.makedirs(folder, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(folder))


# ---------------------------------------------------------------------------
# Icono de la bandeja: una pantallita redonda con un punto de estado
# ---------------------------------------------------------------------------

def tray_pixmap(state, connected, size=32):
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    on = state == "streaming"
    p.setPen(QPen(QColor("#9AA0A6" if not connected else "#E8EAED"), 2.5))
    p.setBrush(QColor("#1F2937" if on else "#111111"))
    p.drawEllipse(3, 3, size - 6, size - 6)
    if on:                                       # "imagen" en la pantalla
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#38BDF8"))
        p.drawEllipse(9, 9, size - 18, size - 18)
    dot = {"streaming": "#22C55E", "nofile": "#F59E0B", "badfile": "#F59E0B",
           "connecting": "#F59E0B"}.get(state, "#EF4444" if not connected else "#9AA0A6")
    p.setPen(QPen(QColor("#111111"), 1.5))
    p.setBrush(QColor(dot))
    p.drawEllipse(size - 13, size - 13, 11, 11)
    p.end()
    return pm


def autostart_enabled():
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.QueryValueEx(k, RUN_NAME)
            return True
    except OSError:
        return False


def set_autostart(on):
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if on:
            exe = sys.executable
            w = os.path.join(os.path.dirname(exe), "pythonw.exe")
            winreg.SetValueEx(k, RUN_NAME, 0, winreg.REG_SZ,
                              '"%s" "%s"' % (w if os.path.exists(w) else exe, os.path.abspath(__file__)))
        else:
            try:
                winreg.DeleteValue(k, RUN_NAME)
            except FileNotFoundError:
                pass


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

class App(QObject):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.backend = Backend()
        self.engine = QQmlApplicationEngine()
        self.engine.rootContext().setContextProperty("backend", self.backend)
        self.engine.load(QUrl.fromLocalFile(os.path.join(HERE, "qml", "Panel.qml")))
        if not self.engine.rootObjects():
            sys.exit("minipantalla: no se pudo cargar Panel.qml")
        self.panel = self.engine.rootObjects()[0]
        # Una ventana nativa (aunque oculta) para que Windows nos avise al cerrar sesión o apagar.
        self.panel.create()
        self._panel_hidden_at = 0.0
        self.panel.visibleChanged.connect(self._on_panel_visible)

        self._build_tray()
        self.backend.stateChanged.connect(self._update_tray)

        self.timer = QTimer(self, interval=10000, timeout=self.backend.refresh)
        self.timer.start()
        self.pause_timer = QTimer(self, interval=400, timeout=self._watch_pause)
        self.pause_timer.start()

        self.guard = SleepGuard(self.backend.streamer)
        self.guard.start()
        app.commitDataRequest.connect(self._session_ending)
        app.aboutToQuit.connect(self.shutdown)

        common.set_paused(False)          # como el servicio: al iniciar sesión, transmite
        self.backend.streamer.start()
        self.backend.refresh()
        self._update_tray()

    def _watch_pause(self):
        # El CLI (minipantalla parar/guardar) crea el archivo "pausa": soltar el USB enseguida.
        if common.paused() and not servicio.halt.is_set():
            servicio.halt.set()
        # minipantalla poner/rotar cambian settings.ini: que estado.json y el panel lo reflejen ya.
        m = servicio.cfg_mtime()
        if m != getattr(self, "_cfg_seen", m):
            self.backend.refresh()
        self._cfg_seen = m

    def _session_ending(self, manager):
        log("cerrando sesión o apagando: apago la pantalla")
        self.shutdown()

    def shutdown(self):
        if not self.backend.streamer.quit.is_set():
            self.backend.streamer.stop()
            try:
                os.remove(common.STATUS)
            except OSError:
                pass

    # ----- panel -----
    def _on_panel_visible(self, visible):
        self.timer.setInterval(2000 if visible else 10000)
        if visible:
            self.backend.refresh()
        else:
            self._panel_hidden_at = time.monotonic()

    def _place_panel(self):
        w, h = self.panel.width(), self.panel.height()
        icon = self.tray.geometry()
        anchor = icon.center() if not icon.isEmpty() else QCursor.pos()
        screen = QGuiApplication.screenAt(anchor) or QGuiApplication.primaryScreen()
        area = screen.availableGeometry()
        m = 8
        x = min(max(anchor.x() - w // 2, area.left() + m), area.right() - w - m)
        y = area.bottom() - h - m if anchor.y() >= area.center().y() else area.top() + m
        if anchor.x() < area.left() or anchor.x() > area.right():
            x = area.left() + m if anchor.x() < area.left() else area.right() - w - m
            y = min(max(anchor.y() - h // 2, area.top() + m), area.bottom() - h - m)
        self.panel.setPosition(x, y)

    def show_panel(self):
        self._place_panel()
        self.panel.show()
        self.panel.raise_()
        self.panel.requestActivate()

    def toggle_panel(self):
        if self.panel.isVisible():
            self.panel.hide()
        elif time.monotonic() - self._panel_hidden_at > 0.3:   # el clic en el icono ya lo cerró
            self.show_panel()

    # ----- bandeja -----
    def _build_tray(self):
        self.tray = QSystemTrayIcon(self)
        menu = self.menu = QMenu()
        a = QAction(tr("open"), menu)
        a.triggered.connect(self.show_panel)
        menu.addAction(a)
        self.pause_action = QAction(tr("pause"), menu)
        self.pause_action.triggered.connect(self.backend.togglePause)
        menu.addAction(self.pause_action)
        a = QAction(tr("folder"), menu)
        a.triggered.connect(self.backend.openFolder)
        menu.addAction(a)
        menu.addSeparator()
        self.auto_action = QAction(tr("autostart"), menu, checkable=True)
        self.auto_action.setChecked(autostart_enabled())
        self.auto_action.toggled.connect(set_autostart)
        menu.addAction(self.auto_action)
        menu.addSeparator()
        a = QAction(tr("quit"), menu)
        a.triggered.connect(self.app.quit)
        menu.addAction(a)
        menu.aboutToShow.connect(lambda: self.auto_action.setChecked(autostart_enabled()))
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray)
        self.tray.setIcon(QIcon(tray_pixmap("connecting", False)))
        self.tray.show()

    def _on_tray(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.toggle_panel()
        elif reason == QSystemTrayIcon.ActivationReason.MiddleClick:
            self.backend.togglePause()

    def _update_tray(self):
        s = self.backend.streamer
        connected = self.backend.connected
        cfg_file = os.path.basename(servicio.core.load_cfg().get("ResPath") or "")
        if s.state == "streaming":
            line = tr("streaming").format(cfg_file)
        elif s.state == "badfile":
            line = tr("badfile").format(cfg_file)
        elif s.state in ("paused", "sleeping", "nofile", "connecting"):
            line = tr(s.state) if connected or s.state == "sleeping" else tr("disconnected")
        else:
            line = tr("disconnected")
        self.tray.setIcon(QIcon(tray_pixmap(s.state, connected)))
        self.tray.setToolTip(tr("title") + "\n" + line)
        self.pause_action.setText(tr("resume") if common.paused() else tr("pause"))


def main():
    common.ensure_data()
    lock = QLockFile(os.path.join(common.DATA, "app.lock"))
    if not lock.tryLock(100):
        log(tr("already"))
        return 0
    QQuickWindow.setGraphicsApi(QSGRendererInterface.GraphicsApi.Software)   # transparencia con cualquier GPU
    QQuickStyle.setStyle("Basic")
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("minipantalla")
    if not QSystemTrayIcon.isSystemTrayAvailable():
        log("aviso: no hay bandeja del sistema")
    _ = App(app)
    code = app.exec()
    lock.unlock()
    return code


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception:
        log("error fatal: %s" % traceback.format_exc())
        raise
