"""Cross-artifact consistency: the mistakes a single-file linter cannot see.

A project can be green in every file and still be wrong: the firmware drives
GPIO 4 while the BOM says GPIO 5, the host speaks a command the firmware never
parses, a must requirement points at a script that does not exist, or a real
API key is committed. These checks compare the artifacts against each other.
"""

from __future__ import annotations

import re
from pathlib import Path

from .intake import SAFETY_FLAGS
from .model import _get, _num


TEXT_EXT = {".h", ".hpp", ".c", ".cc", ".cpp", ".ino", ".py", ".json", ".yaml", ".yml", ".md", ".txt", ".ini"}
SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache", ".venv", "venv", "env",
             "node_modules", ".pio", "build", "dist", ".forge", "forgekit"}
SKIP_FILES = {"forge/evidence.jsonl", "hardware/bom.csv", "README.md", "CHANGELOG.md"}


def _walk(project, subdirs, exts=None):
    root = project.root
    out = []
    for sub in subdirs:
        base = root / sub
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in (exts or TEXT_EXT):
                continue
            rel = path.relative_to(root).as_posix()
            # Compare project-relative parts only: the absolute host path may
            # itself sit under a directory named build/ or dist/.
            if any(part in SKIP_DIRS for part in Path(rel).parts):
                continue
            if rel in SKIP_FILES or path.stat().st_size > 512 * 1024:
                continue
            out.append(path)
    return out


def _read(path):
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _strip_c_comments(text):
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    text = re.sub(r"//[^\n]*", " ", text)
    return text


def _rel(project, path):
    return path.relative_to(project.root).as_posix()


def _declared_pins(project):
    numbers = {}
    for p in project.pins:
        try:
            numbers.setdefault(int(p.get("pin")), []).append(str(p.get("id", "gpio")))
        except (TypeError, ValueError):
            continue
    for bus in project.buses:
        pins = bus.get("pins") or {}
        if isinstance(pins, dict):
            for signal, value in pins.items():
                try:
                    numbers.setdefault(int(value), []).append("%s.%s" % (bus.get("id"), signal))
                except (TypeError, ValueError):
                    continue
    return numbers


RE_DEFINE = re.compile(r"#\s*define\s+(PIN_[A-Z0-9_]+)\s+(\d{1,3})\b")
RE_CONST = re.compile(r"\b(?:constexpr|const)\s+(?:int|uint8_t|gpio_num_t|unsigned)\s+(k?[A-Za-z][A-Za-z0-9_]*(?:Pin|GPIO|Gpio|LED|Led|Touch|Trig|Echo|Motor|Servo|Batt)[A-Za-z0-9_]*)\s*=\s*(\d{1,3})\b")


def _firmware_pins(project):
    found = {}
    files = _walk(project, ["firmware/src", "firmware/include", "firmware/lib"], {".h", ".hpp", ".c", ".cc", ".cpp", ".ino"})
    files += [p for p in _walk(project, ["firmware"], {".h"}) if p.name.lower() in ("config.h", "pins.h", "board.h")]
    for path in files:
        text = _strip_c_comments(_read(path))
        rel = _rel(project, path)
        for macro, number in RE_DEFINE.findall(text):
            found.setdefault(int(number), []).append("%s:%s" % (rel, macro))
        if path.suffix.lower() in (".h", ".hpp") or "config" in path.name.lower():
            for name, number in RE_CONST.findall(text):
                found.setdefault(int(number), []).append("%s:%s" % (rel, name))
    return found


def _pin_consistency(project, findings):
    if "firmware" not in project.domains:
        return {"firmware_pins": 0, "declared": len(project.pins), "mismatches": 0}
    declared = _declared_pins(project)
    firmware = _firmware_pins(project)
    if not firmware:
        findings.append({"rule": "CST-01", "level": "error", "file": "firmware/config.h",
                         "msg": "硬件+固件项目里找不到任何 PIN_*/k*Pin 定义；固件与接线表必须可对照"})
        return {"firmware_pins": 0, "declared": len(project.pins), "mismatches": 0}
    mismatches = 0
    for number, uses in sorted(firmware.items()):
        if number not in declared:
            mismatches += 1
            findings.append({"rule": "CST-01", "level": "error", "file": uses[0].split(":")[0],
                             "msg": "固件使用 GPIO%s（%s），但 robot.yaml 的 pins/buses 没有声明；接线表与固件会打架" % (
                                 number, ", ".join(uses[:3]))})
    for number, names in sorted(declared.items()):
        if number not in firmware:
            bus_only = all("." in name for name in names)
            findings.append({"rule": "CST-02", "level": "info" if bus_only else "warning", "file": "robot.yaml",
                             "msg": ("robot.yaml 声明总线引脚 GPIO%s（%s）；I2C/SPI/I2S 通常由库初始化，确认固件按此接线" if bus_only
                                     else "robot.yaml 声明 GPIO%s（%s）但固件未使用；确认是预留还是漏接") % (
                                 number, ", ".join(names[:3]))})
    return {"firmware_pins": len(firmware), "declared": len(declared), "mismatches": mismatches}


