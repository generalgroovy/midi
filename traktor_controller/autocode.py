from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
from pathlib import Path
from typing import Any

from .common import log
from .eventlog import emit


AUTOCODE_ACTIONS = {
    "status",
    "open",
    "pause",
    "resume",
    "stop",
    "cancel",
    "overnight-stop",
    "morning",
    "acknowledge",
    "cue-test",
}
AUTOCODE_STATES = {
    "idle",
    "starting",
    "running",
    "paused",
    "attention",
    "completed",
    "failed",
    "stopped",
}
MAX_STATE_BYTES = 64 * 1024


def settings(config: dict[str, Any]) -> dict[str, Any]:
    raw = config.get("autocode", {})
    return raw if isinstance(raw, dict) else {}


def enabled(config: dict[str, Any]) -> bool:
    return bool(settings(config).get("enabled", False))


def workspace(config: dict[str, Any]) -> Path:
    raw = str(settings(config).get("workspace", "~/Projects/flux2")).strip()
    if not raw:
        raise ValueError("autocode.workspace must not be empty")
    return Path(raw).expanduser().resolve()


def state_path(config: dict[str, Any]) -> Path:
    raw = str(
        settings(config).get(
            "state_file",
            "~/.local/state/autocode/midi/state.json",
        )
    ).strip()
    if not raw:
        raise ValueError("autocode.state_file must not be empty")
    return Path(os.path.abspath(os.fspath(Path(raw).expanduser())))


def read_state(config: dict[str, Any]) -> dict[str, Any]:
    path = state_path(config)
    if path.is_symlink():
        raise RuntimeError("Autocode state file must not be a symbolic link")
    if not path.exists():
        return {
            "available": False,
            "state": "idle",
            "cue_pending": False,
            "path": str(path),
        }
    details = path.lstat()
    if not stat.S_ISREG(details.st_mode):
        raise RuntimeError("Autocode state file must be a regular file")
    if details.st_size > MAX_STATE_BYTES:
        raise RuntimeError("Autocode state file exceeds 64 KiB")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise RuntimeError("unsupported Autocode MIDI state schema")
    state = str(value.get("state", "idle"))
    if state not in AUTOCODE_STATES:
        raise RuntimeError(f"unsupported Autocode MIDI state: {state}")
    configured_workspace = str(workspace(config))
    foreign = value.get("workspace") not in {None, configured_workspace}
    return {
        **value,
        "available": True,
        "foreign_workspace": foreign,
        "path": str(path),
    }


def command(config: dict[str, Any], action: str) -> list[str]:
    if action not in AUTOCODE_ACTIONS:
        raise ValueError(f"unsupported Autocode action: {action}")
    binary_name = str(settings(config).get("binary", "autocode-local")).strip()
    if not binary_name or Path(binary_name).name != binary_name:
        raise ValueError("autocode.binary must be a simple executable name")
    binary = shutil.which(binary_name)
    if not binary:
        raise FileNotFoundError(f"Autocode executable not found: {binary_name}")
    return [binary, "midi-action", action, str(workspace(config))]


def dispatch(
    config: dict[str, Any],
    action: str,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    if not enabled(config):
        raise RuntimeError("Autocode integration is disabled")
    argv = command(config, action)
    emit("autocode_action_requested", action=action, command=argv, dry_run=dry_run)
    if dry_run:
        return {"ok": True, "action": action, "command": argv, "dry_run": True}
    try:
        result = subprocess.run(
            argv,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        emit("autocode_action_result", action=action, ok=False, error="timeout")
        raise RuntimeError(f"Autocode action timed out: {action}") from exc
    output = ((result.stdout or "") + (result.stderr or ""))[-65_536:]
    response = {
        "ok": result.returncode == 0,
        "action": action,
        "command": argv,
        "exit_code": result.returncode,
        "output": output,
    }
    emit("autocode_action_result", **response)
    if result.returncode != 0:
        log(f"Autocode action failed: {action}: {output.strip() or result.returncode}")
    return response


def validate(config: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    value = settings(config)
    if not isinstance(config.get("autocode", {}), dict):
        return ["autocode must be an object"]
    binary = str(value.get("binary", "autocode-local")).strip()
    if not binary or Path(binary).name != binary:
        errors.append("autocode.binary must be a simple executable name")
    raw_workspace = str(value.get("workspace", "~/Projects/flux2")).strip()
    if not raw_workspace:
        errors.append("autocode.workspace must not be empty")
    raw_state = str(
        value.get("state_file", "~/.local/state/autocode/midi/state.json")
    ).strip()
    if not raw_state:
        errors.append("autocode.state_file must not be empty")
    poll = float(value.get("poll_seconds", 0.25))
    if poll < 0.1 or poll > 10:
        errors.append("autocode.poll_seconds must be between 0.1 and 10")
    for key in ("f1_indicator", "x1_indicator"):
        if key in value and not str(value[key]).strip():
            errors.append(f"autocode.{key} must not be empty")
    return errors
