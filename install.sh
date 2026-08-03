#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="$HOME/.config/traktor-system-controller"
LIB_DIR="$HOME/.local/lib/traktor-system-controller"
RESET_CONFIG=false

if [[ "${1:-}" == "--reset-config" ]]; then
  RESET_CONFIG=true
elif [[ $# -gt 0 ]]; then
  printf 'Usage: %s [--reset-config]\n' "$0" >&2
  exit 2
fi

sudo pacman -S --needed \
  python python-evdev python-hidapi python-pyusb playerctl libnotify wireplumber \
  brightnessctl gammastep easyeffects usbutils hid-tools evtest xdg-utils jq \
  foot wofi zenity grim slurp pavucontrol swaylock qpwgraph \
  btop ncdu bmon fastfetch lm_sensors cliphist wl-clipboard wf-recorder \
  wdisplays blueman pacman-contrib

mkdir -p "$HOME/.local/bin" "$LIB_DIR" "$CONFIG_DIR/defaults" \
  "$CONFIG_DIR/hooks" "$CONFIG_DIR/scripts"
install -m755 "$HERE/traktor-controller.py" "$HOME/.local/bin/traktor-system-controller"
install -m644 "$HERE/traktor-system-controller.py" "$LIB_DIR/backend.py"
rm -rf "$LIB_DIR/traktor_controller" "$LIB_DIR/helpers"
cp -a "$HERE/traktor_controller" "$LIB_DIR/traktor_controller"
cp -a "$HERE/helpers" "$LIB_DIR/helpers"
chmod +x "$LIB_DIR/helpers/system-actions"

install -m644 "$HERE/config.default.json" "$CONFIG_DIR/config.default.json"
install -m644 "$HERE/config.example.json" "$CONFIG_DIR/config.example.json"
install -m644 "$HERE/config.blank.json" "$CONFIG_DIR/config.blank.json"
cp -a "$HERE/defaults/." "$CONFIG_DIR/defaults/"

if [[ ! -e "$CONFIG_DIR/hooks/model-controls-updated" ]]; then
  install -m755 "$HERE/examples/model-controls-updated" \
    "$CONFIG_DIR/hooks/model-controls-updated"
fi

if $RESET_CONFIG && [[ -e "$CONFIG_DIR/config.json" ]]; then
  backup="$CONFIG_DIR/config.backup-$(date +%Y%m%d-%H%M%S).json"
  cp "$CONFIG_DIR/config.json" "$backup"
  printf 'Backed up existing configuration to %s\n' "$backup"
fi
if $RESET_CONFIG || [[ ! -e "$CONFIG_DIR/config.json" ]]; then
  install -m644 "$HERE/config.default.json" "$CONFIG_DIR/config.json"
else
  printf 'Keeping existing configuration: %s\n' "$CONFIG_DIR/config.json"
fi

install -Dm644 "$HERE/traktor-system-controller.service" \
  "$HOME/.config/systemd/user/traktor-system-controller.service"
sudo install -Dm644 "$HERE/70-traktor-system-controller.rules" \
  /etc/udev/rules.d/70-traktor-system-controller.rules
sudo udevadm control --reload-rules
sudo udevadm trigger --subsystem-match=input || true
sudo udevadm trigger --subsystem-match=hidraw || true
sudo udevadm trigger --subsystem-match=usb || true

systemctl --user daemon-reload
systemctl --user enable traktor-system-controller.service

cat <<'EOF'

Installed.

1. Unplug and reconnect the X1 and F1.
2. Validate:
     traktor-system-controller --validate-config
     traktor-system-controller --show-layout
3. Import Sway environment and start:
     systemctl --user import-environment WAYLAND_DISPLAY SWAYSOCK XDG_CURRENT_DESKTOP
     systemctl --user restart traktor-system-controller.service
4. A graphical consent prompt appears when each controller connects.

Useful commands:
  traktor-system-controller --list-devices
  traktor-system-controller --list-themes
  traktor-system-controller --set-theme neon
  traktor-system-controller --approve-connected
  traktor-system-controller --dry-run
EOF
