#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path.home() / ".local/lib/traktor-system-controller"))

from traktor_controller.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
