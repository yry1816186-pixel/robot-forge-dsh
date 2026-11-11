#!/usr/bin/env python3
"""Bundle validator entry point (thin wrapper around forgekit.validate)."""

from __future__ import annotations

import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE_ROOT / "skills" / "robot-forge" / "scripts"))

from forgekit.validate import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
