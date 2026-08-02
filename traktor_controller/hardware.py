from __future__ import annotations

import json
import os
import struct
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Callable, Iterable

from .common import ControlEvent, atomic_write_json, log
from .visuals import F1Visual, X1Visual, resolve_theme

NI_VENDOR_ID = 0x17CC
X1_PRODUCT_ID = 0x2305
F1_PRODUCT_ID = 0x1120
DEVNULL = subprocess.DEVNULL

F1_BUTTON_MASKS = {
    "grid_8": 0x00000001, "grid_7": 0x00000002,
    "grid_6": 0x00000004, "grid_5": 0x00000008,
    "grid_4": 0x00000010, "grid_3": 0x00000020,
    "grid_2": 0x00000040, "grid_1": 0x00000080,
    "grid_16": 0x00000100, "grid_15": 0x00000200,
    "grid_14": 0x00000400, "grid_13": 0x00000800,
    "grid_12": 0x00001000, "grid_11": 0x00002000,
    "grid_10": 0x00004000, "grid_9": 0x00008000,
    "select_push": 0x00040000, "browse": 0x00080000,
    "size": 0x00100000, "type": 0x00200000,
    "reverse": 0x00400000, "shift": 0x00800000,
    "capture": 0x02000000, "quant": 0x04000000,
    "sync": 0x08000000, "play_4": 0x10000000,
    "play_3": 0x20000000, "play_2": 0x40000000,
    "play_1": 0x80000000,
}
F1_ANALOG_OFFSETS = {
    "knob_1": 6, "knob_2": 8, "knob_3": 10, "knob_4": 12,
    "fader_1": 14, "fader_2": 16, "fader_3": 18, "fader_4": 20,
}
X1_BUTTONS: dict[str, tuple[int, int]] = {
    "deck_a_play": (0, 0), "deck_a_cue": (0, 1),
    "deck_a_beat_left": (0, 2), "deck_a_out": (0, 3),
    "deck_a_fx2": (1, 0), "deck_a_fx1": (1, 1),
    "deck_b_in": (1, 4), "deck_b_beat_right": (1, 5),
    "deck_b_cup": (1, 6), "deck_b_sync": (1, 7),
    "deck_b_play": (2, 0), "deck_b_cue": (2, 1),
    "deck_b_beat_left": (2, 2), "deck_b_out": (2, 3),
    "deck_a_in": (2, 4), "deck_a_beat_right": (2, 5),
    "deck_a_cup": (2, 6), "deck_a_sync": (2, 7),
    "deck_a_browse_button": (3, 0), "deck_b_browse_button": (3, 1),
    "deck_a_loop_button": (3, 2), "deck_b_loop_button": (3, 3),
    "fx1_on": (3, 4), "fx1_button_1": (3, 5),
    "fx1_button_2": (3, 6), "fx1_button_3": (3, 7),
    "fx2_on": (4, 0), "fx2_button_1": (4, 1),
    "fx2_button_2": (4, 2), "fx2_button_3": (4, 3),
    "shift": (4, 4), "deck_b_fx2": (4, 5),
    "deck_b_fx1": (4, 6), "hotcue": (4, 7),
}
X1_ENCODERS = {
    "deck_a_browse_encoder": (6, False),
    "deck_b_browse_encoder": (6, True),
    "deck_a_loop_encoder": (7, False),
    "deck_b_loop_encoder": (7, True),
}
X1_ANALOGS = {
    "fx1_dry_wet": (16, 17), "fx1_knob_1": (20, 21),
    "fx1_knob_2": (22, 23), "fx1_knob_3": (18, 19),
    "fx2_dry_wet": (12, 13), "fx2_knob_1": (10, 11),
    "fx2_knob_2": (8, 9), "fx2_knob_3": (14, 15),
}
X1_ENCODER_RAW_CODES = {"ABS_X", "ABS_Y", "ABS_Z", "ABS_MISC"}


def _connection_config(config: dict[str, Any]) -> dict[str, Any]:
    value = config.get("connection", {})
    return value if isinstance(value, dict) else {}


def _decision_path(config: dict[str, Any]) -> Path:
    value = _connection_config(config).get(
        "state_file", "~/.config/traktor-system-controller/device-decisions.json"
    )
    return Path(str(value)).expanduser()


