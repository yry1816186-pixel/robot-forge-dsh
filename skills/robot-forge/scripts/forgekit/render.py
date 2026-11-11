"""Deterministic rendering: markdown blocks, BOM CSV and SVG diagrams."""

from __future__ import annotations

import re
from pathlib import Path

from .model import CATEGORY, ICONS, _get, _int, _list, _num
from .util import read_text, write_text

BLOCK_BEGIN = "<!-- forge:begin %s -->"
BLOCK_END = "<!-- forge:end %s -->"
FENCE = chr(96) * 3

BUS_COLOR = {
    "i2c": "#2563eb",
    "spi": "#7c3aed",
    "uart": "#0891b2",
    "i2s": "#059669",
    "bus-servo": "#d97706",
    "pwm": "#db2777",
    "can": "#4b5563",
    "onewire": "#0d9488",
    "adc": "#9333ea",
}


def _md(value):
    return str(value if value is not None else "").replace("|", "\\|").replace("\n", " ").strip()


def _money(v):
    return "%.2f" % _num(v)


def _wrap(text, max_units=34):
    out, line, units = [], "", 0
    for ch in str(text):
        wide = ch >= "\u3400" and ch <= "\u9fff"
        w = 2 if wide or ch in "，。！？：；、（）【】“”" else 1
        if units + w > max_units and line:
            out.append(line)
            line, units = "", 0
        line += ch
        units += w
    if line:
        out.append(line)
    return out or [""]


def _esc(s):
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


class RenderPlan(object):
    def __init__(self):
        self.files = {}
        self.problems = []
        self.blocks = {}

    def add_block(self, path, name, content):
        rel = str(path)
        target = Path(path)
        if not target.is_file():
            self.problems.append("%s 不存在" % rel)
            return
        if rel not in self.files:
            self.files[rel] = read_text(target)
        new, ok = _replace_block(self.files[rel], name, content)
        if not ok:
            self.problems.append("%s 缺少成对标记 forge:begin/end %s" % (rel, name))
            return
        self.files[rel] = new
        self.blocks.setdefault(rel, []).append(name)


def _replace_block(text, name, content):
    begin = BLOCK_BEGIN % name
    end = BLOCK_END % name
    i = text.find(begin)
    j = text.find(end)
    if i < 0 or j < 0 or j < i:
        return text, False
    head = text[: i + len(begin)]
    tail = text[j:]
    return head + "\n" + content.strip("\n") + "\n" + tail, True


# -- markdown fragments -------------------------------------------------------


def bom_table(project):
    rows = project.bom_rows()
    if not rows:
        return "_还没有物料。先在 forge/robot.yaml 的 components 里写清楚。_"
    lines = ["| 编号 | 类别 | 型号 | 数量 | 单价(¥) | 小计(¥) | 采购渠道 |", "|---:|---|---|---:|---:|---:|---|"]
    for r in rows:
        lines.append(
            "| %d | %s | %s | %d | %s | %s | %s |"
            % (r["no"], r["category"], _md(r["part"]), r["qty"], _money(r["unit"]), _money(r["subtotal"]), _md(r["source"]) or "—")
        )
    return "\n".join(lines)


def bom_total(project):
    total = project.total_cost()
    target = project.budget
    shipping = _num(_get(project.data, "cost", "shipping_cny", default=0))
    if target <= 0:
        return "**合计 ¥%s**（含运费 ¥%s）；未设置预算上限。" % (_money(total), _money(shipping))
    diff = (total / target - 1.0) * 100 if target else 0
    if abs(diff) < 0.05:
        verdict = "正好在预算内"
    elif diff > 0:
        verdict = "超预算 %.1f%%" % diff
    else:
        verdict = "低于预算 %.1f%%" % abs(diff)
    return "**合计 ¥%s**（含运费 ¥%s），目标 ¥%s，%s。" % (_money(total), _money(shipping), _money(target), verdict)


