# Event log retention

MIDILIN rotates its JSONL event log so continuous controller traffic cannot use unlimited storage.

Defaults:

- 8 MiB per active segment;
- 4 rotated segments;
- `full` detail mode;
- `~/.local/state/traktor-system-controller/events.jsonl` unless `XDG_STATE_HOME` is set.

Configuration:

```fish
set -x MIDILIN_EVENT_LOG_MAX_BYTES 8388608
set -x MIDILIN_EVENT_LOG_BACKUPS 4
set -x MIDILIN_EVENT_LOG_MODE actions
traktor-system-controller --monitor
```

`MIDILIN_EVENT_LOG_MAX_BYTES` accepts 1024 through 1073741824. `MIDILIN_EVENT_LOG_BACKUPS` accepts 1 through 20.

Modes:

- `full`: all input, routing, action, backend and lifecycle events;
- `actions`: omits raw input, throttling and unmatched-routing noise while retaining selected mappings and action results;
- `off`: no event persistence.

`--event-tail` reads across the active log and rotations in chronological order. `--clear-event-log` removes all numeric rotations, including files left by an earlier retention setting.

Symbolic-link and non-regular log targets are rejected. The state directory is mode `0700` and log files are mode `0600`.
