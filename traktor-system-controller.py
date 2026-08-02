#!/usr/bin/env python3
"""
Use Native Instruments Traktor Kontrol X1 MK1 and F1 controls as global
Linux system controls.

Backends:
  - X1 MK1 (USB 17cc:2305): Linux evdev via snd-usb-caiaq
  - F1     (USB 17cc:1120): HID via hidapi

Commands:
  traktor-system-controller --list-devices
  traktor-system-controller --monitor
  traktor-system-controller
"""

from __future__ import annotations

import argparse
import json
import struct
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

DEFAULT_CONFIG = Path.home() / ".config/traktor-system-controller/config.json"
DEVNULL = subprocess.DEVNULL

NI_VENDOR_ID = 0x17CC
X1_PRODUCT_ID = 0x2305
F1_PRODUCT_ID = 0x1120

X1_ENCODER_CODES = {"ABS_X", "ABS_Y", "ABS_Z", "ABS_MISC"}

F1_BUTTON_MASKS = {
    "grid_8": 0x00000001,
    "grid_7": 0x00000002,
    "grid_6": 0x00000004,
    "grid_5": 0x00000008,
    "grid_4": 0x00000010,
    "grid_3": 0x00000020,
    "grid_2": 0x00000040,
    "grid_1": 0x00000080,
    "grid_16": 0x00000100,
    "grid_15": 0x00000200,
    "grid_14": 0x00000400,
    "grid_13": 0x00000800,
    "grid_12": 0x00001000,
    "grid_11": 0x00002000,
    "grid_10": 0x00004000,
    "grid_9": 0x00008000,
    "select_push": 0x00040000,
    "browse": 0x00080000,
    "size": 0x00100000,
    "type": 0x00200000,
    "reverse": 0x00400000,
    "shift": 0x00800000,
    "capture": 0x02000000,
    "quant": 0x04000000,
    "sync": 0x08000000,
    "play_4": 0x10000000,
    "play_3": 0x20000000,
    "play_2": 0x40000000,
    "play_1": 0x80000000,
}

F1_ANALOG_OFFSETS = {
    "knob_1": 6,
    "knob_2": 8,
    "knob_3": 10,
    "knob_4": 12,
    "fader_1": 14,
    "fader_2": 16,
    "fader_3": 18,
    "fader_4": 20,
}


def log(message: str) -> None:
    print(message, flush=True)


def run_quiet(command: list[str] | str) -> None:
    try:
        if isinstance(command, str):
            subprocess.Popen(
                ["bash", "-lc", command],
                stdin=DEVNULL,
                stdout=DEVNULL,
                stderr=DEVNULL,
                start_new_session=True,
            )
        else:
            subprocess.Popen(
                command,
                stdin=DEVNULL,
                stdout=DEVNULL,
                stderr=DEVNULL,
                start_new_session=True,
            )
    except FileNotFoundError:
        log(f"Command not found: {command}")
    except Exception as exc:
        log(f"Could not run {command!r}: {exc}")


