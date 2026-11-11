#!/bin/bash
# Installs minipantalla on Omarchy: dependencies, USB permissions, the CLI,
# the live-streaming service and the bar plugin.
#
#   ./install.sh              install (or update) everything
#   ./install.sh --uninstall  remove it again (your pictures are kept)

set -euo pipefail

DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
PLUGIN_ID=corico.minipantalla
PLUGINS_DIR="$HOME/.config/omarchy/plugins"
RULE=/etc/udev/rules.d/70-minipantalla.rules
BIN="$HOME/.local/bin/minipantalla"
UNIT=minipantalla.service
PICS="${MINIPANTALLA_DIR:-$HOME/Pictures/minipantalla}"
DEPS=(python-pyusb python-pillow ffmpeg python-dbus python-gobject)

step() { printf '\n\e[1m==> %s\e[0m\n' "$*"; }

if [[ ${1:-} == "--uninstall" ]]; then
  step "Stopping the service"
  systemctl --user disable --now "$UNIT" 2>/dev/null || true
  rm -f "$HOME/.config/systemd/user/$UNIT"
  systemctl --user daemon-reload
  step "Removing the bar plugin"
  command -v omarchy >/dev/null && omarchy plugin disable "$PLUGIN_ID" 2>/dev/null || true
  rm -rf "${PLUGINS_DIR:?}/$PLUGIN_ID"
  step "Removing the CLI and the USB rule"
  [[ -L $BIN ]] && rm -f "$BIN"
  if [[ -f $RULE ]]; then
    sudo rm -f "$RULE"
    sudo udevadm control --reload-rules
  fi
  echo "Done. $PICS was left untouched."
  exit 0
fi

step "Checking dependencies"
missing=()
for p in "${DEPS[@]}"; do pacman -Q "$p" &>/dev/null || missing+=("$p"); done
if (( ${#missing[@]} )); then
  echo "Installing: ${missing[*]}"
  sudo pacman -S --needed "${missing[@]}"
else
  echo "All present."
fi

step "USB permissions (udev rule)"
if ! cmp -s "$DIR/70-minipantalla.rules" "$RULE" 2>/dev/null; then
  # 70- on purpose: uaccess rules must run before 73-seat-late.rules.
  sudo install -m 644 "$DIR/70-minipantalla.rules" "$RULE"
  sudo udevadm control --reload-rules
  sudo udevadm trigger --subsystem-match=usb --attr-match=idVendor=2a55
  echo "Rule installed. If the screen was already plugged in and fails, unplug it and plug it back."
else
  echo "Already installed."
fi

step "CLI"
mkdir -p "$(dirname "$BIN")"
ln -sfn "$DIR/minipantalla" "$BIN"
echo "$BIN -> $DIR/minipantalla"
case ":$PATH:" in *":$HOME/.local/bin:"*) ;; *) echo "Note: add ~/.local/bin to your PATH." ;; esac

step "Media folder"
mkdir -p "$PICS"
echo "Put your GIFs, images and videos in $PICS"

step "Bar plugin"
if [[ -d $HOME/.config/omarchy ]]; then
  mkdir -p "$PLUGINS_DIR/$PLUGIN_ID"
  rsync -a --delete --exclude='__pycache__/' "$DIR/plugin/$PLUGIN_ID/" "$PLUGINS_DIR/$PLUGIN_ID/"
  if command -v omarchy >/dev/null; then
    omarchy plugin enable "$PLUGIN_ID" || echo "Enable it later with: omarchy plugin enable $PLUGIN_ID"
  fi
else
  echo "Omarchy not found; skipping the bar plugin (the CLI works on its own)."
fi

step "Live-streaming service"
"$DIR/minipantalla" instalar

cat <<EOF

All set. Try:
  minipantalla poner some.gif     # show a file on the screen
  minipantalla rotar 90           # rotate it
  minipantalla estado             # check the service
EOF
