# Visual mapping and hardware feedback

## F1 desktop surface

![F1 desktop map](../assets/f1-linux-ops.svg)

The F1 is optimized for high-frequency desktop actions. Its fourth knob is the
global hardware-light dimmer. Pad 16 closes the currently focused Sway
container with `swaymsg kill`. Hold `SHIFT` to replace the normal pad layer with
the sixteen script slots shown in the diagram.

## X1 window console

![X1 window map](../assets/x1-linux-ops.svg)

The X1 is optimized for spatial window control:

- Browse encoders move the focused container on X and Y.
- Loop encoders resize width and height.
- The right FX knobs set absolute X, Y, width and height.
- Output buttons move or focus across physical screens.
- Transport controls navigate focus, select layouts and use the scratchpad.

Absolute X/Y controls work best after enabling floating mode. Relative encoders
also work on tiled containers, where Sway reorders or resizes the layout tree.

## Live controller-light brightness

F1 Knob 4 writes a persistent brightness percentage. F1 and X1 visual workers
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