RE_WIRE_BEGIN = re.compile(r"Wire\s*\.\s*begin\s*\(\s*(\d{1,3})\s*,\s*(\d{1,3})")


def _bus_consistency(project, findings):
    i2c = [b for b in project.buses if str(b.get("type", "")).lower() in ("i2c", "i²c")]
    for bus in i2c:
        pins = bus.get("pins") or {}
        sda, scl = pins.get("sda"), pins.get("scl")
        if sda is None or scl is None:
            continue
        for path in _walk(project, ["firmware/src", "firmware/lib"], {".cpp", ".c", ".ino", ".h"}):
            m = RE_WIRE_BEGIN.search(_strip_c_comments(_read(path)))
            if not m:
                continue
            if (int(m.group(1)), int(m.group(2))) != (int(sda), int(scl)):
                findings.append({"rule": "CST-03", "level": "error", "file": _rel(project, path),
                                 "msg": "Wire.begin(%s,%s) 与 robot.yaml 的 I2C sda=%s/scl=%s 不一致" % (
                                     m.group(1), m.group(2), sda, scl)})


COMMAND_RE = re.compile(r'["\']([A-Z][A-Z0-9_]{0,9})\b')
HOST_RETURN_RE = re.compile(r'return\s+f?["\']([A-Z][A-Z0-9_]{0,9})\b')


def _protocol_consistency(project, findings):
    host = []
    for path in _walk(project, ["software"], {".py"}):
        if "test" in path.name.lower():
            continue
        host += HOST_RETURN_RE.findall(_read(path))
    firmware = []
    for path in _walk(project, ["firmware/src", "firmware/lib"], {".cpp", ".c", ".ino", ".h"}):
        firmware += COMMAND_RE.findall(_strip_c_comments(_read(path)))
    host = sorted({t for t in host if t not in ("OK", "ERR", "PING") or t == "PING"})
    firmware_set = set(firmware)
    missing = [t for t in host if t not in firmware_set]
    if host and missing and firmware_set:
        findings.append({"rule": "CST-04", "level": "warning", "file": "software",
                         "msg": "主机协议命令 %s 未在固件字符串中出现；若固件按首字符解析请人工确认" % ", ".join(missing)})
    return {"host_commands": host, "firmware_tokens": sorted(firmware_set)[:20]}


def _requirement_consistency(project, findings):
    rows = project.verify_command_rows()
    by_req = {}
    for row in rows:
        reqs = row.get("req") or []
        if isinstance(reqs, str):
            reqs = [reqs]
        for req in reqs:
            by_req.setdefault(str(req), []).append(str(row.get("id", "")))
    missing = []
    optional_only = []
    for req in project.requirements:
        if str(req.get("priority", "must")) != "must":
            continue
        rid = str(req.get("id", ""))
        verify = str(req.get("verify", "")).strip()
        if verify.lower().startswith("manual:"):
            continue
        if rid not in by_req:
            missing.append(rid)
            continue
        commands = [r for r in rows if str(r.get("id")) in by_req[rid]]
        if commands and all(r.get("required") is False for r in commands):
            optional_only.append(rid)
    for rid in missing:
        findings.append({"rule": "CST-05", "level": "error", "file": "verify.yaml",
                         "msg": "must 需求 %s 的 verify 命令没有映射到 verify.yaml 的 req；证据无法自动归因" % rid})
    for rid in optional_only:
        findings.append({"rule": "CST-05", "level": "warning", "file": "verify.yaml",
                         "msg": "must 需求 %s 只被 required:false 命令覆盖；缺工具时会静默跳过" % rid})
    for row in rows:
        reqs = row.get("req") or []
        if not reqs and str(row.get("id")) not in ("self-check", "smoke"):
            findings.append({"rule": "CST-06", "level": "info", "file": "verify.yaml",
                             "msg": "验证命令 %s 没有绑定需求；只用来自检可以，否则至少绑一条" % row.get("id")})
    return {"mapped": len(by_req), "missing": missing, "optional_only": optional_only}


