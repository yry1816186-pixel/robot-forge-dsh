#!/usr/bin/env python3
"""Optional MuJoCo viewer. Not part of the acceptance gate."""

from __future__ import annotations

import math
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    try:
        import mujoco
        import mujoco.viewer
    except ImportError:
        print("mujoco is not installed; run: python -m pip install mujoco")
        return 2

    model = mujoco.MjModel.from_xml_path(str(ROOT / "sim" / "scene.xml"))
    data = mujoco.MjData(model)
    with mujoco.viewer.launch_passive(model, data) as viewer:
        start = time.time()
        while viewer.is_running() and time.time() - start < 20:
            t = time.time() - start
            data.ctrl[0] = 25 * math.sin(t * 0.8)
            data.ctrl[1] = 20 + 15 * math.sin(t * 0.5)
            mujoco.mj_step(model, data)
            viewer.sync()
            time.sleep(model.opt.timestep)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
