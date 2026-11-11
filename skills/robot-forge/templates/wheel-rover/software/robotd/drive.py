"""Differential-drive kinematics for a two-wheel rover."""

from __future__ import annotations

from . import config


def mix(linear_mps: float, angular_radps: float, wheel_base_m: float = 0.16,
        max_wheel_mps: float = 0.45) -> tuple[float, float]:
    """Return (left, right) wheel speeds in m/s for a unicycle command.

    The result is scaled down proportionally when a wheel would exceed
    max_wheel_mps, so the command direction is preserved.
    """
    if wheel_base_m <= 0:
        raise ValueError("wheel_base_m must be positive")
    if max_wheel_mps <= 0:
        raise ValueError("max_wheel_mps must be positive")
    half = angular_radps * wheel_base_m / 2.0
    left = linear_mps - half
    right = linear_mps + half
    peak = max(abs(left), abs(right))
    if peak > max_wheel_mps:
        scale = max_wheel_mps / peak
        left *= scale
        right *= scale
    return left, right


def wheel_speeds_mps(linear_mm_s: int, angular_mrad_s: int,
                     wheel_base_m: float = 0.16, max_wheel_mps: float = 0.45) -> tuple[float, float]:
    return mix(linear_mm_s / 1000.0, angular_mrad_s / 1000.0, wheel_base_m, max_wheel_mps)


def turning_radius_m(linear_mps: float, angular_radps: float) -> float | None:
    """Radius of the circle traced by the robot center; None for straight/spin."""
    if abs(angular_radps) < 1e-9:
        return None
    return linear_mps / angular_radps


def projected_stop_mm(speed_mps: float, latency_s: float = 0.24,
                    brake_decel_mps2: float = 1.5) -> float:
    """Worst-case travel before stop: reaction latency plus braking distance."""
    if speed_mps < 0:
        raise ValueError("speed_mps must be >= 0")
    if brake_decel_mps2 <= 0:
        raise ValueError("brake_decel_mps2 must be positive")
    return speed_mps * latency_s * 1000.0 + (speed_mps ** 2) / (2 * brake_decel_mps2) * 1000.0


def clamp_command(lin_mm_s: int, ang_mrad_s: int) -> tuple[int, int]:
    lin = max(-config.MAX_LINEAR_MM_S, min(config.MAX_LINEAR_MM_S, int(lin_mm_s)))
    ang = max(-config.MAX_ANGULAR_MRAD_S, min(config.MAX_ANGULAR_MRAD_S, int(ang_mrad_s)))
    return lin, ang
