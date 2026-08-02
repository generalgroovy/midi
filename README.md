# Traktor X1/F1 Linux System Controller

Turn a Native Instruments **Traktor Kontrol F1** and **X1 MK1** into two
complementary Linux control surfaces for Garuda Sway:

- **F1:** desktop flow, applications, workspaces, audio, display controls and
  sixteen `SHIFT` script slots.
- **X1:** system monitoring, maintenance, audio/network operations, eight local
  model parameters and eight additional `SHIFT` script slots.

![Default layout overview](assets/default-layout-overview.svg)

The default profile deliberately avoids repeating an action signature on the
same controller. Every mapped control has a distinct role.

## What it provides

- Native Wayland/Sway operation without keyboard emulation.
- Graphical consent prompt when a controller connects: use once, always use,
  ignore once or never use.
- F1 RGB pad colors and press feedback.
- X1 button LEDs and press feedback through the optional raw-USB backend.
- Six visual themes: `category`, `neon`, `matrix`, `sunset`, `mono`, `blackout`.
- Global audio, brightness, workspaces, launcher, clipboard, screenshot,
  recording, display, Bluetooth and network controls.
- System dashboards for processes, sensors, services, logs, disks, ports,
  mounts, USB, timers, packages and power.
- Configurable script slots for Codex, Ollama, Odysseus, Autocode, Aider,
  OpenCode, FLUX2 and arbitrary executables.
- Knob/fader-controlled model parameters persisted as JSON and forwarded to a
  configurable hook.
- Dry-run, event monitor, layout validation and duplicate-action checks.

## Supported hardware

| Controller | USB ID | Default backend | Visual output |
|---|---:|---|---|
| Traktor Kontrol F1 | `17cc:1120` | HID/hidapi | RGB pads, buttons, play LEDs |
| Traktor Kontrol X1 MK1 | `17cc:2305` | PyUSB raw mode | Button LEDs |
| Traktor Kontrol X1 MK1 fallback | `17cc:2305` | `snd-usb-caiaq` evdev | Input only |

Raw X1 mode temporarily detaches `snd-usb-caiaq`, reads the controller directly,
drives its LEDs, and restores the kernel driver when the process exits. Set
`hardware.x1_backend` to `evdev` to retain kernel-only input mode without LEDs.

## Pull, install and run

Use the included Fish script:

```fish
curl -L https://raw.githubusercontent.com/generalgroovy/midi/main/setup-and-run.fish \
  -o /tmp/setup-midi.fish
fish /tmp/setup-midi.fish
```

Or use an existing clone:

```fish
cd ~/Projects/midi
git pull --ff-only
sudo -v
bash ./install.sh --reset-config
systemctl --user import-environment WAYLAND_DISPLAY SWAYSOCK XDG_CURRENT_DESKTOP
systemctl --user restart traktor-system-controller.service
```

`--reset-config` backs up the current root configuration before activating the
new defaults. Script-slot definitions and model hooks can then be edited in the
installed configuration directory.

Unplug and reconnect both controllers after installation. A graphical prompt
asks whether each connected unit should become a system controller.

## Default F1 map

