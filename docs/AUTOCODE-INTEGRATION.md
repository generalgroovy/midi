# MIDILIN Autocode integration

MIDILIN can operate the local Autocode coding stack through a closed action
protocol and display Autocode state on the F1/X1 LEDs. The integration does not
use script slots, `bash -lc`, arbitrary shell commands, sudo, Docker control, or
network tokens.

## Requirements

- Autocode installed on the same Linux user account;
- `autocode-local` available on `PATH`;
- the selected project directory exists;
- MIDILIN installed from the `agent/observable-runtime-20260804` branch.

Validate both installations:

```fish
autocode-local midi-state ~/Projects/flux2
traktor-system-controller --validate-config
```

## Configuration

The default configuration includes `defaults/autocode.json`, but the active
profile remains `linux-ops`. Existing desktop/media mappings are therefore not
replaced automatically.

Edit the installed configuration:

```text
~/.config/traktor-system-controller/config.json
```

Set the Autocode project:

```json
{
  "autocode": {
    "enabled": true,
    "binary": "autocode-local",
    "workspace": "~/Projects/flux2",
    "state_file": "~/.local/state/autocode/midi/state.json",
    "poll_seconds": 0.25,
    "f1_indicator": "grid_16",
    "x1_indicator": "hotcue"
  },
  "active_profile": "autocode-ops"
}
```

The normal configuration include merge retains all default actions and mappings.
Only the selected profile is active.

Validate and inspect:

```fish
traktor-system-controller --validate-config
traktor-system-controller --profile autocode-ops --show-layout
traktor-system-controller --json-status
traktor-system-controller --autocode-state
```

Restart the user service after configuration changes:

```fish
systemctl --user restart traktor-system-controller.service
```

## Fixed actions

The controller may request only these Autocode operations:

```text
status
open
pause
resume
stop
cancel
overnight-stop
morning
acknowledge
cue-test
```

MIDILIN constructs this fixed argv shape:

```text
autocode-local midi-action <ACTION> <WORKSPACE>
```

The executable must be a simple executable name. The workspace and state file
are validated. Unknown action names are rejected before process creation.

Manual tests:

```fish
traktor-system-controller --autocode-action status
traktor-system-controller --autocode-action cue-test
traktor-system-controller --autocode-action acknowledge
```

## F1 `autocode-ops` layout

| Control | Action |
|---|---|
| Grid 1 | Open Control Center |
| Grid 2 | Status |
| Grid 3 | Pause interactive run |
| Grid 4 | Resume interactive run |
| Grid 5 | Stop interactive run |
| Grid 6 | Cancel interactive run |
| Grid 7 | Stop overnight queue |
| Grid 8 | Locate morning report |
| Grid 9 | Acknowledge pending completion |
| Grid 10 | Test desktop/audio cue |
| Grid 16 | Autocode status indicator |

## X1 `autocode-ops` layout

| Control | Action |
|---|---|
| Deck A IN | Open Control Center |
| Deck A OUT | Status |
| Deck A beat left | Pause |
| Deck A beat right | Resume |
| Deck A CUE | Stop |
| Deck A CUP | Cancel |
| Deck A PLAY | Stop overnight queue |
| Deck A SYNC | Acknowledge completion |
| Deck B IN | Morning report |
| Deck B OUT | Cue test |
| HOTCUE LED | Autocode status indicator |

## LED states

The normal visual mapping is rendered first. MIDILIN then applies one optional
Autocode indicator.

F1 indicator colors:

| State | Color intent |
|---|---|
| idle | off |
| starting | blue |
| running | bright blue |
| paused | amber |
| attention | purple |
| completed | green |
| failed | red |
| stopped | dim amber |

The X1 indicator uses brightness levels for the same states. A pending
completion/attention cue forces the indicator bright. It remains pending across
a subsequent running slice until the user presses the acknowledge action.

The overlay is ignored when the state belongs to a different configured
workspace.

## Autocode state contract

MIDILIN reads only:

```text
~/.local/state/autocode/midi/state.json
```

The file must be:

- schema version 1;
- a regular non-symlink file;
- no larger than 64 KiB;
- owned/readable by the same user.

Normalized states:

```text
idle starting running paused attention completed failed stopped
```

MIDILIN does not read prompts, source code, credentials, checkpoint archives, or
model output through this bridge.

## Diagnostics

```fish
traktor-system-controller --json-status
traktor-system-controller --event-tail 100
traktor-system-controller --monitor --profile autocode-ops
journalctl --user -u traktor-system-controller.service -n 100 --no-pager
```

The JSON status reports:

- whether integration is enabled;
- configured workspace;
- current normalized state;
- available fixed actions;
- `arbitrary_commands: false`.

## Validation

```fish
cd ~/Projects/midilin
git fetch origin
git switch agent/observable-runtime-20260804
git pull --ff-only
bash validate-local.sh
bash install.sh
```

Required marker:

```text
MIDILIN_VALIDATION_OK
```

Then verify physically:

- F1/X1 detection;
- each configured button;
- status LED transitions;
- pending-cue persistence and acknowledgement;
- reconnect and service restart;
- no changes to `linux-ops` when that profile is selected.

Automated CI cannot prove USB/HID behavior on the actual controllers.
