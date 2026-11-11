#!/usr/bin/env python3
"""Parametric enclosure for the Xiaodou desktop companion.

Everything is driven by dims.json so the printed part, the simulation and the
docs cannot drift apart. Run:

    python hardware/cad/enclosure.py --out hardware/stl
    python hardware/cad/enclosure.py --coupon --out hardware/stl

build123d is required to export STL; the check is optional in verify.yaml so a
project without CAD tooling still passes the rest of the gates.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DIMS = json.loads((ROOT / "hardware" / "cad" / "dims.json").read_text(encoding="utf-8"))


def _build_parts(tolerance: float):
    from build123d import Box, Cylinder, Pos

    body = DIMS["body"]
    head = DIMS["head"]
    wall = DIMS["wall"]

    base = Pos(0, 0, body["height"] / 2) * Box(body["width"], body["depth"], body["height"])
    cavity = Pos(0, 0, body["height"] / 2 + wall) * Box(
        body["width"] - 2 * wall, body["depth"] - 2 * wall, body["height"]
    )
    base = base - cavity

    for x in (-body["width"] / 2 + 8, body["width"] / 2 - 8):
        for y in (-body["depth"] / 2 + 8, body["depth"] / 2 - 8):
            base = base - Pos(x, y, body["height"] / 2) * Cylinder(1.7, body["height"] + 2)

    lid = Pos(0, 0, 3) * Box(body["width"], body["depth"], 6)
    lid = lid - Pos(0, 0, 3.0) * Box(body["width"] - 2 * wall, body["depth"] - 2 * wall, 6.2)

    shell = Pos(0, 0, head["radius"]) * Cylinder(head["radius"], head["diameter"])
    inner = Pos(0, 0, head["radius"]) * Cylinder(head["radius"] - wall, head["diameter"] + 1)
    shell = shell - inner
    screen = Pos(0, -head["radius"] + 1.2, head["radius"]) * Box(32, 6, 32)
    shell = shell - screen

    bracket = Pos(0, 0, 12) * Box(46, 16, 24)
    bracket = bracket - Pos(0, 0, 16) * Box(40, 18, 18)
    return {"enclosure-bottom": base, "enclosure-top": shell, "neck-bracket": bracket}, lid


def _coupon(tolerance: float):
    from build123d import Box, Cylinder, Pos

    plate = Pos(0, 0, 3) * Box(80, 30, 6)
    holes = (
        (-30, DIMS["fasteners"]["m3_clearance"] + tolerance),
        (-10, DIMS["fasteners"]["m3_self_tap"] + tolerance),
        (10, DIMS["fasteners"]["m3_heat_set"] + tolerance),
        (30, DIMS["fasteners"]["bearing_press"] + tolerance),
    )
    for x, diameter in holes:
        plate = plate - Pos(x, 0, 0) * Cylinder(diameter / 2, 10)
    return plate


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the enclosure STL files")
    parser.add_argument("--out", default=str(ROOT / "hardware" / "stl"))
    parser.add_argument("--coupon", action="store_true", help="export the tolerance coupon only")
    parser.add_argument("--tolerance", type=float, default=float(DIMS["print_tolerance"]))
    args = parser.parse_args()

    try:
        from build123d import export_stl
    except ImportError:
        print("build123d is not installed; run: python -m pip install build123d")
        return 2

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    if args.coupon:
        export_stl(_coupon(args.tolerance), str(out / "tolerance_coupon.stl"))
        print("wrote %s" % (out / "tolerance_coupon.stl"))
        return 0

    parts, lid = _build_parts(args.tolerance)
    parts["enclosure-lid"] = lid
    for name, part in parts.items():
        target = out / (name + ".stl")
        export_stl(part, str(target))
        print("wrote %s" % target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
