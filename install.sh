#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

sudo pacman -S --needed \
  alsa-utils python python-mido python-rtmidi \
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
fi

install -Dm644 \
  "$HERE/traktor-system-controller.service" \
  "$HOME/.config/systemd/user/traktor-system-controller.service"

systemctl --user daemon-reload
systemctl --user enable traktor-system-controller.service

cat <<'EOF'

Installed.

1. Put the X1/F1 into MIDI mode.
2. Inspect ports:
     traktor-system-controller --list-ports
3. Learn controls:
     traktor-system-controller --monitor
4. Edit:
     ~/.config/traktor-system-controller/config.json
5. Remove the placeholder mappings with number 999/998.
6. Import the Sway environment and start:
     systemctl --user import-environment WAYLAND_DISPLAY SWAYSOCK XDG_CURRENT_DESKTOP
     systemctl --user restart traktor-system-controller.service

Recommended Sway config line:
  exec_always sh -lc 'systemctl --user import-environment WAYLAND_DISPLAY SWAYSOCK XDG_CURRENT_DESKTOP; systemctl --user restart traktor-system-controller.service'
EOF
