#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

sudo pacman -S --needed \
  python python-evdev python-hidapi \
  evtest hid-tools usbutils \
  playerctl libnotify wireplumber brightnessctl easyeffects

install -Dm755 \
  "$HERE/traktor-system-controller.py" \
  "$HOME/.local/bin/traktor-system-controller"

mkdir -p "$HOME/.config/traktor-system-controller"
if [[ ! -e "$HOME/.config/traktor-system-controller/config.json" ]]; then
  install -m644 \
    "$HERE/config.example.json" \
    "$HOME/.config/traktor-system-controller/config.json"
else
  printf 'Keeping existing configuration: %s\n' \
    "$HOME/.config/traktor-system-controller/config.json"
  printf 'New example configuration: %s\n' \
    "$HOME/.config/traktor-system-controller/config.example.json"
  install -m644 \
    "$HERE/config.example.json" \
    "$HOME/.config/traktor-system-controller/config.example.json"
fi

sudo install -Dm644 \
  "$HERE/70-traktor-system-controller.rules" \
  "/etc/udev/rules.d/70-traktor-system-controller.rules"

install -Dm644 \
  "$HERE/traktor-system-controller.service" \
  "$HOME/.config/systemd/user/traktor-system-controller.service"

sudo udevadm control --reload-rules
sudo udevadm trigger --subsystem-match=hidraw --subsystem-match=input || true

systemctl --user daemon-reload
systemctl --user enable traktor-system-controller.service

cat <<'EOF'

Installed X1 MK1 evdev and F1 HID support.

Important:
  Unplug and reconnect both controllers after installing the udev rules.

Then run:
  traktor-system-controller --list-devices
  traktor-system-controller --monitor

Edit:
  ~/.config/traktor-system-controller/config.json

If this was an upgrade from the MIDI-only version, compare or replace the old
configuration with:
  ~/.config/traktor-system-controller/config.example.json

Start:
  systemctl --user import-environment WAYLAND_DISPLAY SWAYSOCK XDG_CURRENT_DESKTOP
  systemctl --user restart traktor-system-controller.service

Recommended Sway config line:
  exec_always sh -lc 'systemctl --user import-environment WAYLAND_DISPLAY SWAYSOCK XDG_CURRENT_DESKTOP; systemctl --user restart traktor-system-controller.service'
EOF
