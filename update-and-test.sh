#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

repo="${MIDILIN_REPO:-$HOME/Projects/midilin}"
branch="${MIDILIN_BRANCH:-agent/observable-runtime-20260804}"
config="$HOME/.config/traktor-system-controller/config.json"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
stash_created=0

section() {
  printf '\n========================================================================\n%s\n========================================================================\n' "$1"
}

fail() {
  printf '\nERROR: %s\n' "$*" >&2
  exit 1
}

for command in git python systemctl jq; do
  command -v "$command" >/dev/null 2>&1 || fail "required command not found: $command"
done
[[ -d "$repo/.git" ]] || fail "MIDILIN repository not found: $repo"
cd "$repo"

section "1/8 — Preserve local repository changes and update"
if [[ -n "$(git status --porcelain)" ]]; then
  printf 'Preserving dirty worktree in a stash before update.\n'
  git status --short
  git stash push --include-untracked --message "midilin-pre-update-$stamp"
  stash_created=1
fi

git fetch --prune origin

# An earlier sparse/partial checkout can leave tracked Python modules absent while
# Git reports a clean worktree. Disable sparse mode before switching/pulling.
if git config --bool core.sparseCheckout 2>/dev/null | grep -qx true; then
  printf 'Disabling sparse checkout so the complete MIDILIN runtime is materialized.\n'
  git sparse-checkout disable
fi

git switch "$branch"
git pull --ff-only origin "$branch"
local_head="$(git rev-parse HEAD)"
remote_head="$(git rev-parse "origin/$branch")"
printf 'MIDILIN head: %s\n' "$local_head"
[[ "$local_head" == "$remote_head" ]] || fail "local head does not match origin/$branch"
[[ -z "$(git status --porcelain)" ]] || fail "worktree is not clean after update"

# The user changes were stashed above, so restoring tracked files from the exact
# remote head is safe here and repairs skip-worktree/incomplete checkout states.
printf 'Verifying complete tracked runtime tree.\n'
git restore --ignore-skip-worktree-bits --source="origin/$branch" --worktree -- .

critical_files=(
  traktor-controller.py
  traktor-system-controller.py
  traktor_controller/__init__.py
  traktor_controller/cli.py
  traktor_controller/cli_autocode.py
  traktor_controller/common.py
  traktor_controller/hardware.py
  traktor_controller/router.py
  traktor_controller/visuals.py
)
for path in "${critical_files[@]}"; do
  git cat-file -e "origin/$branch:$path" 2>/dev/null \
    || fail "remote branch is missing required tracked file: $path"
  [[ -f "$path" && ! -L "$path" ]] \
    || fail "local checkout is missing required tracked file after restore: $path"
done

PYTHONPATH="$repo" python - <<'PY'
import traktor_controller.cli
import traktor_controller.cli_autocode
import traktor_controller.router
print("MIDILIN_IMPORTS_OK")
PY

[[ -z "$(git status --porcelain)" ]] || fail "tracked tree differs from origin after repair"

section "2/8 — Run complete source validation"
bash validate-local.sh

section "3/8 — Recover normal controller profile"
if [[ -e "$config" ]]; then
  [[ -f "$config" && ! -L "$config" ]] || fail "unsafe controller config target: $config"
  backup="${config%.json}.before-recovery-$stamp.json"
  install -m600 "$config" "$backup"
  python - "$config" <<'PY'
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

path = Path(sys.argv[1])
value = json.loads(path.read_text(encoding="utf-8"))
if not isinstance(value, dict):
    raise SystemExit("controller config root must be a JSON object")
value["active_profile"] = "linux-ops"
autocode = value.get("autocode")
if not isinstance(autocode, dict):
    autocode = {}
autocode["enabled"] = False
value["autocode"] = autocode
fd, temporary = tempfile.mkstemp(prefix=".config.", dir=path.parent)
try:
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(temporary, 0o600)
    os.replace(temporary, path)
finally:
    if os.path.exists(temporary):
        os.unlink(temporary)
PY
  printf 'Backed up existing config: %s\n' "$backup"
  printf 'Recovery mode: active_profile=linux-ops, autocode.enabled=false\n'
else
  printf 'No installed config yet; installer will create the safe defaults.\n'
fi

section "4/8 — Install current validated build"
bash install.sh

section "5/8 — Validate installed configuration and core mapping layout"
installed="$HOME/.local/bin/traktor-system-controller"
[[ -x "$installed" ]] || fail "installed controller binary is missing: $installed"
"$installed" --validate-config
"$installed" --profile linux-ops --show-layout

section "6/8 — Restart user service with current Sway environment"
systemctl --user import-environment \
  WAYLAND_DISPLAY SWAYSOCK XDG_CURRENT_DESKTOP XDG_RUNTIME_DIR 2>/dev/null || true
systemctl --user daemon-reload
systemctl --user reset-failed traktor-system-controller.service || true
systemctl --user restart traktor-system-controller.service
sleep 2
systemctl --user is-active --quiet traktor-system-controller.service || {
  systemctl --user --no-pager --full status traktor-system-controller.service >&2 || true
  journalctl --user -u traktor-system-controller.service -n 120 --no-pager >&2 || true
  fail "MIDILIN service did not become active"
}
systemctl --user --no-pager --full status traktor-system-controller.service | sed -n '1,22p'

section "7/8 — Runtime diagnostics"
"$installed" --json-status | jq '{
  application,
  config_valid,
  active_profile,
  enabled_mappings,
  service,
  environment,
  backends,
  autocode
}'
printf '\nConnected controller devices:\n'
"$installed" --list-devices || true
printf '\nRecent service log:\n'
journalctl --user -u traktor-system-controller.service -n 80 --no-pager || true

section "8/8 — Result"
printf 'MIDILIN_UPDATE_TEST_OK head=%s\n' "$local_head"
printf '\nPhysical input monitor (service must release the controllers first):\n'
printf '  systemctl --user stop traktor-system-controller.service\n'
printf '  MIDILIN_EVENT_LOG_MODE=off %q --profile linux-ops --monitor\n' "$installed"
printf '  # press Ctrl+C after testing, then:\n'
printf '  systemctl --user restart traktor-system-controller.service\n'
printf '\nIf the worktree stash was created, inspect it later with:\n'
if (( stash_created )); then
  printf '  cd %q && git stash list && git stash show --stat stash@{0}\n' "$repo"
else
  printf '  (no stash was required)\n'
fi
