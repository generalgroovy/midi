# Configuration

## Root and includes

The active root is `~/.config/traktor-system-controller/config.json`. Included
objects merge recursively and arrays concatenate. A minimal override can contain
only the fields that differ from the defaults.

## Override an action

```json
{
  "actions": {
    "browser": ["firefox", "--new-window", "https://github.com"]
  }
}
```

## Add a mapping

```json
{
  "mappings": [
    {
      "profile": "linux-ops",
      "device": "f1",
      "control": "grid_1",
      "kind": "press",
      "action": "browser",
      "enabled": true
    }
  ]
}
```

The default validator rejects repeated action signatures on the same controller.
For generic actions, the target is part of the signature:

- `script_slot:codex`
- `model_parameter_absolute:temperature`

Disable the rule only when intentionally creating mirrors:

```json
{
  "layout_rules": {
    "no_repeated_actions_per_controller": false
  }
}
```

## Shift layers

```json
{
  "requires": ["f1.shift"]
}
```

Use `unless` on the normal mapping so only one layer executes:

```json
{
  "unless": ["f1.shift"]
}
```

## Script slots

A slot is a named command target. It can be enabled, disabled or confirmation
gated independently of the physical mapping.

```json
{
  "script_slots": {
    "autocode": {
      "label": "Autocode",
      "enabled": true,
      "confirm": "Start the autonomous coding workspace?",
      "command": [
        "foot",
        "--working-directory={home}/Projects/autocode"
      ]
    }
  }
}
```

A slot mapping:

```json
{
  "device": "f1",
  "control": "grid_1",
  "kind": "press",
  "action": "script_slot",
  "slot": "autocode",
  "requires": ["f1.shift"]
}
```

## Model parameters

Parameter definitions control range, quantization and defaults:

```json
{
  "model_controls": {
    "parameters": {
      "temperature": {
        "min": 0.0,
        "max": 2.0,
        "step": 0.01,
        "default": 0.7,
        "decimals": 2
      }
    }
  }
}
```

Mapping:

```json
{
  "device": "x1",
  "control": "fx1_dry_wet",
  "kind": "absolute",
  "action": "model_parameter_absolute",
  "parameter": "temperature"
}
```

The controller does not assume a specific inference API. It writes a stable JSON
state and invokes a hook, allowing one layout to configure Ollama, llama.cpp,
OpenAI-compatible clients, Aider, Codex wrappers or Odysseus.

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

Policies:

- `prompt`: show a Wofi or Zenity decision dialog on first connection;
- `always`: activate supported controllers immediately;
- `never`: detect but never claim controllers.

## Hardware mode

```json
{
  "hardware": {
    "x1_backend": "raw_usb",
    "fallback_to_evdev": true
  }
}
```

`raw_usb` provides X1 LEDs. `evdev` leaves the kernel driver attached and provides
input only.

## Visuals

```json
{
  "visuals": {
    "theme": "category",
    "x1": {
      "dim": 5,
      "active": 28,
      "pressed": 127
    }
  }
}
```

The command-line theme state overrides `visuals.theme`:

```fish
traktor-system-controller --set-theme sunset
```

## Validation

```fish
traktor-system-controller --validate-config
traktor-system-controller --show-layout
systemctl --user stop traktor-system-controller.service
traktor-system-controller --dry-run
```
