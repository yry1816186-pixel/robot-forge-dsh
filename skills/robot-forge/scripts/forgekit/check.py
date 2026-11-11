"""Deterministic checks: S1-S14 (model) plus D1-D10 (deliverable)."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from . import yamlmini
from .consistency import consistency_issues
from .design import design_issues
from .model import REQUIRED_DOCS, Issue, _list, validate
from .render import render_plan
from .util import cjk_ratio, read_text

SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "venv",
    "env",
    ".idea",
    ".vscode",
    "forge",
    "diagrams",
    "forgekit",
}
TEXT_EXT = {
    ".md",
    ".txt",
    ".py",
    ".c",
    ".cpp",
    ".h",
    ".hpp",
    ".ino",
    ".ini",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".csv",
    ".xml",
    ".urdf",
    ".sdf",
    ".mjcf",
    ".sh",
    ".ps1",
    ".html",
    ".js",
    ".ts",
}

PLACEHOLDER_RE = re.compile(r"(?<![A-Za-z])(TODO|FIXME|TBD|XXX)(?![A-Za-z])|待补|待填|待定|占位|xxx|待完善|\{\{[^}]+\}\}")
LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
CLAIM_RE = re.compile(r"已实测|实测通过|已通过实机测试|实机验证通过|已通过验证")
TRIVIAL_RE = re.compile(
    r"^\s*(?:true|:|exit\s+0)\s*$"
    r"|^\s*(?:echo|sleep)\b"
    r"|^\s*(?:bash|sh|cmd|powershell)(?:\.exe)?\s+(?:-c|/c)\s+[\"']?(?:true|:|echo|exit\s+0|sleep)\b"
    r"|^\s*(?:python3?|py)(?:\s+-[A-Za-z]+)*\s+-c\s+[\"']?(?:pass|print|exit|import\s+sys\s*;\s*sys\.exit\(0\))",
    re.I,
)
BLOCK_RE = re.compile(r"<!-- forge:begin ([a-z0-9-]+) -->(.*?)<!-- forge:end \1 -->", re.S)
FENCE_RE = re.compile(chr(96) * 3 + r".*?" + chr(96) * 3, re.S)

REQUIRED_MARKERS = {
    "README.md": ["forge:begin status-matrix"],
    "docs/00-总览.md": ["forge:begin arch-graph"],
    "docs/01-物料清单.md": ["forge:begin bom-table", "forge:begin bom-total"],
    "docs/02-组装指南.md": ["forge:begin assembly-parts"],
    "docs/03-接线表.md": ["forge:begin bus-table", "forge:begin pinout", "forge:begin power-table"],
    "docs/09-验证报告.md": ["forge:begin req-evidence", "forge:begin evidence-log", "forge:begin unverified-list"],
}

REQUIRED_SECTIONS = {
    "README.md": [["快速开始", "快速上手"], ["项目结构", "目录结构"], ["安全"]],
    "docs/00-总览.md": [["一句话"], ["能力"], ["边界"], ["不做什么", "非目标"]],
    "docs/01-物料清单.md": [["物料", "BOM"]],
    "docs/02-组装指南.md": [["工具"], ["步骤"], ["检查点"]],
    "docs/03-接线表.md": [["接线"], ["电源"]],
    "docs/04-固件说明.md": [["环境"], ["烧录"], ["代码结构", "目录结构"]],
    "docs/05-软件说明.md": [["安装"], ["运行"], ["配置"]],
    "docs/06-使用手册.md": [["首次使用", "第一次"], ["日常"], ["维护"]],
    "docs/07-安全与隐私.md": [["安全"], ["隐私"]],
    "docs/08-故障排查.md": [["症状", "现象"], ["排查"]],
    "docs/09-验证报告.md": [["结论"], ["复现"]],
    "docs/10-常见问题.md": [["常见问题", "FAQ"]],
}


def _issue(issues, rule, level, msg, file=None):
    issues.append(Issue(rule, level, msg, file))


def iter_text_files(root):
    root = Path(root)
    for dirpath, dirnames, filenames in os.walk(str(root)):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".git")]
        for name in filenames:
            path = Path(dirpath) / name
            ext = path.suffix.lower()
            if ext not in TEXT_EXT:
                continue
            try:
                if path.stat().st_size > 512 * 1024:
                    continue
            except OSError:
                continue
            yield path


def _strip_generated(text):
    text = BLOCK_RE.sub("", text)
    return FENCE_RE.sub("", text)


def _rel(path, root):
    try:
        return str(Path(path).resolve().relative_to(Path(root).resolve())).replace("\\", "/")
    except Exception:
        return str(path)


def check_files(project):
    issues = []
    root = project.root
    for rel in REQUIRED_DOCS:
        if not (root / rel).is_file():
            _issue(issues, "D2", "error", "缺少必需文件 %s" % rel, rel)

    if "cad" in project.domains:
        cad = list((root / "hardware" / "cad").glob("*.py")) if (root / "hardware" / "cad").is_dir() else []
        if not cad:
            _issue(issues, "D2", "error", "cad 域必须有 hardware/cad/*.py（build123d 源码）", "hardware/cad")
    if "firmware" in project.domains:
        for rel in ("firmware/platformio.ini", "firmware/src/main.cpp"):
            if not (root / rel).is_file():
                _issue(issues, "D2", "error", "缺少 %s" % rel, rel)
        tests = list((root / "firmware" / "test").glob("test_*.cpp")) if (root / "firmware" / "test").is_dir() else []
        if not tests:
            _issue(issues, "D2", "warn", "firmware/test 没有 test_*.cpp，固件构建只能靠手工", "firmware/test")
    if "software" in project.domains:
        for rel in ("software/pyproject.toml", "software/robotd/main.py"):
            if not (root / rel).is_file():
                _issue(issues, "D2", "error", "缺少 %s" % rel, rel)
        tests = list((root / "software" / "tests").glob("test_*.py")) if (root / "software" / "tests").is_dir() else []
        if not tests:
            _issue(issues, "D2", "error", "software/tests 没有 test_*.py：没有可自动验证的主机软件", "software/tests")
    if "sim" in project.domains:
        sim = root / "sim"
        if not sim.is_dir():
            _issue(issues, "D2", "error", "sim 域必须有 sim/ 仿真目录", "sim")
        elif not (list(sim.glob("*.xml")) + list(sim.glob("*.py")) + list(sim.glob("*.urdf"))):
            _issue(issues, "D2", "error", "sim/ 里没有场景或仿真脚本", "sim")
        if sim.is_dir() and not (sim / "README.md").is_file():
            _issue(issues, "D2", "warn", "sim/README.md 缺失：写清怎么跑、跑出来算什么", "sim/README.md")

    for rel in ("forge/robot.yaml", "forge/verify.yaml", "forge/plan.md", "forge/decisions.md", "forge/evidence.jsonl"):
        if not (root / rel).is_file():
            _issue(issues, "D2", "error", "缺少状态文件 %s" % rel, rel)
    if not (root / "forge" / "research.md").is_file():
        level = "warn" if project.gear == "quick" else "error"
        _issue(issues, "D2", level, "缺少 forge/research.md：没有调研就没有选型依据", "forge/research.md")

    for rel, markers in REQUIRED_MARKERS.items():
        path = root / rel
        if not path.is_file():
            continue
        text = read_text(path)
        for marker in markers:
            if marker not in text:
                _issue(issues, "D3", "error", "%s 缺少生成块标记 %s" % (rel, marker), rel)
    for rel, groups in REQUIRED_SECTIONS.items():
        path = root / rel
        if not path.is_file():
            continue
        text = read_text(path)
        for alts in groups:
            if not any(a in text for a in alts):
                _issue(issues, "D3", "error", "%s 缺少章节：%s" % (rel, " / ".join(alts)), rel)

    p = root / "docs" / "02-组装指南.md"
    if p.is_file() and read_text(p).count("检查点") < 3:
        _issue(issues, "D3", "error", "docs/02 至少要有 3 个「检查点」，否则装配无法自检", "docs/02-组装指南.md")
    p = root / "docs" / "06-使用手册.md"
    if p.is_file() and read_text(p).count("###") < 3:
        _issue(issues, "D3", "error", "docs/06 至少拆成 3 个使用小节", "docs/06-使用手册.md")
    p = root / "docs" / "10-常见问题.md"
    if p.is_file() and read_text(p).count("###") < 6:
        _issue(issues, "D3", "warn", "docs/10 问题少于 6 条，覆盖不足", "docs/10-常见问题.md")

    verify = project.verify or {}
    if verify.get("_error"):
        _issue(issues, "D2", "error", verify["_error"], "forge/verify.yaml")
    commands = _list(verify.get("commands"))
    if not commands:
        _issue(issues, "D2", "warn", "forge/verify.yaml 没有 commands：没有一键验证", "forge/verify.yaml")
    ids = set()
    for cmd in commands:
        cid = str(cmd.get("id", ""))
        if cid in ids:
            _issue(issues, "D2", "error", "verify.yaml 命令 id 重复：%s" % cid, "forge/verify.yaml")
        ids.add(cid)
        if not str(cmd.get("run", "")).strip():
            _issue(issues, "D2", "error", "verify.yaml 命令 %s 缺 run" % cid, "forge/verify.yaml")
        run = str(cmd.get("run", ""))
        if TRIVIAL_RE.search(run):
            _issue(
                issues,
                "D2",
                "error",
                "verify.yaml 的 %s 是空跑命令，不能证明任何东西：%s" % (cid, run[:80]),
                "forge/verify.yaml",
            )
        cmd_cwd = str(cmd.get("cwd", "") or ".").strip() or "."
        base = root
        try:
            base = (root / cmd_cwd).resolve()
            base.relative_to(root.resolve())
        except (OSError, ValueError):
            base = None
        if base is None or not base.is_dir():
            _issue(
                issues,
                "D2",
                "error",
                "verify.yaml 命令 %s 的 cwd 无效、越界或不存在：%s" % (cid, cmd_cwd),
                "forge/verify.yaml",
            )
        m = re.match(r"^(?:python3?|py)\s+([\w./-]+\.py)\b", run)
        if m and base is not None and not (base / m.group(1)).is_file():
            _issue(issues, "D2", "error", "verify.yaml 的 %s 引用了不存在的脚本 %s" % (cid, m.group(1)), "forge/verify.yaml")
        for need in _list(cmd.get("needs")):
            if need not in ("python", "pytest", "pio", "node", "npm", "pnpm", "git", "kicad-cli", "openscad", "ffmpeg", "mujoco", "build123d", "serial", "esptool"):
                _issue(issues, "D2", "warn", "verify.yaml 命令 %s 的 needs %r 不认识（会当成缺工具）" % (cid, need), "forge/verify.yaml")

    return issues


def check_placeholders(project):
    issues = []
    for path in iter_text_files(project.root):
        rel = _rel(path, project.root)
        if rel.startswith("forge/"):
            continue
        try:
            text = read_text(path)
        except Exception:
            continue
        for m in PLACEHOLDER_RE.finditer(text):
            line = text[: m.start()].count("\n") + 1
            _issue(issues, "S12", "error", "占位内容 %r（第 %d 行）：交付物里不能留半成品" % (m.group(0), line), "%s:%d" % (rel, line))
            break
    return issues


def check_links(project):
    issues = []
    roots = [project.root / "README.md"] + sorted((project.root / "docs").glob("*.md"))
    for path in roots:
        if not path.is_file():
            continue
        text = read_text(path)
        for m in LINK_RE.finditer(text):
            target = m.group(1).strip()
            if target.startswith(("http://", "https://", "mailto:", "#", "data:")):
                continue
            target = target.split("#")[0]
            if not target:
                continue
            resolved = (path.parent / target).resolve()
            if not resolved.exists():
                rel = _rel(path, project.root)
                _issue(issues, "S13", "error", "%s 的链接指向不存在的文件：%s" % (rel, m.group(1)), rel)
    return issues


def check_syntax(project):
    issues = []
    for path in iter_text_files(project.root):
        rel = _rel(path, project.root)
        ext = path.suffix.lower()
        text = read_text(path)
        if ext == ".py":
            try:
                compile(text, str(path), "exec")
            except SyntaxError as exc:
                _issue(issues, "D5", "error", "Python 语法错误：%s（第 %s 行）" % (exc.msg, exc.lineno), rel)
        elif ext == ".json":
            try:
                json.loads(text)
            except Exception as exc:  # noqa: BLE001
                _issue(issues, "D5", "error", "JSON 解析失败：%s" % exc, rel)
        elif ext in (".yaml", ".yml"):
            try:
                yamlmini.loads(text)
            except Exception as exc:  # noqa: BLE001
                _issue(issues, "D5", "error", "YAML 解析失败：%s" % exc, rel)
        elif ext in (".c", ".cpp", ".h", ".hpp", ".ino"):
            if not _braces_balanced(text):
                _issue(issues, "D5", "warn", "花括号不平衡（可能截断，或字符串里有括号）", rel)
        elif ext == ".ini" and path.name == "platformio.ini":
            if "[env:" not in text:
                _issue(issues, "D5", "error", "platformio.ini 缺少 [env:...] 段", rel)
    return issues


def _braces_balanced(text):
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"//[^\n]*", "", text)
    text = re.sub(r'"(?:\\.|[^"\\])*"', '""', text)
    text = re.sub(r"'(?:\\.|[^'\\])*'", "''", text)
    return text.count("{") == text.count("}")


def check_blocks(project):
    issues = []
    plan = render_plan(project)
    for path, content in plan.files.items():
        target = Path(path)
        rel = _rel(target, project.root)
        if not target.is_file():
            continue
        if read_text(target) != content:
            _issue(issues, "D1", "error", "%s 与 robot.yaml 不一致：跑 python tools/forge.py render" % rel, rel)
    for problem in plan.problems:
        if "缺少成对标记" in problem:
            rel = problem.split(" 缺少")[0]
            if (project.root / rel).is_file():
                _issue(issues, "D1", "error", problem, rel)
    return issues


def check_evidence(project, deep=False):
    issues = []
    items = project.evidence()
    seen = set()
    for item in items:
        if item.get("_broken"):
            _issue(issues, "D4", "error", "evidence.jsonl 有一行不是合法 JSON：%s" % str(item.get("claim"))[:80], "forge/evidence.jsonl")
            continue
        eid = str(item.get("id", ""))
        if not eid:
            _issue(issues, "D4", "error", "证据缺 id", "forge/evidence.jsonl")
        elif eid in seen:
            _issue(issues, "D4", "error", "证据 id 重复：%s" % eid, "forge/evidence.jsonl")
        seen.add(eid)
        lvl = str(item.get("level", "")).lower()
        if lvl not in ("measured", "manual", "simulated", "assumed"):
            _issue(issues, "D4", "error", "证据 %s 的 level=%r 不认识（measured/manual/simulated/assumed）" % (eid, lvl), "forge/evidence.jsonl")
        if lvl == "measured" and str(item.get("exit", 0)) not in ("0", "None", ""):
            _issue(issues, "D4", "error", "证据 %s 标成实测但退出码不为 0" % eid, "forge/evidence.jsonl")
        if lvl in ("measured", "manual"):
            if not str(item.get("fingerprint", "") or ""):
                _issue(
                    issues,
                    "D4",
                    "error" if deep else "warn",
                    "证据 %s 是%s但没有源码指纹（旧证据或手写），请重新记录/验证" % (eid, "实测" if lvl == "measured" else "人工"),
                    "forge/evidence.jsonl",
                )
            elif not project.evidence_is_fresh(item):
                _issue(
                    issues,
                    "D4",
                    "error" if deep else "warn",
                    "证据 %s 已过期：源码/配置在验证之后改过，请重新记录/验证" % eid,
                    "forge/evidence.jsonl",
                )
        artifact = str(item.get("artifact", "") or "")
        if artifact and not (project.root / artifact).exists():
            _issue(issues, "D4", "warn", "证据 %s 的 artifact 不存在：%s" % (eid, artifact), "forge/evidence.jsonl")

    for req in project.requirements:
        if str(req.get("priority", "must")) != "must":
            continue
        rid = str(req.get("id", ""))
        level, ev = project.requirement_status(req)
        stale = [
            item
            for item in ev
            if str(item.get("level", "")).lower() in ("measured", "manual") and not project.evidence_is_fresh(item)
        ]
        if not ev:
            _issue(issues, "D4", "error" if deep else "warn", "must 需求 %s 还没有证据（发布审计会阻断）" % rid, "forge/evidence.jsonl")
        elif stale and level not in ("measured", "manual"):
            _issue(
                issues,
                "D4",
                "error" if deep else "warn",
                "must 需求 %s 的实测/人工证据已过期（源码/配置在验证后改过），需要重新验证/记录" % rid,
                "forge/evidence.jsonl",
            )
        elif level == "assumed":
            _issue(issues, "D4", "error" if deep else "warn", "must 需求 %s 只有 assumed 证据（未验证）" % rid, "forge/evidence.jsonl")
        elif level == "simulated" and deep:
            _issue(issues, "D4", "warn", "must 需求 %s 只有仿真证据，实物未验证" % rid, "forge/evidence.jsonl")
        elif level == "manual":
            for item in ev:
                if str(item.get("level", "")).lower() != "manual":
                    continue
                if not str(item.get("note", "") or "").strip():
                    if deep:
                        _issue(issues, "D4", "error", "must 需求 %s 是人工证据但没写 note（谁、怎么确认的）" % rid, "forge/evidence.jsonl")
                    break
    return issues


def check_claims(project):
    issues = []
    must = [r for r in project.requirements if str(r.get("priority", "must")) == "must"]
    covered = all(project.requirement_status(r)[0] in ("measured", "manual") for r in must)
    if covered:
        return issues
    targets = [project.root / "README.md"] + sorted((project.root / "docs").glob("*.md"))
    for path in targets:
        if not path.is_file():
            continue
        text = _strip_generated(read_text(path))
        m = CLAIM_RE.search(text)
        if m:
            rel = _rel(path, project.root)
            _issue(issues, "D8", "error", "声称「%s」但没有任何实测/人工证据" % m.group(0), rel)
    return issues


def check_language(project):
    issues = []
    targets = [project.root / "README.md"] + sorted((project.root / "docs").glob("*.md"))
    for path in targets:
        if not path.is_file():
            continue
        text = BLOCK_RE.sub("", read_text(path))
        if len(text) < 300:
            continue
        ratio = cjk_ratio(text)
        if ratio < 0.45:
            rel = _rel(path, project.root)
            _issue(issues, "D7", "warn", "%s 中文占比只有 %.0f%%：零基础用户读不动，请用中文重写" % (rel, ratio * 100), rel)
    return issues


def check_release(project):
    issues = []
    lic = project.root / "LICENSE"
    if lic.is_file() and len(read_text(lic).strip()) < 100:
        _issue(issues, "D9", "error", "LICENSE 内容过短，不是有效许可证", "LICENSE")
    changelog = project.root / "CHANGELOG.md"
    if changelog.is_file():
        text = read_text(changelog)
        if project.version not in text:
            _issue(issues, "D9", "error", "CHANGELOG.md 没有当前版本 %s 的记录" % project.version, "CHANGELOG.md")
        if "## " not in text:
            _issue(issues, "D9", "warn", "CHANGELOG.md 没有分版本小节", "CHANGELOG.md")
    return issues


def check_bom_file(project):
    issues = []
    path = project.root / "hardware" / "bom.csv"
    if not path.is_file():
        return issues
    lines = [line for line in read_text(path).splitlines() if line.strip()]
    if len(lines) < 2:
        _issue(issues, "D6", "error", "hardware/bom.csv 没有内容", "hardware/bom.csv")
        return issues
    total_line = next((line for line in lines if line.startswith("合计,")), None)
    if not total_line:
        _issue(issues, "D6", "error", "hardware/bom.csv 缺合计行", "hardware/bom.csv")
        return issues
    parts = total_line.split(",")
    try:
        csv_total = float(parts[5])
    except (IndexError, ValueError):
        _issue(issues, "D6", "error", "hardware/bom.csv 合计行格式不对", "hardware/bom.csv")
        return issues
    calc = sum(r["subtotal"] for r in project.bom_rows())
    if abs(csv_total - calc) > 0.05:
        _issue(issues, "D6", "error", "BOM 合计 ¥%.2f 与元件清单 ¥%.2f 不一致" % (csv_total, calc), "hardware/bom.csv")
    return issues


def check_yes_no(project):
    issues = []
    p = project.root / "docs" / "01-物料清单.md"
    text = read_text(p) if p.is_file() else ""
    for c in project.components:
        part = str(c.get("part", ""))
        if text and part and part not in text:
            _issue(issues, "D10", "warn", "元件 %s（%s）没有出现在 docs/01 物料清单里" % (c.get("id"), part), "docs/01-物料清单.md")
    return issues


def check_audit_extra(project):
    issues = []
    for item in project.evidence():
        if item.get("_broken"):
            continue
        if str(item.get("level", "")).lower() == "measured" and not str(item.get("command", "")).strip():
            _issue(issues, "D10", "error", "证据 %s 声称实测但没有记录命令" % item.get("id"), "forge/evidence.jsonl")
    for req in project.requirements:
        if str(req.get("priority", "must")) != "must":
            continue
        level, _ev = project.requirement_status(req)
        if level in ("simulated", "assumed", "none"):
            _issue(issues, "D10", "warn", "发布前未闭环：%s %s（%s）" % (req.get("id"), req.get("text"), level), "forge/evidence.jsonl")
    return issues


def _as_issue(finding):
    level = "warn" if finding.get("level") == "warning" else finding.get("level", "info")
    return Issue(finding.get("rule", "CST-00"), level, str(finding.get("msg", "")), str(finding.get("file", "")))


def run_checks(project, deep=False):
    if project.load_error:
        return [Issue("S1", "error", project.load_error, "forge/robot.yaml")], {"errors": 1, "warnings": 0, "infos": 0}
    issues = []
    issues.extend(validate(project))
    issues.extend(check_files(project))
    issues.extend(check_placeholders(project))
    issues.extend(check_links(project))
    issues.extend(check_syntax(project))
    issues.extend(check_blocks(project))
    issues.extend(check_evidence(project, deep=deep))
    issues.extend(check_claims(project))
    issues.extend(check_language(project))
    issues.extend(check_release(project))
    issues.extend(check_bom_file(project))
    issues.extend(check_yes_no(project))
    # Cross-artifact checks are cheap and catch the errors single-file checks
    # cannot see; numeric design review is deeper and only runs in audit mode.
    issues.extend(_as_issue(f) for f in consistency_issues(project))
    if deep:
        issues.extend(check_audit_extra(project))
        issues.extend(_as_issue(f) for f in design_issues(project))

    seen = set()
    unique = []
    for issue in issues:
        key = (issue.rule, issue.level, issue.msg, issue.file)
        if key in seen:
            continue
        seen.add(key)
        unique.append(issue)
    stats = {
        "errors": sum(1 for i in unique if i.level == "error"),
        "warnings": sum(1 for i in unique if i.level == "warn"),
        "infos": sum(1 for i in unique if i.level == "info"),
    }
    return unique, stats