def bus_table(project):
    rows = project.bus_rows()
    if not rows:
        return "_没有总线（纯 GPIO 直连或纯软件项目）。_"
    lines = ["| 总线 | 类型 | 引脚 | 挂载元件 | 备注 |", "|---|---|---|---|---|"]
    for r in rows:
        lines.append("| %s | %s | %s | %s | %s |" % (_md(r["id"]), _md(r["type"]), _md(r["pins"]), _md(r["members"]), _md(r["note"])))
    return "\n".join(lines)


def pinout(project):
    rows = project.pin_rows()
    if not rows:
        return "_没有引脚分配。_"
    lines = ["| 总线/直连 | 类型 | 信号 | GPIO | 连接到 | 备注 |", "|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(
            "| %s | %s | %s | %s | %s | %s |"
            % (_md(r["bus"]), _md(r["type"]), _md(r["signal"]), _md(r["pin"]), _md(r["connect"]), _md(r["note"]))
        )
    return "\n".join(lines)


def power_table(project):
    rows = project.power_rows()
    if not rows:
        return "_没有电源预算。_"
    lines = [
        "| 电源轨 | 电压(V) | 上限(mA) | 典型(mA) | 峰值(mA) | 典型占比 | 峰值占比 | 状态 |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for r in rows:
        lines.append(
            "| %s | %.1f | %.0f | %.0f | %.0f | %.0f%% | %.0f%% | %s |"
            % (r["id"], r["voltage"], r["max_ma"], r["typ"], r["peak"], r["typ_pct"], r["peak_pct"], r["status"])
        )
    runtime = project.battery_runtime_h()
    if runtime is not None:
        lines.append("")
        lines.append("电池典型续航估算：**约 %.1f 小时**（按 85%% 可用电量）。" % runtime)
    return "\n".join(lines)


def status_matrix(project):
    rows = project.status_rows()
    if not rows:
        return "_还没有 must 需求。_"
    counts = {}
    for r in rows:
        counts[r["icon"]] = counts.get(r["icon"], 0) + 1
    summary = " ".join("%s %d" % (k, v) for k, v in sorted(counts.items()))
    lines = ["> 状态：%s　（✅ 已跑通/人工确认　🟡 仅仿真　⚪ 待验证　⛔ 已知问题）" % summary, ""]
    lines += ["| 能力（must 需求） | 状态 | 依据 |", "|---|---|---|"]
    for r in rows:
        lines.append("| %s %s | %s | %s |" % (_md(r["id"]), _md(r["text"]), r["icon"], _md(r["evidence"]) or "—"))
    return "\n".join(lines)


def req_evidence(project):
    reqs = project.requirements
    if not reqs:
        return "_还没有需求。_"
    order = {"must": 0, "should": 1, "nice": 2}
    reqs = sorted(reqs, key=lambda r: (order.get(str(r.get("priority", "must")), 9), str(r.get("id"))))
    lines = ["| 需求 | 优先级 | 状态 | 证据级别 | 最近证据 | 验证方式 |", "|---|---|---|---|---|---|"]
    for req in reqs:
        level, ev = project.requirement_status(req)
        latest = ev[0] if ev else {}
        lines.append(
            "| %s %s | %s | %s | %s | %s | %s |"
            % (
                _md(req.get("id")),
                _md(req.get("text")),
                _md(req.get("priority", "must")),
                ICONS.get(level, "⚪"),
                level,
                _md(latest.get("claim", "")) or "—",
                _md(req.get("verify", "")) or "—",
            )
        )
    return "\n".join(lines)


def evidence_log(project):
    items = project.evidence()
    if not items:
        return "_还没有证据。跑一次 python tools/forge.py verify。_"
    lines = ["| 编号 | 需求 | 断言 | 级别 | 命令 | 退出码 | 时间 |", "|---|---|---|---|---|---:|---|"]
    for item in items:
        lines.append(
            "| %s | %s | %s | %s | %s | %s | %s |"
            % (
                _md(item.get("id")),
                _md(item.get("req")),
                _md(item.get("claim")),
                _md(item.get("level")),
                _md(item.get("command")) or "—",
                _md(item.get("exit")),
                _md(item.get("at")),
            )
        )
    return "\n".join(lines)


def unverified(project):
    lines = []
    for req in project.requirements:
        level, _ev = project.requirement_status(req)
        if level in ("none", "simulated", "assumed") and str(req.get("priority", "must")) == "must":
            lines.append("- %s %s（当前：%s）" % (req.get("id"), req.get("text"), level))
    if not lines:
        return "无。所有 must 需求都有人工确认或实测证据。"
    return "\n".join(lines)


def assembly_parts(project):
    parts = _list(_get(project.mech, "parts", default=[]))
    fasteners = _list(_get(project.mech, "fasteners", default=[]))
    if not parts and not fasteners:
        return "_还没有结构件清单。_"
    lines = ["| 零件 | 文件 | 数量 | 材料/工艺 | 说明 |", "|---|---|---:|---|---|"]
    for part in parts:
        lines.append(
            "| %s | %s | %d | %s | %s |"
            % (
                _md(part.get("id")),
                _md(part.get("file")),
                max(1, _int(part.get("qty"), 1)),
                _md(part.get("print", part.get("material", ""))) or "—",
                _md(part.get("note", "")),
            )
        )
    for f in fasteners:
        lines.append("| %s | 标准件 | %d | 五金 | — |" % (_md(f.get("spec")), max(1, _int(f.get("qty"), 1))))
    return "\n".join(lines)


# -- SVG ----------------------------------------------------------------------

_SVG_HEAD = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d" '
    'font-family="Microsoft YaHei, PingFang SC, Noto Sans SC, sans-serif">\n'
    "<style>text{fill:#1f2937}.t{font-weight:600}.s{fill:#6b7280}</style>\n"
    '<defs><marker id="a" markerWidth="9" markerHeight="9" refX="8" refY="4.5" orient="auto">'
    '<path d="M0,0 L9,4.5 L0,9 z" fill="#6b7280"/></marker></defs>\n'
    '<rect width="100%%" height="100%%" fill="#ffffff"/>\n'
)


