#!/usr/bin/env python3
"""Power budget, runtime and cost ceiling check.

These are the numbers a language model most often hand-waves: a buck converter
that cannot feed the motors, a runtime shorter than the stated requirement, or
a bill that quietly exceeds the budget.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from forgekit.model import load_project  # noqa: E402

MIN_RUNTIME_H = 0.5
WARN_RUNTIME_H = 1.0


def fail(message: str) -> int:
    print("FAIL " + message)
    return 1


def main() -> int:
    project = load_project(ROOT)
    if project.load_error:
        return fail("cannot load robot.yaml: %s" % project.load_error)

    errors = []
    warnings = []
    rails = {str(rail.get("id")): rail for rail in project.rails}
    totals = {rid: 0.0 for rid in rails}
    peaks = {rid: 0.0 for rid in rails}
    for consumer in project.consumers:
        rid = str(consumer.get("rail", ""))
        if rid not in rails:
            errors.append("consumer %s points at unknown rail %s" % (consumer.get("component"), rid))
            continue
        totals[rid] += float(consumer.get("typical_ma") or 0)
        peaks[rid] += float(consumer.get("peak_ma") or 0)

    for rid, rail in rails.items():
        max_ma = float(rail.get("max_ma") or 0)
        if max_ma <= 0:
            errors.append("rail %s has no max_ma" % rid)
            continue
        peak = peaks[rid]
        pct = peak / max_ma * 100.0
        print("rail %-4s %4.1f V  typical %5.0f mA  peak %5.0f mA  supply %5.0f mA  (%.0f%%)"
              % (rid, float(rail.get("voltage") or 0), totals[rid], peak, max_ma, pct))
        if peak > max_ma:
            errors.append("%s peak %.0f mA exceeds the %.0f mA supply" % (rid, peak, max_ma))
        elif pct > 80.0:
            warnings.append("%s peak is %.0f%% of the supply; keep it under 80%%" % (rid, pct))

    battery = project.data.get("power", {}).get("battery") or {}
    chemistry = str(battery.get("chemistry", "none")).lower()
    if chemistry not in ("", "none", "无"):
        runtime = project.battery_runtime_h()
        if runtime is None:
            errors.append("cannot compute runtime; check battery.mah/cells and consumers")
        else:
            print("battery %s %s mAh x%s -> estimated runtime %.2f h"
                  % (chemistry, battery.get("mah"), battery.get("cells"), runtime))
            if runtime < MIN_RUNTIME_H:
                errors.append("estimated runtime %.2f h is below the %.1f h requirement" % (runtime, MIN_RUNTIME_H))
            elif runtime < WARN_RUNTIME_H:
                warnings.append("estimated runtime %.2f h is below 1 h" % runtime)

    material = 0.0
    for component in project.components:
        material += float(component.get("price_cny") or 0) * max(1, int(component.get("qty") or 1))
    shipping = float(project.data.get("cost", {}).get("shipping_cny") or 0)
    total = material + shipping
    print("cost materials=%.2f shipping=%.2f total=%.2f budget=%.2f" % (material, shipping, total, project.budget))
    if project.budget and total > project.budget:
        errors.append("total cost %.2f exceeds budget %.2f" % (total, project.budget))

    for warning in warnings:
        print("WARN " + warning)
    if errors:
        for error in errors:
            print("FAIL " + error)
        return 1
    print("PASS power, runtime and cost inside the declared envelope")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
