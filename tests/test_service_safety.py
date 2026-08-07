from __future__ import annotations

import unittest
from pathlib import Path


class ServiceSafetyTests(unittest.TestCase):
    def test_user_service_has_bounded_restart_and_no_privilege_gain(self) -> None:
        service = Path("traktor-system-controller.service").read_text(encoding="utf-8")
        required = {
            "StartLimitIntervalSec=60",
            "StartLimitBurst=5",
            "Restart=on-failure",
            "KillMode=control-group",
            "UMask=0077",
            "NoNewPrivileges=yes",
            "LockPersonality=yes",
            "RestrictRealtime=yes",
            "SystemCallArchitectures=native",
            "Environment=MIDILIN_EVENT_LOG_MODE=actions",
            "Environment=MIDILIN_EVENT_LOG_MAX_BYTES=8388608",
            "Environment=MIDILIN_EVENT_LOG_BACKUPS=4",
        }
        for setting in required:
            with self.subTest(setting=setting):
                self.assertIn(setting, service)
        self.assertNotIn("PrivateDevices=yes", service)
        self.assertNotIn("Restart=always", service)

    def test_install_uses_private_configuration_permissions(self) -> None:
        installer = Path("install.sh").read_text(encoding="utf-8")
        self.assertIn('install -d -m700 "$CONFIG_DIR"', installer)
        self.assertIn('install -m600 "$HERE/config.default.json"', installer)
        self.assertIn('chmod 600 "$CONFIG_DIR/config.json"', installer)
        self.assertIn('install -m700 "$HERE/examples/model-controls-updated"', installer)
        self.assertNotIn("chmod 666", installer)
        self.assertNotIn("chmod 777", installer)

    def test_udev_rules_are_device_specific_and_not_world_writable(self) -> None:
        rules = Path("70-traktor-system-controller.rules").read_text(encoding="utf-8")
        self.assertIn('ATTRS{idVendor}=="17cc"', rules)
        self.assertIn('ATTR{idVendor}=="17cc"', rules)
        self.assertIn('MODE="0660"', rules)
        self.assertIn('TAG+="uaccess"', rules)
        self.assertNotIn('MODE="0666"', rules)


if __name__ == "__main__":
    unittest.main()
