"""Serial and mock links that speak the rover protocol."""

from __future__ import annotations

import time

from . import config, protocol


class LinkError(RuntimeError):
    pass


class MockLink:
    """Deterministic in-memory link used by tests and --mock demos."""

    def __init__(self, distance_mm: int = 1200, battery_mv: int = 7800) -> None:
        self.distance_mm = distance_mm
        self.battery_mv = battery_mv
        self.moving = False
        self.linear_mm_s = 0
        self.angular_mrad_s = 0
        self.yaw_mdeg = 0.0
        self._last_tick = time.monotonic()
        self._seq = 0
        self._pending: list[str] = []

    def send(self, line: str) -> str:
        line = line.strip()
        if not line:
            return "ERR 2"
        if line == "PING":
            return "OK"
        if line == "S":
            self.moving = False
            self.linear_mm_s = 0
            self.angular_mrad_s = 0
            return "OK"
        if line.startswith("V "):
            fields = line.split()
            if len(fields) != 3:
                return "ERR 3"
            try:
                lin, ang = int(fields[1]), int(fields[2])
            except ValueError:
                return "ERR 4"
            if abs(lin) > config.MAX_LINEAR_MM_S or abs(ang) > config.MAX_ANGULAR_MRAD_S:
                return "ERR 5"
            if self.distance_mm < config.STOP_DISTANCE_MM and lin > 0:
                return "ERR 6"
            self.linear_mm_s = lin
            self.angular_mrad_s = ang
            self.moving = lin != 0 or ang != 0
            return "OK"
        return "ERR 2"

    def tick(self, dt_s: float | None = None) -> None:
        now = time.monotonic()
        if dt_s is None:
            dt_s = now - self._last_tick
        self._last_tick = now
        dt_s = max(0.0, min(dt_s, 0.5))
        if self.moving:
            self.yaw_mdeg = (self.yaw_mdeg + self.angular_mrad_s * 0.001 * dt_s * 57.2958) % 360.0

    def poll(self) -> list[str]:
        self.tick()
        self._seq += 1
        if self._seq % 2:
            return []
        return [
            "T 0 0 %d %d %d"
            % (self.distance_mm, int(self.yaw_mdeg), self.battery_mv)
        ]

    def close(self) -> None:
        self.moving = False


class SerialLink:
    """Thin wrapper around pyserial; import stays lazy so tests need no hardware."""

    def __init__(self, port: str, baud: int = config.BAUD, timeout_s: float = 0.2) -> None:
        try:
            import serial  # type: ignore
        except ImportError as exc:  # pragma: no cover - depends on environment
            raise LinkError("pyserial is not installed: pip install pyserial") from exc
        try:
            self._ser = serial.Serial(port, baud, timeout=timeout_s)
        except Exception as exc:  # noqa: BLE001 - surface the real OS error
            raise LinkError(f"cannot open {port}: {exc}") from exc
        self._buffer = ""

    def send(self, line: str) -> str:
        if not self._ser.is_open:
            raise LinkError("serial port is closed")
        self._ser.write(line.encode("ascii"))
        self._ser.flush()
        raw = self._ser.readline().decode("ascii", errors="replace")
        return raw.strip() or "ERR 0"

    def poll(self) -> list[str]:
        waiting = getattr(self._ser, "in_waiting", 0)
        if waiting:
            self._buffer += self._ser.read(waiting).decode("ascii", errors="replace")
        lines, self._buffer = protocol.split_lines(self._buffer)
        out = []
        for line in lines:
            out.append(line)
        return out

    def close(self) -> None:
        try:
            self._ser.close()
        except Exception:  # noqa: BLE001 - closing must never raise
            pass


def open_link(port: str | None, mock: bool = False) -> MockLink | SerialLink:
    if mock or not port:
        return MockLink()
    return SerialLink(port)