[![F1 Linux operations map](assets/f1-linux-ops.svg)](docs/VISUAL_MAPPING.md#f1-desktop--script-surface)

Normal pads control applications, workspaces and Linux desktop operations.
Hold the physical F1 `SHIFT` button to access sixteen independent script slots.
The knobs control audio, microphone, brightness and bass presets. The faders
control Sway gaps and three local-model parameters.

## Default X1 map

[![X1 Linux operations map](assets/x1-linux-ops.svg)](docs/VISUAL_MAPPING.md#x1-system-operations--model-console)

The eight upper knobs configure model generation values. The upper buttons
open Ollama/Odysseus and system diagnostics. The center section handles audio,
network, Bluetooth, Sway and package operations. The transport section exposes
monitoring and maintenance tools.

## Configuration model

The active root is:

```text
~/.config/traktor-system-controller/config.json
```

It includes modular fragments:

```text
~/.config/traktor-system-controller/defaults/actions.json
~/.config/traktor-system-controller/defaults/model.json
~/.config/traktor-system-controller/defaults/scripts.json
~/.config/traktor-system-controller/defaults/visuals.json
~/.config/traktor-system-controller/defaults/f1.json
~/.config/traktor-system-controller/defaults/x1.json
```

Objects merge recursively and mapping lists concatenate. Keep the defaults
unchanged and add overrides to `config.json`, or edit the installed fragments
for a complete custom layout.

A normal mapping:

```json
{
  "device": "f1",
  "control": "grid_1",
  "kind": "press",
  "action": "browser",
  "enabled": true
}
```

A script slot on the F1 Shift layer:

```json
{
  "device": "f1",
  "control": "grid_2",
  "kind": "press",
  "action": "script_slot",
  "slot": "codex",
  "requires": ["f1.shift"],
  "enabled": true
}
```

## Script slots

Edit `defaults/scripts.json`:

```json
{
  "script_slots": {
    "codex": {
      "label": "Codex CLI",
      "enabled": true,
      "command": ["foot", "fish", "-lc", "codex; exec fish"]
    },
    "my_backup": {
      "label": "Run backup",
      "enabled": true,
      "confirm": "Run the backup now?",
      "command": ["/home/otp/.local/bin/backup-projects"]
    }
  }
}
```

Disabled slots remain visible in the layout but execute nothing. Commands may
be arrays or shell strings and support `{home}`, `{device}`, `{control}`,
`{value}`, `{percent}`, `{slot}` and other event placeholders.

## Model-control knobs

The default model parameters are:

| Parameter | Range | Default control |
|---|---:|---|
| `temperature` | `0.00–2.00` | X1 FX1 Dry/Wet; F1 Fader 2 |
| `top_p` | `0.05–1.00` | X1 FX1 Knob 1; F1 Fader 3 |
| `repeat_penalty` | `0.80–1.50` | X1 FX1 Knob 2 |
| `max_tokens` | `128–8192` | X1 FX1 Knob 3 |
| `context_length` | `1024–32768` | X1 FX2 Dry/Wet; F1 Fader 4 |
| `threads` | `1–8` | X1 FX2 Knob 1 |
| `gpu_layers` | `0–80` | X1 FX2 Knob 2 |
| `seed` | `0–9999` | X1 FX2 Knob 3 |

Values are written atomically to:

```text
~/.config/traktor-system-controller/model-controls.json
```

After each change, the executable hook is called with:

```text
model-controls-updated PARAMETER VALUE STATE_FILE
```

The bundled hook copies the state to an Ollama-oriented JSON file. Replace it
to update an Ollama Modelfile, an OpenAI-compatible request template, Aider,
Odysseus, Autocode or another local-agent configuration.

## Visual themes

![Controller visual themes](assets/visual-themes.svg)

```fish
traktor-system-controller --list-themes
traktor-system-controller --set-theme neon
systemctl --user restart traktor-system-controller.service
```

F1 colors reflect action categories. X1 uses coordinated brightness because its
LEDs are single-color. Pressed controls flash at full brightness.

## Connection consent

Default policy:

```json
{
  "connection": {
    "policy": "prompt",
    "remember": true
  }
}
```

Manage decisions manually:

```fish
traktor-system-controller --approve-connected
traktor-system-controller --deny-connected
traktor-system-controller --forget-device-decisions
```

Set `policy` to `always`, `prompt` or `never`.

## Validate and troubleshoot

```fish
traktor-system-controller --list-devices
traktor-system-controller --validate-config
traktor-system-controller --show-layout
traktor-system-controller --model-state

systemctl --user stop traktor-system-controller.service
traktor-system-controller --dry-run
traktor-system-controller --monitor

journalctl --user -u traktor-system-controller.service -f
```

`--dry-run` reads real hardware and prints actions without executing them.
`--monitor` prints normalized events without matching any actions.

Detailed references:

- [`docs/LAYOUT.md`](docs/LAYOUT.md) — exact default bindings.
- [`docs/VISUAL_MAPPING.md`](docs/VISUAL_MAPPING.md) — visual maps and LED themes.
- [`docs/CONFIGURATION.md`](docs/CONFIGURATION.md) — overrides, script slots,
  model knobs, connection policy and safety.
- [`docs/SYSTEM_ACTIONS.md`](docs/SYSTEM_ACTIONS.md) — monitoring and maintenance
  commands.

## Safety

- No passwordless `sudo` rule is installed.
- Full system update opens an interactive terminal and asks for confirmation.
- Reboot and power-off require a graphical confirmation.
- Controllers remain inactive until connection consent is granted.
- Unknown or disabled script slots do not execute.
- X1 raw mode restores the kernel driver during normal shutdown.

## Development validation

```bash
python -m py_compile traktor-system-controller.py traktor-controller.py traktor_controller/*.py
python -m unittest discover -s tests -v
TRAKTOR_CONTROLLER_BACKEND=$PWD/traktor-system-controller.py \
  python traktor-controller.py --config config.default.json --validate-config
bash -n install.sh helpers/system-actions examples/model-controls-updated
```

## License

MIT
