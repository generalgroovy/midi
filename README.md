# Traktor X1/F1 Linux System Controller

Use a Native Instruments Traktor Kontrol X1 MK1 and F1 as global desktop,
media, audio and Sway controls on Garuda Linux.

| Controller | USB ID | Backend |
|---|---:|---|
| X1 MK1 | `17cc:2305` | `snd-usb-caiaq` evdev |
| F1 | `17cc:1120` | HID/hidapi |

## Install or upgrade

```fish
cd ~/Projects
if test -d midi/.git
    cd midi
    git pull --ff-only
else
    git clone https://github.com/generalgroovy/midi.git
    cd midi
end
bash ./install.sh --reset-config
```

`--reset-config` backs up an existing configuration before activating the new
default. Omit it to retain the current `config.json`.

Unplug and reconnect both controllers after installation.

## Verify and test

```fish
traktor-system-controller --list-devices
traktor-system-controller --validate-config
traktor-system-controller --show-layout
systemctl --user stop traktor-system-controller.service
traktor-system-controller --dry-run
```

`--dry-run` reads both controllers and prints the command that each mapping
would execute without running it. `--monitor` prints raw and semantic control
events without matching actions.

## Configuration

The active file is:

```text
~/.config/traktor-system-controller/config.json
```

The default root includes modular files:

```text
~/.config/traktor-system-controller/defaults/actions.json
~/.config/traktor-system-controller/defaults/f1.json
~/.config/traktor-system-controller/defaults/x1.json
```

Lists are concatenated and objects are recursively merged. Add overrides to
`config.json`, edit the fragments, or replace the includes with your own files.

Mappings use:

```json
{
  "device": "f1",
  "control": "grid_1",
  "kind": "press",
  "action": "browser",
  "enabled": true
}
```

X1 kernel names are translated to physical names such as `deck_a_play`,
`deck_b_browse_encoder`, `fx1_knob_1` and `shift`. A mapping can use layers:

```json
{
  "device": "x1",
  "control": "deck_a_play",
  "kind": "press",
  "action": "previous_track",
  "requires": "x1.shift"
}
```

Available command placeholders include `{home}`, `{device}`, `{control}`,
`{raw_control}`, `{value}`, `{delta}`, `{ratio}` and `{percent}`.

See [docs/LAYOUT.md](docs/LAYOUT.md) for the complete default surface.

## Default concept

The F1 is the application/workspace/audio pad surface. The X1 is the compact
media and rotary-control surface. Both expose play/pause, track navigation,
volume, brightness, workspace and application controls so either controller
remains useful by itself.

## Service

```fish
systemctl --user import-environment WAYLAND_DISPLAY SWAYSOCK XDG_CURRENT_DESKTOP
systemctl --user restart traktor-system-controller.service
journalctl --user -u traktor-system-controller.service -f
```

Add to `~/.config/sway/config`:

```text
exec_always sh -lc 'systemctl --user import-environment WAYLAND_DISPLAY SWAYSOCK XDG_CURRENT_DESKTOP; systemctl --user restart traktor-system-controller.service'
```

## Validation

```bash
python -m py_compile traktor-system-controller.py traktor-controller.py traktor_controller/*.py
python -m unittest discover -s tests -v
bash -n install.sh
```

## License

MIT
