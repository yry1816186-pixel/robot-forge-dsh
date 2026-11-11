"""Command-line entry point for the rover host software."""

from __future__ import annotations

import argparse
import sys
import time

from . import config, protocol
from .link import LinkError, open_link
from .teleop import KEY_HELP, line_for_key, line_for_script_command


def _print_reply(reply: str) -> None:
    if reply.startswith("T "):
        try:
            t = protocol.parse_reply(reply)
        except protocol.ProtocolError:
            print(f"  <- {reply}")
            return
        print("  <- dist=%dmm yaw=%d° batt=%.2fV" % (
            t["dist_mm"], t["yaw_mdeg"] / 1000.0, t["batt_mv"] / 1000.0))
    else:
        print(f"  <- {reply}")


def _send(link, line: str) -> str:
    reply = link.send(line)
    _print_reply(reply)
    return reply


def run_script(link, script: str) -> int:
    names = [part for part in script.replace(";", ",").split(",") if part.strip()]
    if not names:
        print("script is empty", file=sys.stderr)
        return 2
    for name in names:
        try:
            line = line_for_script_command(name)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        print("->", line.strip())
        _send(link, line)
        for extra in link.poll():
            _print_reply(extra)
        time.sleep(0.05)
    _send(link, protocol.encode_stop())
    return 0


def _key_ready(timeout_s: float = 0.02) -> bool:
    if sys.platform == "win32":
        import msvcrt  # type: ignore

        return msvcrt.kbhit()
    import select  # type: ignore

    ready, _, _ = select.select([sys.stdin], [], [], timeout_s)
    return bool(ready)


def _read_key() -> str:
    if sys.platform == "win32":
        import msvcrt  # type: ignore

        return msvcrt.getwch()
    return sys.stdin.read(1)


def interactive(link) -> int:
    print(KEY_HELP)
    _send(link, protocol.encode_stop())
    last_motion = 0.0
    next_poll = time.monotonic()
    try:
        while True:
            now = time.monotonic()
            if _key_ready():
                key = _read_key()
                if key in ("q", "Q", "\x03"):
                    break
                if key in (" ", "\r", "\n"):
                    _send(link, protocol.encode_stop())
                    last_motion = 0.0
                else:
                    line = line_for_key(key)
                    if line is not None:
                        _send(link, line)
                        last_motion = now
            if last_motion and now - last_motion >= config.RELEASE_STOP_MS / 1000.0:
                _send(link, protocol.encode_stop())
                last_motion = 0.0
            if now >= next_poll:
                for extra in link.poll():
                    _print_reply(extra)
                next_poll = now + 0.1
            time.sleep(0.01)
    except KeyboardInterrupt:
        pass
    finally:
        _send(link, protocol.encode_stop())
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Wheel rover host teleop")
    parser.add_argument("--port", help="serial port, e.g. COM5 or /dev/ttyACM0")
    parser.add_argument("--mock", action="store_true", help="use the in-memory mock link")
    parser.add_argument("--script", help="comma-separated: forward,back,left,right,stop,ping")
    parser.add_argument("--once", help="send one protocol line (V/S/PING), then exit")
    parser.add_argument("--list", action="store_true", help="list available serial ports")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.list:
        try:
            from serial.tools import list_ports  # type: ignore
        except ImportError:
            print("pyserial is not installed", file=sys.stderr)
            return 2
        for p in list_ports.comports():
            print(f"{p.device}\t{p.description}")
        return 0

    if not args.mock and not args.port:
        print("need --port or --mock", file=sys.stderr)
        return 2
    try:
        link = open_link(args.port, mock=args.mock)
    except LinkError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    try:
        if args.once:
            line = args.once if args.once.endswith("\n") else args.once + "\n"
            _send(link, line)
            return 0
        if args.script:
            return run_script(link, args.script)
        return interactive(link)
    except KeyboardInterrupt:
        return 0
    finally:
        try:
            _send(link, protocol.encode_stop())
        except Exception:  # noqa: BLE001 - never mask the original error
            pass
        link.close()


if __name__ == "__main__":
    raise SystemExit(main())