def _load_decisions(config: dict[str, Any]) -> dict[str, str]:
    try:
        value = json.loads(_decision_path(config).read_text(encoding="utf-8"))
        return {str(k): str(v) for k, v in value.items()} if isinstance(value, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_decisions(config: dict[str, Any], decisions: dict[str, str]) -> None:
    atomic_write_json(_decision_path(config), decisions)


def approve_connected(config: dict[str, Any], decision: str) -> int:
    if decision not in {"always", "never"}:
        raise ValueError("decision must be always or never")
    decisions = _load_decisions(config)
    decisions.update({"x1": decision, "f1": decision})
    _save_decisions(config, decisions)
    print(f"Saved {decision!r} for X1 and F1 in {_decision_path(config)}")
    return 0


def forget_device_decisions(config: dict[str, Any]) -> int:
    path = _decision_path(config)
    try:
        path.unlink()
        print(f"Removed {path}")
    except FileNotFoundError:
        print(f"No saved decisions: {path}")
    return 0


class ConnectionConsent:
    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.settings = _connection_config(config)
        self.decisions = _load_decisions(config)

    def _remember(self, device: str, value: str) -> None:
        self.decisions[device] = value
        _save_decisions(self.config, self.decisions)

    @staticmethod
    def _wofi(label: str) -> str | None:
        command = ["wofi", "--dmenu", "--prompt", f"Use {label} as system controller?"]
        choices = "Use once\nAlways use\nIgnore once\nNever use\n"
        try:
            result = subprocess.run(
                command, input=choices, text=True, capture_output=True,
                timeout=60, check=False,
            )
            return result.stdout.strip() if result.returncode == 0 else None
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return None

    @staticmethod
    def _zenity(label: str) -> str | None:
        try:
            result = subprocess.run(
                [
                    "zenity", "--list", "--title=Traktor system controller",
                    f"--text={label} connected. Choose how it should be used:",
                    "--column=Choice", "Use once", "Always use",
                    "Ignore once", "Never use", "--width=430", "--height=330",
                ],
                stdin=DEVNULL, text=True, capture_output=True,
                timeout=60, check=False,
            )
            return result.stdout.strip() if result.returncode == 0 else None
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return None

    def allowed(self, device: str, label: str) -> bool:
        if os.environ.get("TRAKTOR_ASSUME_YES") == "1":
            return True
        policy = str(self.settings.get("policy", "prompt")).lower()
        remembered = self.decisions.get(device)
        if remembered == "always" or policy == "always":
            return True
        if remembered == "never" or policy == "never":
            return False
        if policy not in {"prompt", "ask"}:
            log(f"Unsupported connection policy {policy!r}; refusing {label}.")
            return False
        if not (os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY")):
            log(
                f"Detected {label}, but no graphical session is available for consent. "
                "Run traktor-system-controller --approve-connected to opt in."
            )
            return False
        choice = self._wofi(label) or self._zenity(label)
        if choice == "Always use":
            if bool(self.settings.get("remember", True)):
                self._remember(device, "always")
            return True
        if choice == "Never use":
            if bool(self.settings.get("remember", True)):
                self._remember(device, "never")
            return False
        return choice == "Use once"


def _hid_path_text(path: Any) -> str:
    return path.decode(errors="replace") if isinstance(path, bytes) else str(path)


def _normalize_f1_report(data: Iterable[int]) -> bytes | None:
    report = bytes(data)
    if len(report) >= 22 and report[0] == 0x01:
        return report
    if len(report) >= 21:
        return b"\x01" + report
    return None


def discover_f1_devices() -> list[dict[str, Any]]:
    try:
        import hid
        return list(hid.enumerate(NI_VENDOR_ID, F1_PRODUCT_ID))
    except Exception:
        return []


def discover_x1_usb_devices() -> list[Any]:
    try:
        import usb.core
        return list(
            usb.core.find(
                find_all=True, idVendor=NI_VENDOR_ID, idProduct=X1_PRODUCT_ID
            ) or []
        )
    except Exception:
        return []


def discover_x1_evdev_devices() -> list[tuple[str, str]]:
    try:
        import evdev
    except ImportError:
        return []
    found: list[tuple[str, str]] = []
    for path in evdev.list_devices():
        try:
            device = evdev.InputDevice(path)
            if device.info.vendor == NI_VENDOR_ID and device.info.product == X1_PRODUCT_ID:
                found.append((path, device.name))
            device.close()
        except (PermissionError, OSError):
            continue
    return found


def _x1_identifier(device: Any) -> str:
    serial = ""
    try:
        import usb.util
        if getattr(device, "iSerialNumber", 0):
            serial = str(usb.util.get_string(device, device.iSerialNumber) or "").strip()
    except Exception:
        serial = ""
    return (
        f"serial:{serial}" if serial
        else f"usb:{getattr(device, 'bus', '?')}:{getattr(device, 'address', '?')}"
    )


def _event_code_name(ecodes: Any, event_type: int, code: int) -> str:
    name = ecodes.bytype.get(event_type, {}).get(code, str(code))
    return str(name[0] if isinstance(name, list) else name)


def x1_evdev_worker(
    path: str, router: Any, config: dict[str, Any], theme: str,
    release: Callable[[], None],
) -> None:
    del config, theme
    try:
        import evdev
        from evdev import ecodes
        device = evdev.InputDevice(path)
        log(f"Connected X1 MK1 evdev fallback (LED feedback unavailable): {path}")
        previous_encoders: dict[str, int] = {}
        for event in device.read_loop():
            control = _event_code_name(ecodes, event.type, event.code)
            if event.type == ecodes.EV_KEY:
                if event.value in {0, 1}:
                    router.emit(ControlEvent(
                        "x1", control, "press" if event.value else "release",
                        1 if event.value else 0, source=path,
                    ))
            elif event.type == ecodes.EV_ABS:
                if control in X1_ENCODER_RAW_CODES:
                    previous = previous_encoders.get(control)
                    previous_encoders[control] = int(event.value)
                    if previous is not None:
                        delta = ((int(event.value) - previous + 8) % 16) - 8
                        if delta:
                            router.emit(ControlEvent(
                                "x1", control, "relative", delta, -8, 7, path
                            ))
                else:
                    info = device.absinfo(event.code)
                    router.emit(ControlEvent(
                        "x1", control, "absolute", int(event.value),
                        int(info.min), int(info.max), path,
                    ))
    except Exception as exc:
        log(f"X1 evdev backend ended: {path}: {exc}")
    finally:
        release()


def x1_raw_worker(
    device: Any, router: Any, config: dict[str, Any], theme: str,
    release: Callable[[], None],
) -> None:
    detached = False
    visual: X1Visual | None = None
    identifier = _x1_identifier(device)
    try:
        import usb.util
        try:
            if device.is_kernel_driver_active(0):
                device.detach_kernel_driver(0)
                detached = True
        except (NotImplementedError, Exception):
            pass
        device.set_configuration(1)
        usb.util.claim_interface(device, 0)
        visual = X1Visual(device, config, theme)
        log(f"Connected X1 MK1 raw USB with LED feedback: {identifier}")
        previous_buttons: dict[str, bool] = {}
        previous_encoders: dict[str, int] = {}
        previous_analogs: dict[str, int] = {}
        while True:
            try:
                raw = bytes(device.read(0x84, 24, timeout=100))
            except Exception as exc:
                if "timeout" in str(exc).lower() or "timed out" in str(exc).lower():
                    continue
                raise
            if len(raw) != 24:
                continue
            for control, (byte_index, bit_index) in X1_BUTTONS.items():
                pressed = bool(raw[1 + byte_index] & (1 << bit_index))
                previous = previous_buttons.get(control)
                previous_buttons[control] = pressed
                if previous is None or previous == pressed:
                    continue
                visual.feedback(control, pressed)
                router.emit(ControlEvent(
                    "x1", control, "press" if pressed else "release",
                    1 if pressed else 0, source=identifier,
                ))
            for control, (index, high_nibble) in X1_ENCODERS.items():
                position = raw[index] >> 4 if high_nibble else raw[index] & 0x0F
                previous = previous_encoders.get(control)
                previous_encoders[control] = position
                if previous is None:
                    continue
                delta = ((position - previous + 8) % 16) - 8
                if delta:
                    router.emit(ControlEvent(
                        "x1", control, "relative", delta, -8, 7, identifier
                    ))
            for control, (high, low) in X1_ANALOGS.items():
                value = (raw[high] << 8) | raw[low]
                previous = previous_analogs.get(control)
                previous_analogs[control] = value
                if previous is not None and previous != value:
                    router.emit(ControlEvent(
                        "x1", control, "absolute", value, 0, 4095, identifier
                    ))
    except Exception as exc:
        log(f"X1 raw USB backend ended: {identifier}: {exc}")
    finally:
        if visual:
            visual.clear()
        try:
            import usb.util
            usb.util.release_interface(device, 0)
            usb.util.dispose_resources(device)
        except Exception:
            pass
        if detached:
            try:
                device.attach_kernel_driver(0)
            except Exception:
                pass
        release()


def f1_worker(
    path: Any, router: Any, config: dict[str, Any], theme: str,
    release: Callable[[], None],
) -> None:
    device = None
    visual: F1Visual | None = None
    path_text = _hid_path_text(path)
    try:
        import hid
        device = hid.device()
        device.open_path(path)
        device.set_nonblocking(False)
        visual = F1Visual(device, config, theme)
        log(f"Connected F1 HID with interactive RGB feedback: {path_text}")
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
                    visual.feedback(control, pressed)
                    router.emit(ControlEvent(
                        "f1", control, "press" if pressed else "release",
                        1 if pressed else 0, source=path_text,
                    ))
            previous_buttons = buttons
            encoder = report[5]
            if previous_encoder is not None:
                delta = ((encoder - previous_encoder + 128) % 256) - 128
                if delta:
                    router.emit(ControlEvent(
                        "f1", "select_encoder", "relative", delta,
                        -128, 127, path_text,
                    ))
            previous_encoder = encoder
            for control, offset in F1_ANALOG_OFFSETS.items():
                value = struct.unpack_from("<H", report, offset)[0]
                previous = previous_analog.get(control)
                previous_analog[control] = value
                if previous is not None and previous != value:
                    router.emit(ControlEvent(
                        "f1", control, "absolute", value, 0, 4096, path_text
                    ))
    except Exception as exc:
        log(f"F1 backend ended: {path_text}: {exc}")
    finally:
        if visual:
            visual.clear()
        if device:
            try:
                device.close()
            except Exception:
                pass
        release()


class ControllerRuntime:
    def __init__(
        self, router: Any, config: dict[str, Any], visual_theme: str | None = None,
    ):
        self.router = router
        self.config = config
        self.theme = resolve_theme(config, visual_theme)
        self.consent = ConnectionConsent(config)
        self.active: set[tuple[str, str]] = set()
        self.ignored: set[tuple[str, str]] = set()
        self.present: set[tuple[str, str]] = set()
        self.lock = threading.Lock()

    def _start(
        self, key: tuple[str, str], label: str,
        target: Callable[..., None], *args: Any,
    ) -> None:
        with self.lock:
            if key in self.active or key in self.ignored:
                return
        if not self.consent.allowed(key[0], label):
            log(f"Ignoring {label} for this connection.")
            with self.lock:
                self.ignored.add(key)
            return
        with self.lock:
            self.active.add(key)

        def release() -> None:
            with self.lock:
                self.active.discard(key)
                self.ignored.add(key)

        threading.Thread(
            target=target,
            args=(*args, self.router, self.config, self.theme, release),
            daemon=True,
        ).start()

    def run(self) -> None:
        hardware = self.config.get("hardware", {})
        hardware = hardware if isinstance(hardware, dict) else {}
        x1_backend = str(hardware.get("x1_backend", "raw_usb"))
        fallback = bool(hardware.get("fallback_to_evdev", True))
        log(
            "Watching for Traktor controllers. "
            f"theme={self.theme} x1_backend={x1_backend}. Ctrl+C stops."
        )
        while True:
            current: set[tuple[str, str]] = set()
            raw_x1 = discover_x1_usb_devices() if x1_backend == "raw_usb" else []
            for device in raw_x1:
                identity = _x1_identifier(device)
                key = ("x1", identity)
                current.add(key)
                self._start(key, "Traktor Kontrol X1 MK1", x1_raw_worker, device)
            if x1_backend == "evdev" or (fallback and not raw_x1):
                for path, _name in discover_x1_evdev_devices():
                    key = ("x1", path)
                    current.add(key)
                    self._start(
                        key, "Traktor Kontrol X1 MK1 (evdev fallback)",
                        x1_evdev_worker, path,
                    )
            for info in discover_f1_devices():
                path = info.get("path")
                if path is None:
                    continue
                identity = _hid_path_text(path)
                key = ("f1", identity)
                current.add(key)
                self._start(key, "Traktor Kontrol F1", f1_worker, path)
            with self.lock:
                disconnected = self.present - current
                self.ignored.difference_update(disconnected)
                self.present = current
            time.sleep(2.0)


def list_devices() -> int:
    found = False
    for device in discover_x1_usb_devices():
        found = True
        print(
            f"X1 MK1 raw USB: {_x1_identifier(device)} "
            f"usb={NI_VENDOR_ID:04x}:{X1_PRODUCT_ID:04x} LEDs=yes"
        )
    for path, name in discover_x1_evdev_devices():
        found = True
        print(
            f"X1 MK1 evdev fallback: path={path} name={name!r} "
            f"usb={NI_VENDOR_ID:04x}:{X1_PRODUCT_ID:04x} LEDs=no"
        )
    for info in discover_f1_devices():
        found = True
        print(
            "F1 HID: "
            f"path={_hid_path_text(info.get('path'))!r} "
            f"interface={info.get('interface_number')} "
            f"serial={info.get('serial_number')!r} "
            f"usb={NI_VENDOR_ID:04x}:{F1_PRODUCT_ID:04x} RGB_LEDs=yes"
        )
    if not found:
        print("No supported Traktor X1 MK1 or F1 devices found.")
        return 1
    return 0
