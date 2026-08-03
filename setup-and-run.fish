#!/usr/bin/env fish
set -l repo "$HOME/Projects/midi"
set -l remote "https://github.com/generalgroovy/midi.git"
set -l stamp (date +%Y%m%d-%H%M%S)

mkdir -p "$HOME/Projects"

if test -d "$repo/.git"
    cd "$repo"; or exit 1
    git remote set-url origin "$remote"; or exit 1
    git fetch --prune origin; or exit 1

    set -l backup_branch "backup/local-before-unify-$stamp"
    git branch "$backup_branch" HEAD >/dev/null 2>&1
    or true

    git stash push --include-untracked \
        --message "setup-and-run backup $stamp" >/dev/null
    or exit 1

    git switch --force-create main origin/main; or exit 1
    echo "Local pre-sync commit preserved as $backup_branch"
else
    git clone "$remote" "$repo"; or exit 1
    cd "$repo"; or exit 1
end

sudo -v; or exit 1
bash ./install.sh --reset-config; or exit 1

systemctl --user import-environment \
    WAYLAND_DISPLAY \
    SWAYSOCK \
    XDG_CURRENT_DESKTOP

systemctl --user restart traktor-system-controller.service; or exit 1

traktor-system-controller --validate-config; or exit 1
traktor-system-controller --show-layout
traktor-system-controller --list-devices
systemctl --user status traktor-system-controller.service --no-pager

echo
echo "Unified MIDI controller setup is running from: $repo"
echo "Follow logs with: journalctl --user -u traktor-system-controller.service -f"
