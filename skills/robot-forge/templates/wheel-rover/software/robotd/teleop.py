"""Keyboard mapping and scripted command sequences."""

from __future__ import annotations

from . import config

VELOCITY_KEYS = {
    "w": (config.DEFAULT_LINEAR_MM_S, 0),
    "s": (-config.DEFAULT_LINEAR_MM_S, 0),
    "a": (0, config.TURN_ANGULAR_MRAD_S),
    "d": (0, -config.TURN_ANGULAR_MRAD_S),
}

SCRIPT_COMMANDS = {
    "forward": ("V", config.DEFAULT_LINEAR_MM_S, 0),
    "back": ("V", -config.DEFAULT_LINEAR_MM_S, 0),
    "left": ("V", 0, config.TURN_ANGULAR_MRAD_S),
    "right": ("V", 0, -config.TURN_ANGULAR_MRAD_S),
    "stop": ("S",),
    "ping": ("PING",),
}

KEY_HELP = """按键：
  w/↑ 前进   s/↓ 后退   a/← 左转   d/→ 右转
  空格 立即停车   q 退出
输入字母后回车（不需要连按）。"""


def command_for_key(key: str) -> tuple[int, int] | None:
    """Map a single key to (lin_mm_s, ang_mrad_s); None means stop/quit/unknown."""
    return VELOCITY_KEYS.get(key.lower())


def line_for_key(key: str) -> str | None:
    """Return a protocol line for a key, or None if the key is not a motion key."""
    from .protocol import encode_velocity

    speed = command_for_key(key)
    if speed is None:
        return None
    return encode_velocity(*speed)


def line_for_script_command(name: str) -> str:
    from .protocol import encode_stop, encode_velocity

    name = name.strip().lower()
    if name not in SCRIPT_COMMANDS:
        raise ValueError(f"unknown script command: {name!r} (use {', '.join(sorted(SCRIPT_COMMANDS))})")
    cmd = SCRIPT_COMMANDS[name]
    if cmd[0] == "V":
        return encode_velocity(cmd[1], cmd[2])
    if cmd[0] == "S":
        return encode_stop()
    return "PING\n"
