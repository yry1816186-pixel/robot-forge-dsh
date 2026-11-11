"""Machine-readable payloads shared by the CLI and the DeepSeek Harness tools.

The human CLI keeps its prose output. Everything that a tool or an automated
caller needs to decide the next action lives here so there is one source of
truth for "what is actually true about this project".
"""

from __future__ import annotations

import datetime
import json
from pathlib import Path

from .check import run_checks
from .model import LEVELS, LEVELS_OK, load_project
from .render import render
from .report import MIN_REVIEW_SCORE, review_status
from .util import read_text


def _issues(issues):
    return [i.as_dict() for i in issues]


def _stats(stats):
    errors = int(stats.get("errors", 0))
    warnings = int(stats.get("warnings", 0))
    infos = int(stats.get("infos", 0))
    return {
        "errors": errors,
        "warnings": warnings,
        "infos": infos,
        "total": errors + warnings + infos,
    }


def check_payload(project, deep=False):
    issues, stats = run_checks(project, deep=deep)
    return {
        "project": str(project.root),
        "name": project.name,
        "deep": bool(deep),
        "stats": _stats(stats),
        "issues": _issues(issues),
    }


def render_state(project):
    results = render(project, write=False)
    stale = [str(path) for path, status in results if status in ("stale", "created", "problem")]
    return {
        "stale": stale,
        "problems": [str(path) for path, status in results if status == "problem"],
    }


def _requirement_levels(project):
    rows = []
    for req in project.requirements:
        if str(req.get("priority", "must")) != "must":
            continue
        level, ev = project.requirement_status(req)
        rows.append(
            {
                "id": str(req.get("id", "")),
                "text": str(req.get("text", "")),
                "level": level,
                "evidence": len(ev),
            }
        )
    return rows


