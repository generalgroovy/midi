#!/usr/bin/env fish
set -l repo "$HOME/Projects/midi"
mkdir -p "$HOME/Projects"

if test -d "$repo/.git"
    cd "$repo"
    git pull --ff-only
else
    git clone https://github.com/generalgroovy/midi.git "$repo"
    cd "$repo"
end

sudo -v; or exit 1
bash ./install.sh --reset-config; or exit 1

systemctl --user import-environment WAYLAND_DISPLAY SWAYSOCK XDG_CURRENT_DESKTOP
systemctl --user restart traktor-system-controller.service

traktor-system-controller --validate-config
traktor-system-controller --list-devices
systemctl --user status traktor-system-controller.service --no-pager
