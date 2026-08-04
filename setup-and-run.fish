#!/usr/bin/env fish
set -l repo "$HOME/Projects/midilin"
set -l legacy_repo "$HOME/Projects/midi"
set -l remote "https://github.com/generalgroovy/midilin.git"
set -l stamp (date +%Y%m%d-%H%M%S)

mkdir -p "$HOME/Projects"; or exit 1

# Reuse the pre-rename checkout only when the target path does not exist.
if not test -e "$repo"; and test -d "$legacy_repo/.git"
    mv "$legacy_repo" "$repo"; or exit 1
end

# Preserve an unrelated/non-Git target directory rather than overwriting it.
if test -e "$repo"; and not test -d "$repo/.git"
    set -l displaced "$repo.non-git-backup-$stamp"
    mv "$repo" "$displaced"; or exit 1
    echo "Moved non-Git directory to: $displaced"
end

if not test -d "$repo/.git"
    git clone "$remote" "$repo"; or exit 1
else
    git -C "$repo" remote set-url origin "$remote"; or exit 1
    git -C "$repo" fetch --prune origin; or exit 1

    set -l backup_branch "backup/local-before-midilin-update-$stamp"
    git -C "$repo" branch "$backup_branch" HEAD >/dev/null 2>&1
    or true

    if test -n "$(git -C "$repo" status --porcelain)"
        git -C "$repo" stash push --include-untracked \
            --message "MIDILIN setup backup $stamp"; or exit 1
    end

    git -C "$repo" switch --force-create main origin/main; or exit 1
    echo "Previous checkout preserved as branch: $backup_branch"
end

if not test -f "$repo/install.sh"
    echo "Installer missing after checkout: $repo/install.sh" >&2
    exit 1
end

sudo -v; or exit 1
bash "$repo/install.sh" --reset-config; or exit 1

systemctl --user import-environment \
    WAYLAND_DISPLAY \
    SWAYSOCK \
    XDG_CURRENT_DESKTOP \
    XDG_RUNTIME_DIR
or exit 1

systemctl --user daemon-reload; or exit 1
systemctl --user restart traktor-system-controller.service; or exit 1

traktor-system-controller --validate-config; or exit 1
traktor-system-controller --show-layout
traktor-system-controller --list-devices
traktor-system-controller --diagnose-display
systemctl --user status traktor-system-controller.service --no-pager

echo
echo "MIDILIN is installed from: $repo"
echo "Launch GUI: midilin-gui"
echo "Logs: journalctl --user -u traktor-system-controller.service -f"