def next_payload(project, check=None):
    """Return the single most useful next action, with tool and CLI spellings."""
    if project.load_error:
        return {
            "action": "choose-blueprint",
            "reason": "%s；先选最近蓝本，再创建或修复项目" % project.load_error,
            "tool": "rf_blueprints",
            "arguments": {},
            "commands": [
                "python <插件目录>/skills/robot-forge/scripts/forge.py blueprints",
                "python <插件目录>/skills/robot-forge/scripts/forge.py new 我的机器人 --blueprint <最近蓝本>",
            ],
        }

    state = render_state(project)
    if state["problems"]:
        return {
            "action": "render",
            "reason": "生成块标记被改坏：%s" % ", ".join(state["problems"][:3]),
            "tool": "rf_check",
            "arguments": {},
            "commands": ["python tools/forge.py render"],
        }
    if state["stale"]:
        return {
            "action": "render",
            "reason": "robot.yaml 已改，但生成内容过期：%s" % ", ".join(state["stale"][:3]),
            "tool": "rf_check",
            "arguments": {},
            "commands": ["python tools/forge.py render"],
        }

    if check is None:
        check = check_payload(project)
    # Design review is the first gate that can invalidate the whole build
    # (a servo that cannot lift the arm is not a documentation problem), so it
    # runs before evidence collection rather than after it.
    design_doc = project.root / "forge" / "design.md"
    if not design_doc.exists() and ("hardware" in project.domains or "cad" in project.domains):
        return {
            "action": "design",
            "reason": "还没有设计核算：先算扭矩/功耗/续航/成本，再写证据，避免做完才发现选型不够",
            "tool": "rf_design",
            "arguments": {"write": True},
            "commands": ["python tools/forge.py design --write"],
        }

    if check["stats"]["errors"] > 0:
        first = check["issues"][0] if check["issues"] else {}
        return {
            "action": "fix",
            "reason": "有 %d 个结构/一致性错误，先修 $%s %s" % (
                check["stats"]["errors"],
                first.get("rule", "?"),
                first.get("msg", first.get("message", "")),
            ),
            "tool": "rf_check",
            "arguments": {},
            "commands": ["python tools/forge.py check"],
        }

    must = _requirement_levels(project)
    missing = [r for r in must if r["level"] not in LEVELS_OK]
    if missing:
        covered = set()
        for cmd in project.verify_command_rows():
            reqs = cmd.get("req") or []
            if isinstance(reqs, str):
                reqs = [reqs]
            for req in reqs:
                covered.add(str(req))
        # A requirement whose verify command is the command's run string is
        # covered even when the command omits the req list; validate() accepts
        # that shape, so next-step must not suggest hand-written evidence.
        for cmd in project.verify_command_rows():
            run = " ".join(str(cmd.get("run", "")).split())
            for req in project.requirements:
                if run and " ".join(str(req.get("verify", "")).split()) == run:
                    covered.add(str(req.get("id", "")))
        covered_missing = [r["id"] for r in missing if r["id"] in covered]
        if covered_missing:
            return {
                "action": "verify",
                "reason": (
                    "还有 %d 条 must 需求没有实测/人工证据；%s 由可执行验证覆盖。"
                    "若命令因缺工具被跳过，安装工具后重跑 rf_verify；不要手写实测。"
                    % (len(missing), "、".join(covered_missing[:4]))
                ),
                "tool": "rf_verify",
                "arguments": {},
                "commands": ["python tools/forge.py verify"],
            }
        return {
            "action": "evidence",
            "reason": "还有 %d 条 must 需求只能人工确认，需要真实试用后记录" % len(missing),
            "tool": "rf_evidence",
            "arguments": {},
            "commands": ["python tools/forge.py evidence --req %s --claim '...'" % missing[0]["id"]],
        }

    trace_doc = project.root / "forge" / "trace.md"
    review_doc = project.root / "forge" / "review-packet.md"
    if not trace_doc.exists():
        return {
            "action": "trace",
            "reason": "需求都有证据了；生成需求→验证→证据追踪矩阵，确认没有漏项",
            "tool": "rf_trace",
            "arguments": {"write": True},
            "commands": ["python tools/forge.py trace --write"],
        }
    review = review_status(project)
    if review["valid"] and review["verdict"] in ("needs_revision", "reject"):
        return {
            "action": "fix",
            "reason": "独立盲审结论是 %s：先按 findings 修复，再重跑 trace/review（%s）" % (
                review["verdict"], review["reason"]),
            "tool": "rf_check",
            "arguments": {},
            "commands": ["python tools/forge.py check --deep"],
        }
    if not review_doc.exists() or not review["present"]:
        return {
            "action": "review",
            "reason": "追踪矩阵已生成；生成盲审包并交给独立评审者，记录结论后再发布",
            "tool": "rf_review",
            "arguments": {"write": True},
            "commands": ["python tools/forge.py review --write"],
        }
    if not review["valid"] or review["verdict"] != "pass" or (review["score"] or 0) < MIN_REVIEW_SCORE:
        return {
            "action": "review",
            "reason": "盲审还没有形成有效的 pass 结论：%s；当前结论 %s（%s 分），要求 pass 且 >= %d 分" % (
                review["reason"], review["verdict"] or "无", review["score"], MIN_REVIEW_SCORE),
            "tool": "rf_review",
            "arguments": {"write": True},
            "commands": ["python tools/forge.py review --write"],
        }

    return {
        "action": "deliver",
        "reason": "机器可判定的门都过了，追踪矩阵与盲审包已就绪；跑一次发布审计，然后按 docs/09 写交付说明",
        "tool": "rf_audit",
        "arguments": {},
        "commands": ["python tools/forge.py audit", "python tools/forge.py package"],
    }


def status_payload(project):
    if project.load_error:
        return {
            "ok": False,
            "project": str(project.root),
            "error": project.load_error,
            "next": next_payload(project),
        }
    check = check_payload(project)
    levels = {}
    for row in _requirement_levels(project):
        levels[row["level"]] = levels.get(row["level"], 0) + 1
    return {
        "ok": True,
        "project": str(project.root),
        "name": project.name,
        "slug": project.slug,
        "version": project.version,
        "gear": project.gear,
        "domains": list(project.domains),
        "budget_cny": project.budget,
        "total_cost_cny": project.total_cost(),
        "components": len(project.components),
        "requirements": len(project.requirements),
        "evidence": len(project.evidence()),
        "must_levels": levels,
        "check": check["stats"],
        "top_errors": [i for i in check["issues"] if i.get("level") == "error"][:5],
        "recent_evidence": project.evidence()[-3:],
        "next": next_payload(project, check),
    }


