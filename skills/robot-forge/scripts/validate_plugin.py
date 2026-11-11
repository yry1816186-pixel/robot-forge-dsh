#!/usr/bin/env python3
"""Validate the robot-forge plugin layout without generating projects.

Usage:
    python scripts/validate_plugin.py            # validate this plugin
    python scripts/validate_plugin.py --json     # machine-readable
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from forgekit.validate import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
