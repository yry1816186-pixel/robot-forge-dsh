"""Load and validate the single source of truth: forge/robot.yaml."""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path

from . import yamlmini
from .util import load_json, read_text

DOMAINS = ["hardware", "cad", "firmware", "software", "sim"]
GEARS = ["quick", "standard", "flagship"]
PRIORITIES = ["must", "should", "nice"]
LEVELS = ["measured", "manual", "simulated", "assumed"]
LEVELS_OK = ("measured", "manual")
ICONS = {"measured": "✅", "manual": "✅", "simulated": "🟡", "assumed": "⚪", "none": "⚪", "broken": "⛔"}

REQUIRED_DOCS = [
    "README.md",
    "LICENSE",
    "CHANGELOG.md",
    "docs/00-总览.md",
    "docs/01-物料清单.md",
    "docs/02-组装指南.md",
    "docs/03-接线表.md",
    "docs/04-固件说明.md",
    "docs/05-软件说明.md",
    "docs/06-使用手册.md",
    "docs/07-安全与隐私.md",
    "docs/08-故障排查.md",
    "docs/09-验证报告.md",
    "docs/10-常见问题.md",
]

CATEGORY = {
    "controller": "主控",
    "actuator": "执行器",
    "sensor": "传感器",
    "audio": "音频",
    "display": "显示",
    "power": "电源",
    "structure": "结构",
    "cable": "线材",
    "fastener": "紧固件",
    "tool": "工具",
    "other": "其他",
}

MCU_RESERVED = {
    "esp32-s3": {0, 19, 20, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 45, 46},
    "esp32-c3": {11, 12, 13, 14, 15, 16, 17, 18, 19},
    "esp32": {0, 1, 2, 3, 6, 7, 8, 9, 10, 11, 12, 15},
    "rp2040": set(),
    "stm32": set(),
}

COMMAND_RE = re.compile(r"^(pytest|python3?|py|pio|platformio|npm|pnpm|node|make|cmake|bash|sh|pwsh|powershell|arduino-cli|kicad-cli|forge\.py|\.\/|[\w./-]+\.(py|sh|ps1))(\s|$)")
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,40}$")
PLACEHOLDER_PART_RE = re.compile(r"^(待定|待选|待购|型号|xxx|XXX|tbd|TBD|todo|example|placeholder|\?+)$")

# Source fingerprint: what the last measured verification actually covered.
# Docs, README, generated diagrams/STLs and the evidence ledger are excluded so
# rendering or appending evidence cannot make a fresh run look stale.
FINGERPRINT_SKIP_DIRS = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".ipynb_checkpoints",
    ".venv",
    "venv",
    "env",
    "node_modules",
    ".pio",
    "build",
    "dist",
    "docs",
    "diagrams",
    "tools",
    "stl",
}
FINGERPRINT_SKIP_PATHS = {"forge/evidence.jsonl", "hardware/bom.csv", "README.md", "CHANGELOG.md"}
FINGERPRINT_MAX_BYTES = 4 * 1024 * 1024


class Issue(object):
    __slots__ = ("rule", "level", "msg", "file")

    def __init__(self, rule, level, msg, file=None):
        self.rule = rule
        self.level = level
        self.msg = msg
        self.file = file

    def as_dict(self):
        return {"rule": self.rule, "level": self.level, "msg": self.msg, "file": self.file}

    def __repr__(self):
        return "[%s/%s] %s" % (self.rule, self.level, self.msg)


def _get(d, *keys, **kw):
    default = kw.get("default")
    cur = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


