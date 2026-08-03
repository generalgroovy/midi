# Visual mapping and hardware feedback

## Physical controller overview

![Unified physical controller overview](../assets/layout-overview.svg)

The overview is drawn as a front-panel reference rather than an abstract action
grid. Control families are positioned like the passed controller photographs:

- F1 knobs across the top, four vertical faders, 4×4 RGB pad matrix and bottom
  media triggers;
- X1 dual FX banks, center browse/loop controls and two lower transport decks.

The authoritative mappings are `defaults/f1.json` and `defaults/x1.json`.

## F1 desktop and model surface

Normal layer:

| Hardware | Action |
|---|---|
| Knob 1 | Output volume |
| Knob 2 | Microphone volume |
| Knob 3 | F1/X1 hardware-light brightness |
| Knob 4 | Display brightness |
| Fader 1 | Sway gaps |
| Fader 2 | Pointer acceleration |
| Fader 3 | Color temperature |
| Fader 4 | Touchpad scroll factor |
| Reverse | Close focused window |
| Type / Size / Browse | Fullscreen / floating / window switcher |
| Select turn / push | Workspace navigation / application launcher |
| Pads 1–16 | Desktop, workspace, recording, settings and lock actions |
| Play 1–4 | Play-pause, previous, next and output mute |

Hold F1 `SHIFT` to turn the four knobs and four faders into model controls and
the sixteen pads into configurable script slots.

## X1 window cockpit

| Hardware group | Action family |
|---|---|
| FX1 buttons | Center, left half, right half and maximum presets |
| FX2 buttons | Top half, bottom half, PiP and reset presets |
| FX1 knobs | Absolute window X, Y, width and height |
| FX2 knobs | Opacity, border width, Sway gaps and output selection |
| Browse encoders | Relative horizontal and vertical movement |
| Loop encoders | Relative width and height resizing |
| Browse pushes | Move window to left or right output |
| Loop pushes | Toggle floating or fullscreen |
| Deck A transport | Focus navigation, lock and sticky mode |
| Deck B transport | Layouts, focus mode and scratchpad |

Hold X1 `SHIFT` for the eight upper custom-script slots. Hold `HOTCUE` for the
sixteen diagnostic and maintenance actions printed in `--show-layout`.

## Live controller-light brightness

F1 Knob 3 writes a persistent brightness percentage. F1 and X1 visual workers
poll it and rescale:

- all sixteen F1 RGB pads;
- F1 utility and play LEDs;
- X1 mapped, idle and pressed LED levels.

The state file is:

```text
~/.config/traktor-system-controller/controller-brightness
```

Set a default or alternate path in `defaults/visuals.json`.

## Themes

| Theme | Behavior |
|---|---|
| `category` | action-category colors |
| `neon` | high-saturation colors |
| `matrix` | green terminal palette |
| `sunset` | purple-red-orange palette |
| `mono` | low-distraction neutral palette |
| `blackout` | dark until pressed |

```fish
traktor-system-controller --set-theme category
systemctl --user restart traktor-system-controller.service
```

Theme colors and the global dimmer multiply together. `blackout` remains dark
at idle regardless of the stored brightness.