SOURCING_RULES = {"S2", "S3", "S7", "S14", "D9", "CST-09", "CST-13"}
SAFETY_RULES = {"S11", "CST-07", "CST-10", "CST-11"}
DOC_RULES = {"D7", "D8"}


def _scorecard(project, issues, coverage):
    """100-point scorecard mirroring references/quality.md, derived from findings.

    The four evidence-independent dimensions are docked from their weights;
    evidence is the only dimension that scales with measured coverage. This
    keeps the number explainable: a reader can add up the six rows.
    """
    buckets = {"buyable": [0, 0], "buildable": [0, 0], "runnable": [0, 0], "explainable": [0, 0], "safety": [0, 0]}

    def bucket(issue):
        rule = str(issue.rule)
        file = str(issue.file or "").replace("\\", "/")
        if rule in SAFETY_RULES:
            return "safety"
        if rule in SOURCING_RULES:
            return "buyable"
        if rule in DOC_RULES or file.startswith(("docs/", "README", "CHANGELOG", "LICENSE")):
            return "explainable"
        if file.startswith(("firmware/", "software/", "sim/")) or rule in {"CST-08"}:
            return "runnable"
        return "buildable"

    for issue in issues:
        level = str(issue.level)
        if level not in ("error", "warn"):
            continue
        # Evidence misses are already priced by the evidenced dimension; do not
        # dock the buildable score for the same missing evidence twice.
        if str(issue.rule) == "D4":
            continue
        row = buckets[bucket(issue)]
        row[0 if level == "error" else 1] += 1

    weights = {"buyable": 15, "buildable": 20, "runnable": 25, "explainable": 15, "safety": 10}
    scorecard = {}
    for key, weight in weights.items():
        errors, warnings = buckets[key]
        scorecard[key] = max(0, weight - errors * 6 - warnings * 1)
    scorecard["evidenced"] = round(15 * coverage / 100.0, 1)
    total = int(round(sum(scorecard.values())))
    return total, scorecard


def audit_payload(project):
    issues, stats = run_checks(project, deep=True)
    must = [r for r in project.requirements if str(r.get("priority", "must")) == "must"]
    covered = 0
    levels = {}
    for req in must:
        level, _ev = project.requirement_status(req)
        levels[level] = levels.get(level, 0) + 1
        if level in LEVELS_OK:
            covered += 1
    coverage = (covered / len(must) * 100) if must else 100
    score, scorecard = _scorecard(project, issues, coverage)
    review = review_status(project)
    review_ok = bool(review["valid"] and review["verdict"] == "pass" and not review["blockers"] and (review["score"] or 0) >= MIN_REVIEW_SCORE)
    review_failed = bool(review["valid"] and review["verdict"] in ("needs_revision", "reject"))
    if review_failed:
        verdict = "不可发布：独立盲审未通过（%s）" % review["verdict"]
        release_level = "blocked"
    elif stats["errors"] == 0 and coverage >= 100 and score >= 85 and review_ok:
        verdict = "可以发布"
        release_level = "release"
    elif stats["errors"] == 0:
        if not review["present"]:
            verdict = "可发布 Beta：机器门通过，但还没有独立盲审结论"
        elif not review["valid"]:
            verdict = "可发布 Beta：盲审结论已过期或与当前构建不一致，需重新评审"
        elif review["verdict"] == "pass" and (review["score"] or 0) < MIN_REVIEW_SCORE:
            verdict = "可发布 Beta：盲审分数 %s 低于 %d" % (review["score"], MIN_REVIEW_SCORE)
        else:
            verdict = "可发布 Beta，但必须标注未验证项"
        release_level = "beta"
    else:
        verdict = "不可发布"
        release_level = "blocked"
    from .design import design_payload

    return {
        "project": str(project.root),
        "name": project.name,
        "version": project.version,
        "score": score,
        "scorecard": scorecard,
        "verdict": verdict,
        "release_level": release_level,
        "trace": (project.root / "forge" / "trace.md").exists(),
        "review_packet": (project.root / "forge" / "review-packet.md").exists(),
        "review": review,
        "design": design_payload(project),
        "stats": _stats(stats),
        "requirements": {
            "must": len(must),
            "covered": covered,
            "coverage": round(coverage, 1),
            "levels": levels,
        },
        "evidence": len(project.evidence()),
        "issues": _issues(issues),
        "next": next_payload(project),
    }


