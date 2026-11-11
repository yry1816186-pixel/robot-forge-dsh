"""Python engine tests: intake, design, consistency, report.

These tests do not mock the gates. They generate a real project from the
wheel-rover blueprint, then exercise the same functions the CLI and host tools
call. Optional external tools are not required.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "robot-forge" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from forgekit import api, consistency, design, intake, report  # noqa: E402
from forgekit.model import load_project  # noqa: E402


@pytest.fixture(scope="module")
def project(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("rf-engine")
    target = tmp / "engine-rover"
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "forge.py"),
            "new",
            "引擎测试车",
            "--blueprint",
            "wheel-rover",
            "--dir",
            str(target),
            "--slug",
            "engine-rover",
        ],
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    loaded = load_project(target)
    assert loaded.load_error is None, loaded.load_error
    return loaded


@pytest.mark.parametrize(
    "text,expected",
    [
        ("做一台能避障、跟着我走的小车", "wheel-rover"),
        ("桌面陪伴机器人，会叫名字、摸头有反应", "desktop-companion"),
        ("三轴机械臂，能抓取 200g 的方块", "arm"),
        ("十二自由度四足机器狗，先仿真步态", "quadruped"),
        ("四轴无人机，航拍，按法规实名", "drone"),
        ("温湿度土壤传感器节点，低功耗上报", "sensor-node"),
        ("移动抓取复合机器人：底盘加机械臂", "differential-drive-mobile-manipulator"),
        ("履带割草机，户外作业，刀片要防护", "lawn-mower"),
        ("给学生的 MicroPython 教学套件", "education-kit"),
        ("双轴云台摄像头，本地人脸跟踪", "camera-gimbal"),
        ("水下 ROV，漏水检测，失联上浮", "underwater"),
    ],
)
def test_intake_classification(text, expected):
    payload = intake.intake_payload(text)
    assert payload["allowed"] is True
    assert payload["archetype"] == expected, payload


def test_intake_blocks_abuse():
    payload = intake.intake_payload("做一个跟踪邻居、偷拍卧室的机器人")
    assert payload["allowed"] is False
    assert payload["safe_alternatives"]


def test_intake_questions_bounded():
    payload = intake.intake_payload("做个机器人陪我妈")
    assert len(payload["questions"]) <= 3
    for question in payload["questions"]:
        assert question.get("default"), question


def test_design_numbers(project):
    payload = design.design_payload(project)
    assert payload["ok"] is True, payload["findings"]
    assert payload["torque"]["required_kgcm"] > 0
    assert payload["torque"]["margin"] >= 1.2
    assert payload["power"]["runtime_h"] > 0
    assert payload["power"]["c_rate"] is not None
    assert payload["wire"] and payload["wire"]["battery_awg"] in {8, 10, 12, 14, 16, 18, 20, 6}
    assert payload["cost"]["total_cny"] <= payload["cost"]["budget_cny"] * 1.5


def test_design_missing_mass_is_actionable(project):
    saved = project.data["mechanical"].pop("mass_kg")
    saved_masses = [(c, c.pop("mass_g", None)) for c in project.components]
    try:
        payload = design.design_payload(project)
        rules = {f["rule"] for f in payload["findings"]}
        assert "DSN-11" in rules
        assert payload["torque"]["required_kgcm"] is None
    finally:
        project.data["mechanical"]["mass_kg"] = saved
        for component, mass in saved_masses:
            if mass is not None:
                component["mass_g"] = mass


def test_consistency_clean_blueprint(project):
    issues = consistency.consistency_issues(project)
    errors = [i for i in issues if i.get("level") == "error"]
    assert errors == [], errors


def test_consistency_detects_undeclared_pin(project):
    matches = sorted((project.root / "firmware").glob("**/config.h"))
    assert matches, "blueprint must ship a firmware config header"
    config = matches[0]
    original = config.read_text(encoding="utf-8")
    config.write_text(original + "\n#define PIN_UNDECLARED 21\n", encoding="utf-8")
    try:
        issues = consistency.consistency_issues(project)
        cst01 = [i for i in issues if i.get("rule") == "CST-01" and i.get("level") == "error"]
        assert cst01, issues
        assert any("21" in str(i.get("msg")) for i in cst01)
    finally:
        config.write_text(original, encoding="utf-8")


def test_trace_and_review_packet(project):
    trace = report.trace_payload(project)
    assert trace["must"] == 6
    assert trace["coverage"] == 0.0
    assert trace["ok"] is False
    packet = report.review_payload(project)
    assert len(packet["sha256"]) == 64
    import json

    data = json.loads((project.root / "forge" / "review-packet.json").read_text(encoding="utf-8"))
    assert data["packet_sha256"] == packet["sha256"]
    assert data["trace"]["must"] == 6



def _new_project(parent, name):
    target = parent / name
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "forge.py"),
            "new",
            "发布门测试车",
            "--blueprint",
            "wheel-rover",
            "--dir",
            str(target),
            "--slug",
            name,
        ],
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    loaded = load_project(target)
    assert loaded.load_error is None, loaded.load_error
    return loaded


def test_release_requires_recorded_review(tmp_path):
    project = _new_project(tmp_path, "release-rover")
    assert api.audit_payload(project)["release_level"] == "blocked"

    for req in ("REQ-001", "REQ-002", "REQ-003", "REQ-004", "REQ-005", "REQ-006"):
        api.evidence_payload(
            project,
            req,
            "pytest：按 docs/06 完成人工复核",
            level="manual",
            note="pytest 模拟用户真实试用；不是模型自评",
        )

    report.review_payload(project)
    no_review = api.audit_payload(project)
    assert no_review["release_level"] == "beta", no_review
    assert no_review["review"]["present"] is False

    recorded = report.review_payload(
        project,
        verdict="pass",
        score=90,
        reviewer="pytest independent reviewer",
        findings=[],
    )
    assert recorded["review"]["valid"] is True, recorded
    peek = report.review_payload(project)
    assert peek["sha256"] == recorded["sha256"], "peeking at the packet must not change its hash"
    assert peek["review"]["valid"] is True, peek
    released = api.audit_payload(project)
    assert released["release_level"] == "release", released
    assert released["score"] >= 85
    packed = report.package_payload(project)
    assert packed["ok"] is True and packed["release_level"] == "release", packed

    main_cpp = project.root / "firmware" / "src" / "main.cpp"
    original = main_cpp.read_text(encoding="utf-8")
    main_cpp.write_text(original + "\n// build changed after review\n", encoding="utf-8")
    project._fingerprint = None
    try:
        stale = api.audit_payload(project)
        assert stale["review"]["valid"] is False, stale
        assert stale["release_level"] == "blocked", stale
    finally:
        main_cpp.write_text(original, encoding="utf-8")


def test_review_record_requires_packet_hash_and_reviewer(tmp_path):
    project = _new_project(tmp_path, "tamper-rover")
    for req in ("REQ-001", "REQ-002", "REQ-003", "REQ-004", "REQ-005", "REQ-006"):
        api.evidence_payload(project, req, "pytest：人工复核", level="manual", note="pytest")
    recorded = report.review_payload(
        project, verdict="pass", score=90, reviewer="pytest reviewer", findings=[]
    )
    assert recorded["review"]["valid"] is True
    path = project.root / "forge" / "review.json"
    original = path.read_text(encoding="utf-8")
    try:
        row = json.loads(original)
        row.pop("packet_sha256")
        path.write_text(json.dumps(row), encoding="utf-8")
        assert report.review_status(project)["valid"] is False
        row = json.loads(original)
        row["reviewer"] = ""
        path.write_text(json.dumps(row), encoding="utf-8")
        assert report.review_status(project)["valid"] is False
    finally:
        path.write_text(original, encoding="utf-8")


def test_package_refuses_unverified(project):
    payload = report.package_payload(project)
    assert payload["ok"] is False
    assert "包" in payload["error"] or "错误" in payload["error"]
