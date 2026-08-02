# System monitoring and maintenance actions

The helper `helpers/system-actions` centralizes Linux-specific operations. This
keeps JSON mappings readable and provides graceful fallbacks.

| Action | Tool or behavior |
|---|---|
| `dashboard` | `btop` process/resource dashboard |
| `system-info` | `fastfetch` hardware/system summary |
| `sensors` | `lm_sensors` thermal/voltage readings |
| `network-monitor` | `bmon` interface throughput |
| `open-ports` | `ss -tulpn` listeners |
| `journal-errors` | current-boot priority errors |
| `kernel-log` | current boot kernel journal |
| `failed-services` | system and user failed units |
| `controller-logs` | live controller service journal |
| `disk-usage` | `ncdu` home-directory browser |
| `mounts` | `findmnt` hierarchy |
| `usb-devices` | `lsusb` and USB topology |
| `user-services` | running user services |
| `system-timers` | system and user timers |
| `orphan-packages` | `pacman -Qtdq` |
| `package-cache` | package-cache size and recent files |
| `package-updates` | `checkupdates` or `pacman -Qu` |
| `system-update` | interactive `garuda-update` or `sudo pacman -Syu` |
| `screen-record-toggle` | starts/stops `wf-recorder` |
| `screenshot` | region selection with `slurp` and `grim` |
| `power-menu` | Wofi power selector with reboot/off confirmation |

The helper never installs a passwordless sudo rule. Update commands run in an
interactive terminal so the normal authentication boundary remains visible.
