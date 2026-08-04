#!/usr/bin/env bash
set -Eeuo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$repo_root"

python_bin="${PYTHON:-python}"
backend="$repo_root/traktor-system-controller.py"
status_file="$(mktemp)"
trap 'rm -f -- "$status_file"' EXIT

printf '== Python compile ==\n'
"$python_bin" -m py_compile \
  traktor-system-controller.py \
  traktor-controller.py \
  traktor_controller/*.py

printf '\n== JSON configuration syntax ==\n'
for file in config.default.json config.example.json config.blank.json defaults/*.json; do
  printf '  %s\n' "$file"
  "$python_bin" -m json.tool "$file" >/dev/null
done

printf '\n== Runtime configuration validation ==\n'
TRAKTOR_CONTROLLER_BACKEND="$backend" \
  "$python_bin" traktor-controller.py \
  --config config.default.json \
  --validate-config

printf '\n== Unit and integration tests ==\n'
WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-test}" \
  "$python_bin" -m unittest discover -s tests -v

printf '\n== Structured status contract ==\n'
TRAKTOR_CONTROLLER_BACKEND="$backend" \
  "$python_bin" traktor-controller.py \
  --config config.default.json \
  --json-status >"$status_file"
"$python_bin" -m json.tool "$status_file" >/dev/null
"$python_bin" - "$status_file" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path

status = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
if status.get("application") != "midilin":
    raise SystemExit(f"unexpected application field: {status.get('application')!r}")
if status.get("schema_version") != 1:
    raise SystemExit(f"unexpected schema version: {status.get('schema_version')!r}")
if not status.get("config_valid"):
    raise SystemExit("default configuration is not valid: " + "; ".join(status.get("config_errors", [])))
event_log = status.get("event_log")
if not isinstance(event_log, dict):
    raise SystemExit("status is missing event_log metadata")
if event_log.get("mode") not in {"full", "actions", "off"}:
    raise SystemExit(f"invalid event-log mode: {event_log.get('mode')!r}")
if not isinstance(event_log.get("max_bytes"), int) or event_log["max_bytes"] < 1024:
    raise SystemExit("status is missing a valid event-log size limit")
if not isinstance(event_log.get("backup_count"), int) or event_log["backup_count"] < 1:
    raise SystemExit("status is missing a valid event-log backup count")
segments = event_log.get("segments")
if not isinstance(segments, list) or len(segments) != event_log["backup_count"] + 1:
    raise SystemExit("status event-log segment inventory is inconsistent")
service = status.get("service")
if not isinstance(service, dict) or "available" not in service:
    raise SystemExit("status is missing systemd service metadata")
print("MIDILIN_JSON_STATUS_OK")
PY

printf '\n== Shell syntax ==\n'
bash -n \
  install.sh \
  validate-local.sh \
  helpers/system-actions \
  examples/model-controls-updated

printf '\n== SVG assets ==\n'
"$python_bin" - <<'PY'
import xml.etree.ElementTree as ET
from pathlib import Path

paths = sorted(Path("assets").glob("*.svg"))
for path in paths:
    ET.parse(path)
print(f"validated {len(paths)} SVG assets")
PY

printf '\nMIDILIN_VALIDATION_OK\n'
