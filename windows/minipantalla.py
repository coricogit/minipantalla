"""minipantalla para Windows: los mismos comandos que el CLI de Linux.

    minipantalla poner <archivo> [--fit cover|contain|stretch]
    minipantalla rotar 0|90|180|270
    minipantalla estado
    minipantalla iniciar | parar
    minipantalla guardar <archivo> [--fit ...] [--colores N] [--avi]
    minipantalla transmitir <archivo> [--fit ...]
    minipantalla info

Lo que en Linux hace minipantalla.service aquí lo hace la app de la bandeja
(minipantalla.pyw): `poner` y `rotar` solo cambian los ajustes y la app los
aplica al momento; `parar` le pide que suelte el USB y apague la pantalla.
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


def utf8():
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass


def gui_python():
    w = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    return w if os.path.exists(w) else sys.executable


def start_app():
    """Abre la app de la bandeja si no está abierta. Devuelve True si ya lo estaba."""
    if common.read_status():
        return True
    flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    subprocess.Popen([gui_python(), APP], cwd=HERE, creationflags=flags, close_fds=True)
    return False


def release_usb():
    """Pide a la app que suelte el USB (apaga la pantalla) y espera a que lo haga."""
    st = common.read_status()
    common.set_paused(True)
    if not st:
        return
    end = time.time() + 10
    while time.time() < end:
        st = common.read_status()
        if not st or st.get("state") in ("paused", "sleeping"):
            time.sleep(0.3)           # el USB tarda un instante en quedar libre
            return
        time.sleep(0.2)
    raise SystemExit("La app no soltó la pantalla. Ciérrala desde la bandeja y vuelve a probar.")


def need_free_usb():
    st = common.read_status()
    if st and not st.get("paused"):
        raise SystemExit("La app de la bandeja está usando la pantalla. Apágala antes con: minipantalla parar")


def acciones(*args):
    """acciones.py en este mismo Python (guardar y mostrar abren el USB)."""
    return subprocess.call([sys.executable, os.path.join(common.ROOT, "acciones.py"), *args])


def estado():
    st = common.read_status()
    if not st:
        print("La app de la bandeja no está abierta (minipantalla iniciar).")
        print("Pantalla:", "conectada" if common.usb_present() else "no conectada")
        return 0
    texto = {"streaming": "transmitiendo", "paused": "pantalla apagada (minipantalla iniciar para encenderla)",
             "nofile": "conectada, sin archivo elegido", "connecting": "conectando",
             "disconnected": "pantalla no conectada", "sleeping": "PC suspendido",
             "badfile": "no se puede reproducir el archivo"}.get(st.get("state"), st.get("state"))
    print("Estado:   ", texto)
    if st.get("msg"):
        print("Aviso:    ", st["msg"])
    print("Archivo:  ", st.get("file") or "(ninguno)")
    print("Rotación: ", "%d°" % st.get("rotation", 0))
    print("Carpeta:  ", st.get("folder"))
    return 0


def main():
    utf8()
    ap = argparse.ArgumentParser(prog="minipantalla",
                                 description="Controla la mini pantalla USB AX206 2.1\" (2a55:9990) desde Windows.")
    sp = ap.add_subparsers(dest="cmd", required=True, metavar="comando")
    fit = dict(choices=["cover", "contain", "stretch"], default="cover", help="recortar, encajar o estirar")
    p = sp.add_parser("poner", help="transmite en vivo ese gif/imagen/video (lo hace la app de la bandeja)")
    p.add_argument("archivo")
    p.add_argument("--fit", **fit)
    p = sp.add_parser("rotar", help="gira la imagen")
    p.add_argument("grados", type=int, choices=[0, 90, 180, 270])
    sp.add_parser("estado", help="muestra qué está haciendo la app")
    sp.add_parser("iniciar", help="abre la app y enciende la pantalla")
    sp.add_parser("parar", help="apaga la pantalla y suelta el USB (la app sigue en la bandeja)")
    p = sp.add_parser("guardar", help="graba el archivo en la memoria de la pantalla (para verlo sin PC)")
    p.add_argument("archivo")
    p.add_argument("--fit", **fit)
    p.add_argument("--colores", type=int, choices=[2, 4, 8, 16, 32, 64, 128, 256], default=128)
    p.add_argument("--avi", action="store_true", help="experimental: guardar como AVI MJPEG")
    p = sp.add_parser("transmitir", help="transmite a mano en esta terminal (Ctrl+C para parar)")
    p.add_argument("archivo")
    p.add_argument("--fit", **fit)
    sp.add_parser("mostrar", help="hace que la pantalla muestre lo que tiene guardado")
    sp.add_parser("info", help="muestra la resolución (prueba la conexión)")
    a = ap.parse_args()

    if a.cmd == "poner":
        r = acciones("elegir", os.path.abspath(a.archivo), "--fit", a.fit)
        if r:
            return r
        common.set_paused(False)
        if not start_app():
            print("Abriendo la app de la bandeja para transmitir.")
        return 0
    if a.cmd == "rotar":
        return acciones("rotar", str(a.grados // 90))
    if a.cmd == "estado":
        return estado()
    if a.cmd == "iniciar":
        common.set_paused(False)
        start_app()
        return 0
    if a.cmd == "parar":
        release_usb()
        print("Pantalla apagada. 'minipantalla iniciar' para volver a transmitir.")
        return 0
    if a.cmd == "guardar":
        if common.read_status() and not common.paused():
            release_usb()
            print("  (transmisión parada; 'minipantalla iniciar' para volver a transmitir)")
        common.set_paused(True)
        return acciones("guardar", os.path.abspath(a.archivo), "--fit", a.fit, "--colores", str(a.colores),
                        *(["--avi"] if a.avi else []))
    if a.cmd == "transmitir":
        need_free_usb()
        common.set_paused(True)
        try:
            return subprocess.call([sys.executable, os.path.join(common.ROOT, "vendor", "cli.py"), "preview",
                                    os.path.abspath(a.archivo), "--loop", "--fit", a.fit])
        except KeyboardInterrupt:
            return 0
    if a.cmd == "mostrar":
        need_free_usb()
        return acciones("mostrar")
    if a.cmd == "info":
        need_free_usb()
        return subprocess.call([sys.executable, os.path.join(common.ROOT, "vendor", "cli.py"), "info"])
    return 1


if __name__ == "__main__":
    sys.exit(main())
