#!/usr/bin/env python3
"""Power budget and cost ceiling check.

Both are physical facts that a language model tends to hand-wave: a rail that
cannot supply its peak current, or a bill that quietly exceeds the budget.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from forgekit.model import load_project  # noqa: E402


def main() -> int:
    project = load_project(ROOT)
    if project.load_error:
        print("FAIL cannot load robot.yaml: %s" % project.load_error)
        return 1

    errors = []
    rails = {str(rail.get("id")): rail for rail in project.rails}
    totals = {rid: 0.0 for rid in rails}
    peaks = {rid: 0 for rid in rails}
    for consumer in project.consumers:
        rid = str(consumer.get("rail", ""))
        if rid not in rails:
            errors.append("consumer %s points at unknown rail %s" % (consumer.get("component"), rid))
            continue
        totals[rid] += float(consumer.get("typical_ma") or 0)
        peaks[rid] += int(consumer.get("peak_ma") or 0)

    for rid, rail in rails.items():
        max_ma = int(float(rail.get("max_ma") or 0))
        peak = peaks[rid]
        if peak > max_ma:
            errors.append("%s peak %d mA exceeds the %d mA supply" % (rid, peak, max_ma))
        elif max_ma and peak > max_ma * 0.8:
            print("WARN %s peak %d mA is above 80%% of the %d mA supply" % (rid, peak, max_ma))
        print("rail %-4s typical %5.0f mA  peak %5d mA  supply %5d mA" % (rid, totals[rid], peak, max_ma))

    material = 0.0
    for component in project.components:
        material += float(component.get("price_cny") or 0) * max(1, int(component.get("qty") or 1))
    shipping = float(project.data.get("cost", {}).get("shipping_cny") or 0)
    total = material + shipping
    print("cost materials=%.2f shipping=%.2f total=%.2f budget=%.2f" % (material, shipping, total, project.budget))
    if project.budget and total > project.budget:
        errors.append("total cost %.2f exceeds budget %.2f" % (total, project.budget))

    if errors:
        for error in errors:
            print("FAIL " + error)
        return 1
    print("PASS power and cost inside the declared envelope")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
