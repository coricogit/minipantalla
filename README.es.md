# minipantalla

Soporte en Linux para la **mini pantalla USB redonda de 2.1"** que se vende como
QTKeJi / "SmatCool" / AX206 (480×480). El fabricante solo trae
programa para Windows. Este repo incluye:

- un CLI, `minipantalla`, para poner GIFs, imágenes y videos en la pantalla y girarlos
- un servicio de usuario que transmite en vivo, a todo color y fluido. La pantalla
  se apaga cuando apagas o suspendes el PC.
- un plugin para la barra de [Omarchy](https://omarchy.org/), **Mini Screen**, para elegir el archivo y girarlo con un clic

## ¿Es compatible mi pantalla?

Conéctala y ejecuta:

```bash
lsusb | grep 2a55:9990
```

Si sale una línea, es el mismo chip con el que se probó. Otras pantallas AX206
(otro tamaño u otro ID USB) **no están probadas** y seguramente necesiten cambios.

## Instalación

Necesitas Arch Linux. El plugin de la barra necesita además Omarchy; sin él, el CLI y el servicio funcionan igual.

```bash
git clone https://github.com/coricogit/minipantalla.git ~/minipantalla
cd ~/minipantalla
./install.sh
```

El instalador pide `sudo` para instalar los paquetes que falten
(`python-pyusb python-pillow ffmpeg python-dbus python-gobject`) y la regla udev
que deja a tu usuario usar la pantalla. Además:

- enlaza `~/.local/bin/minipantalla` a esta carpeta (no la muevas después de clonarla)
- crea `~/Pictures/minipantalla` para tus archivos (se cambia con `MINIPANTALLA_DIR`)
- copia el plugin a `~/.config/omarchy/plugins/corico.minipantalla` y lo activa
- instala y arranca `minipantalla.service` (unidad de usuario de systemd)

Para actualizar: `git pull && ./install.sh`. Para quitarlo: `./install.sh --uninstall`.

## Uso

| Comando | Qué hace |
|---|---|
| `minipantalla poner <archivo>` | Muestra un GIF, imagen o video (lo transmite el servicio) |
| `minipantalla rotar 0\|90\|180\|270` | Gira la imagen |
| `minipantalla estado` | Estado del servicio |
| `minipantalla iniciar` / `parar` | Arranca o para el servicio (al parar, la pantalla se apaga) |
| `minipantalla guardar <archivo>` | Graba el archivo en la memoria de la pantalla para que se vea sin PC |
| `minipantalla transmitir <archivo>` | Transmite a mano en la terminal (con el servicio parado) |
| `minipantalla info` | Muestra la resolución (prueba la conexión) |

`--fit cover|contain|stretch` elige cómo encajar un archivo que no sea de 480×480.

## Límites conocidos

- **Lo grabado con `guardar` se traba con GIFs pesados**, porque el chip los decodifica por
  software. Los GIFs sencillos (≈15–20 KB por fotograma) van bien; los de tipo foto, no.
  `--colores N` reduce la paleta para ayudar. La transmisión en vivo (lo normal) no tiene este límite.
- **El AVI no se reproduce** desde la memoria de la pantalla. No se sabe qué formato
  exacto espera el firmware, así que `--avi` es experimental.
- Mientras el servicio está activo, ocupa el USB: `info` y `transmitir` te piden pararlo antes.

## Créditos y licencia

El código del protocolo USB en [`vendor/`](vendor/) es una copia revisada de
[caioklein/AX206-LCD-Screen](https://github.com/caioklein/AX206-LCD-Screen)
(el commit exacto está en `vendor/UPSTREAM`). Gracias a su autor por
descifrar la pantalla.

Por eso todo el proyecto se publica bajo la [GNU GPL v3](LICENSE).
