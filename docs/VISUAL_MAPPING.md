# Visual default mapping

These diagrams are the repository-native reference for the active `desktop`
profile. They are generated from the same control names and actions used by the
configuration fragments.

## Traktor Kontrol F1

![Traktor Kontrol F1 default action map](../assets/f1-default-actions.svg)

Configuration source: [`defaults/f1.json`](../defaults/f1.json).

The F1 is the application, workspace and audio surface:

- Knobs: output volume, bass preset, brightness and microphone volume.
- Pads 1–4: browser, terminal, files and application launcher.
- Pads 5–8: Sway workspaces 1–4.
- Pads 9–13: screenshot, audio panel, EasyEffects, lock and microphone mute.
- Pads 15–16: previous and next workspace.
- Bottom buttons: play/pause, previous, next and output mute.
- Browse encoder: relative output volume; encoder push toggles output mute.
- Faders are disabled alternatives. Pad 14 is a disabled custom-script hook.
- `SYNC`, `QUANT`, `CAPTURE`, `SHIFT`, `REVERSE`, `TYPE` and `SIZE` are
  intentionally unmapped in the default profile.

## Traktor Kontrol X1 MK1

![Traktor Kontrol X1 MK1 default action map](../assets/x1-default-actions.svg)

Configuration source: [`defaults/x1.json`](../defaults/x1.json).

The X1 is the compact media, audio and rotary-control surface:

- Deck play buttons: play/pause. Hold `SHIFT` for previous/next track.
- Deck cues: previous/next track.
- Deck sync buttons: output mute and microphone mute.
- Browse encoders: relative output volume and brightness.
- Browse pushes: terminal/browser. Hold `SHIFT` for launcher/files.
- Loop encoders: media seek and relative workspace navigation.
- Deck FX buttons: workspaces 1–4.
- FX On buttons: PipeWire controls and EasyEffects.
- FX buttons: screenshot, lock, track navigation, terminal and browser.
- Dry/Wet knobs: output volume and bass preset.
- FX knob 1: brightness and microphone volume.
- FX knobs 2–3, loop pushes, transport `IN`, `OUT`, beat and `CUP` controls are
  intentionally unmapped. `HOTCUE` is a disabled custom-script hook.

## Color meaning

| Color | Meaning |
|---|---|
| Green | Media transport and seeking |
| Blue | Applications and launchers |
| Purple | Sway workspace control |
| Orange | Audio volume, mute and processing |
| Red | System actions such as brightness, screenshot and lock |
| Yellow | Modifier or Shift-layer behavior |
| Gray | Disabled mapping or intentionally unmapped control |

## Configuration model

The active root file is:

```text
~/.config/traktor-system-controller/config.json
```

It includes:

```text
~/.config/traktor-system-controller/defaults/actions.json
~/.config/traktor-system-controller/defaults/f1.json
~/.config/traktor-system-controller/defaults/x1.json
```

`actions.json` defines executable commands and X1 raw-to-semantic aliases.
`f1.json` and `x1.json` define control-to-action mappings.

A normal mapping:

```json
{
  "profile": "desktop",
  "device": "f1",
  "control": "grid_1",
  "kind": "press",
  "action": "browser",
  "enabled": true
}
```

A Shift-layer mapping:

```json
{
  "profile": "desktop",
  "device": "x1",
  "control": "deck_a_play",
  "kind": "press",
  "action": "previous_track",
  "requires": ["x1.shift"],
  "enabled": true
}
```

A control can remain visible as an optional hook by setting:

```json
"enabled": false
```

## Validate changes

```fish
traktor-system-controller --validate-config
traktor-system-controller --show-layout
systemctl --user stop traktor-system-controller.service
traktor-system-controller --dry-run
```

`--dry-run` reads real hardware and prints the command that would execute without
running it. Use `--monitor` when you need raw and semantic event names.