def load_config(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(
            f"Configuration not found: {path}\n"
            "Run install.sh or copy config.example.json there."
        )
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {path}: {exc}")


@dataclass(frozen=True)
class ControlEvent:
    device: str
    control: str
    kind: str
    value: int
    minimum: int = 0
    maximum: int = 1
    source: str = ""

    def describe(self) -> str:
        return (
            f"device={self.device} control={self.control} kind={self.kind} "
            f"value={self.value} min={self.minimum} max={self.maximum} "
            f"source={self.source}"
        )


class ActionDispatcher:
    def __init__(self, config: dict[str, Any]):
        self.actions: dict[str, list[str] | str] = config.get("actions", {})
        self.bass_presets: list[str] = config.get("bass_presets", [])
        self.last_bass_index: int | None = None

    @staticmethod
    def normalized_value(event: ControlEvent, invert: bool = False) -> float:
        span = event.maximum - event.minimum
        if span <= 0:
            return 0.0
        ratio = (event.value - event.minimum) / span
        ratio = min(max(ratio, 0.0), 1.0)
        return 1.0 - ratio if invert else ratio

    def dispatch(self, mapping: dict[str, Any], event: ControlEvent) -> None:
        action = str(mapping["action"])

        if action in self.actions:
            run_quiet(self.actions[action])
            return

        invert = bool(mapping.get("invert", False))

        if action == "volume_absolute":
            percent = round(self.normalized_value(event, invert) * 100)
            run_quiet(
                [
                    "wpctl",
                    "set-volume",
                    "-l",
                    "1.0",
                    "@DEFAULT_AUDIO_SINK@",
                    f"{percent}%",
                ]
            )
            return

        if action == "volume_relative":
            sensitivity = max(1, int(mapping.get("sensitivity", 1)))
            delta = event.value * sensitivity
            step = min(max(abs(delta), 1), 10)
            suffix = "+" if delta > 0 else "-"
            run_quiet(
                [
                    "wpctl",
                    "set-volume",
                    "-l",
                    "1.0",
                    "@DEFAULT_AUDIO_SINK@",
                    f"{step}%{suffix}",
                ]
            )
            return

        if action == "brightness_absolute":
            percent = max(1, round(self.normalized_value(event, invert) * 100))
            run_quiet(["brightnessctl", "set", f"{percent}%"])
            return

        if action == "brightness_relative":
            sensitivity = max(1, int(mapping.get("sensitivity", 1)))
            delta = event.value * sensitivity
            step = min(max(abs(delta), 1), 10)
            suffix = "+" if delta > 0 else "-"
            run_quiet(["brightnessctl", "set", f"{step}%{suffix}"])
            return

        if action == "bass_preset_absolute":
            if not self.bass_presets:
                log("No bass_presets configured.")
                return
            ratio = self.normalized_value(event, invert)
            index = min(len(self.bass_presets) - 1, int(ratio * len(self.bass_presets)))
            if index == self.last_bass_index:
                return
            self.last_bass_index = index
            preset = self.bass_presets[index]
            run_quiet(["easyeffects", "--load-preset", preset])
            log(f"Bass preset: {preset}")
            return

        log(f"Unknown action: {action}")


class EventRouter:
    def __init__(self, config: dict[str, Any], monitor: bool):
        self.monitor = monitor
        self.dispatcher = ActionDispatcher(config)
        self.mappings: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
        self.last_dispatch: dict[tuple[str, str, str], float] = {}

        for mapping in config.get("mappings", []):
            if not bool(mapping.get("enabled", True)):
                continue
            key = (
                str(mapping["device"]),
                str(mapping["control"]),
                str(mapping["kind"]),
            )
            self.mappings.setdefault(key, []).append(mapping)

    def emit(self, event: ControlEvent) -> None:
        if self.monitor:
            log(event.describe())
            return

        key = (event.device, event.control, event.kind)
        mappings = self.mappings.get(key, [])
        if not mappings:
            return

        if event.kind == "absolute":
            now = time.monotonic()
            if now - self.last_dispatch.get(key, 0.0) < 0.025:
                return
            self.last_dispatch[key] = now

        for mapping in mappings:
            self.dispatcher.dispatch(mapping, event)


def _event_code_name(ecodes: Any, event_type: int, code: int) -> str:
    name = ecodes.bytype.get(event_type, {}).get(code, str(code))
    if isinstance(name, list):
        return str(name[0])
    return str(name)


def discover_x1_devices() -> list[tuple[str, str]]:
    try:
        import evdev
    except ImportError:
        return []

    found: list[tuple[str, str]] = []
    for path in evdev.list_devices():
        try:
            device = evdev.InputDevice(path)
            if (
                device.info.vendor == NI_VENDOR_ID
                and device.info.product == X1_PRODUCT_ID
            ):
                found.append((path, device.name))
            device.close()
        except (PermissionError, OSError):
            continue
    return found


def x1_worker(
    path: str,
    emit: Callable[[ControlEvent], None],
    release: Callable[[], None],
) -> None:
    try:
        import evdev
        from evdev import ecodes

        device = evdev.InputDevice(path)
        log(f"Connected X1 MK1 evdev: {path} ({device.name})")
        previous_encoders: dict[str, int] = {}

        for event in device.read_loop():
            if event.type == ecodes.EV_KEY:
                control = _event_code_name(ecodes, event.type, event.code)
                if event.value == 1:
                    emit(
                        ControlEvent(
                            "x1",
                            control,
                            "press",
                            1,
                            source=path,
                        )
                    )
                elif event.value == 0:
                    emit(
                        ControlEvent(
                            "x1",
                            control,
                            "release",
                            0,
                            source=path,
                        )
                    )
                continue

            if event.type != ecodes.EV_ABS:
                continue

            control = _event_code_name(ecodes, event.type, event.code)

            if control in X1_ENCODER_CODES:
                previous = previous_encoders.get(control)
                previous_encoders[control] = int(event.value)
                if previous is None:
                    continue
                delta = ((int(event.value) - previous + 8) % 16) - 8
                if delta:
                    emit(
                        ControlEvent(
                            "x1",
                            control,
                            "relative",
                            delta,
                            minimum=-8,
                            maximum=7,
                            source=path,
                        )
                    )
                continue

            info = device.absinfo(event.code)
            emit(
                ControlEvent(
                    "x1",
                    control,
                    "absolute",
                    int(event.value),
                    int(info.min),
                    int(info.max),
                    path,
                )
            )
    except PermissionError:
        log(f"Permission denied reading X1 at {path}; reinstall udev rules and replug.")
    except OSError as exc:
        log(f"X1 disconnected: {path}: {exc}")
    except Exception as exc:
        log(f"X1 backend failed for {path}: {exc}")
    finally:
        release()


def discover_f1_devices() -> list[dict[str, Any]]:
    try:
        import hid
    except ImportError:
        return []

    try:
        return list(hid.enumerate(NI_VENDOR_ID, F1_PRODUCT_ID))
    except Exception as exc:
        log(f"Could not enumerate F1 HID devices: {exc}")
        return []


def _hid_path_text(path: Any) -> str:
    if isinstance(path, bytes):
        return path.decode(errors="replace")
    return str(path)


def _normalize_f1_report(data: Iterable[int]) -> bytes | None:
    report = bytes(data)
    if len(report) >= 22 and report[0] == 0x01:
        return report
    if len(report) >= 21:
        return b"\x01" + report
    return None


def f1_worker(
    path: Any,
    emit: Callable[[ControlEvent], None],
    release: Callable[[], None],
) -> None:
    device = None
    path_text = _hid_path_text(path)
    try:
        import hid

        device = hid.device()
        device.open_path(path)
        device.set_nonblocking(False)
        log(f"Connected F1 HID: {path_text}")

        previous_buttons: int | None = None
        previous_encoder: int | None = None
        previous_analog: dict[str, int] = {}

        while True:
            raw = device.read(64, 1000)
            if not raw:
                continue
            report = _normalize_f1_report(raw)
            if report is None:
                continue

            buttons = int.from_bytes(report[1:5], "little")
            if previous_buttons is not None:
                changed = previous_buttons ^ buttons
                for control, mask in F1_BUTTON_MASKS.items():
                    if not changed & mask:
                        continue
                    pressed = bool(buttons & mask)
                    emit(
                        ControlEvent(
                            "f1",
                            control,
                            "press" if pressed else "release",
                            1 if pressed else 0,
                            source=path_text,
                        )
                    )
            previous_buttons = buttons

            encoder = report[5]
            if previous_encoder is not None:
                delta = ((encoder - previous_encoder + 128) % 256) - 128
                if delta:
                    emit(
                        ControlEvent(
                            "f1",
                            "select_encoder",
                            "relative",
                            delta,
                            minimum=-128,
                            maximum=127,
                            source=path_text,
                        )
                    )
            previous_encoder = encoder

            for control, offset in F1_ANALOG_OFFSETS.items():
                value = struct.unpack_from("<H", report, offset)[0]
                previous = previous_analog.get(control)
                previous_analog[control] = value
                if previous is None or previous == value:
                    continue
                emit(
                    ControlEvent(
                        "f1",
                        control,
                        "absolute",
                        value,
                        minimum=0,
                        maximum=4096,
                        source=path_text,
                    )
                )
    except PermissionError:
        log(f"Permission denied reading F1 at {path_text}; reinstall udev rules and replug.")
    except OSError as exc:
        log(f"F1 disconnected: {path_text}: {exc}")
    except Exception as exc:
        log(f"F1 backend failed for {path_text}: {exc}")
    finally:
        if device is not None:
            try:
                device.close()
            except Exception:
                pass
        release()


class ControllerRuntime:
    def __init__(self, router: EventRouter):
        self.router = router
        self.active: set[tuple[str, str]] = set()
        self.lock = threading.Lock()

    def _start(
        self,
        key: tuple[str, str],
        target: Callable[..., None],
        *args: Any,
    ) -> None:
        with self.lock:
            if key in self.active:
                return
            self.active.add(key)

        def release() -> None:
            with self.lock:
                self.active.discard(key)

        threading.Thread(
            target=target,
            args=(*args, self.router.emit, release),
            daemon=True,
        ).start()

    def run(self) -> None:
        log("Watching for Traktor X1 MK1 and F1 controllers. Ctrl+C stops.")
        while True:
            for path, _name in discover_x1_devices():
                self._start(("x1", path), x1_worker, path)

            for info in discover_f1_devices():
                path = info.get("path")
                if path is None:
                    continue
                key_path = _hid_path_text(path)
                self._start(("f1", key_path), f1_worker, path)

            time.sleep(2.0)


def list_devices() -> int:
    found = False

    for path, name in discover_x1_devices():
        found = True
        print(
            f"X1 MK1 evdev: path={path} name={name!r} "
            f"usb={NI_VENDOR_ID:04x}:{X1_PRODUCT_ID:04x}"
        )

    for info in discover_f1_devices():
        found = True
        print(
            "F1 HID: "
            f"path={_hid_path_text(info.get('path'))!r} "
            f"interface={info.get('interface_number')} "
            f"serial={info.get('serial_number')!r} "
            f"usb={NI_VENDOR_ID:04x}:{F1_PRODUCT_ID:04x}"
        )

    if not found:
        print("No supported Traktor X1 MK1 or F1 devices found.")
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument(
        "--monitor",
        action="store_true",
        help="Print normalized controller events and execute nothing.",
    )
    parser.add_argument(
        "--list-devices",
        action="store_true",
        help="List detected X1 MK1 evdev and F1 HID devices.",
    )
    parser.add_argument(
        "--list-ports",
        action="store_true",
        help="Compatibility alias for --list-devices.",
    )
    args = parser.parse_args()

    if args.list_devices or args.list_ports:
        return list_devices()

    config = load_config(args.config)
    router = EventRouter(config, monitor=args.monitor)
    runtime = ControllerRuntime(router)

    try:
        runtime.run()
    except KeyboardInterrupt:
        print()
        return 0


if __name__ == "__main__":
    sys.exit(main())
