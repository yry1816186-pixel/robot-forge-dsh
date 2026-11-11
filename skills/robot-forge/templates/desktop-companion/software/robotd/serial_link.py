"""Serial transport plus an in-memory mock used by tests and demos."""

from __future__ import annotations

import time
from collections.abc import Iterator


class LinkError(RuntimeError):
    """Raised when the transport is not available or was closed."""


class MockLink:
    """Scripted device used by the mock mode and by the test suite."""

    def __init__(self, scenario: list[tuple[float, str]] | None = None, speed: float = 1.0) -> None:
        self.scenario = scenario or []
        self.speed = speed
        self.sent: list[str] = []
        self._closed = False

    def send(self, line: str) -> None:
        if self._closed:
            raise LinkError("link closed")
        self.sent.append(line)

    def read_events(self) -> Iterator[str]:
        if not self.scenario:
            yield "READY"
            return
        delay = 0.0
        for offset, event in self.scenario:
            if self.speed > 0 and offset > delay:
                time.sleep((offset - delay) * self.speed)
                delay = offset
            if event == "__idle__":
                continue
            yield event

    def close(self) -> None:
        self._closed = True


class SerialLink:
    """Thin wrapper over pyserial; pyserial is an optional dependency."""

    def __init__(self, port: str, baud: int = 921600, timeout: float = 0.2) -> None:
        try:
            import serial  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover - depends on environment
            raise LinkError("pyserial is not installed; run pip install pyserial") from exc
        self._serial = serial.Serial(port, baud, timeout=timeout)

    def send(self, line: str) -> None:
        self._serial.write((line + "\n").encode("utf-8"))
        self._serial.flush()

    def read_events(self) -> Iterator[str]:
        while True:
            raw = self._serial.readline()
            if not raw:
                continue
            text = raw.decode("utf-8", errors="replace").strip()
            if text:
                yield text

    def close(self) -> None:
        self._serial.close()
