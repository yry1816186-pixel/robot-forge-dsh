"""Text protocol between the host and the rover firmware.

Host -> firmware (one line each):
    V <lin_mm_s> <ang_mrad_s>
    S
    PING

Firmware -> host:
    OK
    ERR <code>
    T <enc_l> <enc_r> <dist_mm> <yaw_mdeg> <batt_mv>
"""

from __future__ import annotations

from . import config


class ProtocolError(ValueError):
    """Raised when a line does not follow the protocol."""


def _bounded_int(value: object, limit: int, name: str) -> int:
    try:
        number = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise ProtocolError(f"{name} is not an integer: {value!r}") from exc
    if abs(number) > limit:
        raise ProtocolError(f"{name}={number} exceeds limit {limit}")
    return number


def encode_velocity(lin_mm_s: int, ang_mrad_s: int) -> str:
    """Build a velocity command. Values are clamped by the caller, not silently here."""
    lin = _bounded_int(lin_mm_s, config.MAX_LINEAR_MM_S, "lin_mm_s")
    ang = _bounded_int(ang_mrad_s, config.MAX_ANGULAR_MRAD_S, "ang_mrad_s")
    return f"V {lin} {ang}\n"


def encode_stop() -> str:
    return "S\n"


def encode_ping() -> str:
    return "PING\n"


def split_lines(buffer: str) -> tuple[list[str], str]:
    """Split a serial buffer into complete lines plus the unterminated tail."""
    parts = buffer.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    return [p.strip() for p in parts[:-1] if p.strip()], parts[-1]


def parse_reply(line: str) -> dict:
    """Parse OK / ERR / T lines. Raises ProtocolError on anything else."""
    line = line.strip()
    if line == "OK":
        return {"kind": "ok"}
    if line.startswith("ERR"):
        fields = line.split()
        if len(fields) != 2:
            raise ProtocolError(f"bad ERR line: {line!r}")
        try:
            code = int(fields[1])
        except ValueError as exc:
            raise ProtocolError(f"bad ERR code: {line!r}") from exc
        return {"kind": "err", "code": code}
    if line.startswith("T "):
        fields = line.split()
        if len(fields) != 6:
            raise ProtocolError(f"telemetry needs 5 values: {line!r}")
        try:
            values = [int(x) for x in fields[1:]]
        except ValueError as exc:
            raise ProtocolError(f"telemetry values must be integers: {line!r}") from exc
        return {
            "kind": "telemetry",
            "enc_l": values[0],
            "enc_r": values[1],
            "dist_mm": values[2],
            "yaw_mdeg": values[3],
            "batt_mv": values[4],
        }
    raise ProtocolError(f"unknown line: {line!r}")


def describe_error(code: int) -> str:
    return {
        1: "line too long",
        2: "unknown command",
        3: "wrong argument count",
        4: "argument is not a number",
        5: "value out of range",
        6: "obstacle stop",
    }.get(code, f"error {code}")
