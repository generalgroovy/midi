# Configuration

The active configuration is:

```text
~/.config/traktor-system-controller/config.json
```

It includes the modular defaults under `defaults/`.

## Override one binding

Append an override mapping to `config.json`, or edit the installed controller
fragment directly. The authoritative defaults are:

```text
defaults/f1.json
defaults/x1.json
```

## Hardware-light dimmer

```json
{
  "visuals": {
    "brightness": 100,
    "brightness_state_file": "~/.config/traktor-system-controller/controller-brightness"
  }
}
```

`brightness` is used until the state file exists. F1 Knob 4 updates the state
file from 0 to 100. Both LED backends poll the file and apply changes live.

## Window control sensitivity

```json
{
  "device": "x1",
  "control": "deck_a_browse_encoder",
  "kind": "relative",
  "action": "window_move_horizontal_relative",
  "sensitivity": 45
}
```

The sensitivity is pixels per encoder step. Width/height absolute mappings can
set `minimum_percent` and `maximum_percent`.

Absolute X and Y use the focused window and active output geometry returned by
Sway. They are most useful for floating windows.

## Close focused window

The default uses exactly one binding:

```json
{
  "device": "f1",
  "control": "grid_16",
  "kind": "press",
  "action": "close_focused_window",
  "unless": ["f1.shift"]
}
```

The action resolves to `swaymsg kill`.

## Script slots

```json
{
  "script_slots": {
    "codex": {
      "label": "Codex CLI",
      "enabled": true,
      "command": ["foot", "fish", "-lc", "codex; exec fish"]
    }
  }
}
```

Use `requires: ["f1.shift"]` or `requires: ["x1.shift"]` for a shifted layer.

## Connection policy

```json
{
  "connection": {
    "policy": "prompt",
    "remember": true
  }
}
```

Policies are `prompt`, `always` and `never`.

## Validate

```fish
traktor-system-controller --validate-config
traktor-system-controller --show-layout
systemctl --user stop traktor-system-controller.service
traktor-system-controller --dry-run
```
