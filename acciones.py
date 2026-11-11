#!/usr/bin/env python3
"""Acciones de minipantalla que completan el CLI original (vendor/cli.py).

    acciones.py elegir <archivo> [--fit cover|contain|stretch]   (lo transmite el servicio)
    acciones.py rotar <0|1|2|3>                                   (idem)
    acciones.py guardar <archivo> [--fit ...] [--colores N] [--avi]
    acciones.py mostrar

`elegir` y `rotar` solo cambian settings.ini: el servicio (servicio.py) lo
detecta y transmite en vivo. `guardar` escribe en la memoria de la pantalla.

Diferencias con `cli.py save`:
  * GIFs y videos se guardan como GIF de 480x480 optimizado para el chip
    (paleta reducida, solo la zona que cambia en cada fotograma). Con --avi se
    prueba AVI MJPEG escrito a mano en formato AVI 1.0 mínimo (el AVI de ffmpeg,
    con índice OpenDML y JUNK, la pantalla no lo reprodujo).
  * La rotación se aplica al contenido antes de guardarlo: la pantalla ignora
    su ajuste de rotación para lo que tiene en memoria. Al dispositivo siempre
    se le deja la rotación en 0 para no rotar dos veces.
  * Al terminar envía "off mode = mostrar lo guardado" (CD 04 01), que es lo
    que hace el programa del fabricante al cerrarse. Sin eso la pantalla se
    queda esperando imágenes del PC y no reproduce lo que se acaba de guardar.
"""
import argparse
import io
import os
import shutil
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(HERE, "vendor"))

from PIL import Image, ImageSequence  # noqa: E402

import core  # noqa: E402
import media  # noqa: E402
from lcdproto import MAX_RES, Lcd, LcdError, MediaError  # noqa: E402

SHOW_SAVED = 1
BUDGET = int(MAX_RES * 0.97)
STILL = {".png", ".bmp", ".jpg", ".jpeg"}


def say(msg):
    print("\r  " + msg, end="", flush=True)


def rotated(img, rot):
    return img.rotate(-90 * (rot & 3), expand=True) if rot & 3 else img


def gif_fps(path):
    with Image.open(path) as im:
        d = [fr.info.get("duration", 100) or 100 for fr in ImageSequence.Iterator(im)]
    return max(5, min(25, round(1000 / (sum(d) / len(d)))))


def still_payload(path, w, h, fit, rot):
    with Image.open(path) as im:
        img = rotated(media.fit_image(im, w, h, fit), rot)
    return media.header(1, w * h * 2) + media.rgb565_be(img)


def avi_mjpeg(jpegs, w, h, fps):
    """AVI 1.0 mínimo: hdrl (avih + strl con strh/strf), movi con trozos '00dc'
    e idx1. Sin índice OpenDML, sin JUNK ni metadatos: lo que suelen esperar
    los reproductores de microcontrolador."""
    def chunk(fourcc, data):
        return fourcc + struct.pack("<I", len(data)) + data + (b"\0" if len(data) % 2 else b"")

    def lst(kind, data):
        return b"LIST" + struct.pack("<I", len(data) + 4) + kind + data

    n, biggest = len(jpegs), max(len(j) for j in jpegs)
    avih = struct.pack("<14I", round(1000000 / fps), biggest * fps, 0, 0x10, n, 0, 1, biggest,
                       w, h, 0, 0, 0, 0)
    strh = struct.pack("<4s4sIHHIIIIIIIIhhhh", b"vids", b"MJPG", 0, 0, 0, 0, 1, fps, 0, n,
                       biggest, 0xFFFFFFFF, 0, 0, 0, w, h)
    strf = struct.pack("<IiiHH4sIiiII", 40, w, h, 1, 24, b"MJPG", w * h * 3, 0, 0, 0, 0)
    hdrl = lst(b"hdrl", chunk(b"avih", avih) + lst(b"strl", chunk(b"strh", strh) + chunk(b"strf", strf)))
    movi_body, idx, off = b"", b"", 4
    for j in jpegs:
        c = chunk(b"00dc", j)
        idx += struct.pack("<4sIII", b"00dc", 0x10, off, len(j))
        movi_body += c
        off += len(c)
    body = b"AVI " + hdrl + lst(b"movi", movi_body) + chunk(b"idx1", idx)
    return b"RIFF" + struct.pack("<I", len(body)) + body


def jpeg_baseline(img, quality):
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=quality, subsampling=2, optimize=False, progressive=False)
    return buf.getvalue()


def timeline(frames, durs, fps):
    """Remuestrea fotogramas de duración variable (GIF) a una tasa fija."""
    total = sum(durs)
    out, t, i, acc = [], 0.0, 0, durs[0]
    step = 1000.0 / fps
    while t < total:
        while t >= acc and i < len(frames) - 1:
            i += 1
            acc += durs[i]
        out.append(frames[i])
        t += step
    return out


