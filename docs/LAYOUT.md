# Default `linux-ops` layout

The default is deliberately split by purpose. The F1 is the daily desktop and
launcher surface. The X1 is the focused-window geometry, layout and operations
surface. No enabled action signature is repeated on the same controller.

Run `traktor-system-controller --show-layout` for the exact installed map.

## F1 — desktop, media, lights and local-model controls

### Normal layer

| Area | Control | Action |
|---|---|---|
| Knobs | 1 | Output volume |
| Knobs | 2 | Microphone volume |
| Knobs | 3 | F1 and X1 hardware-light brightness, 0–100% |
| Knobs | 4 | Display brightness |
| Utility | Sync | Toggle microphone mute |
| Utility | Quant | Toggle notification do-not-disturb |
| Utility | Capture | Region screenshot |
| Utility | Reverse | Close the currently focused window with `swaymsg kill` |
| Utility | Type | Toggle focused-window fullscreen |
| Utility | Size | Toggle focused-window floating mode |
| Utility | Browse | Window switcher |
| Encoder | Turn / push | Previous-next workspace / application launcher |
| Pads 1–4 | | Browser / terminal / files / projects |
| Pads 5–8 | | Workspaces 1–4 |
| Pads 9–12 | | Screen recording / clipboard / displays / notifications |
| Pads 13–16 | | Audio / network / Bluetooth / lock |
| Play 1–4 | | Play-pause / previous / next / output mute |

### Model layer

Hold the F1 `SHIFT` button while turning the four knobs:

| Shift control | Parameter |
|---|---|
| Shift + Knob 1 | `temperature` |
| Shift + Knob 2 | `top_p` |
| Shift + Knob 3 | `repeat_penalty` |
| Shift + Knob 4 | `max_tokens` |

The four faders provide the remaining parameters:

| Fader | Parameter |
|---|---|
| 1 | `context_length` |
| 2 | `threads` |
| 3 | `gpu_layers` |
| 4 | `seed` |

### Script layer

Hold `SHIFT` while pressing Pads 1–16:

```text
autocode  codex  ollama  odysseus
flux2     github_midi  aider  opencode
ollama_logs  odysseus_status  model_hook  controller_repo
custom_01  custom_02  custom_03  custom_04
```

## X1 — focused-window cockpit

### Eight geometry knobs

| Control | Action |
|---|---|
| FX1 Dry/Wet | Move focused floating window across the virtual desktop X axis |
| FX1 Knob 1 | Move it across the virtual desktop Y axis |
| FX1 Knob 2 | Set window width |
| FX1 Knob 3 | Set window height |
| FX2 Dry/Wet | Set window opacity |
| FX2 Knob 1 | Set border width |
| FX2 Knob 2 | Set global Sway inner gaps |
| FX2 Knob 3 | Move the focused container to an active output |

Position and size controls automatically enable floating mode. Output selection
sorts active screens by their global X/Y position.

### Upper buttons: window presets

| Button | Normal | Shift |
|---|---|---|
| FX1 On | Centered window | `custom_05` |
| FX1 Button 1 | Left half | `custom_06` |
| FX1 Button 2 | Right half | `custom_07` |
| FX1 Button 3 | Maximum usable area | `custom_08` |
| FX2 On | Top half | `custom_09` |
| FX2 Button 1 | Bottom half | `custom_10` |
| FX2 Button 2 | Picture-in-picture | `custom_11` |
| FX2 Button 3 | Reset tiling, opacity and border | `custom_12` |

### Center section

| Control | Action |
|---|---|
| Browse encoder A/B | Focus left-right / up-down |
| Loop encoder A/B | Move container left-right / up-down |
| Browse push A/B | Focus parent / child |
| Loop push A/B | Toggle floating / fullscreen |
| Deck FX A1/A2 | Horizontal / vertical split |
| Deck FX B1/B2 | Tabbed / stacking layout |

### Transport section

Without `HOTCUE`, the transport section is pure window navigation and movement.
Hold `HOTCUE` to temporarily expose system diagnostics.

| Control group | Normal | Hold HOTCUE |
|---|---|---|
| Deck A In/Out/Beat | Focus left/right/up/down | System info / sensors / network / ports |
| Deck A Cue/Cup/Play/Sync | Move left/right/up/down | Journal / failed services / processes / kernel log |
| Deck B In/Out | Move to output left/right | USB devices / mounts |
| Deck B Beat Left/Right | Previous/next workspace | Package updates / user services |
| Deck B Cue/Cup | Scratchpad show/move | Timers / controller logs |
| Deck B Play/Sync | Sticky toggle / focus mode toggle | Power menu / controller restart |
