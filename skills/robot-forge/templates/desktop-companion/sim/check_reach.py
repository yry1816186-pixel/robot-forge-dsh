#!/usr/bin/env python3
"""Static reach and clearance check for the two-axis head.

This runs without MuJoCo: it reads the project model and the CAD dimensions and
proves that the commanded range is inside the servo travel and that the head
cannot hit the body at either tilt extreme.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from forgekit.model import load_project  # noqa: E402


def fail(message: str) -> int:
    print("FAIL " + message)
    return 1


def main() -> int:
    project = load_project(ROOT)
    if project.load_error:
        return fail("cannot load robot.yaml: %s" % project.load_error)

    dims_path = ROOT / "hardware" / "cad" / "dims.json"
    if not dims_path.is_file():
        return fail("missing hardware/cad/dims.json")
    dims = json.loads(dims_path.read_text(encoding="utf-8"))

    limits = project.mech.get("limits") or {}
    pan = limits.get("pan_deg") or dims["limits"]["pan"]
    tilt = limits.get("tilt_deg") or dims["limits"]["tilt"]
    if list(pan) != list(dims["limits"]["pan"]) or list(tilt) != list(dims["limits"]["tilt"]):
        return fail("robot.yaml limits and dims.json disagree")

    errors = []
    if not (-45 <= pan[0] < pan[1] <= 45):
        errors.append("pan range %s exceeds the +/-45 degree mechanical stop" % pan)
    if not (-10 <= tilt[0] < tilt[1] <= 60):
        errors.append("tilt range %s exceeds the -10..60 degree mechanical stop" % tilt)

    pivot_z = dims["pivot"]["z"]
    radius = dims["head"]["radius"]
    offset = dims["head"]["offset_from_pivot"]
    body_top = dims["body"]["top_z"]
    min_clearance = dims["checks"]["min_clearance"]

    lowest = pivot_z + offset * math.sin(math.radians(tilt[0])) - radius
    clearance = lowest - body_top
    print("tilt low point z=%.2f mm, body top z=%.2f mm, clearance=%.2f mm" % (lowest, body_top, clearance))
    if clearance < min_clearance:
        errors.append("head hits the body at tilt %s (clearance %.2f mm)" % (tilt[0], clearance))

    top = pivot_z + offset * math.sin(math.radians(tilt[1])) + radius
    print("head top at tilt max z=%.2f mm, stated height=%.2f mm" % (top, dims["overall"]["height"]))
    if top > dims["overall"]["height"] + 2:
        errors.append("head exceeds the stated height by %.2f mm" % (top - dims["overall"]["height"]))

    servo_min, servo_max, servo_center = 0, 180, 90
    for name, value in (("pan", pan), ("tilt", tilt)):
        if servo_center + value[0] < servo_min or servo_center + value[1] > servo_max:
            errors.append("%s command leaves the 0..180 servo travel" % name)

    if errors:
        for error in errors:
            print("FAIL " + error)
        return 1
    print("PASS reach and clearance inside the mechanical envelope")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