def source_frames(path, w, h, fit, rot, fps):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".gif":
        with Image.open(path) as im:
            frames, durs = [], []
            for fr in ImageSequence.Iterator(im):
                frames.append(rotated(media.fit_image(fr.convert("RGBA"), w, h, fit), rot))
                durs.append(fr.info.get("duration", 100) or 100)
        return timeline(frames, durs, fps)
    frames = []
    for jpg, _ in media.frames(path, w, h, rot, fit, fps):     # video vía ffmpeg (máx. 20 s)
        frames.append(Image.open(io.BytesIO(jpg)).convert("RGB"))
        if len(frames) >= fps * 20:
            break
    return frames


def avi_payload(path, w, h, fit, rot, fps):
    """AVI MJPEG con la mejor calidad JPEG que cabe en la memoria."""
    say("convirtiendo...")
    frames = source_frames(path, w, h, fit, rot, fps)
    if not frames:
        raise MediaError("No se pudo leer ningún fotograma")
    cache = {}

    def build_at(q):
        if q not in cache:
            say("convirtiendo... calidad %d" % q)
            cache[q] = avi_mjpeg([jpeg_baseline(f, q) for f in frames], w, h, fps)
        return cache[q]

    qualities = (90, 85, 80, 75, 70, 60, 50, 40, 30, 20)
    if len(build_at(qualities[-1])) > BUDGET:
        raise MediaError("No cabe en la memoria de la pantalla (3.7 MB): usa un clip más corto")
    lo, hi = 0, len(qualities) - 1
    while lo < hi:
        mid = (lo + hi) // 2
        if len(build_at(qualities[mid])) <= BUDGET:
            hi = mid
        else:
            lo = mid + 1
    data = build_at(qualities[lo])
    return media.header(4, len(data)) + data


def _gif_frame_data(img):
    """Datos LZW de un fotograma (bloque de imagen sin cabeceras), codificado por Pillow."""
    buf = io.BytesIO()
    img.save(buf, "GIF", optimize=False, interlace=False)
    d = buf.getvalue()
    p = 13 + (3 * (2 << (d[10] & 7)) if d[10] & 0x80 else 0)
    while d[p] == 0x21:                                    # saltar extensiones
        p += 2
        while d[p]:
            p += d[p] + 1
        p += 1
    assert d[p] == 0x2C and not d[p + 9] & 0x80, "fotograma inesperado"
    return d[p + 10:d.rindex(b"\x3b")]                     # código LZW + subbloques


