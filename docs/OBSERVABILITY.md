# MIDILIN runtime observability

MIDILIN records normalized controller input, aliases, modifier state, input
throttling, profile-aware mapping decisions, action messages, and lifecycle
events in an append-only JSONL ledger.

Default path:

```text
~/.local/state/traktor-system-controller/events.jsonl
```

`XDG_STATE_HOME` is honored. Override the path for one invocation:

```bash
midilin --event-log ~/AgentWorkspaces/midilin-events.jsonl --monitor
```

Use `traktor-system-controller` instead of `midilin` when running the installed
service CLI directly.

## Status

```bash
traktor-system-controller --json-status
```

The JSON report includes:

- configuration validity and errors;
- active profile and enabled mapping count;
- systemd user-service state and PID;
- Wayland, Sway, and XDG runtime environment availability;
- detected paths for brightnessctl, ddcutil, wlsunset, gammastep, and swaymsg;
- display-control configuration;
- event-ledger path, size, and recent event count.

## Inspect or clear the ledger

```bash
traktor-system-controller --event-tail 100
traktor-system-controller --clear-event-log
```

Common password, token, API-key, Bearer, and OpenAI-shaped secrets are redacted
before persistence.

## Event kinds

- `runtime_started`, `runtime_stopped`, `runtime_rejected`;
- `runtime_log` for existing human-readable action/backend messages;
- `control_input` with raw and aliased controls;
- `modifier_state` with the current held-control set;
- `input_throttled` for debounced high-rate absolute controls;
- `mapping_selected` with profile, index, conditions, and action;
- `mapping_unmatched` with candidate count and held controls.

Monitor and dry-run operation remain non-mutating while producing the same
input and routing evidence.

## Mapping validation

Validation rejects enabled mappings that have the same device, control, event
kind, required controls, excluded controls, and profile set. Identical physical
inputs remain valid when explicitly assigned to distinct profiles. Validation
also rejects conditions that both require and exclude the same control.
