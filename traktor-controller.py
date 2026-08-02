#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

installed = Path.home() / ".local/lib/traktor-system-controller"
if installed.is_dir() and str(installed) not in sys.path:
    sys.path.insert(0, str(installed))

from traktor_controller.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
