#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

launcher = Path(__file__).resolve()
source_package = launcher.parent / "traktor_controller"
installed = Path.home() / ".local/lib/traktor-system-controller"

# When invoked from a repository checkout, Python already places the launcher's
# directory first on sys.path. Do not shadow that source tree with a stale
# previously installed MIDILIN package. The installed wrapper in ~/.local/bin
# has no sibling traktor_controller directory, so it deliberately uses the
# installed library tree instead.
if not source_package.is_dir() and installed.is_dir() and str(installed) not in sys.path:
    sys.path.insert(0, str(installed))

from traktor_controller.cli_autocode import main

if __name__ == "__main__":
    raise SystemExit(main())
