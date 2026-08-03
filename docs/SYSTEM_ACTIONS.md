# Linux, Sway and maintenance actions

`helpers/system-actions` centralizes operations that need shell logic, tool
fallbacks or output geometry. Straightforward Sway actions remain direct
commands in `defaults/actions.json`.

## Focused-window operations

| Action | Behavior |
|---|---|
| `close_focused_window` | `swaymsg kill`; closes only the focused container |
| `window-preset center` | Floating centered window using 72% × 76% of the focused output |
| `window-preset left/right` | Left or right half with margins |
| `window-preset top/bottom` | Top or bottom half with margins |
| `window-preset max` | Maximum floating size inside output margins |
| `window-preset pip` | Bottom-right picture-in-picture placement |
| `window-preset reset` | Return to tiling, opacity 1 and normal border |
| X/Y knob actions | Position the focused floating window across all active outputs |
| Width/height knobs | Enable floating mode and resize the focused window |
| Output knob | Select an active output ordered by global X/Y position |
| Browse/loop encoders | Focus or move containers horizontally and vertically |

The preset helper reads the focused output and its rectangle from Sway using
`swaymsg` and `jq`; dimensions are therefore based on the actual output rather
than a hard-coded screen size.

## Desktop actions

| Action | Tool or behavior |
|---|---|
| `clipboard-history` | `cliphist`, Wofi and `wl-copy` |
| `notifications` | Toggle SwayNC, or restore through Mako |
| `notification-dnd` | Toggle notification do-not-disturb |
| `network-settings` | Open `nmtui` in Foot |
| `bluetooth-settings` | Open Blueman, falling back to `bluetoothctl` |
| `screen-record-toggle` | Start or stop `wf-recorder` using a PID file |
| `screenshot` | Select a region with `slurp` and capture with `grim` |

## HOTCUE diagnostics

| Action | Tool or behavior |
|---|---|
| `system-info` | `fastfetch` |
| `sensors` | `lm_sensors` readings |
| `network-monitor` | `bmon` throughput dashboard |
| `open-ports` | `ss -tulpn` listeners |
| `journal-errors` | Current-boot priority errors |
| `failed-services` | Failed system and user units |
| `top-processes` | `btop` |
| `kernel-log` | Current boot kernel journal |
| `usb-devices` | USB topology and device list |
| `mounts` | `findmnt` hierarchy |
| `package-updates` | `checkupdates` or `pacman -Qu` |
| `user-services` | Running user services |
| `system-timers` | System and user timers |
| `controller-logs` | Live controller user-service journal |
| `power-menu` | Wofi selector with confirmation for reboot and poweroff |
| `controller-restart` | Restart the controller user service |

No passwordless sudo rule is installed. Any privileged maintenance command must
run in an interactive terminal and retain the normal authentication boundary.
