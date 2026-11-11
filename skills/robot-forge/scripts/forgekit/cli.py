"""Command line interface: python tools/forge.py <command>."""

from __future__ import annotations

import argparse
import datetime
import importlib.util
import json
import os
import re
import shutil
import sys
from pathlib import Path

from . import __version__
from . import api, design, intake, report
from .check import run_checks
from .model import SLUG_RE, Issue, load_project
from .render import render
from .util import C, enable_color, find_project, read_text, run, setup_console, truncate, which, write_text

SKILL_ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = SKILL_ROOT / "templates"
TOKENS = ("{{NAME}}", "{{SLUG}}", "{{DATE}}", "{{BLUEPRINT}}")

MODULES = {
    "pytest": "pytest",
    "build123d": "build123d",
    "mujoco": "mujoco",
    "serial": "serial",
    "yaml": "yaml",
    "numpy": "numpy",
}
TOOLS = {
    "python": None,
    "git": "git",
    "node": "node",
    "npm": "npm",
    "pio": "pio",
    "arduino-cli": "arduino-cli",
    "kicad-cli": "kicad-cli",
    "openscad": "openscad",
    "ffmpeg": "ffmpeg",
    "esptool": "esptool.py",
    "pwsh": "pwsh",
}


def _ok(flag):
    return C.paint("✅", C.GREEN) if flag else C.paint("⚪", C.YELLOW)


def _find_project(args):
    root = Path(args.project).resolve() if getattr(args, "project", None) else find_project()
    if not root:
        print(C.paint("当前目录不在 robot-forge 项目里。", C.RED))
        print("先创建：python tools/forge.py new 我的机器人 --blueprint <最近蓝本>（先跑 blueprints 选起点）")
        print("或进入项目根目录（含 forge/robot.yaml）再运行。")
        return None
    return load_project(root)


def _module_ok(name):
    try:
        return importlib.util.find_spec(name) is not None
    except Exception:
        return False


def cmd_doctor(args):
    print(C.paint("robot-forge doctor", C.BOLD))
    print("Python      %s (%s)" % (sys.version.split()[0], sys.executable))
    print("forgekit    %s" % __version__)
    print("skill root  %s" % SKILL_ROOT)
    print("")
    rows = []
    rows.append(("python", True, sys.version.split()[0]))
    for key, exe in TOOLS.items():
        if key == "python":
            continue
        path = which(exe) if exe else which("python")
        rows.append((key, bool(path), path or "未安装"))
    for key, mod in MODULES.items():
        rows.append((key, _module_ok(mod), "import %s" % mod))
    for name, ok, detail in rows:
        print("  %s %-12s %s" % (_ok(ok), name, C.paint(detail, C.DIM)))
    missing = [r[0] for r in rows if not r[1]]
    print("")
    if missing:
        print(C.paint("缺少：%s" % ", ".join(missing), C.YELLOW))
        print("缺工具不会让 check 失败；但对应的实测/构建步骤只能标 ⚪ 待验证。")
    else:
        print(C.paint("工具链齐全。", C.GREEN))

    project = _find_project(args) if (args.project or find_project()) else None
    if project and not project.load_error:
        print("")
        print(C.paint("项目：%s" % project.name, C.BOLD))
        needs = sorted({n for cmd in project.verify.get("commands", []) for n in (cmd.get("needs") or [])})
        if needs:
            print("verify 需要：%s" % ", ".join(needs))
            for need in needs:
                if need in MODULES:
                    ok = _module_ok(MODULES[need])
                elif need in TOOLS:
                    ok = bool(which(TOOLS[need] or need))
                else:
                    ok = False
                print("  %s %s" % (_ok(ok), need))
    return 0


def _slugify(text):
    text = str(text).strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text[:40] or "my-robot"