def _text(x, y, s, size=13, weight="normal", anchor="start", fill="#1f2937"):
    return '<text x="%d" y="%d" font-size="%d" font-weight="%s" text-anchor="%s" fill="%s">%s</text>\n' % (
        x,
        y,
        size,
        weight,
        anchor,
        fill,
        _esc(s),
    )


def _box(x, y, w, h, title, lines, fill="#f8fafc", stroke="#cbd5e1", title_color="#111827"):
    out = '<rect x="%d" y="%d" width="%d" height="%d" rx="10" fill="%s" stroke="%s" stroke-width="1.3"/>\n' % (
        x,
        y,
        w,
        h,
        fill,
        stroke,
    )
    out += _text(x + 12, y + 22, title, 13, "600", fill=title_color)
    for i, line in enumerate(lines[:3]):
        out += _text(x + 12, y + 41 + i * 16, line, 11.5, fill="#4b5563")
    return out


def architecture_svg(project):
    width = 920
    bands = _layers(project)
    heights = []
    for _label, items in bands:
        rows = max(1, (len(items) + 2) // 3)
        heights.append(max(74, 20 + rows * 68))
    height = 40 + sum(heights) + 12 * (len(bands) - 1) + 30
    out = [_SVG_HEAD % (width, height, width, height)]
    out.append(_text(24, 28, "%s · 系统分层" % project.name, 16, "600"))
    y = 44
    for idx, ((label, items), h) in enumerate(zip(bands, heights)):
        out.append('<rect x="20" y="%d" width="880" height="%d" rx="14" fill="#f1f5f9"/>\n' % (y, h))
        out.append(_box(32, y + 10, 96, h - 20, label, [], fill="#ffffff"))
        for i, item in enumerate(items):
            col = i % 3
            row = i // 3
            bx = 148 + col * 252
            by = y + 12 + row * 68
            out.append(_box(bx, by, 236, 56, item["title"], item["lines"], fill=item.get("fill", "#ffffff")))
        if idx != len(bands) - 1:
            out.append(
                '<line x1="460" y1="%d" x2="460" y2="%d" stroke="#6b7280" stroke-width="1.5" marker-end="url(#a)"/>\n'
                % (y + h - 1, y + h + 11)
            )
        y += h + 12
    out.append("</svg>\n")
    return "".join(out)


def _human_interface(project):
    labels = []
    roles = {str(c.get("role", "")).lower() for c in project.components}
    ids = " ".join(str(c.get("id", "")).lower() for c in project.components)
    app = _get(project.data, "software", "app", default="none")
    if app and str(app).lower() not in ("none", "无", ""):
        labels.append("App")
    if "audio" in roles:
        labels.append("语音")
    if "display" in roles:
        labels.append("屏幕")
    if any(word in ids for word in ("touch", "button", "key", "btn", "switch")):
        labels.append("按键/触摸")
    return " / ".join(labels[:3]) or "上位机"


def _layers(project):
    bands = []
    env = str(_get(project.data, "wish", "environment", default="") or "现场")
    app = _get(project.data, "software", "app", default="none")
    if app and str(app).lower() not in ("none", "无", ""):
        bands.append(
            (
                "用户/App",
                [
                    {"title": "App / 前端", "lines": _wrap(str(app), 26)},
                    {"title": "使用环境", "lines": _wrap(env, 26)},
                ],
            )
        )
    else:
        bands.append(
            (
                "用户/环境",
                [
                    {"title": "人机接口", "lines": _wrap(_human_interface(project), 26)},
                    {"title": "使用环境", "lines": _wrap(env, 26)},
                ],
            )
        )
    host = _get(project.data, "architecture", "host", default=None) or _get(project.data, "software", "host", default=None)
    if host and "software" in project.domains:
        items = [
            {
                "title": "主机软件",
                "lines": _wrap("%s · %s" % (host.get("language", "python"), host.get("entry", "software/robotd/main.py")), 26),
                "fill": "#eff6ff",
            }
        ]
        for f in project.features:
            if f.get("software_only"):
                items.append({"title": str(f.get("name", "能力")), "lines": _wrap(str(f.get("how", "")), 26)})
        bands.append(("主机", items[:4]))
    comms = _get(project.data, "architecture", "comms", default="USB 串口")
    bands.append(("连接", [{"title": "通信", "lines": _wrap(str(comms), 26)}]))
    if "firmware" in project.domains:
        mcu = project.mcu()
        items = [
            {
                "title": "固件",
                "lines": _wrap(str(mcu.get("part", "主控")) if mcu else "待定主控", 26),
                "fill": "#f0fdf4",
            }
        ]
        for f in project.features:
            refs = [str(x) for x in _list(f.get("components"))]
            if mcu and str(mcu.get("id")) in refs:
                items.append({"title": str(f.get("name", "能力")), "lines": _wrap(str(f.get("how", "")), 26)})
        bands.append(("固件", items[:4]))
    if project.components:
        items = []
        groups = {}
        for c in project.components:
            key = CATEGORY.get(str(c.get("role", "other")).lower(), "其他")
            groups.setdefault(key, []).append(str(c.get("part", "")))
        for key, parts in groups.items():
            items.append({"title": key, "lines": _wrap("、".join(parts), 26), "fill": "#fefce8"})
        bands.append(("硬件", items[:6]))
    return bands


def wiring_svg(project):
    rows = project.pin_rows()
    buses = project.buses
    comps = project.components
    width = 980
    left_h = max(160, 74 + len(rows) * 26)
    mid_total = max(120, len(buses) * 78)
    height = max(left_h, mid_total, 160) + 90
    out = [_SVG_HEAD % (width, height, width, height)]
    out.append(_text(24, 28, "%s · 接线关系" % project.name, 16, "600"))
    out.append('<rect x="30" y="46" width="250" height="%d" rx="12" fill="#f8fafc" stroke="#94a3b8"/>\n' % (left_h - 20))
    out.append(_text(46, 70, "主控", 14, "600"))
    mcu = project.mcu()
    out.append(_text(46, 90, str(mcu.get("part", "MCU")) if mcu else "MCU", 11, fill="#6b7280"))

    row_y = {}
    for i, row in enumerate(rows):
        y = 112 + i * 26
        row_y["%s|%s" % (row["bus"], row["signal"])] = y
        out.append(_text(46, y, "%s %s" % (row["pin"], row["signal"]), 11.5))
        out.append(_text(130, y, row["type"], 10, fill="#94a3b8"))

    bus_y = {}
    for i, bus in enumerate(buses):
        by = 60 + i * 78
        bus_y[str(bus.get("id"))] = by
        color = BUS_COLOR.get(str(bus.get("type")), "#6b7280")
        out.append(
            _box(
                340,
                by,
                180,
                56,
                "%s · %s" % (bus.get("id"), bus.get("type")),
                [],
                fill="#ffffff",
                stroke=color,
                title_color=color,
            )
        )
        for signal in (bus.get("pins") or {}):
            key = "%s|%s" % (bus.get("id"), signal)
            if key in row_y:
                out.append(
                    '<path d="M280,%d C310,%d 310,%d 340,%d" fill="none" stroke="%s" stroke-width="1.4"/>\n'
                    % (row_y[key], row_y[key], by + 28, by + 28, color)
                )

    comp_y = {}
    y = 60
    for c in comps:
        cid = str(c.get("id"))
        bus_ref = str(c.get("bus", "") or "")
        if not bus_ref:
            continue
        comp_y[cid] = y
        out.append(_box(620, y, 320, 52, "%s · %s" % (cid, c.get("part")), [], fill="#ffffff", stroke="#cbd5e1"))
        if bus_ref in bus_y:
            out.append(
                '<path d="M520,%d C560,%d 580,%d 620,%d" fill="none" stroke="#6b7280" stroke-width="1.4" marker-end="url(#a)"/>\n'
                % (bus_y[bus_ref] + 28, bus_y[bus_ref] + 28, y + 26, y + 26)
            )
        y += 64

    for p in project.pins:
        pid = str(p.get("id"))
        target = str(p.get("connect", ""))
        row = next((r for r in rows if r["bus"] == pid), None)
        if row and target in comp_y:
            y0 = row_y.get("%s|%s" % (pid, row["signal"]))
            if y0:
                out.append(
                    '<path d="M280,%d C420,%d 500,%d 620,%d" fill="none" stroke="#6b7280" stroke-width="1.4" marker-end="url(#a)"/>\n'
                    % (y0, y0, comp_y[target] + 26, comp_y[target] + 26)
                )
    if not rows:
        out.append(_text(360, 120, "没有引脚分配（或纯软件项目）", 13, fill="#6b7280"))
    out.append("</svg>\n")
    return "".join(out)


def assembly_svg(project):
    parts = _list(_get(project.mech, "parts", default=[]))
    width = 820
    height = max(220, 70 + max(1, len(parts)) * 64 + 60)
    out = [_SVG_HEAD % (width, height, width, height)]
    out.append(_text(24, 28, "%s · 结构件分解" % project.name, 16, "600"))
    y = 60
    for i, part in enumerate(parts):
        x = 60 + (i % 3) * 18
        out.append('<rect x="%d" y="%d" width="300" height="48" rx="8" fill="#eef2ff" stroke="#818cf8"/>\n' % (x, y))
        out.append(_text(x + 14, y + 20, "%s ×%d" % (part.get("id"), max(1, _int(part.get("qty"), 1))), 13, "600"))
        out.append(
            _text(
                x + 14,
                y + 38,
                "%s · %s" % (part.get("print", part.get("material", "")), part.get("note", "")),
                10.5,
                fill="#4b5563",
            )
        )
        out.append(_text(400, y + 28, str(part.get("file", "")), 11.5, fill="#6b7280"))
        y += 60
    if not parts:
        out.append(_text(60, 100, "还没有结构件。", 13, fill="#6b7280"))
    out.append("</svg>\n")
    return "".join(out)


def arch_mermaid(project):
    lines = ["graph TD", '  user["用户"]']
    host = _get(project.data, "architecture", "host", default=None) or _get(project.data, "software", "host", default=None)
    if host and "software" in project.domains:
        lines.append('  host["主机软件<br/>%s"]' % _mm(str(host.get("entry", "software/robotd/main.py"))))
        lines.append("  user --> host")
        tail = "host"
    else:
        tail = "user"
    if "firmware" in project.domains:
        mcu = project.mcu()
        lines.append('  fw["固件<br/>%s"]' % _mm(str(mcu.get("part", "MCU")) if mcu else "MCU"))
        lines.append("  %s --> fw" % tail)
        tail = "fw"
    for c in project.components:
        cid = "c_" + re.sub(r"[^A-Za-z0-9_]", "_", str(c.get("id")))
        lines.append('  %s["%s<br/>%s"]' % (cid, _mm(str(c.get("id"))), _mm(str(c.get("part")))))
        bus = str(c.get("bus", "") or "")
        if bus:
            lines.append('  %s -->|"%s"| %s' % (tail, _mm(bus), cid))
        else:
            lines.append("  %s --> %s" % (tail, cid))
    return "\n".join(lines)


def _mm(s):
    return str(s).replace('"', "'").replace("\n", " ")[:60]


# -- render plan --------------------------------------------------------------


def render_plan(project):
    plan = RenderPlan()
    if project.load_error:
        plan.problems.append(project.load_error)
        return plan
    root = project.root
    plan.add_block(root / "README.md", "status-matrix", status_matrix(project))
    plan.add_block(root / "docs" / "00-总览.md", "arch-graph", FENCE + "mermaid\n" + arch_mermaid(project) + "\n" + FENCE)
    plan.add_block(root / "docs" / "01-物料清单.md", "bom-table", bom_table(project))
    plan.add_block(root / "docs" / "01-物料清单.md", "bom-total", bom_total(project))
    plan.add_block(root / "docs" / "02-组装指南.md", "assembly-parts", assembly_parts(project))
    plan.add_block(root / "docs" / "03-接线表.md", "bus-table", bus_table(project))
    plan.add_block(root / "docs" / "03-接线表.md", "pinout", pinout(project))
    plan.add_block(root / "docs" / "03-接线表.md", "power-table", power_table(project))
    plan.add_block(root / "docs" / "09-验证报告.md", "req-evidence", req_evidence(project))
    plan.add_block(root / "docs" / "09-验证报告.md", "evidence-log", evidence_log(project))
    plan.add_block(root / "docs" / "09-验证报告.md", "unverified-list", unverified(project))

    plan.files[str(root / "hardware" / "bom.csv")] = _bom_csv(project)
    plan.files[str(root / "diagrams" / "architecture.svg")] = architecture_svg(project)
    plan.files[str(root / "diagrams" / "wiring.svg")] = wiring_svg(project)
    plan.files[str(root / "diagrams" / "assembly.svg")] = assembly_svg(project)
    return plan


def _bom_csv(project):
    rows = project.bom_rows()
    out = ["no,category,part,qty,unit_cny,subtotal_cny,source,note"]
    for r in rows:
        out.append(
            "%d,%s,%s,%d,%.2f,%.2f,%s,%s"
            % (
                r["no"],
                _csv(r["category"]),
                _csv(r["part"]),
                r["qty"],
                r["unit"],
                r["subtotal"],
                _csv(r["source"]),
                _csv(r["note"]),
            )
        )
    out.append("合计,,,%d,,%.2f,," % (sum(r["qty"] for r in rows), sum(r["subtotal"] for r in rows)))
    return "\n".join(out) + "\n"


def _csv(s):
    s = str(s or "")
    if any(ch in s for ch in ',"\n'):
        return '"' + s.replace('"', '""') + '"'
    return s


def render(project, write=True):
    plan = render_plan(project)
    results = []
    for path, content in plan.files.items():
        target = Path(path)
        old = read_text(target) if target.is_file() else None
        if old == content:
            results.append((path, "current"))
            continue
        if write:
            write_text(target, content)
            results.append((path, "written" if old is not None else "created"))
        else:
            results.append((path, "stale" if old is not None else "created"))
    for problem in plan.problems:
        results.append((problem, "problem"))
    return results