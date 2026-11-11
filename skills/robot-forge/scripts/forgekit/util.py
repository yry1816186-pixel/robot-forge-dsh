"""Shared helpers for forgekit."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

CJK_RE = re.compile(r"[\u3400-\u9fff]")


def setup_console():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


class C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[36m"
    MAGENTA = "\033[35m"

    enabled = True

    @classmethod
    def paint(cls, text, color):
        if not cls.enabled:
            return text
        return color + str(text) + cls.RESET


def enable_color(flag):
    C.enabled = bool(flag) and os.environ.get("NO_COLOR") is None


def eprint(*args):
    print(*args, file=sys.stderr)


def read_text(path):
    return Path(path).read_text(encoding="utf-8", errors="replace")


def write_text(path, text):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8", newline="\n")


def load_json(path, default=None):
    try:
        return json.loads(read_text(path))
    except Exception:
        return default


def dump_json(path, data):
    write_text(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def find_project(start=None):
    cur = Path(start or Path.cwd()).resolve()
    for candidate in [cur] + list(cur.parents):
        if (candidate / "forge" / "robot.yaml").is_file():
            return candidate
    return None


def rel(path, root):
    try:
        return str(Path(path).resolve().relative_to(Path(root).resolve())).replace("\\", "/")
    except Exception:
        return str(path)


def which(name):
    return shutil.which(name)


def run(cmd, cwd, timeout=900, env=None):
    """Run a shell command, return (exit_code, combined_output)."""
    merged = os.environ.copy()
    if env:
        merged.update(env)
    try:
        proc = subprocess.run(
            cmd,
            shell=True,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            env=merged,
        )
        out = proc.stdout.decode("utf-8", errors="replace")
        return proc.returncode, out
    except subprocess.TimeoutExpired as exc:
        out = (exc.output or b"").decode("utf-8", errors="replace")
        return 124, out + "\n[timeout] %ss" % timeout
    except Exception as exc:  # noqa: BLE001 - surface any launch failure as failure
        return 127, "cannot run command: %r" % (exc,)


def cjk_ratio(text):
    if not text:
        return 0.0
    cjk = len(CJK_RE.findall(text))
    letters = len(re.findall(r"[A-Za-z\u3400-\u9fff]", text))
    return cjk / letters if letters else 0.0


def human_size(n):
    for unit in ("B", "KB", "MB"):
        if n < 1024:
            return "%.0f %s" % (n, unit) if unit == "B" else "%.1f %s" % (n, unit)
        n /= 1024.0
    return "%.1f GB" % n


def truncate(text, limit=4000):
    text = text or ""
    if len(text) <= limit:
        return text
    return text[: limit // 2] + "\n... [truncated %d chars] ...\n" % (len(text) - limit) + text[-limit // 2:]
