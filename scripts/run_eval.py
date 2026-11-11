#!/usr/bin/env python3
"""Deterministic post-checks for one robot-forge eval case.

Run an agent on evals/cases/<case>.md in a fresh directory, then:

    python scripts/run_eval.py <project-dir> <case-id> [--no-verify] [--json]

Exit codes: 0 pass, 1 fail, 2 cannot evaluate (missing project for a mandatory case).
Manual rubric items still need a human/LLM reviewer; this script only checks what a
machine can check, which is the point: no self-reported claims.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
EVALS = PLUGIN_ROOT / "evals" / "evals.json"
FORGE = PLUGIN_ROOT / "skills" / "robot-forge" / "scripts" / "forge.py"
TEXT_SUFFIXES = {".md", ".py", ".yaml", ".yml", ".json", ".csv", ".ini", ".cpp", ".h", ".txt", ".toml"}


def load_evals():
    return json.loads(EVALS.read_text(encoding="utf-8"))


def expand(project: Path, pattern: str):
    if any(ch in pattern for ch in "*?["):
        return [p for p in project.glob(pattern) if p.is_file()]
    return [project / pattern] if (project / pattern).exists() else []


def text_files(project: Path, scopes):
    seen = set()
    for scope in scopes:
        if any(ch in scope for ch in "*?["):
            hits = [p for p in project.glob(scope) if p.is_file()]
        else:
            hits = [p for p in project.rglob(scope) if p.is_file()] if (project / scope).is_dir() else [project / scope]
        for path in hits:
            relative = path.resolve().relative_to(project.resolve())
            # tools/forgekit is the vendored engine copied from the plugin; its
            # own source necessarily contains template placeholders and rule
            # strings, so it is not user content and must not be graded.
            if relative.parts[:2] == ("tools", "forgekit"):
                continue
            if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES and path.stat().st_size < 2_000_000:
                seen.add(path.resolve())
    return sorted(seen)


def run(cmd, cwd):
    proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, timeout=1800)
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def parse_json(text):
    start = text.find("{")
    if start < 0:
        return {}
    try:
        return json.loads(text[start:])
    except json.JSONDecodeError:
        return {}


def run_json(cmd, cwd):
    code, out = run(cmd, cwd)
    return code, out, parse_json(out)


def prompt_text(case):
    rel = str(case.get("prompt", ""))
    path = EVALS.parent / rel
    return path.read_text(encoding="utf-8").strip() if path.is_file() else ""


def intake_check(case, expect):
    """Run the classifier on the case prompt itself; no project needed."""
    text = prompt_text(case)
    code, out, data = run_json([sys.executable, str(FORGE), "intake", text, "--json"], PLUGIN_ROOT)
    checks = []
    expected_allowed = bool(expect.get("allowed", True))
    checks.append({"check": "intake:allowed=%s" % expected_allowed, "ok": bool(data.get("allowed", True)) == expected_allowed, "detail": "exit %s" % code})
    want = expect.get("archetype")
    if want:
        checks.append({"check": "intake:archetype=%s" % want, "ok": data.get("archetype") == want, "detail": str(data.get("archetype"))})
    need_flags = expect.get("safety_contains") or []
    if need_flags:
        got = {f.get("id", f.get("key", "")) for f in data.get("safety", []) if isinstance(f, dict)}
        checks.append({"check": "intake:safety" + ",".join(need_flags), "ok": set(need_flags).issubset(got), "detail": ",".join(sorted(got))})
    max_q = expect.get("max_questions")
    if max_q is not None:
        questions = data.get("questions", [])
        checks.append({"check": "intake:questions<=%s" % max_q, "ok": len(questions) <= int(max_q), "detail": "%d 个" % len(questions)})
    return checks


def check_project(project: Path, case: dict, run_verify: bool):
    expect = case["expect"]
    results = []

    def add(name, ok, detail=""):
        results.append({"check": name, "ok": bool(ok), "detail": detail})

    if expect.get("intake"):
        results.extend(intake_check(case, expect["intake"]))

    if not (project / "forge" / "robot.yaml").is_file():
        add("project-exists", False, "没有 forge/robot.yaml")
        return results

    for rel in expect.get("required_files", []):
        add("file:" + rel, (project / rel).is_file())

    for pattern in expect.get("require_glob", []):
        add("glob:" + pattern, bool(expand(project, pattern)))

    for rel in expect.get("forbidden_paths", []):
        add("forbidden:" + rel, not (project / rel).exists())

    for rule in expect.get("forbid_regex", []):
        pattern = re.compile(rule["pattern"])
        hits = []
        for path in text_files(project, rule.get("scope", ["**/*"])):
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except Exception:  # noqa: BLE001
                continue
            if pattern.search(text):
                hits.append(str(path.relative_to(project)))
        add("regex-absent:" + rule["pattern"], not hits, ", ".join(hits[:5]))

    if "check_exit" in expect:
        code, out = run([sys.executable, "tools/forge.py", "check", "--json"], project)
        ok = code == 0
        data = parse_json(out)
        stats = data.get("stats", {})
        detail = "errors=%s warnings=%s" % (stats.get("errors"), stats.get("warnings")) if stats else (out.strip().splitlines()[-1] if out.strip() else "no output")
        add("check-exit", ok, detail)
        max_warnings = expect.get("max_warnings")
        if max_warnings is not None:
            warnings = stats.get("warnings", 10**9)
            add("check:warnings<=%s" % max_warnings, warnings <= int(max_warnings), "%s 条" % warnings)
        rules = expect.get("check_no_error_rules") or []
        if rules:
            bad = [i for i in data.get("issues", []) if i.get("level") == "error" and i.get("rule") in rules]
            add("check:no-error-rules" + ",".join(rules), not bad, "; ".join(i.get("rule", "") + " " + i.get("msg", "") for i in bad[:3]))

    if "design_exit" in expect:
        code, out, data = run_json([sys.executable, "tools/forge.py", "design", "--json"], project)
        add("design-exit", code == 0, "exit %s; findings=%s" % (code, len(data.get("findings", []))))
        min_margin = expect.get("design_min_margin")
        if min_margin is not None:
            margin = (data.get("torque") or {}).get("margin")
            add("design:torque-margin>=%s" % min_margin, margin is not None and margin >= float(min_margin), "margin=%s" % margin)
        min_runtime = expect.get("design_min_runtime_h")
        if min_runtime is not None:
            runtime = (data.get("power") or {}).get("runtime_h")
            add("design:runtime>=%sh" % min_runtime, runtime is not None and runtime >= float(min_runtime), "runtime=%s" % runtime)

    if run_verify and "verify_exit" in expect:
        code, out = run([sys.executable, "tools/forge.py", "verify", "--no-record"], project)
        add("verify-exit", code == 0, "exit %s" % code)

    if "max_budget_cny" in expect:
        try:
            sys.path.insert(0, str(PLUGIN_ROOT / "skills" / "robot-forge" / "scripts"))
            from forgekit.model import load_project  # noqa: PLC0415

            proj = load_project(project)
            budget = proj.budget
            add("budget<=%s" % expect["max_budget_cny"], budget <= expect["max_budget_cny"], "预算 %s" % budget)
        except Exception as exc:  # noqa: BLE001
            add("budget<=%s" % expect["max_budget_cny"], False, str(exc))

    if "trace_min_coverage" in expect:
        code, out, data = run_json([sys.executable, "tools/forge.py", "trace", "--json"], project)
        coverage = data.get("coverage")
        add("trace:coverage>=%s" % expect["trace_min_coverage"], coverage is not None and coverage >= float(expect["trace_min_coverage"]), "coverage=%s" % coverage)
        if expect.get("trace_file"):
            add("trace:file", (project / "forge" / "trace.md").is_file(), "forge/trace.md")

    if expect.get("review_packet"):
        packet = project / "forge" / "review-packet.json"
        ok = False
        detail = "missing forge/review-packet.json"
        if packet.is_file():
            try:
                payload = json.loads(packet.read_text(encoding="utf-8"))
                ok = bool(payload.get("packet_sha256")) and bool(payload.get("trace"))
                detail = "sha=%s coverage=%s" % (str(payload.get("packet_sha256"))[:12], (payload.get("trace") or {}).get("coverage"))
            except Exception as exc:  # noqa: BLE001
                detail = str(exc)
        add("review:packet", ok, detail)

    if expect.get("package_artifact"):
        zips = sorted((project / "dist").glob("*.zip"))
        ok = bool(zips)
        detail = zips[0].name if zips else "missing dist/*.zip"
        manifest_ok = False
        if zips:
            try:
                with zipfile.ZipFile(zips[0]) as zf:
                    names = zf.namelist()
                    manifest_ok = any(n.endswith("/RELEASE.json") for n in names) and any(n.endswith("/SHA256SUMS") for n in names)
            except Exception as exc:  # noqa: BLE001
                detail += " / " + str(exc)
        add("package:artifact", ok, detail)
        add("package:manifest", manifest_ok, "RELEASE.json + SHA256SUMS")

    if "min_evidence" in expect:
        try:
            ev = project / "forge" / "evidence.jsonl"
            rows = [line for line in ev.read_text(encoding="utf-8").splitlines() if line.strip()] if ev.is_file() else []
            add("min-evidence", len(rows) >= int(expect["min_evidence"]), "%d 条" % len(rows))
        except Exception as exc:  # noqa: BLE001
            add("min-evidence", False, str(exc))

    if expect.get("forbid_caches"):
        bad = [str(p.relative_to(project)) for p in project.rglob("*") if p.name in ("__pycache__", ".pytest_cache", ".ruff_cache") or p.suffix == ".pyc"]
        add("no-caches", not bad, ", ".join(bad[:5]))

    return results


def main(argv=None):
    parser = argparse.ArgumentParser(prog="run_eval.py", description="robot-forge eval 判定（只信文件与命令输出）")
    parser.add_argument("project", help="被测项目目录")
    parser.add_argument("case", help="evals.json 里的用例 id")
    parser.add_argument("--no-verify", action="store_true", help="跳过 verify（较慢）")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    project = Path(args.project).resolve()
    data = load_evals()
    case = next((c for c in data["cases"] if c["id"] == args.case), None)
    if not case:
        print("没有这个用例：%s" % args.case, file=sys.stderr)
        return 2

    has_project = (project / "forge" / "robot.yaml").is_file()
    if not has_project and not case["expect"].get("project_optional"):
        print("用例 %s 需要项目，但 %s 里没有 forge/robot.yaml" % (args.case, project), file=sys.stderr)
        return 2

    results = check_project(project, case, run_verify=not args.no_verify) if has_project else []
    failed = [r for r in results if not r["ok"]]
    payload = {
        "case": args.case,
        "project": str(project),
        "has_project": has_project,
        "passed": not failed,
        "failed": failed,
        "checks": results,
        "manual_rubric": case["expect"].get("manual_rubric", ""),
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print("用例 %s · %s" % (args.case, case["title"]))
        for row in results:
            print("  %s %s%s" % ("PASS" if row["ok"] else "FAIL", row["check"], (" — " + row["detail"]) if row["detail"] else ""))
        if not has_project:
            print("  （无项目：本题只看对话行为，按 manual_rubric 人工/LLM 复核）")
        print("")
        print("机器判定：%s" % ("通过" if not failed else "%d 项失败" % len(failed)))
        if payload["manual_rubric"]:
            print("还需人工复核：" + payload["manual_rubric"])
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