SECRET_PATTERNS = [
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "AWS access key"),
    (re.compile(r"\bghp_[A-Za-z0-9]{30,}\b"), "GitHub token"),
    (re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"), "API key"),
    (re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----"), "private key"),
    (re.compile(r"(?i)(?:password|passwd|secret|token)\s*[:=]\s*[\"'][^\"'\s]{8,}[\"']"), "hard-coded credential"),
]


def _secret_scan(project, findings):
    hits = 0
    for path in _walk(project, ["."]):
        rel = _rel(project, path)
        if rel.startswith(("docs/", "evals/")) and path.suffix == ".md":
            continue
        text = _read(path)
        for pattern, label in SECRET_PATTERNS:
            if pattern.search(text):
                hits += 1
                level = "error" if label != "hard-coded credential" else "warning"
                findings.append({"rule": "CST-07", "level": level, "file": rel,
                                 "msg": "疑似提交了%s；改为环境变量/密钥文件并加入 .gitignore" % label})
                break
    return {"secret_hits": hits}


def _test_quality(project, findings):
    min_tests = int(_num(_get(project.data, "test_plan", "min_tests"), 6) or 6)
    py_tests = 0
    asserts = 0
    for path in _walk(project, ["software/tests", "tests"], {".py"}):
        text = _read(path)
        py_tests += len(re.findall(r"^\s*def\s+test_", text, flags=re.M))
        asserts += len(re.findall(r"^\s*assert\b", text, flags=re.M))
    cpp_tests = 0
    for path in _walk(project, ["firmware/test", "firmware/tests"], {".cpp", ".cc", ".c"}):
        cpp_tests += len(re.findall(r"\bTEST(?:_CASE|_F)?\s*\(", _read(path)))
    total = py_tests + cpp_tests
    if "software" in project.domains and total == 0:
        findings.append({"rule": "CST-08", "level": "error", "file": "software/tests",
                         "msg": "没有可执行测试；软件域必须有 pytest 或固件 native 测试，不能只靠人工点一遍"})
    elif total < min_tests:
        findings.append({"rule": "CST-08", "level": "warning", "file": "software/tests",
                         "msg": "测试仅 %d 个，低于 test_plan.min_tests=%d；至少覆盖协议、边界与失败路径" % (total, min_tests)})
    if py_tests and asserts < py_tests:
        findings.append({"rule": "CST-08", "level": "warning", "file": "software/tests",
                         "msg": "%d 个 pytest 但只有 %d 个 assert；测试可能只跑不断言" % (py_tests, asserts)})
    return {"tests": total, "pytest": py_tests, "cpp": cpp_tests, "asserts": asserts, "min_tests": min_tests}


def _supply(project, findings):
    missing_source = []
    eol = []
    long_lead = []
    for c in project.components:
        if _num(c.get("price")) <= 0:
            continue
        cid = str(c.get("id"))
        if not str(c.get("source", "")).strip():
            missing_source.append(cid)
        availability = str(c.get("availability", "")).lower()
        if availability in ("eol", "discontinued", "停产", "停售"):
            eol.append(cid)
        if _num(c.get("lead_time_days")) > 30 and project.gear != "flagship":
            long_lead.append(cid)
    if missing_source:
        findings.append({"rule": "CST-09", "level": "warning", "file": "robot.yaml",
                         "msg": "%d 个元件没有 source 采购来源：%s" % (len(missing_source), ", ".join(missing_source[:5]))})
    for cid in eol:
        findings.append({"rule": "CST-09", "level": "error", "file": "robot.yaml",
                         "msg": "元件 %s 已停产/停售；换在产替代，别让后来者买不到" % cid})
    for cid in long_lead:
        findings.append({"rule": "CST-09", "level": "warning", "file": "robot.yaml",
                         "msg": "元件 %s 交期 >30 天，与 %s 档位不匹配" % (cid, project.gear)})
    return {"missing_source": missing_source, "eol": eol, "long_lead": long_lead}


def _term_hit(terms, low):
    """Substring for CJK, token boundary for short ASCII words (app != happy)."""
    for term in terms:
        t = str(term).lower().strip()
        if not t:
            continue
        if re.fullmatch(r"[a-z0-9 .+\-]+", t):
            if re.search(r"(?<![a-z0-9])" + re.escape(t) + r"(?![a-z0-9])", low):
                return True
        elif t in low:
            return True
    return False


def _safety_text(project):
    """Only positive intent: wish.story/must/nice, features, parts. Not wish.forbidden,
    and never compliance/security prose (otherwise the mitigation triggers itself)."""
    data = project.data
    parts = []
    wish = data.get("wish") or {}
    for key in ("story", "must", "nice"):
        value = wish.get(key)
        if isinstance(value, list):
            parts.extend(str(v) for v in value)
        elif value:
            parts.append(str(value))
    arch = data.get("architecture") or {}
    features = arch.get("features") or data.get("features") or []
    for feat in features:
        if isinstance(feat, dict):
            parts.append(str(feat.get("text") or ""))
            parts.append(str(feat.get("name") or ""))
            parts.append(str(feat.get("how") or ""))
    for comp in data.get("components") or []:
        if isinstance(comp, dict):
            parts.append(str(comp.get("part") or ""))
            parts.append(str(comp.get("role") or ""))
            parts.append(str(comp.get("note") or ""))
    parts.append(str(arch.get("summary") or ""))
    parts.append(str(arch.get("comms") or ""))
    behavior = data.get("behavior") or {}
    parts.append(str(behavior))
    if data.get("motion"):
        parts.append("运动")
    return "\n".join(parts).lower()


def _compliance(project, findings):
    text = _safety_text(project)
    triggers = []
    for terms, key, title, requirement in SAFETY_FLAGS:
        if _term_hit(terms, text):
            triggers.append({"key": key, "title": title, "requirement": requirement})
    compliance = _get(project.data, "compliance", default={}) or {}
    if triggers and not compliance:
        findings.append({"rule": "CST-10", "level": "warning", "file": "robot.yaml",
                         "msg": "有安全触发项（%s）但没写 compliance 块；docs/07 需要标准/标签/限用边界" % (
                             "、".join(t["title"] for t in triggers))})
    if triggers:
        docs = sorted((project.root / "docs").glob("07-*.md"))
        safety_doc = docs[0] if docs else project.root / "docs" / "07-安全与隐私.md"
        body = _read(safety_doc) if safety_doc.exists() else ""
        doc_terms = {
            "battery": ("电池", "过充", "过放", "短路", "热失控"),
            "mains": ("市电", "接地", "漏保", "隔离", "断电"),
            "motion": ("运动", "夹伤", "堵转", "急停", "限位", "断电"),
            "laser": ("激光", "护目", "直视", "扫描"),
            "privacy": ("隐私", "摄像头", "麦克风", "采集"),
            "network": ("联网", "鉴权", "密码", "OTA", "网络"),
            "children": ("儿童", "小零件", "监护", "误吞"),
            "outdoor": ("户外", "防水", "IP", "涉水", "排水"),
            "medical": ("医疗", "诊断", "持证"),
        }
        for trigger in triggers:
            terms = doc_terms.get(trigger["key"], (trigger["title"],))
            if not any(term.lower() in body.lower() for term in terms):
                findings.append({"rule": "CST-11", "level": "warning", "file": str(safety_doc.relative_to(project.root)).replace("\\", "/"),
                                 "msg": "触发项“%s”在安全文档里找不到对应内容（期望覆盖：%s）" % (trigger["title"], "、".join(terms))})
    if "network" in [t["key"] for t in triggers]:
        security = _get(project.data, "security", default={}) or {}
        if not security:
            findings.append({"rule": "CST-12", "level": "warning", "file": "robot.yaml",
                             "msg": "联网项目缺 security 块：至少写 threats/鉴权/OTA/默认口令处理"})
    return {"triggers": [t["key"] for t in triggers], "has_block": bool(compliance)}


def _bom_docs(project, findings):
    doc = project.root / "docs" / "01-物料清单.md"
    if not doc.exists():
        return {"missing_parts": []}
    body = _read(doc)
    missing = []
    for c in project.components:
        part = str(c.get("part", "")).strip()
        if not part:
            continue
        key = re.sub(r"\s+", "", part)[:12]
        if key and key not in re.sub(r"\s+", "", body):
            missing.append(str(c.get("id")))
    if missing:
        findings.append({"rule": "CST-13", "level": "warning", "file": "docs/01-物料清单.md",
                         "msg": "BOM 元件未出现在物料文档：%s；文档与清单会漂移" % ", ".join(missing[:6])})
    return {"missing_parts": missing}


def _feature_trace(project, findings):
    untraced = []
    for f in project.features:
        if f.get("software_only"):
            continue
        if not f.get("components"):
            untraced.append(str(f.get("id", "?")))
    if untraced:
        findings.append({"rule": "CST-14", "level": "info", "file": "robot.yaml",
                         "msg": "功能 %s 没有绑定元件；确认是纯软件能力还是漏写" % ", ".join(untraced[:6])})
    return {"untraced": untraced}


def consistency_issues(project):
    findings = []
    _pin_consistency(project, findings)
    _bus_consistency(project, findings)
    _protocol_consistency(project, findings)
    _requirement_consistency(project, findings)
    _secret_scan(project, findings)
    _test_quality(project, findings)
    _supply(project, findings)
    _compliance(project, findings)
    _bom_docs(project, findings)
    _feature_trace(project, findings)
    return findings


def consistency_payload(project):
    findings = consistency_issues(project)
    return {
        "project": str(project.root),
        "findings": findings,
        "stats": {
            "errors": len([f for f in findings if f["level"] == "error"]),
            "warnings": len([f for f in findings if f["level"] == "warning"]),
            "infos": len([f for f in findings if f["level"] == "info"]),
        },
    }