def blueprints_payload(templates_dir):
    rows = []
    for path in sorted(Path(templates_dir).glob("*/blueprint.json")):
        try:
            meta = json.loads(read_text(path))
        except Exception:
            meta = {"name": path.parent.name}
        rows.append(
            {
                "id": path.parent.name,
                "name": meta.get("name", path.parent.name),
                "one_liner": meta.get("one_liner", ""),
                "cost_cny": meta.get("cost_cny"),
                "time": meta.get("time", ""),
                "difficulty": meta.get("difficulty", ""),
                "domains": meta.get("domains", []),
                "needs": meta.get("needs", []),
                "tags": meta.get("tags", []),
            }
        )
    return rows


def evidence_payload(project, req, claim, level="manual", note="", artifact=""):
    claim = str(claim or "").strip()
    note = str(note or "").strip()
    artifact = str(artifact or "").strip()
    level = str(level or "manual").lower()
    if not claim:
        raise ValueError("claim 不能为空：写清谁在什么条件下确认了什么")
    if level not in LEVELS or level == "measured":
        raise ValueError("evidence 只能记 manual/simulated/assumed；measured 必须由 rf_verify 跑命令产生")
    req = str(req or "").strip()
    if req and req not in {str(r.get("id", "")) for r in project.requirements}:
        raise ValueError("需求不存在：%s" % req)
    if level == "manual" and not note:
        raise ValueError("manual 证据必须写 note：谁、在哪台实物上、按什么步骤确认")
    if artifact:
        root = project.root.resolve()
        candidate = Path(artifact)
        if candidate.is_absolute():
            raise ValueError("artifact 必须是项目内相对路径")
        candidate = (root / candidate).resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            raise ValueError("artifact 越出项目根目录：%s" % artifact)
        if not candidate.exists():
            raise ValueError("artifact 不存在：%s" % artifact)
    existing = {str(i.get("id")) for i in project.evidence()}
    row = {
        "id": _new_evidence_id(existing),
        "at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "req": req or "",
        "claim": claim,
        "kind": "manual",
        "command": "",
        "exit": 0,
        "level": level,
        "artifact": artifact or "",
        "note": note or "",
        "fingerprint": project.source_fingerprint(),
    }
    _append_evidence(project, [row])
    render(project, write=True)
    return row


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
    existing.add(candidate)
    return candidate