def cmd_new(args):
    blueprint = args.blueprint
    if not blueprint:
        print(C.paint("必须用 --blueprint 指定蓝本。", C.RED))
        print("先运行 blueprints 选最近起点；没有完全匹配的蓝本时，选最近起点后按 references/blueprints.md §3 的 freeform 协议改造。")
        return 2
    src = TEMPLATES / blueprint
    if not src.is_dir():
        print(C.paint("没有这个蓝本：%s" % blueprint, C.RED))
        print("可用：" + ", ".join(sorted(p.name for p in TEMPLATES.glob("*/blueprint.json"))))
        print("没有合适的蓝本？选最接近的蓝本作为起点，按 references/blueprints.md §3 的 freeform 协议改造；不要从空白目录手搓。")
        return 2
    name = str(args.name or "").strip()
    if not name:
        print(C.paint("项目名不能为空。", C.RED))
        return 2
    if "\n" in name or "\r" in name:
        print(C.paint("项目名不能包含换行。", C.RED))
        return 2
    slug = str(args.slug or _slugify(name)).strip()
    if not SLUG_RE.match(slug):
        print(C.paint("slug 只能由小写字母/数字/连字符组成，长度 2-41：%r" % slug, C.RED))
        return 2
    dest = Path(args.dir).resolve() if args.dir else Path.cwd() / slug
    cwd = Path.cwd().resolve()
    home = Path.home().resolve()
    if dest == cwd or dest == home or dest.parent == dest or dest in cwd.parents:
        print(C.paint("拒绝写入危险目录：%s（当前目录、家目录、根目录或其祖先）" % dest, C.RED))
        return 2
    if dest.exists() and not dest.is_dir():
        print(C.paint("目标已存在且不是目录：%s" % dest, C.RED))
        return 2
    nonempty = dest.exists() and any(dest.iterdir())
    if nonempty and not args.force:
        print(C.paint("目标目录非空：%s（用 --force 覆盖）" % dest, C.RED))
        return 2
    if nonempty and args.force and not (dest / "forge" / "robot.yaml").is_file():
        print(C.paint("--force 只覆盖已有 robot-forge 项目（缺 forge/robot.yaml）：%s" % dest, C.RED))
        return 2
    if dest.exists() and args.force:
        for child in dest.iterdir():
            if child.name in (".git",):
                continue
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
    dest.mkdir(parents=True, exist_ok=True)
    today = datetime.date.today().isoformat()
    for path in sorted(src.rglob("*")):
        if path.is_dir():
            (dest / path.relative_to(src)).mkdir(parents=True, exist_ok=True)
            continue
        rel = path.relative_to(src)
        if path.name == "blueprint.json" or "__pycache__" in path.parts:
            continue
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        raw = path.read_bytes()
        if path.suffix.lower() in (".md", ".yaml", ".yml", ".py", ".txt", ".ini", ".json", ".csv"):
            text = raw.decode("utf-8")
            text = text.replace("{{NAME}}", name).replace("{{SLUG}}", slug).replace("{{DATE}}", today).replace("{{BLUEPRINT}}", blueprint)
            write_text(target, text)
        else:
            target.write_bytes(raw)
    # vendor forgekit so the project runs without the plugin
    shutil.copytree(
        SKILL_ROOT / "scripts" / "forgekit",
        dest / "tools" / "forgekit",
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    write_text(dest / "tools" / "forge.py", LAUNCHER)
    gitignore = dest / ".gitignore"
    if not gitignore.is_file():
        write_text(gitignore, DEFAULT_GITIGNORE)

    project = load_project(dest)
    if project.load_error:
        print(C.paint("生成的项目有问题：%s" % project.load_error, C.RED))
        return 1
    results = render(project, write=True)
    changed = [r for r in results if r[1] in ("written", "created")]
    if args.json:
        print(
            json.dumps(
                {
                    "ok": True,
                    "project": str(dest),
                    "name": name,
                    "slug": slug,
                    "blueprint": blueprint,
                    "components": len(project.components),
                    "budget_cny": project.budget,
                    "generated": [str(path) for path, _status in changed],
                    "next": api.next_payload(project),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    print(C.paint("已创建 %s" % dest, C.GREEN))
    print("蓝本 %s · %d 个元件 · 预算 ¥%.0f" % (blueprint, len(project.components), project.budget))
    print("生成文件 %d 个，下一步：" % len(changed))
    print("  cd %s" % dest)
    print("  python tools/forge.py check")
    print("  python tools/forge.py verify")
    print("")
    print("接下来：让 AI 读技能 SKILL.md 与 references/blueprints.md，按 wish 改造 robot.yaml 与文档。")
    return 0


def cmd_render(args):
    project = _find_project(args)
    if not project:
        return 2
    results = render(project, write=not args.check)
    if args.check:
        stale = [r for r in results if r[1] in ("stale", "created")]
        for path, status in stale:
            print("%s %s" % (C.paint("OUTDATED", C.RED), path))
        problems = [r for r in results if r[1] == "problem"]
        for path, status in problems:
            print("%s %s" % (C.paint("MARKER", C.RED), path))
        if not stale and not problems:
            print(C.paint("所有生成内容都是最新的。", C.GREEN))
            return 0
        return 1
    changed = [r for r in results if r[1] in ("written", "created")]
    problems = [r for r in results if r[1] == "problem"]
    for path, status in changed:
        print("%s %s" % (C.paint(status.upper(), C.GREEN), path))
    for path, status in problems:
        print("%s %s" % (C.paint("PROBLEM", C.RED), path))
    print("")
    print("已更新 %d 个文件。" % len(changed))
    if problems:
        print(C.paint("有 %d 个生成块标记问题，见上。" % len(problems), C.YELLOW))
    return 0


def _print_issues(issues, limit=60):
    order = {"error": 0, "warn": 1, "info": 2}
    issues = sorted(issues, key=lambda i: (order.get(i.level, 3), i.rule, i.file or ""))
    shown = 0
    for issue in issues:
        if shown >= limit:
            print("... 还有 %d 条，用 --json 查看全部" % (len(issues) - shown))
            break
        color = C.RED if issue.level == "error" else (C.YELLOW if issue.level == "warn" else C.BLUE)
        tag = C.paint(issue.level.upper().ljust(5), color)
        where = (" " + C.paint(issue.file, C.DIM)) if issue.file else ""
        print("  %s [%s] %s%s" % (tag, issue.rule, issue.msg, where))
        shown += 1


def cmd_check(args):
    project = _find_project(args)
    if not project:
        return 2
    issues, stats = run_checks(project, deep=args.deep)
    if args.json:
        payload = api.check_payload(project, deep=args.deep)
        payload["next"] = api.next_payload(project, payload)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 1 if stats["errors"] else 0
    print(C.paint("%s · check" % project.name, C.BOLD))
    _print_issues(issues, limit=args.limit)
    print("")
    print(
        "%s %d 错误 · %s %d 警告 · %d 条"
        % (C.paint("✗", C.RED) if stats["errors"] else C.paint("✓", C.GREEN), stats["errors"], C.paint("!", C.YELLOW), stats["warnings"], len(issues))
    )
    if stats["errors"] == 0:
        print(C.paint("机器可验证的部分都过了。下一步：python tools/forge.py verify", C.GREEN))
    return 1 if stats["errors"] else 0


def _need_ok(need):
    if need in MODULES:
        return _module_ok(MODULES[need])
    if need in TOOLS:
        return bool(which(TOOLS[need] or need))
    return bool(which(need))


def _append_evidence(project, rows):
    path = project.root / "forge" / "evidence.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def _new_evidence_id(existing):
    now = datetime.datetime.now()
    base = "E-%s-%s" % (now.strftime("%Y%m%d-%H%M%S"), now.strftime("%f")[:3])
    candidate = base
    i = 2
    while candidate in existing:
        candidate = "%s-%d" % (base, i)
        i += 1
    # Several rows can be recorded in the same millisecond; reserve the id so
    # the next call cannot hand out the same one again.
    existing.add(candidate)
    return candidate


def cmd_verify(args):
    project = _find_project(args)
    if not project:
        return 2
    if project.load_error:
        print(C.paint(project.load_error, C.RED))
        return 2
    payload = api.verify_payload(project, only=args.only, record=not args.no_record)
    if payload.get("error"):
        print(C.paint(payload["error"], C.YELLOW))
        return 2
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 1 if payload["failures"] or payload.get("partial") else 0
    print(C.paint("%s · verify" % project.name, C.BOLD))
    for row in payload["results"]:
        status = row.get("status")
        if status == "skip":
            print("  %s %-28s 缺工具，已跳过（非必需）" % (C.paint("SKIP", C.YELLOW), row["id"]))
            continue
        if row.get("missing"):
            print("  %s %-28s 缺工具：%s" % (C.paint("FAIL", C.RED), row["id"], ", ".join(row["missing"])))
            continue
        print("  %s %-28s %s" % (C.paint("RUN ", C.BLUE), row["id"], C.paint(row.get("run", ""), C.DIM)))
        if status == "pass":
            print("        %s" % C.paint("PASS", C.GREEN))
        else:
            print("        %s (exit %s)" % (C.paint("FAIL", C.RED), row.get("exit")))
            for line in (row.get("tail") or "").splitlines()[-12:]:
                print("        " + line[:160])
    if payload["evidence_ids"]:
        print("")
        print("已记录 %d 条证据，并刷新 docs/09 与 README。" % len(payload["evidence_ids"]))
    print("")
    if payload["failures"]:
        print(C.paint("%d 条必需验证失败。" % payload["failures"], C.RED))
        if payload.get("partial"):
            print(C.paint("这只跑了子集；未跑：%s。" % ", ".join(payload.get("omitted_required", [])), C.YELLOW))
        return 1
    if payload.get("partial"):
        print(C.paint("只跑了子集，不能声称全部通过；未跑：%s。" % ", ".join(payload.get("omitted_required", [])), C.YELLOW))
        return 1
    skipped = payload.get("skipped", 0)
    print(C.paint("全部必需验证通过%s。" % ("（跳过 %d 条非必需）" % skipped if skipped else ""), C.GREEN))
    return 0
def cmd_audit(args):
    project = _find_project(args)
    if not project:
        return 2
    payload = api.audit_payload(project)
    stats = payload["stats"]
    requirements = payload["requirements"]
    color = {"release": C.GREEN, "beta": C.YELLOW}.get(payload["release_level"], C.RED)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if payload["release_level"] == "release" else 1
    print(C.paint("%s · 发布审计" % project.name, C.BOLD))
    print("评分 %s / 100　结论：%s　门槛：0 error + must 覆盖 100%% + 评分 ≥ 85" % (
        C.paint(str(payload["score"]), C.BOLD), C.paint(payload["verdict"], color)))
    labels = {
        "buyable": "买得到", "buildable": "造得出", "runnable": "跑得起来",
        "explainable": "说得清", "evidenced": "证得了", "safety": "安全与许可",
    }
    weights = {"buyable": 15, "buildable": 20, "runnable": 25, "explainable": 15, "evidenced": 15, "safety": 10}
    print("  " + "  ".join("%s %.0f/%d" % (labels[k], payload["scorecard"][k], weights[k]) for k in labels))
    print(
        "must 需求 %d 条，已实时/人工确认 %d 条（%.0f%%）；证据 %d 条；错误 %d，警告 %d"
        % (requirements["must"], requirements["covered"], requirements["coverage"],
           payload["evidence"], stats["errors"], stats["warnings"])
    )
    if requirements.get("levels"):
        print("证据分布：" + "  ".join("%s=%d" % (k, v) for k, v in sorted(requirements["levels"].items())))
    print("")
    issues = [Issue(i.get("rule", "?"), i.get("level", "info"), i.get("msg", ""), i.get("file")) for i in payload["issues"]]
    _print_issues(issues, limit=args.limit)
    print("")
    if stats["errors"]:
        print(C.paint("先修错误，再谈发布。", C.RED))
        return 1
    if payload["release_level"] != "release":
        print(C.paint("没有机器可判定的错误，但还不能宣称可发布：结论为「%s」。" % payload["verdict"], C.YELLOW))
        if requirements["coverage"] < 100:
            print(C.paint("还有 must 需求没有实测/人工证据：发布说明里必须列出来。", C.YELLOW))
        return 1
    print(C.paint("通过发布审计：可以发布。", C.GREEN))
    return 0


def cmd_status(args):
    project = _find_project(args)
    if not project:
        return 2
    if project.load_error:
        print(C.paint(project.load_error, C.RED))
        return 1
    if args.json:
        print(json.dumps(api.status_payload(project), ensure_ascii=False, indent=2))
        return 0
    print(C.paint("%s  v%s" % (project.name, project.version), C.BOLD))
    print("slug      %s" % project.slug)
    print("档位      %s" % project.gear)
    print("域        %s" % ", ".join(project.domains))
    print("预算      ¥%.0f（清单 ¥%.0f）" % (project.budget, project.total_cost()))
    print("元件      %d 个 / %d 条需求 / %d 条证据" % (len(project.components), len(project.requirements), len(project.evidence())))
    must = [r for r in project.requirements if str(r.get("priority", "must")) == "must"]
    counts = {}
    for req in must:
        level, _ev = project.requirement_status(req)
        counts[level] = counts.get(level, 0) + 1
    print("must 证据 " + ("  ".join("%s=%d" % (k, v) for k, v in sorted(counts.items())) or "无"))
    issues, stats = run_checks(project)
    print("检查      %d 错误 / %d 警告" % (stats["errors"], stats["warnings"]))
    for issue in [i for i in issues if i.level == "error"][:5]:
        print("  %s [%s] %s" % (C.paint("✗", C.RED), issue.rule, issue.msg))
    evidence = project.evidence()[-3:]
    if evidence:
        print("最近证据：")
        for item in evidence:
            print("  %s %s %s" % (item.get("at", ""), item.get("level", ""), item.get("claim", "")))
    nxt = api.next_payload(project)
    print("")
    print("下一步    %s：%s" % (nxt["tool"], nxt["reason"]))
    return 0


def cmd_next(args):
    root = Path(args.project).resolve() if getattr(args, "project", None) else find_project()
    if not root:
        payload = {
            "action": "choose-blueprint",
            "reason": "当前目录不在 robot-forge 项目里；先选最近蓝本，再创建项目",
            "tool": "rf_blueprints",
            "arguments": {},
            "commands": [
                "python <插件目录>/skills/robot-forge/scripts/forge.py blueprints",
                "python <插件目录>/skills/robot-forge/scripts/forge.py new 我的机器人 --blueprint <最近蓝本>",
            ],
        }
    else:
        project = load_project(root)
        payload = api.next_payload(project)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    print(C.paint("下一步：%s" % payload["action"], C.BOLD))
    print(payload["reason"])
    print("工具：%s" % payload.get("tool", ""))
    for command in payload.get("commands") or []:
        print("  " + command)
    return 0


def cmd_blueprints(args):
    if args.json:
        print(json.dumps({"blueprints": api.blueprints_payload(TEMPLATES)}, ensure_ascii=False, indent=2))
        return 0
    rows = sorted(TEMPLATES.glob("*/blueprint.json"))
    if not rows:
        print("没有蓝本。")
        return 1
    print(C.paint("可用蓝本", C.BOLD))
    for path in rows:
        try:
            meta = json.loads(read_text(path))
        except Exception:
            meta = {"name": path.parent.name}
        print("")
        print("  %s  %s" % (C.paint(meta.get("name", path.parent.name), C.BOLD), C.paint("(%s)" % path.parent.name, C.DIM)))
        print("    %s" % meta.get("one_liner", ""))
        print(
            "    预算 ¥%s · 工期 %s · 难度 %s · 域 %s"
            % (meta.get("cost_cny", "?"), meta.get("time", "?"), meta.get("difficulty", "?"), ", ".join(meta.get("domains", [])))
        )
    print("")
    print("用法：python forge.py new 我的机器人 --blueprint <名字>")
    print("蓝本不是形态白名单：没有完全匹配的，就选最近起点，按 references/blueprints.md §3 的 freeform 协议改造。")
    return 0


def cmd_evidence(args):
    project = _find_project(args)
    if not project:
        return 2
    try:
        row = api.evidence_payload(project, args.req, args.claim, args.level, args.note, args.artifact)
    except ValueError as exc:
        print(C.paint(str(exc), C.RED))
        return 2
    if args.json:
        print(json.dumps({"ok": True, "evidence": row}, ensure_ascii=False, indent=2))
        return 0
    print(C.paint("已记录证据 %s（%s）" % (row["id"], row["level"]), C.GREEN))
    if args.level in ("assumed", "simulated"):
        print(C.paint("提醒：assumed 不算验证；simulated 只算仿真。", C.YELLOW))
    return 0


def cmd_intake(args):
    text = args.text or ""
    if not text:
        print(C.paint("给一段自然语言描述，例如：python tools/forge.py intake \"做一个能跟着我走、避开障碍的小车，预算 300 元\"", C.RED))
        return 2
    payload = intake.intake_payload(text, budget=args.budget)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if payload.get("allowed", True) else 1
    print(intake.render_text(payload))
    return 0 if payload.get("allowed", True) else 1


def cmd_design(args):
    project = _find_project(args)
    if not project:
        return 2
    if project.load_error:
        print(C.paint(project.load_error, C.RED))
        return 2
    payload = design.design_payload(project)
    if args.write:
        lines = [
            "# 设计核算",
            "",
            "> 由 `python tools/forge.py design --write` 生成；改选型/预算/机械参数后重跑。",
            "> 核算不替代实物测试：扭矩、续航、温升都是估算，实测数据以 forge/evidence.jsonl 为准。",
            "",
            "```",
            design.render_text(payload),
            "```",
            "",
            "## 发现",
            "",
        ]
        for finding in payload["findings"]:
            lines.append("- [%s] %s %s" % (finding.get("level"), finding.get("rule"), finding.get("msg")))
        if not payload["findings"]:
            lines.append("- 无")
        lines.append("")
        write_text(project.root / "forge" / "design.md", "\n".join(lines))
        payload["path"] = str(project.root / "forge" / "design.md")
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if payload["ok"] else 1
    print(design.render_text(payload))
    if args.write:
        print("")
        print(C.paint("已写入 forge/design.md", C.GREEN))
    return 0 if payload["ok"] else 1


def cmd_trace(args):
    project = _find_project(args)
    if not project:
        return 2
    if project.load_error:
        print(C.paint(project.load_error, C.RED))
        return 2
    payload = report.trace_payload(project, write=args.write)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if payload["ok"] else 1
    print(report.trace_markdown(project, payload=payload))
    if args.write:
        print("")
        print(C.paint("已写入 forge/trace.md", C.GREEN))
    return 0 if payload["ok"] else 1


def _json_argument(raw, label):
    """Accept inline JSON or @path so a review finding list can live in a file."""
    if raw is None:
        return None
    value = raw.strip()
    if value.startswith("@"):
        try:
            value = Path(value[1:]).read_text(encoding="utf-8")
        except OSError as exc:
            raise ValueError("读不到 %s 文件：%s" % (label, exc))
    try:
        return json.loads(value)
    except ValueError as exc:
        raise ValueError("%s 不是合法 JSON：%s" % (label, exc))


def cmd_review(args):
    project = _find_project(args)
    if not project:
        return 2
    if project.load_error:
        print(C.paint(project.load_error, C.RED))
        return 2
    try:
        findings = _json_argument(getattr(args, "findings", None), "--findings")
    except ValueError as exc:
        print(C.paint(str(exc), C.RED))
        return 2
    payload = report.review_payload(
        project,
        write=not args.no_write,
        verdict=getattr(args, "verdict", None),
        score=getattr(args, "score", None),
        findings=findings,
        reviewer=getattr(args, "reviewer", None),
        note=getattr(args, "note", "") or "",
    )
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if payload["ok"] else 1
    print(report.review_text(payload))
    return 0 if payload["ok"] else 1


def cmd_package(args):
    project = _find_project(args)
    if not project:
        return 2
    if project.load_error:
        print(C.paint(project.load_error, C.RED))
        return 2
    payload = report.package_payload(project, allow_beta=args.beta, out_dir=args.out)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if payload.get("ok") else 1
    print(report.package_text(payload))
    return 0 if payload.get("ok") else 1


def cmd_selftest(args):
    from .selftest import main as selftest_main

    return selftest_main(args)


DEFAULT_GITIGNORE = """# forge
__pycache__/
*.pyc
.pytest_cache/
.venv/
venv/
node_modules/
.pio/
build/
*.log
hardware/stl/*.tmp
"""

LAUNCHER = """#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from forgekit.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
"""


def build_parser():
    parser = argparse.ArgumentParser(prog="forge.py", description="robot-forge: 从愿望到可复现的机器人项目")
    parser.add_argument("--project", help="项目根目录（默认向上找 forge/robot.yaml）")
    parser.add_argument("--version", action="version", version="robot-forge %s" % __version__)
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("doctor", help="检查本机工具链与项目需求")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("new", help="用蓝本创建一个新项目")
    p.add_argument("name", help="项目名（中文即可）")
    p.add_argument("--blueprint", required=True, help="蓝本名（先运行 blueprints 选最近起点）")
    p.add_argument("--slug", help="目录名/仓库名（默认从名字生成）")
    p.add_argument("--dir", help="目标目录（默认 ./<slug>）")
    p.add_argument("--force", action="store_true", help="目标非空时清空重建")
    p.add_argument("--json", action="store_true", help="输出 JSON")
    p.set_defaults(func=cmd_new)

    p = sub.add_parser("render", help="从 robot.yaml 生成 BOM/接线/电源/报告/图")
    p.add_argument("--check", action="store_true", help="只检查是否过期，不写文件")
    p.set_defaults(func=cmd_render)

    p = sub.add_parser("check", help="结构与交付物检查（不跑命令）")
    p.add_argument("--deep", action="store_true", help="额外做发布前检查")
    p.add_argument("--json", action="store_true", help="输出 JSON")
    p.add_argument("--limit", type=int, default=60, help="最多显示多少条")
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("verify", help="执行 verify.yaml 并记录证据")
    p.add_argument("--only", help="只跑这些 id，逗号分隔")
    p.add_argument("--json", action="store_true", help="输出 JSON")
    p.add_argument("--no-record", action="store_true", help="不写证据")
    p.set_defaults(func=cmd_verify)

    p = sub.add_parser("audit", help="发布审计：评分、证据覆盖、未验证项")
    p.add_argument("--json", action="store_true", help="输出 JSON")
    p.add_argument("--limit", type=int, default=80, help="最多显示多少条")
    p.set_defaults(func=cmd_audit)

    p = sub.add_parser("status", help="一页看完项目状态")
    p.add_argument("--json", action="store_true", help="输出 JSON")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("blueprints", help="列出可用蓝本")
    p.add_argument("--json", action="store_true", help="输出 JSON")
    p.set_defaults(func=cmd_blueprints)

    p = sub.add_parser("evidence", help="手工记录一条证据（采访、试用、实物确认）")
    p.add_argument("--req", help="需求 id，如 REQ-001")
    p.add_argument("--claim", required=True, help="证明了什么")
    p.add_argument("--level", default="manual", choices=["manual", "simulated", "assumed"], help="证据级别")
    p.add_argument("--note", help="怎么确认的、谁确认的")
    p.add_argument("--artifact", help="证据文件（截图、日志）相对路径")
    p.add_argument("--json", action="store_true", help="输出 JSON")
    p.set_defaults(func=cmd_evidence)

    p = sub.add_parser("next", help="给出下一步该做什么")
    p.add_argument("--json", action="store_true", help="输出 JSON")
    p.set_defaults(func=cmd_next)

    p = sub.add_parser("intake", help="把一句愿望分类到形态、补齐默认值、列出要确认的问题")
    p.add_argument("text", nargs="?", help="自然语言需求描述")
    p.add_argument("--budget", type=int, help="预算（元）")
    p.add_argument("--json", action="store_true", help="输出 JSON")
    p.set_defaults(func=cmd_intake)

    p = sub.add_parser("design", help="设计核算：扭矩/续航/电流/线径/散热/成本")
    p.add_argument("--write", action="store_true", help="写入 forge/design.md")
    p.add_argument("--json", action="store_true", help="输出 JSON")
    p.set_defaults(func=cmd_design)

    p = sub.add_parser("trace", help="需求→验证→证据追踪矩阵")
    p.add_argument("--write", action="store_true", help="写入 forge/trace.md")
    p.add_argument("--json", action="store_true", help="输出 JSON")
    p.set_defaults(func=cmd_trace)

    p = sub.add_parser("review", help="生成独立盲审包，并记录评审者的结论")
    p.add_argument("--no-write", action="store_true", help="只打印，不写文件")
    p.add_argument("--verdict", choices=["pass", "needs_revision", "reject"], help="评审结论")
    p.add_argument("--score", type=int, help="评审分数 0–100（release 要求 >= 70）")
    p.add_argument("--reviewer", help="评审者：人/独立代理的名字，不能为空")
    p.add_argument("--findings", help="findings 的 JSON 数组，或 @文件路径")
    p.add_argument("--note", default="", help="评审备注")
    p.add_argument("--json", action="store_true", help="输出 JSON")
    p.set_defaults(func=cmd_review)

    p = sub.add_parser("package", help="通过审计后打发布包（zip + SHA256SUMS）")
    p.add_argument("--beta", action="store_true", help="允许未验证项的 Beta 包")
    p.add_argument("--out", default="dist", help="输出目录（默认 dist）")
    p.add_argument("--json", action="store_true", help="输出 JSON")
    p.set_defaults(func=cmd_package)

    p = sub.add_parser("selftest", help="验证插件自身：所有蓝本可生成、可检查")
    p.add_argument("--quick", action="store_true", help="跳过 verify，只做结构与生成检查")
    p.set_defaults(func=cmd_selftest)
    return parser


def main(argv=None):
    setup_console()
    enable_color(sys.stdout.isatty() and os.environ.get("NO_COLOR") is None)
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 0
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("\n中断。")
        return 130
    except Exception as exc:  # noqa: BLE001 - CLI should explain, not dump a traceback
        if os.environ.get("FORGE_DEBUG"):
            raise
        print(C.paint("forge.py 内部错误：%s" % exc, C.RED))
        print("设置 FORGE_DEBUG=1 可看完整堆栈；顺手报个 issue。")
        return 2