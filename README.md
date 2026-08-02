# Traktor X1/F1 Linux System Controller

Use Native Instruments Traktor Kontrol X1 MK1 and F1 controls as global system
controls under Garuda Linux and Sway.

The current hardware backends are:

| Controller | USB ID | Linux backend |
|---|---:|---|
| Traktor Kontrol X1 MK1 | `17cc:2305` | `snd-usb-caiaq` → evdev |
| Traktor Kontrol F1 | `17cc:1120` | USB HID → hidapi |

These devices do not expose ALSA MIDI ports in this setup. The service reads
their native Linux interfaces directly and translates buttons, encoders, knobs
and faders into commands such as:

- launch Firefox, Foot, Thunar or custom applications
- control PipeWire volume and microphone mute through `wpctl`
- control media through `playerctl`
- switch Sway workspaces through `swaymsg`
- select EasyEffects bass/EQ presets
- control display brightness

## Install or upgrade

```bash
cd ~/Projects
git clone https://github.com/generalgroovy/midi.git
cd midi
bash ./install.sh
```

For an existing clone:

```bash
cd ~/Projects/midi
git pull --ff-only
bash ./install.sh
```

Unplug and reconnect both controllers after installation so the udev access
rules are applied.

The installer adds:

```text
~/.local/bin/traktor-system-controller
~/.config/traktor-system-controller/config.json
~/.config/systemd/user/traktor-system-controller.service
/etc/udev/rules.d/70-traktor-system-controller.rules
```

On upgrades, an existing configuration is preserved and the latest example is
written to:

```text
~/.config/traktor-system-controller/config.example.json
```

The MIDI-only configuration format from the first repository revision is not
compatible with the native evdev/HID mapping format.

## Detect the controllers

```bash
traktor-system-controller --list-devices
```

Expected output resembles:

```text
X1 MK1 evdev: path=/dev/input/event... usb=17cc:2305
F1 HID: path=... interface=... usb=17cc:1120
```

The old `--list-ports` option is retained as an alias.

Low-level diagnostics:

```bash
lsusb | grep -Ei '17cc|traktor|kontrol'
sudo evtest
sudo hid-recorder /dev/hidraw4
```

## Learn controls

Stop the service while monitoring:

```bash
systemctl --user stop traktor-system-controller.service
traktor-system-controller --monitor
```

Move or press one physical control at a time. Events are normalized to:

```text
device=x1 control=BTN_0 kind=press value=1 ...
device=x1 control=ABS_X kind=relative value=1 ...
device=f1 control=grid_1 kind=press value=1 ...
device=f1 control=knob_1 kind=absolute value=2048 min=0 max=4096 ...
```

Edit:

```text
~/.config/traktor-system-controller/config.json
```

Restart and inspect logs:

```bash
systemctl --user restart traktor-system-controller.service
journalctl --user -u traktor-system-controller.service -f
```

## Mapping examples

Open Firefox from F1 pad 1:

```json
{
  "device": "f1",
  "control": "grid_1",
  "kind": "press",
  "action": "browser"
}
```

Use F1 knob 1 for system output volume:

```json
{
  "device": "f1",
  "control": "knob_1",
  "kind": "absolute",
  "action": "volume_absolute"
}
```

Use an X1 encoder for relative volume after learning its reported `ABS_*`
control:

```json
{
  "device": "x1",
  "control": "ABS_X",
  "kind": "relative",
  "action": "volume_relative",
  "sensitivity": 1
}
```

Use an X1 button after learning its reported `BTN_*` control:

```json
{
  "device": "x1",
  "control": "BTN_0",
  "kind": "press",
  "action": "play_pause"
}
```

Absolute mappings support `"invert": true`. Relative mappings support an
integer `"sensitivity"`.

## F1 control names

```text
grid_1 ... grid_16
play_1 ... play_4
sync
quant
capture
shift
reverse
type
size
browse
select_push
select_encoder
knob_1 ... knob_4
fader_1 ... fader_4
```

X1 names come from the Linux evdev interface and are printed by `--monitor`.
The X1 MK1 kernel driver exposes buttons as `BTN_*`, its analog controls as
`ABS_HAT*`, and its four wrapped encoders as `ABS_X`, `ABS_Y`, `ABS_Z`, and
`ABS_MISC`.

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
stronger low-frequency processing. Map an absolute knob:

```json
{
  "device": "f1",
  "control": "knob_2",
  "kind": "absolute",
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

## Technical references

- Linux `snd-usb-caiaq` supports USB `17cc:2305` and exposes X1 controls through
  the Linux input subsystem.
- Mixxx documents the F1 HID report layout used by this service.
- The project currently targets the original X1/MK1. X1 MK2 and MK3 use
  different USB IDs and protocols and require separate backends.

## License

MIT