def verify_payload(project, only=None, record=True):
    commands_all = list(project.verify.get("commands") or [])
    if not commands_all:
        return {
            "ok": False,
            "project": str(project.root),
            "error": "forge/verify.yaml 没有可跑的命令",
            "results": [],
            "failures": 0,
            "skipped": 0,
            "partial": False,
            "omitted_required": [],
            "evidence_ids": [],
            "next": next_payload(project),
        }
    if only:
        wanted = {x.strip() for x in str(only).split(",") if x.strip()}
        commands = [c for c in commands_all if str(c.get("id")) in wanted]
        if not commands:
            return {
                "ok": False,
                "project": str(project.root),
                "error": "--only 没有匹配到任何命令：%s" % ", ".join(sorted(wanted)),
                "results": [],
                "failures": 0,
                "skipped": 0,
                "partial": True,
                "omitted_required": [
                    str(c.get("id", "?")) for c in commands_all if c.get("required", True) is not False
                ],
                "evidence_ids": [],
                "next": next_payload(project),
            }
    else:
        commands = list(commands_all)

    selected_ids = {str(c.get("id", "?")) for c in commands}
    omitted_required = [
        str(c.get("id", "?"))
        for c in commands_all
        if c.get("required", True) is not False and str(c.get("id", "?")) not in selected_ids
    ]
    partial = bool(omitted_required)

    from .cli import _need_ok, _new_evidence_id  # local import avoids a cycle at module load

    existing = {str(i.get("id")) for i in project.evidence()}
    fingerprint = project.source_fingerprint() if record else ""
    rows = []
    results = []
    failures = 0
    skipped = 0
    for cmd in commands:
        cid = str(cmd.get("id", "?"))
        name = str(cmd.get("name", cid))
        required = cmd.get("required", True) is not False
        needs = [str(n) for n in (cmd.get("needs") or [])]
        missing = [n for n in needs if not _need_ok(n)]
        if missing:
            if required:
                failures += 1
                results.append(
                    {
                        "id": cid,
                        "name": name,
                        "run": str(cmd.get("run", "")),
                        "required": True,
                        "status": "fail",
                        "exit": 127,
                        "missing": missing,
                        "tail": "缺工具：%s" % ", ".join(missing),
                    }
                )
                if record:
                    rows.append(
                        {
                            "id": _new_evidence_id(existing),
                            "at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
                            "req": cmd.get("req", ""),
                            "claim": name + "（缺工具，未执行）",
                            "kind": "command",
                            "command": str(cmd.get("run", "")),
                            "exit": 127,
                            "level": "assumed",
                            "artifact": "",
                            "note": "缺工具：%s" % ", ".join(missing),
                            "fingerprint": fingerprint,
                        }
                    )
            else:
                skipped += 1
                results.append(
                    {
                        "id": cid,
                        "name": name,
                        "run": str(cmd.get("run", "")),
                        "required": False,
                        "status": "skip",
                        "exit": None,
                        "missing": missing,
                        "tail": "缺工具，已跳过（非必需）",
                    }
                )
            continue

        timeout = int(cmd.get("timeout", cmd.get("timeout_s", 600)) or 600)
        from .util import run, truncate

        cwd_value = str(cmd.get("cwd", "") or "").strip()
        run_cwd = project.root
        cwd_error = ""
        if cwd_value:
            try:
                candidate = (project.root / cwd_value).resolve()
                candidate.relative_to(project.root.resolve())
            except (OSError, ValueError):
                candidate = None
            if candidate is None or not candidate.is_dir():
                cwd_error = "verify cwd 无效、越界或不存在：%s" % cwd_value
            else:
                run_cwd = candidate
        if cwd_error:
            code, out = 127, cwd_error
        else:
            code, out = run(str(cmd.get("run", "")), run_cwd, timeout=timeout)
        tail = truncate(out.strip(), 1800)
        status = "pass" if code == 0 else "fail"
        # required=false only makes a MISSING tool non-fatal. Once the tool is
        # present and the command runs, a failure is a real failure; otherwise
        # an optional firmware/CAD test could fail while verify still says OK.
        if code != 0:
            failures += 1
        results.append(
            {
                "id": cid,
                "name": name,
                "run": str(cmd.get("run", "")),
                "required": required,
                "status": status,
                "exit": code,
                "missing": [],
                "tail": tail[-1200:],
            }
        )
        if record:
            reqs = cmd.get("req") or []
            if isinstance(reqs, str):
                reqs = [reqs]
            if not reqs:
                reqs = [""]
            for req in reqs:
                rows.append(
                    {
                        "id": _new_evidence_id(existing),
                        "at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
                        "req": str(req),
                        "claim": name,
                        "kind": "command",
                        "command": str(cmd.get("run", "")),
                        "exit": code,
                        "level": "measured" if code == 0 else "assumed",
                        "artifact": str(cmd.get("artifact", "")),
                        "note": "" if code == 0 else tail[-500:],
                        "fingerprint": fingerprint,
                    }
                )
    if rows and record:
        _append_evidence(project, rows)
        render(project, write=True)
    return {
        "ok": failures == 0 and not partial,
        "project": str(project.root),
        "results": results,
        "failures": failures,
        "skipped": skipped,
        "partial": partial,
        "omitted_required": omitted_required,
        "evidence_ids": [r["id"] for r in rows],
        "next": next_payload(project),
    }