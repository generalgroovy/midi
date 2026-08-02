# MIDI System Controller

Use Native Instruments Traktor Kontrol X1 and F1 MIDI controls as global Linux
system controls under Garuda Linux and Sway.

The service translates MIDI notes, buttons, encoders, knobs and faders into
native commands such as:

- launch Firefox, Foot, Thunar or custom applications
- control PipeWire volume and microphone mute through `wpctl`
- control media through `playerctl`
- switch Sway workspaces or run arbitrary `swaymsg` commands
- select EasyEffects bass/EQ presets
- control display brightness

The design uses native MIDI events rather than emulated keyboard input, so it
works globally under Wayland without depending on the focused application.

## Requirements

- Garuda Linux or another Arch-based distribution
- Sway/Wayland
- PipeWire and WirePlumber
- a controller exposing an ALSA MIDI input port
- Traktor Kontrol X1 or F1 in MIDI mode

## Install

```bash
cd ~/Projects
git clone https://github.com/generalgroovy/midi.git
cd midi
bash ./install.sh
```

The installer adds:

```text
~/.local/bin/traktor-system-controller
~/.config/traktor-system-controller/config.json
~/.config/systemd/user/traktor-system-controller.service
```

## Detect the controllers

Put the X1/F1 into MIDI mode and run:

```bash
traktor-system-controller --list-ports
```

For ALSA-level diagnostics:

```bash
aconnect -l
aseqdump -l
```

## Learn MIDI controls

Stop the background service while learning mappings:

```bash
systemctl --user stop traktor-system-controller.service
traktor-system-controller --monitor
```

Move or press one physical control at a time. Monitor output reports the device,
message type, MIDI channel, note/controller number and value.

Edit:

```text
~/.config/traktor-system-controller/config.json
```

Replace and remove the example mappings that use numbers `999` and `998`.

Restart and inspect logs:

```bash
systemctl --user restart traktor-system-controller.service
journalctl --user -u traktor-system-controller.service -f
```

## Mapping examples

Open Firefox from an F1 note button:

```json
{
  "device": "f1",
  "type": "note",
  "channel": 0,
  "number": 42,
  "action": "browser"
}
```

Use an absolute F1 knob or fader for output volume:

```json
{
  "device": "f1",
  "channel": 0,
  "number": 21,
  "action": "volume_absolute"
}
```

Use an endless X1 encoder for relative volume:

```json
{
  "device": "x1",
  "channel": 0,
  "number": 14,
  "action": "volume_relative",
  "relative_mode": "twos-complement"
}
```

## Mapping types

- MIDI `note_on`: `button_mappings` with `"type": "note"`
- CC button: `button_mappings` with `"type": "cc_button"`
- absolute knob/fader: `cc_mappings` with an absolute action
- endless encoder: `cc_mappings` with a relative action

Supported relative encoder formats:

- `twos-complement`: clockwise `1`, counter-clockwise `127`
- `binary-offset`: clockwise `65`, counter-clockwise `63`
- `sign-magnitude`: clockwise `1`, counter-clockwise `65`

## Included actions

```text
browser
terminal
files
play_pause
next_track
previous_track
mute_output
mute_microphone
workspace_1
workspace_2
lock_screen
volume_absolute
volume_relative
brightness_absolute
brightness_relative
bass_preset_absolute
```

Custom actions can be command arrays or shell command strings in
`config.json`.

## EasyEffects bass control

Create output presets named `Bass-0` through `Bass-7`, with progressively
stronger low-frequency processing. Map an absolute knob to:

```json
{
  "device": "f1",
  "channel": 0,
  "number": 22,
  "action": "bass_preset_absolute"
}
```

## Sway environment

Add this line to `~/.config/sway/config` so the systemd user service receives
the active Sway and Wayland environment:

```text
exec_always sh -lc 'systemctl --user import-environment WAYLAND_DISPLAY SWAYSOCK XDG_CURRENT_DESKTOP; systemctl --user restart traktor-system-controller.service'
```

Reload Sway:

```bash
swaymsg reload
```

## Development validation

```bash
python -m py_compile traktor-system-controller.py
python -m json.tool config.example.json >/dev/null
bash -n install.sh
```

## License

MIT
