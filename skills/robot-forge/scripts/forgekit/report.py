"""Release artifacts: trace matrix, blind-review packet, and deterministic zip.

Reviewers should not have to trust the builder's prose. This module produces
three things a reviewer (human or another model) can verify independently:
a requirement-to-evidence trace, a self-contained blind-review packet with the
exact commands to rerun, and a package whose hash can be compared after upload.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import zipfile
from pathlib import Path

from .check import run_checks
from .model import LEVELS_OK
from .util import read_text


EXCLUDE_DIRS = {".git", "__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache", ".venv", "venv", "env",
                "node_modules", ".pio", "dist", ".forge", ".idea", ".vscode"}
EXCLUDE_SUFFIX = {".pyc", ".pyo", ".zip", ".log"}
EXCLUDE_FILES = {"forge/review-packet.md", "forge/review-packet.json", "forge/trace.md"}
FIXED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)


def _rel(project, path):
    return path.relative_to(project.root).as_posix()


def _sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 256), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _zip_add(zf, arcname, payload):
    """Add bytes with a fixed timestamp/mode so equal inputs give equal bytes."""
    info = zipfile.ZipInfo(arcname, date_time=FIXED_ZIP_TIME)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = (0o100644 & 0xFFFF) << 16
    zf.writestr(info, payload)


def _evidence_index(project):
    index = {}
    for row in project.evidence():
        index.setdefault(str(row.get("req", "")), []).append(row)
    return index


def _trace_rows(project):
    evidence = _evidence_index(project)
    commands = project.verify_command_rows()
    by_req = {}
    for cmd in commands:
        reqs = cmd.get("req") or []
        if isinstance(reqs, str):
            reqs = [reqs]
        for req in reqs:
            by_req.setdefault(str(req), []).append(str(cmd.get("id", "")))
    rows = []
    for req in project.requirements:
        rid = str(req.get("id", ""))
        level, ev = project.requirement_status(req)
        rows.append(
            {
                "id": rid,
                "text": str(req.get("text", "")),
                "priority": str(req.get("priority", "must")),
                "verify": str(req.get("verify", "")),
                "commands": by_req.get(rid, []),
                "evidence": len(evidence.get(rid, [])),
                "level": level,
                "ok": level in LEVELS_OK,
                "features": req.get("features") or [],
            }
        )
    return rows


def trace_payload(project, write=False):
    rows = _trace_rows(project)
    must = [r for r in rows if r["priority"] == "must"]
    covered = [r for r in must if r["ok"]]
    path = project.root / "forge" / "trace.md"
    if write:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(trace_markdown(project, rows), encoding="utf-8", newline="\n")
    return {
        "ok": len(covered) == len(must),
        "project": str(project.root),
        "rows": rows,
        "must": len(must),
        "covered": len(covered),
        "coverage": round(len(covered) / len(must) * 100, 1) if must else 100.0,
        "path": str(path) if write else "",
    }


def _manual_verify(row):
    verify = str(row.get("verify", "") or "").strip()
    if not verify:
        return "-"
    if verify.lower().startswith("manual"):
        return verify[:64]
    return "-"


def trace_markdown(project, rows=None, payload=None):
    rows = rows if rows is not None else _trace_rows(project)
    lines = [
        "# 需求追踪矩阵（生成文件，勿手改）",
        "",
        "> 由 forge.py trace --write 生成。证据等级：measured > manual > simulated > assumed。",
        "",
        "| 需求 | 优先级 | 内容 | 验证命令 | 证据数 | 等级 | 状态 |",
        "|---|---|---|---|---:|---|---|",
    ]
    for r in rows:
        mark = {"measured": "✅ 实测", "manual": "✅ 人工", "simulated": "🟡 仿真", "assumed": "⚪ 假设"}.get(r["level"], r["level"])
        lines.append(
            "| %s | %s | %s | %s | %d | %s | %s |" % (
                r["id"], r["priority"], str(r["text"]).replace("|", "\\|"),
                ", ".join(r["commands"]) or _manual_verify(r), r["evidence"], mark, "ok" if r["ok"] else "未闭环")
        )
    must = [r for r in rows if r["priority"] == "must"]
    covered = [r for r in must if r["ok"]]
    lines += ["", "**must 覆盖：%d/%d（%.1f%%）**" % (
        len(covered), len(must), len(covered) / len(must) * 100 if must else 100.0), ""]
    if len(covered) < len(must):
        lines += ["未闭环：", ""]
        lines += ["- %s %s（%s）" % (r["id"], r["text"], r["level"]) for r in must if not r["ok"]]
        lines.append("")
    return "\n".join(lines)


def _project_files(project):
    root = project.root
    files = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = _rel(project, path)
        # Only project-relative parts matter. The absolute host path may contain
        # directories such as build/ or dist/ outside the project.
        if any(part in EXCLUDE_DIRS for part in Path(rel).parts):
            continue
        if rel in EXCLUDE_FILES or path.suffix.lower() in EXCLUDE_SUFFIX:
            continue
        files.append(path)
    return files


REVIEW_VERDICTS = ("pass", "needs_revision", "reject")
MIN_REVIEW_SCORE = 70


def review_status(project):
    """Read the independent review result and check it still matches this build.

    A packet with no review.json means "reviewed by nobody"; a review.json whose
    fingerprint or packet hash no longer matches means the code changed after the
    review. Both are reported instead of being silently treated as a pass.
    """
    packet_path = project.root / "forge" / "review-packet.json"
    review_path = project.root / "forge" / "review.json"
    state = {
        "present": False,
        "valid": False,
        "verdict": "",
        "score": None,
        "findings": [],
        "blockers": [],
        "reviewer": "",
        "packet_sha256": "",
        "reason": "还没有盲审包；先运行 rf_review",
    }
    if not packet_path.is_file():
        return state
    try:
        packet = json.loads(read_text(packet_path))
    except (OSError, ValueError):
        state["reason"] = "review-packet.json 无法解析；重新运行 rf_review"
        return state
    packet_sha = str(packet.get("packet_sha256") or "")
    state["packet_sha256"] = packet_sha
    if not packet_sha:
        state["reason"] = "盲审包缺少 packet_sha256；重新运行 rf_review"
        return state
    if not review_path.is_file():
        state["reason"] = "盲审包已生成，但还没有独立评审结论（forge/review.json）"
        return state
    state["present"] = True
    try:
        review = json.loads(read_text(review_path))
    except (OSError, ValueError):
        state["reason"] = "forge/review.json 无法解析；请评审者重新记录"
        return state
    verdict = str(review.get("verdict") or "")
    score = review.get("score")
    findings = review.get("findings") or []
    if not isinstance(findings, list):
        findings = []
    state.update({
        "verdict": verdict,
        "score": score,
        "findings": findings,
        "reviewer": str(review.get("reviewer") or ""),
        "packet_sha256": str(review.get("packet_sha256") or ""),
    })
    state["blockers"] = [
        f for f in findings
        if isinstance(f, dict) and str(f.get("severity")) == "blocker" and not f.get("resolved")
    ]
    if verdict not in REVIEW_VERDICTS:
        state["reason"] = "review.json 的 verdict 必须是 pass/needs_revision/reject"
        return state
    if not isinstance(score, (int, float)) or not 0 <= float(score) <= 100:
        state["reason"] = "review.json 的 score 必须是 0–100"
        return state
    if not state["reviewer"]:
        state["reason"] = "review.json 缺少 reviewer：必须写明谁/哪个独立代理做的评审"
        return state
    if str(review.get("fingerprint") or "") != project.source_fingerprint():
        state["reason"] = "盲审结论针对旧版本：源码已变，必须重新评审"
        return state
    if state["packet_sha256"] != packet_sha:
        state["reason"] = "盲审结论与当前盲审包不一致；重新运行 rf_review 后再评审"
        return state
    if verdict == "pass" and state["blockers"]:
        state["reason"] = "verdict=pass 但仍有未解决的 blocker"
        return state
    state["valid"] = True
    state["reason"] = "独立盲审已记录：%s（%s 分）" % (verdict, score)
    return state


def _write_review_record(project, packet_sha, verdict, score, findings, reviewer, note):
    if verdict not in REVIEW_VERDICTS:
        raise ValueError("verdict 必须是 pass、needs_revision 或 reject")
    try:
        score = int(score)
    except (TypeError, ValueError):
        raise ValueError("score 必须是 0–100 的整数")
    if not 0 <= score <= 100:
        raise ValueError("score 必须是 0–100 的整数")
    if not str(reviewer or "").strip():
        raise ValueError("reviewer 不能为空：必须写明谁/哪个独立代理做的评审")
    if findings is None:
        findings = []
    if not isinstance(findings, list):
        raise ValueError("findings 必须是数组")
    blockers = [f for f in findings if isinstance(f, dict) and str(f.get("severity")) == "blocker" and not f.get("resolved")]
    if verdict == "pass" and blockers:
        raise ValueError("有未解决的 blocker 时不能给 pass")
    record = {
        "project": project.slug,
        "version": project.version,
        "verdict": verdict,
        "score": score,
        "findings": findings,
        "reviewer": str(reviewer).strip(),
        "note": str(note or ""),
        "reviewed_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "fingerprint": project.source_fingerprint(),
        "packet_sha256": packet_sha,
    }
    path = project.root / "forge" / "review.json"
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return path


def review_payload(project, write=True, verdict=None, score=None, findings=None, reviewer=None, note=""):
    if verdict is None and (score is not None or reviewer or findings or note):
        return {
            "ok": False,
            "project": str(project.root),
            "error": "要记录评审结论，必须同时给出 verdict（pass/needs_revision/reject）",
            "review": review_status(project),
        }
    from .api import audit_payload

    audit = audit_payload(project)
    trace = trace_payload(project)
    # A review must stay valid across reruns of the same build. Deriving the
    # timestamp from source mtimes (or SOURCE_DATE_EPOCH) keeps the packet hash
    # stable; a wall-clock stamp would invalidate a good review on every peek.
    # review.json is excluded: writing the verdict must not change the packet
    # that the verdict hashes.
    packet_files = [p for p in _project_files(project) if _rel(project, p) != "forge/review.json"]
    packet_time = _snapshot_time(packet_files)
    packet_audit = dict(audit)
    packet_audit.pop("review", None)
    issues = audit.get("issues", [])
    errors = [i for i in issues if i.get("level") == "error"]
    warnings = [i for i in issues if i.get("level") in ("warn", "warning")]
    coverage = packet_audit.get("requirements", {}).get("coverage", 0)
    machine_verdict = "机器门通过，待独立盲审" if not errors and coverage >= 100 else "机器门未通过"
    packet_audit["verdict"] = machine_verdict
    packet_audit.pop("release_level", None)
    evidence = project.evidence()
    body = [
        "# 盲审包（生成文件）",
        "",
        "- 项目：%s（%s）v%s" % (project.name, project.slug, project.version),
        "- 生成时间：%s" % packet_time,
        "- 源码指纹：%s" % project.source_fingerprint(),
        "- 机器结论：**%s** ｜ 分数 %d/100" % (machine_verdict, packet_audit.get("score", 0)),
        "- 错误/警告：%d / %d ｜ must 覆盖：%.1f%%" % (len(errors), len(warnings), coverage),
        "",
        "## 盲审规则（评审者必读）",
        "",
        "1. 先不看作者的辩解与结论，只读交付物、代码、测试、证据账本。",
        "2. 自己重跑下面“复现命令”，记录退出码；不要相信截图与口头声明。",
        "3. 用四副眼镜看：逻辑（需求→实现→测试是否闭环）、攻击面（电/热/运动/网络/隐私）、可维护性（后来者能否改）、可复现性（换一个人能否买齐做出来）。",
        "4. 只报可定位、可修复的问题；每条给文件/行号、证据、修复要求。禁止“感觉不好”。",
        "5. 不谈判、不看人情；blocker 一票否决。",
        "",
        "## 复现命令（在项目根目录）",
        "",
        "~~~bash",
        "python tools/forge.py check --deep",
        "python tools/forge.py trace",
        "python tools/forge.py verify --json",
        "python tools/forge.py audit",
        "~~~",
        "",
        "## 需求追踪",
        "",
        trace_markdown(project, trace["rows"]),
        "",
        "## 证据账本（最近 40 条，完整见 forge/evidence.jsonl）",
        "",
        "~~~json",
        json.dumps(evidence[-40:], ensure_ascii=False, indent=2),
        "~~~",
        "",
        "## 机器发现（%d 条）" % len(issues),
        "",
    ]
    for issue in issues:
        body.append("- [%s] %s %s (%s)" % (issue.get("level"), issue.get("rule"), issue.get("msg"), issue.get("file", "")))
    if not issues:
        body.append("- 无")
    body += [
        "",
        "## 评审输出格式（复制后填写）",
        "",
        "~~~json",
        json.dumps({
            "verdict": "pass|needs_revision|reject",
            "score": 0,
            "findings": [
                {"id": "QF-1-01", "severity": "blocker|high|medium|low", "file": "path:line",
                 "problem": "可复现的现象", "required_fix": "最小修复", "evidence": "命令/日志/照片"}
            ],
            "rerun": {"check_deep": "0 errors?", "verify": "all required pass?", "must_coverage": "100%?"},
        }, ensure_ascii=False, indent=2),
        "~~~",
        "",
        "## 安全与合规提示",
        "",
    ]
    safety_score = packet_audit.get("scorecard", {}).get("safety", 0)
    body.append("- 安全分：%s/10；按 references/quality.md 安全触发项逐条核对 docs/07，分数低说明有安全发现。" % safety_score)
    body.append("- 发布前必须由真实用户按 docs/06 操作；机器门不能替代实机。")
    text = "\n".join(body) + "\n"
    path = project.root / "forge" / "review-packet.md"
    json_path = project.root / "forge" / "review-packet.json"
    packet_sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
    if write:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
        json_path.write_text(
            json.dumps(
                {
                    "project": project.slug,
                    "version": project.version,
                    "generated_at": packet_time,
                    "fingerprint": project.source_fingerprint(),
                    "audit": packet_audit,
                    "trace": trace,
                    "packet_sha256": packet_sha,
                },
                ensure_ascii=False,
                indent=2,
            ) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    if verdict is not None:
        if not write:
            return {
                "ok": False,
                "project": str(project.root),
                "error": "要记录评审结论，必须先写入盲审包（不要用 --no-write）",
                "review": review_status(project),
            }
        try:
            _write_review_record(project, packet_sha, verdict, score, findings, reviewer, note)
        except ValueError as exc:
            return {
                "ok": False,
                "project": str(project.root),
                "error": str(exc),
                "review": review_status(project),
            }
    return {
        "ok": not errors and audit.get("requirements", {}).get("coverage", 0) >= 100,
        "project": str(project.root),
        "path": str(path) if write else "",
        "json_path": str(json_path) if write else "",
        "sha256": packet_sha,
        "review": review_status(project),
        "score": audit.get("score", 0),
        "verdict": audit.get("verdict", ""),
        "errors": len(errors),
        "warnings": len(warnings),
        "coverage": audit.get("requirements", {}).get("coverage", 0),
        "focus": [i.get("msg") for i in errors[:5]] or [i.get("msg") for i in warnings[:5]],
    }


def review_text(payload):
    lines = [
        "盲审包：%s" % ("✅ 可交给评审" if payload["ok"] else "⚠ 仍有阻断/未闭环"),
        "结论：%s（%d 分）｜ 错误 %d ｜ 警告 %d ｜ must 覆盖 %.1f%%" % (
            payload["verdict"], payload["score"], payload["errors"], payload["warnings"], payload["coverage"]),
        "文件：%s" % (payload["path"] or "（未写入）"),
    ]
    if payload["focus"]:
        lines.append("优先核对：" + "；".join(str(x) for x in payload["focus"][:3]))
    lines.append("下一步：把 packet 交给独立评审者，按四副眼镜出 findings；修复后重跑 trace/review。")
    return "\n".join(lines)


def _snapshot_time(files):
    """Stable timestamp: SOURCE_DATE_EPOCH if set, else newest source mtime."""
    epoch = os.environ.get("SOURCE_DATE_EPOCH")
    if epoch:
        try:
            return datetime.datetime.fromtimestamp(int(epoch), tz=datetime.timezone.utc).astimezone().isoformat(timespec="seconds")
        except (TypeError, ValueError, OverflowError):
            pass
    stamps = []
    for path in files:
        try:
            stamps.append(path.stat().st_mtime)
        except OSError:
            continue
    moment = datetime.datetime.fromtimestamp(max(stamps)) if stamps else datetime.datetime.now()
    return moment.astimezone().isoformat(timespec="seconds")


def _release_json(project, audit, files):
    manifest = {
        "name": project.name,
        "slug": project.slug,
        "version": project.version,
        "generated_at": _snapshot_time(files),
        "fingerprint": project.source_fingerprint(),
        "verdict": audit.get("verdict"),
        "release_level": "release" if audit.get("release_level") == "release" else "beta",
        "score": audit.get("score"),
        "requirements": audit.get("requirements"),
        "scorecard": audit.get("scorecard"),
        "files": {},
    }
    for path in files:
        manifest["files"][_rel(project, path)] = _sha256(path)
    return manifest


def package_payload(project, allow_beta=False, out_dir="dist"):
    from .api import audit_payload

    audit = audit_payload(project)
    errors = [i for i in audit.get("issues", []) if i.get("level") == "error"]
    level = audit.get("release_level", "blocked")
    if errors:
        return {
            "ok": False,
            "project": str(project.root),
            "error": "有 %d 个错误，不能打包发布；先跑 rf_check --deep" % len(errors),
            "blockers": [i.get("msg") for i in errors[:8]],
            "score": audit.get("score"),
            "verdict": audit.get("verdict"),
        }
    if level == "blocked":
        return {
            "ok": False,
            "project": str(project.root),
            "error": "审计结论为不可发布；Beta 也不是绕过通道。先修错误，或修完盲审 findings 后重新评审。",
            "blockers": [i.get("msg") for i in audit.get("issues", []) if i.get("level") == "error"][:8],
            "review": audit.get("review"),
            "score": audit.get("score"),
            "verdict": audit.get("verdict"),
        }
    if level != "release" and not allow_beta:
        return {
            "ok": False,
            "project": str(project.root),
            "error": "当前为 Beta（未完成独立盲审 pass，或 must 覆盖/警告未达标）。确要发布 Beta 时加 --beta，并在 README 标注未验证项。",
            "blockers": [i.get("msg") for i in audit.get("issues", []) if i.get("level") in ("warn", "warning")][:8],
            "review": audit.get("review"),
            "score": audit.get("score"),
            "verdict": audit.get("verdict"),
        }
    files = _project_files(project)
    manifest = _release_json(project, audit, files)
    manifest["release_level"] = "beta" if allow_beta and level != "release" else "release"
    digest_lines = ["%s  %s" % (sha, rel) for rel, sha in sorted(manifest["files"].items())]
    out = (project.root / out_dir).resolve()
    try:
        out.relative_to(project.root.resolve())
    except ValueError:
        raise ValueError("out_dir 必须位于项目内：%s" % out_dir)
    out.mkdir(parents=True, exist_ok=True)
    suffix = "-beta" if manifest["release_level"] == "beta" else ""
    zip_path = out / ("%s-%s%s.zip" % (project.slug, project.version, suffix))
    arc_root = "%s-%s" % (project.slug, project.version)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in files:
            _zip_add(zf, "%s/%s" % (arc_root, _rel(project, path)), path.read_bytes())
        _zip_add(zf, "%s/RELEASE.json" % arc_root, (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
        _zip_add(zf, "%s/SHA256SUMS" % arc_root, ("\n".join(digest_lines) + "\n").encode("utf-8"))
    sha = _sha256(zip_path)
    (out / (zip_path.name + ".sha256")).write_text("%s  %s\n" % (sha, zip_path.name), encoding="utf-8", newline="\n")
    return {
        "ok": True,
        "project": str(project.root),
        "path": str(zip_path),
        "sha256": sha,
        "bytes": zip_path.stat().st_size,
        "files": len(files) + 2,
        "release_level": manifest["release_level"],
        "score": audit.get("score"),
        "verdict": audit.get("verdict"),
        "warnings": len([i for i in audit.get("issues", []) if i.get("level") in ("warn", "warning")]),
    }


def package_text(payload):
    if not payload.get("ok"):
        lines = ["✗ 打包被拒绝：" + str(payload.get("error", ""))]
        lines += ["  - " + str(b) for b in payload.get("blockers", [])[:5]]
        return "\n".join(lines)
    return "\n".join(
        [
            "✓ 已打包（%s）：%s" % (payload["release_level"], payload["path"]),
            "SHA256：%s" % payload["sha256"],
            "大小：%.1f KB ｜ 文件：%d ｜ 分数：%s ｜ 警告：%d" % (
                payload["bytes"] / 1024.0, payload["files"], payload["score"], payload["warnings"]),
            "发布时把 .zip 与 .sha256 一起上传，并在 release notes 引用 RELEASE.json。",
        ]
    )
