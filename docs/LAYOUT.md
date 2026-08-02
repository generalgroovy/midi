# Default `linux-ops` layout

The authoritative machine-readable mappings are `defaults/f1.json` and
`defaults/x1.json`. Run `traktor-system-controller --show-layout` to inspect the
installed merged configuration.

## F1 normal layer

| Area | Control | Action |
|---|---|---|
| Knobs | 1 / 2 / 3 / 4 | output volume / microphone volume / brightness / bass preset |
| Faders | 1 / 2 / 3 / 4 | Sway gaps / temperature / top_p / context length |
| Utility | Sync / Quant / Capture | network / Bluetooth / screenshot |
| Utility | Reverse / Type / Size / Browse | clipboard / notifications / displays / windows |
| Encoder | turn / push | workspace next-prev / app launcher |
| Pads 1–4 | | browser / terminal / files / projects |
| Pads 5–8 | | workspaces 1–4 |
| Pads 9–12 | | recording / audio / audio graph / dashboard |
| Pads 13–16 | | config / layout / logs / lock |
| Play 1–4 | | play-pause / previous / next / mute output |

## F1 Shift layer

Pads 1–16 map to:

```text
autocode  codex  ollama  odysseus
flux2     github_midi  aider  opencode
ollama_logs  odysseus_status  model_hook  controller_repo
custom_01  custom_02  custom_03  custom_04
```

## X1 model and status bank

| Control | Normal | Shift |
|---|---|---|
| FX1 On | model state | custom_05 |
| FX1 buttons 1–3 | Ollama status / Ollama models / Odysseus | custom_06–08 |
| FX2 On | dashboard | custom_09 |
| FX2 buttons 1–3 | journal errors / failed services / disk usage | custom_10–12 |
| FX1 knobs | temperature / top_p / repeat penalty / max tokens | — |
| FX2 knobs | context / threads / GPU layers / seed | — |

## X1 center and transport

| Control | Action |
|---|---|
| Browse encoders A/B | output / microphone volume |
| Loop encoders A/B | brightness / workspace navigation |
| Browse pushes A/B | audio / network settings |
| Loop pushes A/B | Bluetooth / PipeWire graph |
| Deck FX A1/A2 | restart controller / reload Sway |
| Deck FX B1/B2 | package check / confirmed system update |
| Deck A transport | system info, sensors, network, ports, controller logs, kernel log, processes, lock |
| Deck B transport | USB, mounts, orphans, cache, user services, timers, recording, power menu |
