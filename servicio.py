#!/usr/bin/env python3
"""Servicio de minipantalla: transmite en vivo el archivo elegido.

Lo arranca systemd (unidad de usuario minipantalla.service). Lee el archivo,
el ajuste y la rotación de ~/.config/AppotechLCD/settings.ini (los escribe
`minipantalla poner/rotar`) y cambia de archivo sin cortar la transmisión
cuando ese fichero cambia.

La pantalla queda en modo "Off Lcd":
  * al arrancar se graban sus ajustes como WorkMode=0 (al encenderse espera al
    PC, no reproduce lo guardado) y OffMode=0 (si el PC deja de mandar imagen,
    apaga el panel);
  * al parar el servicio (apagar el PC, cerrar sesión, `systemctl --user stop`)
    se le envía "off mode = apagar", que deja el panel negro al momento.
Al suspender, logind avisa antes (bloqueo "delay" de systemd-inhibit, permitido
a cualquier usuario): se deja de transmitir, se apaga el panel y solo entonces se
suelta el bloqueo. Al despertar se vuelve a transmitir.
Si la pantalla se desconecta, reintenta cada pocos segundos.
"""
import os
import queue
import signal
import sys
import threading
import time

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(HERE, "vendor"))

import core  # noqa: E402
from lcdproto import Lcd, LcdError, MediaError  # noqa: E402

OFF_LCD = 0          # OffMode: 0 = apagar el panel, 1 = reproducir lo guardado
LIVE = 0             # WorkMode al encender: 0 = esperar al PC, 1 = lo guardado
RETRY_S = 3
POLL_S = 0.5

stop = threading.Event()        # parar el servicio
sleeping = threading.Event()    # el PC está suspendiéndose / suspendido
halt = threading.Event()        # cortar la transmisión en curso (stop o sleeping)
in_session = threading.Event()


class SleepGuard:
    """Bloqueo 'delay' de logind: el PC espera a que apaguemos el panel antes de dormir."""

    def __init__(self):
        self.fd = None
        self.lock = threading.Lock()
        self.manager = None

    def start(self):
        try:
            import dbus
            from dbus.mainloop.glib import DBusGMainLoop
            from gi.repository import GLib
            DBusGMainLoop(set_as_default=True)
            bus = dbus.SystemBus()
            obj = bus.get_object("org.freedesktop.login1", "/org/freedesktop/login1")
            self.manager = dbus.Interface(obj, "org.freedesktop.login1.Manager")
            bus.add_signal_receiver(self.on_prepare, "PrepareForSleep", "org.freedesktop.login1.Manager",
                                    "org.freedesktop.login1", "/org/freedesktop/login1")
            self.take()
            threading.Thread(target=GLib.MainLoop().run, daemon=True).start()
        except Exception as e:                 # noqa: BLE001 - sin D-Bus el resto sigue funcionando
            log("aviso: no se podrá apagar la pantalla al suspender (%r)" % e)

    def take(self):
        with self.lock:
            if self.fd is None and self.manager is not None:
                try:
                    self.fd = self.manager.Inhibit("sleep", "minipantalla", "Apagar la mini pantalla",
                                                   "delay").take()
                except Exception as e:         # noqa: BLE001
                    log("aviso: no se pudo pedir el bloqueo de suspensión (%r)" % e)

    def release(self):
        with self.lock:
            if self.fd is not None:
                os.close(self.fd)
                self.fd = None

    def on_prepare(self, going):
        if going:
            log("suspendiendo: apago la pantalla")
            sleeping.set()
            halt.set()
            if not in_session.is_set():        # no se estaba transmitiendo: nada que esperar
                self.release()
        else:
            log("despertando")
            sleeping.clear()
            self.take()
            if not stop.is_set():
                halt.clear()


guard = SleepGuard()


def log(msg):
    print(msg, flush=True)               # va al journal: journalctl --user -u minipantalla


def cfg_mtime():
    try:
        return os.stat(core.config_path()).st_mtime_ns
    except OSError:
        return None


def wanted(cfg):
    """(archivo, ajuste, rotación) que hay que transmitir, o None si no hay archivo válido."""
    path = cfg.get("ResPath") or ""
    if not os.path.isfile(path):
        return None
    return path, cfg.get("Fit") or "cover", cfg["LcdDir"] & 3


def load():
    cfg = core.load_cfg()
    cfg["OffMode"] = OFF_LCD            # lo usa do_play al terminar (exit_off_mode)
    return cfg


def watch(cfg, cmds, current, done):
    """Hilo: si cambia settings.ini, pide a do_play que cambie de archivo/rotación."""
    seen = cfg_mtime()
    while not halt.is_set() and not done.is_set():
        time.sleep(POLL_S)
        m = cfg_mtime()
        if m == seen:
            continue
        seen = m
        new = load()
        w = wanted(new)
        if w is None or w == current[0]:
            continue
        cfg["LcdDir"] = w[2]               # do_play lee la rotación de este mismo dict
        current[0] = w
        log("cambio a %s (rotación %d°)" % (os.path.basename(w[0]), w[2] * 90))
        cmds.put(("media", w[0], w[1], None))


def session():
    """Una conexión: transmite hasta que se pide parar o falla el USB."""
    cfg = load()
    w = wanted(cfg)
    if w is None:
        return "sin archivo"
    with Lcd() as lcd:
        lcd.write_settings(LIVE, OFF_LCD, 0)   # la rotación va en el contenido; el panel siempre a 0
        cmds, current, done = queue.Queue(), [w], threading.Event()
        threading.Thread(target=watch, args=(cfg, cmds, current, done), daemon=True).start()
        log("transmitiendo %s" % os.path.basename(w[0]))
        try:
            core.do_play(w[0], cfg, halt, loop=True, fps=cfg.get("Fps") or 15, fit=w[1], lcd=lcd, cmds=cmds,
                         exit_mode=True, on_error=lambda m: log("aviso: " + m))
        finally:
            done.set()
    return None


def wait_change(seconds):
    """Espera `seconds` o hasta que cambie settings.ini (p. ej. se eligió otro archivo)."""
    m = cfg_mtime()
    end = time.time() + seconds
    while not halt.is_set() and time.time() < end:
        if cfg_mtime() != m:
            return
        time.sleep(POLL_S)


def main():
    def quit_(*_):
        stop.set()
        halt.set()
    signal.signal(signal.SIGTERM, quit_)
    signal.signal(signal.SIGINT, quit_)
    guard.start()
    last = None
    while not stop.is_set():
        if sleeping.is_set():                  # panel ya apagado: dejar dormir al PC y esperar
            guard.release()
            while sleeping.is_set() and not stop.is_set():
                time.sleep(POLL_S)
            last = None
            continue
        try:
            in_session.set()
            try:
                why = session()
            finally:
                in_session.clear()
            if sleeping.is_set():
                continue
            if why:
                if why != last:
                    log("en espera: " + why)
                last = why
                wait_change(3600)
                continue
        except MediaError as e:                # archivo que no se puede reproducir: esperar a otro
            log("no se puede reproducir: %s" % e)
            last = None
            wait_change(3600)
            continue
        except LcdError as e:                  # desconectada, suspendida o USB ocupado
            msg = str(e).split(".")[0]
            if msg != last:
                log("pantalla no disponible: %s" % msg)
            last = msg
        except Exception as e:                 # noqa: BLE001 - que el servicio no muera por un fallo raro
            log("error: %r" % e)
            last = None
        wait_change(RETRY_S)
    log("parado: pantalla apagada")
    return 0


if __name__ == "__main__":
    sys.exit(main())