def _num(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _int(v, default=0):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default


def _list(v):
    return v if isinstance(v, list) else []


def pin_number(v):
    """Normalise GPIO specs: 8, '8', 'GPIO8', 'D8' -> int; complex names stay str."""
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    text = str(v).strip().upper()
    m = re.search(r"(\d+)", text)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            return None
    return None


class Project(object):
    def __init__(self, root, data, verify, load_error=None):
        self.root = Path(root)
        self.data = data or {}
        self.verify = verify or {}
        self.load_error = load_error
        self.components = _list(_get(self.data, "components", default=[]))
        self.buses = _list(_get(self.data, "buses", default=[]))
        self.pins = _list(_get(self.data, "pins", default=[]))
        self.rails = _list(_get(self.data, "power", "rails", default=[]))
        self.consumers = _list(_get(self.data, "power", "consumers", default=[]))
        self.requirements = _list(_get(self.data, "requirements", default=[]))
        self.risks = _list(_get(self.data, "risks", default=[]))
        self.features = _list(_get(self.data, "architecture", "features", default=[]))
        self.domains = _list(_get(self.data, "project", "domains", default=[]))
        self.mech = _get(self.data, "mechanical", default={}) or {}
        self._fingerprint = None

    # -- convenience -----------------------------------------------------
    @property
    def name(self):
        return _get(self.data, "project", "name", default="未命名项目")

    @property
    def slug(self):
        return _get(self.data, "project", "slug", default="robot")

    @property
    def version(self):
        return str(_get(self.data, "project", "version", default="0.1.0"))

    @property
    def gear(self):
        return _get(self.data, "project", "gear", default="standard")

    @property
    def budget(self):
        return _num(_get(self.data, "cost", "target_cny", default=0))

    def comp(self, cid):
        for c in self.components:
            if str(c.get("id")) == str(cid):
                return c

    def verify_command_rows(self):
        raw = self.verify.get("commands") if isinstance(self.verify, dict) else []
        return [c for c in _list(raw) if isinstance(c, dict)]

    def bus(self, bid):
        for b in self.buses:
            if str(b.get("id")) == str(bid):
                return b
        return None

    def rail(self, rid):
        for r in self.rails:
            if str(r.get("id")) == str(rid):
                return r
        return None

    def mcu(self):
        for c in self.components:
            if str(c.get("role", "")).lower() == "controller":
                return c
        return None

    def mcu_family(self):
        mcu = self.mcu()
        part = str(mcu.get("part", "")).lower() if mcu else ""
        for fam in ("esp32-s3", "esp32-c3", "esp32", "rp2040", "stm32"):
            if fam in part:
                return fam
        return ""

    def bom_rows(self):
        rows = []
        for i, c in enumerate(self.components, 1):
            qty = max(1, _int(c.get("qty"), 1))
            price = _num(c.get("price_cny"))
            rows.append(
                {
                    "no": i,
                    "id": str(c.get("id", "")),
                    "category": CATEGORY.get(str(c.get("role", "other")).lower(), "其他"),
                    "part": str(c.get("part", "?")),
                    "qty": qty,
                    "unit": price,
                    "subtotal": round(price * qty, 2),
                    "source": str(c.get("source", "")),
                    "note": str(c.get("note", "")),
                }
            )
        return rows

    def total_cost(self):
        total = sum(r["subtotal"] for r in self.bom_rows())
        return round(total + _num(_get(self.data, "cost", "shipping_cny", default=0)), 2)

    def pin_rows(self):
        rows = []
        for b in self.buses:
            buses_pins = b.get("pins") or {}
            if isinstance(buses_pins, dict):
                for signal, pin in buses_pins.items():
                    rows.append(
                        {
                            "bus": str(b.get("id", "")),
                            "type": str(b.get("type", "")),
                            "signal": str(signal),
                            "pin": str(pin),
                            "connect": ", ".join(str(c.get("id")) for c in self.components if str(c.get("bus", "")) == str(b.get("id"))) or "-",
                            "note": str(b.get("note", "")),
                        }
                    )
        for p in self.pins:
            rows.append(
                {
                    "bus": str(p.get("id", "")),
                    "type": str(p.get("function", "gpio")),
                    "signal": str(p.get("function", "")),
                    "pin": str(p.get("pin", "")),
                    "connect": str(p.get("connect", "-")),
                    "note": str(p.get("note", "")),
                }
            )
        return rows

    def bus_rows(self):
        rows = []
        for b in self.buses:
            pins = b.get("pins") or {}
            pin_txt = ", ".join("%s=%s" % (k, v) for k, v in pins.items()) if isinstance(pins, dict) else ""
            members = [str(c.get("id")) for c in self.components if str(c.get("bus", "")) == str(b.get("id"))]
            rows.append(
                {
                    "id": str(b.get("id", "")),
                    "type": str(b.get("type", "")),
                    "pins": pin_txt,
                    "members": ", ".join(members) or "-",
                    "note": str(b.get("note", "")),
                }
            )
        return rows

    def power_rows(self):
        agg = {}
        for r in self.rails:
            agg[str(r.get("id"))] = {"typ": 0.0, "peak": 0.0}
        for c in self.consumers:
            rid = str(c.get("rail", ""))
            if rid in agg:
                agg[rid]["typ"] += _num(c.get("typical_ma"))
                agg[rid]["peak"] += _num(c.get("peak_ma"))
        rows = []
        for r in self.rails:
            rid = str(r.get("id"))
            max_ma = _num(r.get("max_ma"))
            typ = agg[rid]["typ"]
            peak = agg[rid]["peak"]
            typ_pct = (typ / max_ma * 100) if max_ma else 0
            peak_pct = (peak / max_ma * 100) if max_ma else 0
            if peak_pct > 90:
                status = "⛔ 峰值超限"
            elif typ_pct > 70:
                status = "🟡 典型偏高"
            else:
                status = "✅ 余量充足"
            rows.append(
                {
                    "id": rid,
                    "voltage": _num(r.get("voltage")),
                    "max_ma": max_ma,
                    "typ": typ,
                    "peak": peak,
                    "typ_pct": typ_pct,
                    "peak_pct": peak_pct,
                    "status": status,
                }
            )
        return rows

    def battery_runtime_h(self):
        bat = _get(self.data, "power", "battery", default={}) or {}
        chemistry = str(bat.get("chemistry", "none")).lower()
        if chemistry in ("", "none", "无"):
            return None
        mah = _num(bat.get("mah"))
        cells = max(1, _int(bat.get("cells"), 1))
        wh = mah / 1000.0 * cells * 3.7
        watts = 0.0
        for c in self.consumers:
            rail = self.rail(str(c.get("rail", "")))
            if rail:
                watts += _num(rail.get("voltage"), 5.0) * _num(c.get("typical_ma")) / 1000.0
        if watts <= 0:
            return None
        return wh * 0.85 / watts

    def evidence(self):
        path = self.root / "forge" / "evidence.jsonl"
        items = []
        if not path.is_file():
            return items
        for line in read_text(path).splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                import json

                item = json.loads(line)
                if isinstance(item, dict):
                    items.append(item)
            except Exception:
                items.append({"id": "broken", "req": "", "claim": line, "level": "assumed", "_broken": True})
        return items

    def evidence_for(self, req_id):
        found = []
        for item in self.evidence():
            if str(item.get("req", "")) == str(req_id):
                found.append(item)
        rank = {name: i for i, name in enumerate(LEVELS)}
        found.sort(key=lambda x: rank.get(str(x.get("level", "assumed")).lower(), 3))
        return found

    def source_fingerprint(self):
        """Stable hash of the inputs a measured verification depends on.

        Docs, generated files, tool copies and the evidence ledger are skipped:
        rendering a report or appending evidence must not make a fresh run look
        stale, while changing software/firmware/sim/hardware must.
        """
        if self._fingerprint is not None:
            return self._fingerprint
        digest = hashlib.sha256()
        for dirpath, dirnames, filenames in os.walk(self.root):
            here = Path(dirpath)
            rel_dir = here.relative_to(self.root)
            dirnames[:] = sorted(d for d in dirnames if d not in FINGERPRINT_SKIP_DIRS)
            for filename in sorted(filenames):
                rel = (rel_dir / filename).as_posix()
                if rel in FINGERPRINT_SKIP_PATHS or filename.endswith(".log"):
                    continue
                # Only the two manifests under forge/ are inputs. Plan, decisions,
                # risks, audits and research notes are documentation and must not
                # invalidate a measured run.
                if rel.startswith("forge/") and rel not in ("forge/robot.yaml", "forge/verify.yaml"):
                    continue
                path = here / filename
                try:
                    if path.stat().st_size > FINGERPRINT_MAX_BYTES:
                        continue
                    payload = path.read_bytes()
                except OSError:
                    continue
                digest.update(rel.encode("utf-8"))
                digest.update(b"\0")
                digest.update(payload)
        self._fingerprint = digest.hexdigest()[:16]
        return self._fingerprint

    def evidence_is_fresh(self, item):
        level = str(item.get("level", "assumed")).lower()
        if level not in ("measured", "manual"):
            return True
        recorded = str(item.get("fingerprint", "") or "")
        return bool(recorded) and recorded == self.source_fingerprint()

    def requirement_status(self, req):
        req_id = str(req.get("id", ""))
        ev = self.evidence_for(req_id)
        if not ev:
            return "none", ev
        fresh = [item for item in ev if self.evidence_is_fresh(item)]
        if not fresh:
            return "assumed", ev
        best = "none"
        for item in fresh:
            lvl = str(item.get("level", "assumed")).lower()
            if lvl not in LEVELS:
                lvl = "assumed"
            if best == "none" or LEVELS.index(lvl) < LEVELS.index(best):
                best = lvl
        return best, ev

    def status_rows(self):
        rows = []
        for req in self.requirements:
            if str(req.get("priority", "must")) != "must":
                continue
            level, ev = self.requirement_status(req)
            icon = ICONS.get(level, "⚪")
            latest = ev[0] if ev else {}
            rows.append(
                {
                    "id": str(req.get("id", "")),
                    "text": str(req.get("text", "")),
                    "icon": icon,
                    "level": level,
                    "evidence": str(latest.get("claim", "") or latest.get("note", "")),
                }
            )
        return rows

    def features_of(self, component_id):
        out = []
        for f in self.features:
            ids = [str(x) for x in _list(f.get("components"))]
            if str(component_id) in ids:
                out.append(str(f.get("name", f.get("id", ""))))
        return out


def load_project(root):
    root = Path(root)
    robot_path = root / "forge" / "robot.yaml"
    verify_path = root / "forge" / "verify.yaml"
    if not robot_path.is_file():
        return Project(root, {}, {}, load_error="找不到 %s" % robot_path)
    try:
        data = yamlmini.loads(read_text(robot_path))
    except Exception as exc:  # noqa: BLE001 - parser detail matters to the user
        return Project(root, {}, {}, load_error="forge/robot.yaml 解析失败：%s" % exc)
    verify = {}
    if verify_path.is_file():
        try:
            verify = yamlmini.loads(read_text(verify_path))
        except Exception as exc:  # noqa: BLE001
            verify = {"commands": [], "_error": "forge/verify.yaml 解析失败：%s" % exc}
    return Project(root, data, verify)


# -- validation ---------------------------------------------------------------


def validate(project):
    """Schema + relationship checks (S1-S14). Returns a list of Issue."""
    issues = []
    if project.load_error:
        return [Issue("S1", "error", project.load_error, "forge/robot.yaml")]
    d = project.data
    add = lambda rule, level, msg, file=None: issues.append(Issue(rule, level, msg, file))

    if _int(d.get("schema")) != 1:
        add("S1", "error", "schema 必须是 1（当前 %r）" % d.get("schema"), "forge/robot.yaml")
    proj = d.get("project") or {}
    if not isinstance(proj, dict):
        add("S1", "error", "project 必须是对象", "forge/robot.yaml")
        proj = {}
    if not str(proj.get("name", "")).strip():
        add("S1", "error", "project.name 不能为空", "forge/robot.yaml")
    if not SLUG_RE.match(str(proj.get("slug", ""))):
        add("S1", "error", "project.slug 只能小写字母/数字/连字符，如 xiaoman-companion", "forge/robot.yaml")
    if str(proj.get("gear", "standard")) not in GEARS:
        add("S1", "error", "project.gear 必须是 %s 之一" % "/".join(GEARS), "forge/robot.yaml")
    domains = _list(proj.get("domains"))
    if not domains:
        add("S1", "error", "project.domains 至少写一个：%s" % "/".join(DOMAINS), "forge/robot.yaml")
    for dom in domains:
        if dom not in DOMAINS:
            add("S1", "error", "未知 domain %r（可选 %s）" % (dom, "/".join(DOMAINS)), "forge/robot.yaml")
    if _num(proj.get("budget_cny")) <= 0:
        add("S1", "warn", "project.budget_cny 未填，成本门禁会失去意义", "forge/robot.yaml")

    story = str(_get(d, "wish", "story", default="")).strip()
    if len(story) < 20:
        add("S1", "error", "wish.story 太短（<20 字）：写清谁在什么场景下用它、最想解决的 1 件事", "forge/robot.yaml")
    if not _list(_get(d, "wish", "must", default=[])):
        add("S1", "error", "wish.must 至少写 1 条「必须做到」的用户语言需求", "forge/robot.yaml")

    features = _list(_get(d, "architecture", "features", default=[]))
    if not features:
        add("S1", "error", "architecture.features 至少 1 条能力", "forge/robot.yaml")
    feat_ids = set()
    for f in features:
        fid = str(f.get("id", ""))
        if not fid:
            add("S1", "error", "feature 缺 id", "forge/robot.yaml")
        elif fid in feat_ids:
            add("S2", "error", "feature id 重复：%s" % fid, "forge/robot.yaml")
        feat_ids.add(fid)
        if not str(f.get("how", "")).strip():
            add("S1", "error", "feature %s 缺 how（怎么实现）" % fid, "forge/robot.yaml")

    if ("hardware" in domains or "firmware" in domains) and not project.components:
        add("S1", "error", "有硬件/固件域，components 不能为空", "forge/robot.yaml")
    if "firmware" in domains and not project.mcu():
        add("S1", "error", "有固件域，但 components 里没有 role: controller 的主控", "forge/robot.yaml")

    comp_ids = set()
    for c in project.components:
        cid = str(c.get("id", ""))
        if not cid:
            add("S1", "error", "component 缺 id", "forge/robot.yaml")
        elif cid in comp_ids:
            add("S2", "error", "component id 重复：%s" % cid, "forge/robot.yaml")
        comp_ids.add(cid)
        for key in ("role", "part", "qty", "price_cny"):
            if key not in c:
                add("S1", "error", "component %s 缺字段 %s" % (cid or "?", key), "forge/robot.yaml")
        if _int(c.get("qty"), 0) < 1:
            add("S1", "error", "component %s 的 qty 必须 ≥1" % cid, "forge/robot.yaml")
        if _num(c.get("price_cny"), -1) < 0:
            add("S1", "error", "component %s 的 price_cny 必须 ≥0" % cid, "forge/robot.yaml")
        if str(c.get("role", "")) in ("controller", "actuator", "sensor", "audio", "display", "power"):
            if not str(c.get("source", "")).strip():
                add("S3", "warn", "component %s（%s）缺 source 采购渠道" % (cid, c.get("part")), "forge/robot.yaml")
        if PLACEHOLDER_PART_RE.match(str(c.get("part", "")).strip()):
            add("S14", "error", "component %s 的 part 是占位型号 %r：写真实可买型号" % (cid, c.get("part")), "forge/robot.yaml")

    # buses
    bus_ids = set()
    pin_owner = {}
    for b in project.buses:
        bid = str(b.get("id", ""))
        if not bid:
            add("S1", "error", "bus 缺 id", "forge/robot.yaml")
        elif bid in bus_ids:
            add("S2", "error", "bus id 重复：%s" % bid, "forge/robot.yaml")
        bus_ids.add(bid)
        btype = str(b.get("type", ""))
        if btype not in ("i2c", "spi", "uart", "i2s", "pwm", "bus-servo", "can", "onewire", "adc"):
            add("S1", "error", "bus %s 的类型 %r 不认识" % (bid, btype), "forge/robot.yaml")
        ctrl = str(b.get("controller", "mcu"))
        if ctrl and ctrl not in comp_ids:
            add("S3", "error", "bus %s 的 controller %r 不存在" % (bid, ctrl), "forge/robot.yaml")
        pins = b.get("pins") or {}
        if not isinstance(pins, dict) or not pins:
            add("S1", "error", "bus %s 缺 pins（如 {sda: 8, scl: 9}）" % bid, "forge/robot.yaml")
            continue
        for signal, pin in pins.items():
            num = pin_number(pin)
            if num is None:
                add("S4", "error", "bus %s 的 %s 引脚 %r 不是有效 GPIO 号" % (bid, signal, pin), "forge/robot.yaml")
                continue
            if num in pin_owner:
                add("S4", "error", "GPIO%d 冲突：%s 与 %s 抢同一脚" % (num, pin_owner[num], "%s.%s" % (bid, signal)), "forge/robot.yaml")
            else:
                pin_owner[num] = "%s.%s" % (bid, signal)

    # explicit pins
    for p in project.pins:
        pid = str(p.get("id", ""))
        num = pin_number(p.get("pin"))
        if num is None:
            add("S4", "error", "pin %s 的引脚 %r 不是有效 GPIO 号" % (pid, p.get("pin")), "forge/robot.yaml")
            continue
        if num in pin_owner:
            add("S4", "error", "GPIO%d 冲突：%s 与 %s" % (num, pid, pin_owner[num]), "forge/robot.yaml")
        else:
            pin_owner[num] = pid

    fam = project.mcu_family()
    reserved = MCU_RESERVED.get(fam, set())
    if reserved:
        for num, owner in sorted(pin_owner.items()):
            if num in reserved:
                add("S4", "error", "GPIO%d（%s）在 %s 上是启动/Flash/USB 保留脚，不能这样用" % (num, owner, fam), "forge/robot.yaml")

    # component bus references + address collisions
    for c in project.components:
        cid = str(c.get("id", ""))
        bus_ref = str(c.get("bus", "") or "")
        if bus_ref and bus_ref not in bus_ids:
            add("S3", "error", "component %s 引用了不存在的 bus %r" % (cid, bus_ref), "forge/robot.yaml")
        if bus_ref and bus_ref in bus_ids:
            addr = c.get("address")
            if addr is not None:
                for other in project.components:
                    if other is c:
                        continue
                    if str(other.get("bus", "")) == bus_ref and str(other.get("address")) == str(addr):
                        add("S5", "error", "bus %s 上地址冲突：%s 与 %s 都用 %s" % (bus_ref, cid, other.get("id"), addr), "forge/robot.yaml")

    # power
    rail_ids = set()
    for r in project.rails:
        rid = str(r.get("id", ""))
        if rid in rail_ids:
            add("S2", "error", "rail id 重复：%s" % rid, "forge/robot.yaml")
        rail_ids.add(rid)
        if _num(r.get("voltage")) <= 0:
            add("S6", "error", "rail %s 的 voltage 必须 >0" % rid, "forge/robot.yaml")
        if _num(r.get("max_ma")) <= 0:
            add("S6", "error", "rail %s 的 max_ma 必须 >0" % rid, "forge/robot.yaml")
    for c in project.consumers:
        cid = str(c.get("component", ""))
        rid = str(c.get("rail", ""))
        if cid not in comp_ids:
            add("S3", "error", "power.consumers 引用了不存在的元件 %r" % cid, "forge/robot.yaml")
        if rid not in rail_ids:
            add("S3", "error", "power.consumers 引用了不存在的 rail %r" % rid, "forge/robot.yaml")
        if _num(c.get("typical_ma")) > _num(c.get("peak_ma")):
            add("S6", "error", "power.consumers %s 的 typical_ma 大于 peak_ma" % cid, "forge/robot.yaml")
    if project.rails and project.consumers:
        for row in project.power_rows():
            if row["max_ma"] and row["peak_pct"] > 90:
                add("S6", "error", "rail %s 峰值 %.0f%% > 90%%：换更大电源或错峰" % (row["id"], row["peak_pct"]), "forge/robot.yaml")
            elif row["max_ma"] and row["typ_pct"] > 70:
                add("S6", "warn", "rail %s 典型负载 %.0f%% > 70%%：余量偏小" % (row["id"], row["typ_pct"]), "forge/robot.yaml")
    runtime = project.battery_runtime_h()
    if runtime is not None and runtime < 1.0:
        add("S6", "warn", "电池典型续航约 %.1f h，低于 1 h：加大电池或降功耗" % runtime, "forge/robot.yaml")

    # features ↔ components
    for f in features:
        fid = str(f.get("id", ""))
        refs = [str(x) for x in _list(f.get("components"))]
        if not refs and not f.get("software_only"):
            add("S8", "error", "feature %s 没写 components（或在纯软件能力上标 software_only: true）" % fid, "forge/robot.yaml")
        for ref in refs:
            if ref not in comp_ids:
                add("S8", "error", "feature %s 引用了不存在的元件 %r" % (fid, ref), "forge/robot.yaml")

    # requirements
    req_ids = set()
    for req in project.requirements:
        rid = str(req.get("id", ""))
        if not rid:
            add("S1", "error", "requirement 缺 id", "forge/robot.yaml")
        elif rid in req_ids:
            add("S2", "error", "requirement id 重复：%s" % rid, "forge/robot.yaml")
        req_ids.add(rid)
        if str(req.get("priority", "must")) not in PRIORITIES:
            add("S1", "error", "requirement %s 的 priority 必须是 must/should/nice" % rid, "forge/robot.yaml")
        if len(str(req.get("text", "")).strip()) < 4:
            add("S1", "error", "requirement %s 的 text 太短" % rid, "forge/robot.yaml")
        verify = str(req.get("verify", "")).strip()
        if not verify:
            add("S9", "error", "requirement %s 缺 verify（一条可执行命令，或 manual: 步骤）" % rid, "forge/robot.yaml")
        elif not verify.startswith("manual:") and not COMMAND_RE.match(verify):
            add("S9", "error", "requirement %s 的 verify 不像可执行命令：%r" % (rid, verify[:60]), "forge/robot.yaml")
        elif verify.startswith("manual:") and str(req.get("priority", "must")) == "must":
            add("S9", "warn", "requirement %s 是 must 但只有人工验证" % rid, "forge/robot.yaml")
        if verify.startswith("manual:"):
            steps = verify[len("manual:"):].strip()
            if len(steps) < 6:
                add("S9", "error", "requirement %s 的 manual: 后面要写具体、可复现的人工步骤" % rid, "forge/robot.yaml")

    # requirement -> verify.yaml mapping: a command named in robot.yaml must
    # actually be runnable from verify.yaml, otherwise next-step/audit can look
    # covered while nothing ever executes.
    if not project.verify.get("_error"):
        commands = project.verify_command_rows()
        for req in project.requirements:
            verify = str(req.get("verify", "")).strip()
            if not verify or verify.startswith("manual:"):
                continue
            rid = str(req.get("id", ""))
            wanted = " ".join(verify.split())
            matched = False
            for command in commands:
                run = " ".join(str(command.get("run", "")).split())
                if run == wanted or rid in [str(x) for x in _list(command.get("req"))]:
                    matched = True
                    break
            if not matched:
                add(
                    "S9",
                    "error",
                    "requirement %s 的 verify 命令没有出现在 forge/verify.yaml，或对应命令的 req 未包含它" % rid,
                    "forge/robot.yaml",
                )

    # risks
    for risk in project.risks:
        rid = str(risk.get("id", ""))
        sev = _int(risk.get("sev"), 0)
        lik = _int(risk.get("lik"), 0)
        if not rid:
            add("S1", "error", "risk 缺 id", "forge/robot.yaml")
        if not (1 <= sev <= 5 and 1 <= lik <= 5):
            add("S10", "error", "risk %s 的 sev/lik 必须是 1-5 整数" % rid, "forge/robot.yaml")
        if sev * lik >= 12:
            if not str(risk.get("mitigation", "")).strip():
                add("S10", "error", "高风险 %s（%d×%d）缺 mitigation" % (rid, sev, lik), "forge/robot.yaml")
            if not str(risk.get("verify", "")).strip():
                add("S10", "error", "高风险 %s（%d×%d）缺 verify" % (rid, sev, lik), "forge/robot.yaml")

    # cost
    total = project.total_cost()
    target = project.budget
    if target > 0:
        if total > target * 1.5:
            add("S7", "error", "总价 ¥%.0f 超预算 ¥%.0f 的 150%%" % (total, target), "forge/robot.yaml")
        elif total > target * 1.15:
            add("S7", "warn", "总价 ¥%.0f 超预算 ¥%.0f 的 15%%（需在 decisions.md 说明）" % (total, target), "forge/robot.yaml")

    # ground truth files used by render
    for part in _list(_get(project.mech, "parts", default=[])):
        f = str(part.get("file", ""))
        if f and not (project.root / f).is_file():
            add("S3", "error", "mechanical.parts 引用的文件不存在：%s" % f, "forge/robot.yaml")

    # safety documentation
    battery = _get(d, "power", "battery", default={}) or {}
    chem = str(battery.get("chemistry", "none")).lower()
    triggers = []
    if chem not in ("", "none", "无"):
        triggers.append(("电池", "电池"))
    if re.search(r"220|市电|mains", str(_get(d, "power", "source", default="")), re.I):
        triggers.append(("市电", "市电"))
    if any(str(c.get("role", "")) == "actuator" for c in project.components):
        triggers.append(("运动", "夹|运动|堵转|限位"))
    text_feats = " ".join(str(f.get("name", "")) + str(f.get("how", "")) for f in features)
    if "激光" in text_feats:
        triggers.append(("激光", "激光"))
    if any(x in text_feats for x in ("麦克风", "录音", "摄像头", "相机")):
        triggers.append(("隐私", "隐私"))
    if triggers:
        safe = project.root / "docs" / "07-安全与隐私.md"
        body = read_text(safe) if safe.is_file() else ""
        for name, pattern in triggers:
            if body and not re.search(pattern, body):
                add("S11", "error", "项目涉及%s，docs/07-安全与隐私.md 没有对应章节" % name, "docs/07-安全与隐私.md")

    return issues