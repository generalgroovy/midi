# Visual mapping

The diagrams match the default `linux-ops` configuration. Cyan identifies
focused-window operations, magenta model controls, blue applications, purple
workspaces, orange audio, green monitoring, yellow maintenance and red system
actions.

## F1 desktop, scripts and model controls

![F1 Linux operations map](../assets/f1-linux-ops.svg)

The normal layer handles desktop flow. Hold `SHIFT` for the script labels shown
under the pad actions and for the four knob-based model parameters. Knob 3 on
the normal layer dims both controllers' hardware lights and persists the value.

## X1 focused-window cockpit

![X1 Linux operations map](../assets/x1-linux-ops.svg)

The upper eight knobs continuously control position, size, opacity, border,
gaps and target output. Upper buttons apply predictable geometry presets. The
transport section controls windows normally and becomes a diagnostics surface
while `HOTCUE` is held.

## Hardware feedback

- F1 RGB pads use action-category colors and brighten while pressed.
- X1 mapped buttons use idle and pressed brightness in raw-USB mode.
- F1 Knob 3 scales all F1 RGB/button output and all X1 LED values live.
- The brightness value is stored in
  `~/.config/traktor-system-controller/light-brightness.json`.
- `blackout` remains fully dark except for press feedback, which is also scaled
  by the hardware-light knob.

## Theme selection

```fish
traktor-system-controller --list-themes
traktor-system-controller --set-theme category
systemctl --user restart traktor-system-controller.service
```
