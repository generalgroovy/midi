# Default desktop layout

Run `traktor-system-controller --show-layout` for the authoritative active
profile. The default is intentionally practical rather than DJ-oriented.

## F1

| Control | Action |
|---|---|
| Play 1 / 2 / 3 | Play-pause / previous / next |
| Play 4 | Toggle output mute |
| Pads 1–4 | Browser / terminal / files / launcher |
| Pads 5–8 | Sway workspaces 1–4 |
| Pads 9–13 | Screenshot / audio controls / EasyEffects / lock / mic mute |
| Pads 15–16 | Previous / next workspace |
| Knobs 1–4 | Output volume / bass preset / brightness / microphone volume |
| Browse encoder | Relative output volume |
| Browse push | Toggle output mute |

Pad 14 is a disabled custom-script example. The four faders are retained as
disabled alternatives for volume, microphone, brightness and bass.

## X1 MK1

| Control | Action |
|---|---|
| Deck A/B Play | Play-pause |
| Shift + Deck A/B Play | Previous / next track |
| Deck A/B Cue | Previous / next track |
| Deck A/B Sync | Output mute / microphone mute |
| Deck A/B Browse encoder | Volume / brightness |
| Deck A/B Loop encoder | Seek / change workspace |
| Deck A Browse push | Terminal; Shift: launcher |
| Deck B Browse push | Browser; Shift: files |
| Deck FX1/FX2 buttons | Workspaces 1–4 |
| FX1/FX2 On | PipeWire controls / EasyEffects |
| FX buttons | Screenshot, track navigation, terminal, lock, browser |
| FX1/FX2 dry-wet | Output volume / bass preset |
| FX1/FX2 knob 1 | Brightness / microphone volume |

The X1 semantic aliases are derived from the stable `snd-usb-caiaq` evdev
layout. Override any raw-to-semantic name under `control_aliases.x1`.

## Profiles and layers

Set `active_profile` or launch with `--profile NAME`. Use `profile` or
`profiles` on individual mappings. Use `requires` and `unless` for held-button
layers; modifier tokens accept `x1.shift`, `x1:shift`, or same-device `shift`.