def simple_gif(frames, durs, palette):
    """GIF89a lo más simple posible para el chip: una sola paleta global, sin
    paletas locales, sin transparencia, sin entrelazado y fotogramas completos.
    (Pillow mete paletas locales y transparencia desde el 2º fotograma y la
    pantalla entonces se queda en el primero.)"""
    w, h = frames[0].size
    bits = max(1, (len(palette) // 3 - 1).bit_length())
    pal = bytes(palette) + b"\0" * (3 * (1 << bits) - len(palette))
    out = [b"GIF89a", struct.pack("<HHBBB", w, h, 0x80 | 0x70 | (bits - 1), 0, 0), pal,
           b"\x21\xff\x0bNETSCAPE2.0\x03\x01\0\0\0"]
    for f, ms in zip(frames, durs):
        out.append(b"\x21\xf9\x04" + struct.pack("<BHBB", 1 << 2, max(2, round(ms / 10)), 0, 0))
        out.append(b"\x2c" + struct.pack("<HHHHB", 0, 0, w, h, 0))
        out.append(_gif_frame_data(f))
    out.append(b"\x3b")
    return b"".join(out)


def gif_payload(path, w, h, fit, rot, colors=128):
    """GIF al tamaño del panel con paleta común reducida (aligera la
    decodificación en el chip). Si no cabe, salta fotogramas."""
    with Image.open(path) as im:
        frames, durs = [], []
        for fr in ImageSequence.Iterator(im):
            frames.append(rotated(media.fit_image(fr.convert("RGBA"), w, h, fit), rot).convert("RGB"))
            durs.append(fr.info.get("duration", 100) or 100)
    sample = frames[::max(1, len(frames) // 8)][:8]        # paleta común con colores de todo el GIF
    montage = Image.new("RGB", (w, h * len(sample)))
    for i, f in enumerate(sample):
        montage.paste(f, (0, h * i))
    pal = montage.quantize(colors, method=Image.Quantize.MEDIANCUT)
    q = [f.quantize(palette=pal, dither=Image.Dither.NONE) for f in frames]
    palette = pal.getpalette()[:3 * colors]
    step = 1
    while True:
        sel = q[::step]
        d = [sum(durs[i:i + step]) for i in range(0, len(durs), step)]
        data = simple_gif(sel, d, palette)
        if len(data) <= MAX_RES or len(sel) <= 2:
            break
        step += 1
    if len(data) > MAX_RES:
        raise MediaError("El GIF no cabe en la memoria de la pantalla (3.7 MB)")
    return media.header(2, len(data)) + data


def video_to_gif(path, w, h, fit, rot):
    """Convierte un video a GIF temporal con ffmpeg y lo pasa por gif_payload."""
    ff = media._ffmpeg()
    tmp = tempfile.mkdtemp(prefix="minipantalla-")
    out = os.path.join(tmp, "o.gif")
    try:
        for fps in (12, 10, 8, 6):
            say("convirtiendo...")
            vf = media._video_filter(w, h, fit, fps, rot)
            r = subprocess.run([ff, "-y", "-v", "error", "-i", path, "-an", "-sn", "-t", "20",
                                      "-vf", vf + ",split[a][b];[a]palettegen=max_colors=128[p];[b][p]paletteuse=dither=none",
                                      out], stdin=subprocess.DEVNULL, capture_output=True)
            if r.returncode:
                raise MediaError("ffmpeg falló: " + r.stderr.decode("utf-8", "replace")[-200:])
            if os.path.getsize(out) <= MAX_RES:
                with open(out, "rb") as fh:
                    data = fh.read()
                return media.header(2, len(data)) + data
        raise MediaError("El video no cabe en la memoria de la pantalla (3.7 MB): usa un clip más corto")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def build(path, w, h, fit, rot, as_avi=False, colors=128):
    ext = os.path.splitext(path)[1].lower()
    if ext in STILL:
        return still_payload(path, w, h, fit, rot)
    if ext == ".gif":
        with Image.open(path) as im:
            animated = getattr(im, "n_frames", 1) > 1
        if not animated:
            return still_payload(path, w, h, fit, rot)
        if as_avi:
            return avi_payload(path, w, h, fit, rot, gif_fps(path))
        return gif_payload(path, w, h, fit, rot, colors)
    if as_avi:
        return avi_payload(path, w, h, fit, rot, 15)
    return video_to_gif(path, w, h, fit, rot)


def progress(done, total):
    say("saving... %3d%%" % (100 * done // total))


def poner(path, fit, as_avi=False, colors=128):
    if not os.path.isfile(path):
        raise MediaError("No existe el archivo: %s" % path)
    cfg = core.load_cfg()
    rot = cfg["LcdDir"] & 3
    with Lcd() as lcd:
        w, h = lcd.get_info()
        blob = build(path, w, h, fit, rot, as_avi, colors)
        lcd.flash_write(blob, progress)
        lcd.write_settings(1, SHOW_SAVED, 0)
        lcd.set_off_mode(SHOW_SAVED)
    print("\n  saved %.2f MB" % (len(blob) / 1048576))
    cfg.update(ResPath=os.path.abspath(path), WorkMode=1, OffMode=SHOW_SAVED, Fit=fit, Colores=colors)
    core.save_cfg(cfg)


def elegir(path, fit):
    """Deja el archivo como el que transmite el servicio (sin tocar el USB)."""
    if not os.path.isfile(path):
        raise MediaError("No existe el archivo: %s" % path)
    if os.path.splitext(path)[1].lower() not in media_exts():
        raise MediaError("Formato no soportado: %s" % os.path.basename(path))
    cfg = core.load_cfg()
    cfg.update(ResPath=os.path.abspath(path), Fit=fit, OffMode=0, WorkMode=0)
    core.save_cfg(cfg)


def media_exts():
    return {"." + e.split(".")[-1] for e in core.MEDIA_TYPES.split()}


def rotar(r):
    """Cambia la rotación; el servicio la aplica al momento."""
    cfg = core.load_cfg()
    cfg["LcdDir"] = r & 3
    core.save_cfg(cfg)


def mostrar():
    cfg = core.load_cfg()
    with Lcd() as lcd:
        lcd.set_off_mode(SHOW_SAVED)
    cfg["OffMode"] = SHOW_SAVED
    core.save_cfg(cfg)


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    e = sp.add_parser("elegir")
    e.add_argument("file")
    e.add_argument("--fit", choices=["cover", "contain", "stretch"], default="cover")
    p = sp.add_parser("guardar")
    p.add_argument("file")
    p.add_argument("--fit", choices=["cover", "contain", "stretch"], default="cover")
    p.add_argument("--colores", type=int, choices=[2, 4, 8, 16, 32, 64, 128, 256], default=128,
                   help="colores del GIF; menos = más liviano para el chip (más fluido)")
    p.add_argument("--avi", action="store_true", help="experimental: guardar como AVI MJPEG")
    r = sp.add_parser("rotar")
    r.add_argument("dir", type=int, choices=[0, 1, 2, 3])
    sp.add_parser("mostrar")
    a = ap.parse_args()
    try:
        if a.cmd == "elegir":
            elegir(a.file, a.fit)
        elif a.cmd == "guardar":
            poner(a.file, a.fit, a.avi, a.colores)
        elif a.cmd == "rotar":
            rotar(a.dir)
        else:
            mostrar()
    except LcdError as e:
        print("error:", e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
