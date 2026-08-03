# Default `linux-ops` layout

The default deliberately avoids repeated action signatures on each controller.
F1 is the everyday desktop surface. X1 is the window-management, layout,
diagnostics and focused model-configuration surface.

## F1: desktop, audio and scripts

| Area | Control | Default action |
|---|---|---|
| Knobs | 1 / 2 / 3 / 4 | output volume / microphone volume / screen brightness / controller-light brightness |
| Faders | 1 / 2 / 3 / 4 | Sway gaps / pointer acceleration / color temperature / touchpad scroll factor |
| Utility | Sync / Quant / Capture | network / Bluetooth / screenshot |
| Utility | Reverse / Type / Size / Browse | clipboard / notifications / displays / window picker |
| Encoder | turn / push | previous-next workspace / application launcher |
| Pads 1–4 | | browser / terminal / files / projects |
| Pads 5–8 | | workspaces 1–4 |
| Pads 9–12 | | recording / audio panel / PipeWire graph / quick settings |
| Pads 13–16 | | config / layout / logs / **close focused window** |
| Play 1–4 | | play-pause / previous / next / output mute |

Knob 4 writes `0–100` to:

```text
~/.config/traktor-system-controller/controller-brightness
```

Both controllers watch this file and update their hardware LEDs live.

### F1 Shift layer

Pads 1–16 map to:

```text
autocode  codex  ollama  odysseus
flux2     github_midi  aider  opencode
ollama_logs  odysseus_status  model_hook  controller_repo
custom_01  custom_02  custom_03  custom_04
```

## X1: windows, layouts and diagnostics

### Upper buttons

| Control | Normal | Shift |
|---|---|---|
| FX1 On | system dashboard | custom_05 |
| FX1 buttons 1–3 | boot errors / failed services / sensors | custom_06–08 |
| FX2 On | system information | custom_09 |
| FX2 buttons 1–3 | package check / network monitor / disk usage | custom_10–12 |

### Upper knobs

| Control | Action |
|---|---|
| FX1 Dry/Wet | model temperature |
| FX1 Knob 1 | model top_p |
| FX1 Knob 2 | model context length |
| FX1 Knob 3 | model max tokens |
| FX2 Dry/Wet | floating-window horizontal position |
| FX2 Knob 1 | floating-window vertical position |
| FX2 Knob 2 | focused-window width |
| FX2 Knob 3 | focused-window height |

Absolute X/Y placement is intended for floating windows. Width and height are
calculated against the active output.

### Encoders and center controls

| Control | Action |
|---|---|
| A/B Browse turn | move focused window horizontally / vertically |
| A/B Loop turn | resize focused window width / height |
| A/B Browse push | move container to left / right output |
| A/B Loop push | floating / fullscreen toggle |
| Deck A FX1/FX2 | focus left / right output |
| Deck B FX1/FX2 | center floating window / toggle border |

Relative encoders remain useful for tiled windows: Sway interprets move commands
as tree reordering and resize commands as split adjustment.

### Transport

Deck A controls focus navigation: left, right, up, down, parent, child, lock and
sticky mode.

Deck B controls layouts: tabbed, stacking, horizontal split, vertical split,
layout cycle, tiled/floating focus switch, send to scratchpad and show
scratchpad.

`HOTCUE` opens the power menu. The only default close-window binding is F1 Pad
16, reducing accidental duplicate close commands.
