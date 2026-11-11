"""CLI entry point: wire protocol, personality and speech together."""

from __future__ import annotations

import argparse
import os
import sys
import time

from . import __version__
from .personality import Personality, Reaction
from .protocol import ProtocolError, emo, led, mic, parse_line, pose
from .serial_link import LinkError, MockLink, SerialLink

DEFAULT_SCENARIO = [
    (0.0, "READY"),
    (0.6, "TOUCH head"),
    (1.4, "DIST 900"),
    (2.2, "TOUCH chin"),
]


class ExternalBrain:
    """Placeholder for a user-supplied HTTP brain. Never enabled by default."""

    def __init__(self, url: str) -> None:
        if os.environ.get("ROBOTD_NETWORK", "0") != "1":
            raise RuntimeError("external brain needs ROBOTD_NETWORK=1")
        self.url = url

    def reply(self, text: str, context: dict | None = None) -> str:  # pragma: no cover
        raise NotImplementedError("plug your own HTTP client here, keeping the key out of the repo")


def emit(reaction: Reaction, link, *, speak: bool = True) -> None:
    link.send(emo(reaction.emotion))
    link.send(pose(reaction.pan, reaction.tilt))
    link.send(led(*reaction.led))
    print(f"[face] {reaction.emotion}")
    print(f"[pose] pan={reaction.pan} tilt={reaction.tilt}")
    if speak and reaction.speech:
        print(f"[say] {reaction.speech}")


def handle_event(line: str, personality: Personality, link) -> None:
    try:
        message = parse_line(line)
    except ProtocolError as exc:
        print(f"[warn] dropped invalid line: {exc}", file=sys.stderr)
        return
    if message.name == "READY":
        print(f"[boot] robotd {__version__} connected")
    elif message.name == "TOUCH":
        emit(personality.on_touch(message.args[0].lower()), link)
    elif message.name == "DIST":
        emit(personality.on_distance(int(message.args[0])), link, speak=False)
    elif message.name == "ERR":
        print(f"[device] error: {message.args[0]}", file=sys.stderr)
    else:
        print(f"[device] {line}")


def run(link, seconds: float | None = None) -> int:
    personality = Personality()
    link.send(mic("ON"))
    print(f"[boot] robotd {__version__}")
    deadline = None if not seconds else time.time() + seconds
    try:
        for event in link.read_events():
            handle_event(event, personality, link)
            if event.startswith("TOUCH head"):
                emit(personality.on_name("小豆"), link)
            if deadline is not None and time.time() >= deadline:
                break
    except KeyboardInterrupt:  # pragma: no cover - interactive path
        print("\n[exit] interrupted")
    finally:
        link.close()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="robotd", description="Xiaodou host brain")
    parser.add_argument("--port", default=os.environ.get("ROBOTD_PORT", ""), help="serial port, e.g. COM5")
    parser.add_argument("--mock", action="store_true", help="use the built-in scripted device")
    parser.add_argument("--seconds", type=float, default=None, help="stop after N seconds (mock mode)")
    parser.add_argument("--brain", default=os.environ.get("ROBOTD_BRAIN", "rule"), choices=("rule", "external"))
    parser.add_argument("--brain-url", default=os.environ.get("ROBOTD_BRAIN_URL", ""))
    parser.add_argument("--version", action="version", version=f"robotd {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.brain == "external":
        if not args.brain_url:
            print("[error] --brain external needs --brain-url", file=sys.stderr)
            return 2
        if os.environ.get("ROBOTD_NETWORK", "0") != "1":
            print("[error] external brain is off unless ROBOTD_NETWORK=1", file=sys.stderr)
            return 2
    if args.mock or not args.port:
        link = MockLink(DEFAULT_SCENARIO, speed=0.0 if args.seconds == 0 else 1.0)
        if not args.mock and not args.port:
            print("[info] no port given, falling back to mock mode")
        return run(link, seconds=args.seconds)
    try:
        return run(SerialLink(args.port))
    except LinkError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())