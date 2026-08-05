#!/usr/bin/env python3
"""Compatibility backend module loaded by traktor_controller.cli."""
from traktor_controller.autocode_visuals import install as install_autocode_visuals
from traktor_controller.hardware import (
    ConnectionConsent,
    ControllerRuntime,
    approve_connected,
    forget_device_decisions,
    list_devices,
)
from traktor_controller.visuals import F1Visual, THEMES, X1Visual, set_theme

install_autocode_visuals()

__all__ = [
    "ConnectionConsent", "ControllerRuntime", "F1Visual", "THEMES", "X1Visual",
    "set_theme", "list_devices", "approve_connected", "forget_device_decisions",
]
