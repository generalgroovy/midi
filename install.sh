#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="$HOME/.config/traktor-system-controller"
LIB_DIR="$HOME/.local/lib/traktor-system-controller"
RESET_CONFIG=false
PACMAN_LOCK="/var/lib/pacman/db.lck"
PACMAN_WAIT_SECONDS="${PACMAN_WAIT_SECONDS:-180}"

if [[ "${1:-}" == "--reset-config" ]]; then
  RESET_CONFIG=true
elif [[ $# -gt 0 ]]; then
  printf 'Usage: %s [--reset-config]\n' "$0" >&2
  exit 2
fi

active_package_managers() {
  local found=1
  local name
  for name in pacman pamac-daemon pamac-tray garuda-update paru yay; do
    if pgrep -a -x "$name" 2>/dev/null; then
      found=0
    fi
  done
  return "$found"
}

prepare_pacman_lock() {
  local waited=0
  local processes=""

  while sudo test -e "$PACMAN_LOCK"; do
    processes="$(active_package_managers || true)"

    if [[ -n "$processes" ]]; then
      if (( waited == 0 )); then
        printf 'Pacman database is in use. Waiting up to %s seconds.\n' \
          "$PACMAN_WAIT_SECONDS" >&2
        printf '%s\n' "$processes" >&2
      fi

      if (( waited >= PACMAN_WAIT_SECONDS )); then
        printf '\nPackage management is still active. Do not remove %s yet.\n' \
          "$PACMAN_LOCK" >&2
        printf 'Wait for the process to finish, then rerun this installer.\n' >&2
        exit 1
      fi

      sleep 3
      ((waited += 3))
      continue
    fi

    printf '\nFound %s, but no package-manager process is running.\n' \
      "$PACMAN_LOCK" >&2
    printf 'This normally means the lock is stale after an interrupted update.\n' >&2

    if [[ ! -t 0 ]]; then
      printf 'Run interactively, verify no package manager is active, then remove the stale lock.\n' >&2
      exit 1
    fi

    read -r -p 'Remove the stale Pacman lock and continue? [y/N] ' answer
    case "$answer" in
      y|Y|yes|YES|Yes)
        sudo rm -f -- "$PACMAN_LOCK"
        printf 'Removed stale Pacman lock.\n'
        ;;
      *)
        printf 'Installer stopped without changing the lock.\n' >&2
        exit 1
        ;;
    esac
  done
}

prepare_pacman_lock

sudo pacman -S --needed \
  python python-evdev python-hidapi python-pyusb playerctl libnotify wireplumber \
  brightnessctl gammastep wlsunset easyeffects usbutils hid-tools evtest xdg-utils jq \
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
     systemctl --user import-environment WAYLAND_DISPLAY SWAYSOCK XDG_CURRENT_DESKTOP XDG_RUNTIME_DIR
     systemctl --user restart traktor-system-controller.service
4. A graphical consent prompt appears when each controller connects.

Useful commands:
  traktor-system-controller --list-devices
  traktor-system-controller --list-themes
  traktor-system-controller --set-theme neon
  traktor-system-controller --approve-connected
  traktor-system-controller --dry-run
EOF
