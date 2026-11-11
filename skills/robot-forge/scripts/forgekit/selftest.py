"""Plugin self-test: validate layout, then build every blueprint and gate it."""

from __future__ import annotations

import io
import json
import shutil
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace

from . import __version__
from .check import run_checks
from .model import load_project
from .render import render
from .validate import validate_plugin

SKILL_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = SKILL_ROOT.parents[1]
TEMPLATES = SKILL_ROOT / "templates"


def _section(title):
    print("")
    print(title)
    print("-" * min(72, max(24, len(title) + 4)))


def _check_validate():
    issues, _versions = validate_plugin(PLUGIN_ROOT)
    errors = [i for i in issues if i.level == "error"]
    warnings = [i for i in issues if i.level == "warn"]
    for issue in issues:
        print("  " + str(issue))
    if errors:
        print("  插件结构：%d 错误" % len(errors))
        return False
    print("  插件结构：%d 警告（不阻塞）" % len(warnings))
    return True


def _build(blueprint, tmp):
    from .cli import cmd_new

    dest = Path(tmp) / ("bp-" + blueprint)
    args = SimpleNamespace(name="自检机器人", blueprint=blueprint, slug="selftest-" + blueprint, dir=str(dest), force=True, project=None, json=False)
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        code = cmd_new(args)
    if code != 0:
        print("  %s 生成失败（exit %s）" % (blueprint, code))
        for line in buffer.getvalue().splitlines()[-6:]:
            print("    " + line)
        return None
    return dest


def _gate(blueprint, dest, run_verify=True):
    ok = True
    project = load_project(dest)
    if project.load_error:
        print("  %s 加载失败：%s" % (blueprint, project.load_error))
        return False

    results = render(project, write=False)
    stale = [r for r in results if r[1] in ("stale", "created", "problem")]
    if stale:
        ok = False
        print("  %s 生成块不新鲜：%s" % (blueprint, ", ".join(str(s[0]) for s in stale[:6])))

    issues, stats = run_checks(project, deep=False)
    if stats["errors"]:
        ok = False
        for issue in [i for i in issues if i.level == "error"][:10]:
            print("  %s 检查错误 %s" % (blueprint, issue))
    print("  %s check：%d 错误 / %d 警告" % (blueprint, stats["errors"], stats["warnings"]))

    leftovers = []
    for path in dest.rglob("*"):
        if "tools" in path.parts and "forgekit" in path.parts:
            continue
        if path.name in ("__pycache__", ".pytest_cache", ".ruff_cache"):
            leftovers.append(path)
        elif path.is_file() and path.suffix in (".py", ".md", ".yaml", ".yml", ".json", ".csv", ".ini", ".cpp", ".h"):
            text = path.read_text(encoding="utf-8", errors="ignore")
            if "{{NAME}}" in text or "{{SLUG}}" in text or "{{DATE}}" in text:
                leftovers.append(path)
    if leftovers:
        ok = False
        print("  %s 模板残留：%s" % (blueprint, ", ".join(str(p.relative_to(dest)) for p in leftovers[:5])))

    if run_verify:
        from .cli import cmd_verify

        buffer = io.StringIO()
        vargs = SimpleNamespace(project=str(dest), only=None, no_record=True, json=False)
        with redirect_stdout(buffer):
            try:
                code = cmd_verify(vargs)
            except SystemExit as exc:  # pragma: no cover - defensive
                code = int(exc.code or 2)
        if code != 0:
            ok = False
            print("  %s verify 失败（exit %s）" % (blueprint, code))
            for line in buffer.getvalue().splitlines()[-8:]:
                print("    " + line)
        else:
            print("  %s verify：通过" % blueprint)
    return ok


def main(args=None, argv=None):
    run_verify = not bool(getattr(args, "quick", False))
    if argv is not None:
        run_verify = "--quick" not in argv
    print("robot-forge selftest %s" % __version__)
    print("插件根 %s" % PLUGIN_ROOT)
    print("Python %s" % sys.version.split()[0])

    ok = True
    _section("1. 插件结构")
    ok = _check_validate() and ok

    _section("2. 蓝本生成与门禁")
    blueprints = sorted(p.parent.name for p in TEMPLATES.glob("*/blueprint.json")) if TEMPLATES.is_dir() else []
    if not blueprints:
        print("  没有蓝本可测（在生成的项目里 selftest 只做结构检查）。")
    tmp = tempfile.mkdtemp(prefix="forge-selftest-")
    try:
        for blueprint in blueprints:
            print("  [%s]" % blueprint)
            dest = _build(blueprint, tmp)
            if not dest:
                ok = False
                continue
            ok = _gate(blueprint, dest, run_verify=run_verify) and ok
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    _section("结论")
    if ok:
        print("  自检通过：插件结构 + 全部蓝本可生成、可检查%s。" % ("、可验证" if run_verify else ""))
        return 0
    print("  自检失败：先修上面的问题，不要发布。")
    return 1