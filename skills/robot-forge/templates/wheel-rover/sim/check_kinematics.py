#!/usr/bin/env python3
"""Check the differential-drive numbers declared in forge/robot.yaml.

No simulator is needed. This proves that the requested top speed fits the
motors, that the turn radius is physically possible, and that the 30 cm sonar
stop still has room left after latency and braking.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from forgekit.model import load_project  # noqa: E402

# Datasheet figures for the TT motor supplied with the 2WD chassis kit.
MOTOR_NO_LOAD_RPM = 200.0
MOTOR_RATED_RPM = 170.0
CONTROL_LATENCY_S = 0.24   # serial + decode + main loop + driver
SONAR_PERIOD_S = 0.06
BRAKE_DECEL_MPS2 = 1.5
MIN_MARGIN_MM = 50.0


def fail(message: str) -> int:
    print("FAIL " + message)
    return 1


def main() -> int:
    project = load_project(ROOT)
    if project.load_error:
        return fail("cannot load robot.yaml: %s" % project.load_error)

    motion = project.data.get("motion") or {}
    try:
        wheel_d_mm = float(motion.get("wheel_diameter_mm") or project.mech.get("wheel_diameter_mm"))
        wheel_base_mm = float(motion.get("wheel_base_mm") or project.mech.get("wheel_base_mm"))
        max_linear = float(motion.get("max_linear_mps"))
        max_angular = float(motion.get("max_angular_radps"))
        stop_mm = float(motion.get("stop_distance_mm"))
        control_hz = float(motion.get("control_hz") or 50)
    except (TypeError, ValueError) as exc:
        return fail("motion section is incomplete: %s" % exc)

    errors = []
    wheel_d_m = wheel_d_mm / 1000.0
    wheel_base_m = wheel_base_mm / 1000.0
    if wheel_d_m <= 0 or wheel_base_m <= 0:
        return fail("wheel diameter and wheel base must be positive")

    rpm = max_linear / (math.pi * wheel_d_m) * 60.0
    print("top speed %.2f m/s -> %.1f rpm at the wheel (motor rated %.0f rpm)" % (max_linear, rpm, MOTOR_RATED_RPM))
    if rpm > MOTOR_RATED_RPM:
        errors.append("top speed needs %.1f rpm, above the motor's rated %.0f rpm" % (rpm, MOTOR_RATED_RPM))

    differential = max_angular * wheel_base_m / 2.0
    print("turn rate %.2f rad/s -> wheel differential %.3f m/s" % (max_angular, differential))
    if differential > max_linear * 1.5:
        errors.append("turn rate needs %.3f m/s per wheel, more than 1.5x the top speed" % differential)

    if max_angular > 0:
        radius = max_linear / max_angular
        print("minimum turn radius at top speed %.3f m" % radius)
        if radius < wheel_base_m * 0.5:
            errors.append("turn radius %.3f m is smaller than half the wheel base" % radius)

    reaction_mm = max_linear * (CONTROL_LATENCY_S + SONAR_PERIOD_S) * 1000.0
    brake_mm = max_linear * max_linear / (2.0 * BRAKE_DECEL_MPS2) * 1000.0
    stop_need = reaction_mm + brake_mm
    print("stop distance needed at top speed %.1f mm (reaction %.1f + brake %.1f)" % (stop_need, reaction_mm, brake_mm))
    if stop_need + MIN_MARGIN_MM > stop_mm:
        errors.append(
            "%.1f mm stopping distance plus %.0f mm margin exceeds the %.0f mm sonar threshold"
            % (stop_need, MIN_MARGIN_MM, stop_mm)
        )

    loop_ms = 1000.0 / control_hz
    print("control loop %.1f ms, heartbeat must be longer than one loop" % loop_ms)
    if control_hz < 20:
        errors.append("control loop %.0f Hz is too slow; use at least 20 Hz" % control_hz)

    if errors:
        for error in errors:
            print("FAIL " + error)
        return 1
    print("PASS kinematics, turn radius and stopping distance inside the declared limits")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
