from __future__ import annotations

import json
import os
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_LOCK = threading.Lock()
_DEFAULT_MAX_BYTES = 8 * 1024 * 1024
_DEFAULT_BACKUPS = 4
_SECRET_PATTERNS = (
    re.compile(r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s]+"),
    re.compile(r"(?i)((?:password|passwd|token|api[_-]?key)\s*[:=]\s*)[^\s,;]+"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),
)
_SUPPRESSED_BY_ACTION_MODE = {
    "control_input",
    "input_throttled",
    "mapping_unmatched",
    "modifier_state",
}


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def event_path() -> Path:
    configured = os.environ.get("MIDILIN_EVENT_LOG", "").strip()
    if configured:
        return Path(configured).expanduser()
    state_home = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
    return state_home / "traktor-system-controller/events.jsonl"


def _bounded_int(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.environ.get(name, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if value < minimum or value > maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


def _boolean_env(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off", ""}:
        return False
    raise ValueError(f"{name} must be a boolean value")


def max_bytes() -> int:
    return _bounded_int(
        "MIDILIN_EVENT_LOG_MAX_BYTES",
        _DEFAULT_MAX_BYTES,
        1024,
        1024 * 1024 * 1024,
    )


def backup_count() -> int:
    return _bounded_int("MIDILIN_EVENT_LOG_BACKUPS", _DEFAULT_BACKUPS, 1, 20)


def log_mode() -> str:
    # Action-level logging is the safe default for a high-rate controller.
    mode = os.environ.get("MIDILIN_EVENT_LOG_MODE", "actions").strip().lower()
    if mode not in {"full", "actions", "off"}:
        raise ValueError("MIDILIN_EVENT_LOG_MODE must be full, actions, or off")
    return mode


def fsync_enabled() -> bool:
    # Per-event fsync can stall MIDI/HID dispatch for tens of milliseconds.
    return _boolean_env("MIDILIN_EVENT_LOG_FSYNC", False)


def strict_mode() -> bool:
    # Runtime observability must not break controller actions. Tests/diagnostics
    # can explicitly enable strict mode when validating path and retention rules.
    return _boolean_env("MIDILIN_EVENT_LOG_STRICT", False)


def _secure_parent(path: Path) -> None:
    if path.parent.is_symlink():
        raise RuntimeError(f"event-log directory must not be a symbolic link: {path.parent}")
    path.parent.mkdir(parents=True, exist_ok=True)
    if os.name != "nt":
        os.chmod(path.parent, 0o700)


def _assert_regular_target(path: Path) -> None:
    if path.is_symlink():
        raise RuntimeError(f"event-log path must not be a symbolic link: {path}")
    if path.exists() and not path.is_file():
        raise RuntimeError(f"event-log path is not a regular file: {path}")


def _rotated(path: Path, index: int) -> Path:
    return path.with_name(f"{path.name}.{index}")


def _existing_rotation_indices(path: Path) -> set[int]:
    indices: set[int] = set()
    if not path.parent.exists():
        return indices
    prefix = f"{path.name}."
    for candidate in path.parent.glob(f"{path.name}.*"):
        suffix = candidate.name[len(prefix):]
        if suffix.isdigit() and int(suffix) > 0:
            indices.add(int(suffix))
    return indices


def event_files(path: Path | None = None) -> list[Path]:
    target = path or event_path()
    indices = set(range(1, backup_count() + 1)) | _existing_rotation_indices(target)
    return [_rotated(target, index) for index in sorted(indices, reverse=True)] + [target]


def redact(value: Any) -> Any:
    if isinstance(value, str):
        rendered = value
        for pattern in _SECRET_PATTERNS:
            if pattern.groups:
                rendered = pattern.sub(r"\1<REDACTED>", rendered)
            else:
                rendered = pattern.sub("<REDACTED>", rendered)
        return rendered
    if isinstance(value, dict):
        return {str(key): redact(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(item) for item in value]
    return value


def _should_persist(kind: str, fields: dict[str, Any]) -> bool:
    mode = log_mode()
    if mode == "off":
        return False
    if mode != "actions":
        return True
    if kind in _SUPPRESSED_BY_ACTION_MODE:
        return False
    # Absolute controls can generate dozens of selection events per second.
    if kind == "mapping_selected" and fields.get("event_kind") == "absolute":
        return False
    return True


def _rotate_if_needed(path: Path, incoming_bytes: int) -> None:
    _assert_regular_target(path)
    limit = max_bytes()
    backups = backup_count()
    if not path.exists() or path.stat().st_size + incoming_bytes <= limit:
        return
    for index in sorted(_existing_rotation_indices(path), reverse=True):
        if index >= backups:
            stale = _rotated(path, index)
            _assert_regular_target(stale)
            stale.unlink(missing_ok=True)
    oldest = _rotated(path, backups)
    _assert_regular_target(oldest)
    oldest.unlink(missing_ok=True)
    for index in range(backups - 1, 0, -1):
        source = _rotated(path, index)
        destination = _rotated(path, index + 1)
        _assert_regular_target(source)
        _assert_regular_target(destination)
        if source.exists():
            os.replace(source, destination)
    os.replace(path, _rotated(path, 1))


def _append(path: Path, line: str) -> None:
    _secure_parent(path)
    _assert_regular_target(path)
    flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags, 0o600)
    try:
        if os.name != "nt":
            os.fchmod(fd, 0o600)
        encoded = line.encode("utf-8")
        offset = 0
        while offset < len(encoded):
            offset += os.write(fd, encoded[offset:])
        if fsync_enabled():
            os.fsync(fd)
    finally:
        os.close(fd)


def _persist(event: dict[str, Any], fields: dict[str, Any]) -> None:
    kind = str(event["kind"])
    if not _should_persist(kind, fields):
        return
    path = event_path()
    line = json.dumps(
        event,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    ) + "\n"
    with _LOCK:
        _secure_parent(path)
        _rotate_if_needed(path, len(line.encode("utf-8")))
        _append(path, line)


def emit(kind: str, **fields: Any) -> dict[str, Any]:
    event = {
        "schema_version": 1,
        "timestamp": utcnow(),
        "kind": str(kind),
        **redact(fields),
    }
    try:
        _persist(event, fields)
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        if strict_mode():
            raise
        # Observability is best effort in the live controller path. Surface the
        # error to callers without interrupting the mapped action itself.
        event["log_error"] = f"{type(exc).__name__}: {exc}"
    return event


def read_tail(limit: int = 100) -> list[dict[str, Any]]:
    if limit < 1:
        raise ValueError("event tail limit must be positive")
    lines: list[str] = []
    for path in event_files():
        _assert_regular_target(path)
        if not path.exists():
            continue
        lines.extend(path.read_text(encoding="utf-8", errors="replace").splitlines())
    events: list[dict[str, Any]] = []
    for line in lines[-limit:]:
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            events.append(value)
    return events


def clear() -> bool:
    removed = False
    with _LOCK:
        for path in event_files():
            _assert_regular_target(path)
            if path.exists():
                path.unlink()
                removed = True
    return removed
