"""Line protocol between robotd and the ESP32-S3 firmware.

Every message is one UTF-8 line terminated by a newline. Commands from the host
are upper-case verbs; events from the device are upper-case nouns. Parsing is
strict on purpose: an unknown command must never reach the firmware, because a
robot that silently ignores garbage is harder to debug than one that refuses it.
"""

from __future__ import annotations

from dataclasses import dataclass

MAX_LINE = 120

EMOTIONS = ("idle", "happy", "curious", "sleepy", "alert")
TOUCH_ZONES = ("head", "chin")
MIC_STATES = ("ON", "OFF")

COMMANDS = ("EMO", "POSE", "LED", "MIC", "VOL")
EVENTS = ("TOUCH", "DIST", "LEVEL", "READY", "ERR")


class ProtocolError(ValueError):
    """Raised when a line cannot be understood or is out of range."""


@dataclass(frozen=True)
class Message:
    """A parsed protocol line."""

    name: str
    args: tuple[str, ...] = ()

    def render(self) -> str:
        return " ".join((self.name, *self.args))


def _ints(args: tuple[str, ...], count: int) -> tuple[int, ...]:
    if len(args) != count:
        raise ProtocolError(f"expected {count} numbers, got {len(args)}")
    try:
        return tuple(int(a) for a in args)
    except ValueError as exc:  # pragma: no cover - covered via wrong type cases
        raise ProtocolError(f"not a number: {args}") from exc


def parse_line(raw: str) -> Message:
    """Parse one line, raising ProtocolError on anything invalid."""

    line = raw.strip()
    if not line:
        raise ProtocolError("empty line")
    if len(line) > MAX_LINE:
        raise ProtocolError(f"line longer than {MAX_LINE} characters")
    parts = line.split()
    name = parts[0].upper()
    args = tuple(parts[1:])
    if name not in COMMANDS + EVENTS:
        raise ProtocolError(f"unknown message: {parts[0]}")

    if name == "EMO":
        if len(args) != 1 or args[0].lower() not in EMOTIONS:
            raise ProtocolError(f"bad emotion: {args}")
    elif name == "POSE":
        pan, tilt = _ints(args, 2)
        if not -45 <= pan <= 45:
            raise ProtocolError(f"pan out of range: {pan}")
        if not -10 <= tilt <= 60:
            raise ProtocolError(f"tilt out of range: {tilt}")
    elif name == "LED":
        rgb = _ints(args, 3)
        if any(not 0 <= value <= 255 for value in rgb):
            raise ProtocolError(f"led out of range: {rgb}")
    elif name == "MIC":
        if len(args) != 1 or args[0].upper() not in MIC_STATES:
            raise ProtocolError(f"bad mic state: {args}")
    elif name == "VOL":
        (volume,) = _ints(args, 1)
        if not 0 <= volume <= 100:
            raise ProtocolError(f"volume out of range: {volume}")
    elif name == "TOUCH":
        if len(args) != 1 or args[0].lower() not in TOUCH_ZONES:
            raise ProtocolError(f"bad touch zone: {args}")
    elif name == "DIST":
        (mm,) = _ints(args, 1)
        if not 0 <= mm <= 8190:
            raise ProtocolError(f"distance out of range: {mm}")
    elif name == "LEVEL":
        (level,) = _ints(args, 1)
        if not 0 <= level <= 100:
            raise ProtocolError(f"level out of range: {level}")
    elif name == "ERR":
        if len(args) != 1 or not args[0].replace("-", "").isalnum():
            raise ProtocolError(f"bad error code: {args}")
    else:  # READY
        if args:
            raise ProtocolError("READY takes no arguments")
    return Message(name, args)


def emo(name: str) -> str:
    return Message("EMO", (name,)).render()


def pose(pan: int, tilt: int) -> str:
    return Message("POSE", (str(int(pan)), str(int(tilt)))).render()


def led(red: int, green: int, blue: int) -> str:
    return Message("LED", (str(int(red)), str(int(green)), str(int(blue)))).render()


def mic(state: str) -> str:
    return Message("MIC", (state.upper(),)).render()


def volume(level: int) -> str:
    return Message("VOL", (str(int(level)),)).render()


def touch(zone: str) -> str:
    return Message("TOUCH", (zone,)).render()


def distance(mm: int) -> str:
    return Message("DIST", (str(int(mm)),)).render()