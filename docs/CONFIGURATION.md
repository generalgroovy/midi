# Configuration

## Root and includes

The active root is `~/.config/traktor-system-controller/config.json`. Included
objects merge recursively and mapping arrays concatenate.

Default fragments:

```text
defaults/actions.json
defaults/model.json
defaults/scripts.json
defaults/visuals.json
defaults/f1.json
defaults/x1.json
```

## Duplicate-action rule

The default validator rejects repeated enabled action signatures on the same
controller. Parameterized actions include their target in the signature:

```text
script_slot:codex
model_parameter_absolute:temperature
```

Disable the rule only when an intentional mirror is required:

```json
{
  "layout_rules": {
    "no_repeated_actions_per_controller": false
  }
}
```

## Layers

Mappings can require or exclude held buttons:

```json
{"requires": ["f1.shift"]}
```

```json
{"unless": ["f1.shift"]}
```

The default uses `f1.shift` for model knobs and scripts, `x1.shift` for custom
upper-button scripts, and `x1.hotcue` for transport diagnostics.

## Hardware-light brightness

The built-in action `hardware_light_absolute` scales all F1 RGB/button output
and X1 LED output from zero to full.

```json
{
  "device": "f1",
  "control": "knob_3",
  "kind": "absolute",
  "action": "hardware_light_absolute",
  "unless": ["f1.shift"]
}
```

```json
{
  "visuals": {
    "light_brightness_default": 0.75,
    "light_brightness_state_file":
      "~/.config/traktor-system-controller/light-brightness.json"
  }
}
```

## Focused-window geometry

Built-in continuous actions:

```text
window_x_absolute
window_y_absolute
window_width_absolute
window_height_absolute
window_opacity_absolute
window_border_absolute
window_output_absolute
window_focus_horizontal_relative
window_focus_vertical_relative
window_move_horizontal_relative
window_move_vertical_relative
```

Example:

```json
{
  "device": "x1",
  "control": "fx1_knob_2",
  "kind": "absolute",
  "action": "window_width_absolute",
  "minimum": 320
}
```

Position and size controls enable floating mode. X/Y spans the bounding
rectangle of all active outputs. `window_output_absolute` sorts active outputs
by global X/Y position and selects one from the knob position.

## Close the focused window

The only default close binding is F1 `REVERSE`:

```json
{
  "actions": {
    "close_focused_window": ["swaymsg", "kill"]
  }
}
```

## Script slots

```json
{
  "script_slots": {
    "custom_01": {
      "label": "Local agent",
      "enabled": true,
      "confirm": "Start the local agent?",
      "command": [
        "foot",
        "--working-directory=/home/otp/Projects/flux2",
        "fish",
        "-lc",
        "autocode; exec fish"
      ]
    }
  }
}
```

## Model parameters

The default exposes four parameters on `SHIFT + F1 knobs` and four on F1
faders. Definitions control range, quantization and defaults. State is written
to `model-controls.json`, then the optional hook runs after the debounce period.

## Connection policy

```json
{
  "connection": {
    "policy": "prompt",
    "remember": true,
    "state_file": "~/.config/traktor-system-controller/device-decisions.json"
  }
}
```

Policies: `prompt`, `always`, `never`.

## X1 hardware mode

```json
{
  "hardware": {
    "x1_backend": "raw_usb",
    "fallback_to_evdev": true
  }
}
```

`raw_usb` provides X1 LED output. `evdev` retains kernel-only input without LED
control.

## Validate

```fish
traktor-system-controller --validate-config
traktor-system-controller --show-layout
systemctl --user stop traktor-system-controller.service
traktor-system-controller --dry-run
```
