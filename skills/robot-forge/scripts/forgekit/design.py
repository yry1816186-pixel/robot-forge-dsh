"""Engineering design review: the numbers a human team would compute before buying.

This module does not pretend to be CAD/CAE. It performs the checks that catch
the expensive mistakes early: undersized torque, impossible battery runtime,
over-current wiring, thermal blind spots, budget drift, and missing actuator
ratings. Every unknown is reported as an assumption or a warning, never hidden.
"""

from __future__ import annotations

import math

from .consistency import _safety_text, _term_hit
from .intake import SAFETY_FLAGS
from .model import _get, _int, _num


G = 9.81
CRR = 0.03          # rubber wheel on smooth floor
DRIVE_MARGIN = 1.5  # acceleration + slope + friction margin
CONVERTER_EFF = 0.85


def _mech(project):
    return _get(project.data, "mechanical", default={}) or {}


def _motion(project):
    return _get(project.data, "motion", default={}) or {}


def _battery(project):
    return _get(project.data, "power", "battery", default={}) or {}


def _components(project):
    return [c for c in project.components if isinstance(c, dict)]


def _is_drive(component):
    text = " ".join(str(component.get(k, "")) for k in ("id", "role", "part", "note")).lower()
    return any(w in text for w in ("motor", "wheel", "drive", "电机", "轮", "履带", "推进", "servo", "舵机"))


def _is_actuator(component):
    return str(component.get("role", "")).lower() == "actuator" or _is_drive(component)


def _mass_kg(project):
    mech = _mech(project)
    mass = _num(mech.get("mass_kg"), 0.0)
    if mass > 0:
        return mass, "mechanical.mass_kg"
    grams = sum(_num(c.get("mass_g")) for c in _components(project))
    if grams > 0:
        return grams / 1000.0, "BOM mass_g 合计"
    return 0.0, "unknown"


def _wheel_radius_m(project):
    mech = _mech(project)
    motion = _motion(project)
    diameter = _num(mech.get("wheel_diameter_mm")) or _num(motion.get("wheel_diameter_mm"))
    return diameter / 2000.0 if diameter > 0 else 0.0


def _drive_count(project):
    mech = _mech(project)
    count = _int(mech.get("drive_count"), 0)
    if count > 0:
        return count
    return max(1, len([c for c in _components(project) if _is_drive(c) and str(c.get("role", "")).lower() == "actuator"]))


def _joint_count(project):
    return max(1, len([c for c in _components(project) if _is_actuator(c)]))


def _torque_review(project, findings):
    """Wheel torque or arm joint torque, only when the recipe has a geometry."""
    mech = _mech(project)
    motion = _motion(project)
    drive = [c for c in _components(project) if _is_actuator(c) and _is_drive(c)]
    rated = [_num(c.get("torque_kgcm")) for c in drive if _num(c.get("torque_kgcm")) > 0]
    out = {
        "required_kgcm": None,
        "available_kgcm": round(min(rated), 2) if rated else None,
        "margin": None,
        "assumption": None,
    }
    if _wheel_radius_m(project) > 0:
        mass, source = _mass_kg(project)
        payload = _num(mech.get("payload_kg"))
        slope = math.radians(max(0.0, _num(mech.get("max_slope_deg"))))
        if mass <= 0:
            # DSN-11 (missing mass) is the actionable finding; do not also emit
            # a torque finding that cannot produce a number.
            return out
        total_kg = mass + payload
        force = total_kg * G * (math.sin(slope) + CRR * math.cos(slope)) * DRIVE_MARGIN
        radius = _wheel_radius_m(project)
        count = _drive_count(project)
        required_nm = force * radius / count
        required_kgcm = required_nm * 10.197
        out["required_kgcm"] = round(required_kgcm, 2)
        out["assumption"] = "质量=%.2fkg（%s），轮径=%.0fmm，驱动=%d，坡度=%.0f°，滚阻=%.2f，余量=%.1f" % (
            total_kg, source, radius * 2000, count, math.degrees(slope), CRR, DRIVE_MARGIN)
        if rated:
            available = min(rated)
            out["available_kgcm"] = round(available, 2)
            out["margin"] = round(available / required_kgcm, 2)
            if available < required_kgcm:
                findings.append({"rule": "DSN-01", "level": "error", "file": "robot.yaml",
                                 "msg": "轮上扭矩不足：需要 %.2f kg·cm/轮，最弱驱动件仅 %.2f kg·cm（余量 %.2f）" % (
                                     required_kgcm, available, available / required_kgcm)})
            elif available < required_kgcm * 1.2:
                findings.append({"rule": "DSN-01", "level": "warning", "file": "robot.yaml",
                                 "msg": "扭矩余量偏小：需要 %.2f，现有 %.2f kg·cm；建议 ≥1.2 倍" % (required_kgcm, available)})
        else:
            findings.append({"rule": "DSN-02", "level": "warning", "file": "robot.yaml",
                             "msg": "驱动件没有 torque_kgcm，无法验证扭矩；补规格书数值（堵转扭矩的 1/3–1/2 作为连续值）"})
        return out
    reach = _num(mech.get("reach_m"))
    if reach > 0 and drive:
        payload = max(0.05, _num(mech.get("payload_kg"), 0.2))
        required_kgcm = payload * G * reach * 10.197 * 1.5
        out["required_kgcm"] = round(required_kgcm, 2)
        out["assumption"] = "臂展=%.2fm，负载=%.2fkg，含 1.5 倍动态余量" % (reach, payload)
        if rated:
            available = min(rated)
            out["available_kgcm"] = round(available, 2)
            out["margin"] = round(available / required_kgcm, 2)
            if available < required_kgcm:
                findings.append({"rule": "DSN-01", "level": "error", "file": "robot.yaml",
                                 "msg": "关节扭矩不足：最坏姿态需要 %.1f kg·cm，最弱舵机 %.1f kg·cm" % (required_kgcm, available)})
        else:
            findings.append({"rule": "DSN-02", "level": "warning", "file": "robot.yaml",
                             "msg": "舵机没有 torque_kgcm；按臂展×负载核算后补规格"})
    return out


def _power_review(project, findings):
    rows = project.power_rows()
    battery = _battery(project)
    runtime = project.battery_runtime_h()
    wh = None
    mah = _num(battery.get("mah"))
    cells = max(1, _int(battery.get("cells"), 1))
    if mah > 0:
        wh = mah / 1000.0 * cells * 3.7
    source_voltage = _num(_get(project.data, "power", "source_voltage_v"))
    if source_voltage <= 0:
        rails = [r for r in project.rails if str(r.get("id", "")) in ("vbat", "battery", "vin", "v12", "v24")]
        source_voltage = _num(rails[0].get("voltage")) if rails else 0.0
    peak_a = 0.0
    continuous_a = 0.0
    for row in rows:
        peak_a += row["voltage"] * row["peak"] / 1000.0 / max(1.0, source_voltage) / CONVERTER_EFF if source_voltage else 0.0
        continuous_a += row["voltage"] * row["typ"] / 1000.0 / max(1.0, source_voltage) / CONVERTER_EFF if source_voltage else 0.0
    c_rate = None
    if mah > 0 and continuous_a > 0:
        c_rate = continuous_a / (mah / 1000.0)
    target_h = _num(_get(project.data, "behavior", "runtime_target_h"), 0.0)
    if runtime is not None:
        if target_h > 0 and runtime < target_h * 0.8:
            findings.append({"rule": "DSN-03", "level": "error", "file": "robot.yaml",
                             "msg": "续航不足：估算 %.1fh，目标 %.1fh（差 %.0f%%）；加电池/降功耗/减功能" % (
                                 runtime, target_h, (1 - runtime / target_h) * 100)})
    if c_rate is not None:
        chemistry = str(battery.get("chemistry", "")).lower()
        limit = 1.0 if "li-ion" in chemistry or "18650" in chemistry else 3.0
        if c_rate > limit * 2:
            findings.append({"rule": "DSN-04", "level": "error", "file": "robot.yaml",
                             "msg": "持续放电 %.1fC 超过电芯能力（%s 建议 ≤%.1fC 连续）；换高倍率电芯/加并联/限功率" % (
                                 c_rate, chemistry or "未知", limit)})
        elif c_rate > limit:
            findings.append({"rule": "DSN-04", "level": "warning", "file": "robot.yaml",
                             "msg": "持续放电 %.1fC 接近/超过建议值 %.1fC；核对电芯规格与温升" % (c_rate, limit)})
    for row in rows:
        if row["peak_pct"] > 100:
            findings.append({"rule": "DSN-05", "level": "error", "file": "robot.yaml",
                             "msg": "电源轨 %s 峰值 %.0f%% 超过额定；换更大降压/分路" % (row["id"], row["peak_pct"])})
    return {
        "source_voltage_v": round(source_voltage, 2) if source_voltage else None,
        "rails": [
            {
                "id": row["id"], "voltage": row["voltage"], "max_ma": row["max_ma"],
                "typical_ma": row["typ"], "peak_ma": row["peak"],
                "typical_pct": round(row["typ_pct"], 1), "peak_pct": round(row["peak_pct"], 1),
                "status": row["status"],
            }
            for row in rows
        ],
        "battery_wh": round(wh, 1) if wh else None,
        "runtime_h": round(runtime, 2) if runtime is not None else None,
        "runtime_target_h": target_h or None,
        "continuous_current_a": round(continuous_a, 2) if continuous_a else None,
        "peak_current_a": round(peak_a, 2) if peak_a else None,
        "c_rate": round(c_rate, 2) if c_rate is not None else None,
        "assumption": "转换效率 %.0f%%，续航系数 0.85；峰值按全部负载同时最坏估算（实际通常更低）" % (CONVERTER_EFF * 100),
    }


# (continuous amps, AWG, copper mm^2) for short runs at ~30 K rise.
AWG_TABLE = [(5, 20, 0.52), (10, 18, 0.82), (15, 16, 1.31), (25, 14, 2.08), (35, 12, 3.31), (50, 10, 5.26), (70, 8, 8.37)]


def _wire(current_a):
    for limit, awg, mm2 in AWG_TABLE:
        if current_a <= limit:
            return {"awg": awg, "mm2": mm2}
    return {"awg": 6, "mm2": 13.3}


def _mechanical_review(project, findings):
    mech = _mech(project)
    motion = _motion(project)
    mass, source = _mass_kg(project)
    payload = _num(mech.get("payload_kg"))
    out = {
        "mass_kg": round(mass, 2) if mass else None,
        "mass_source": source,
        "payload_kg": payload or None,
        "wheel_diameter_mm": _num(mech.get("wheel_diameter_mm")) or _num(motion.get("wheel_diameter_mm")) or None,
        "wheel_base_mm": _num(mech.get("wheel_base_mm")) or _num(motion.get("wheel_base_mm")) or None,
        "max_linear_mps": _num(motion.get("max_linear_mps")) or _num(_get(project.data, "mechanical", "limits", "max_linear_mps")) or None,
        "reach_m": _num(mech.get("reach_m")) or None,
        "drive_count": _drive_count(project),
    }
    if mass > 0 and payload > 0 and payload > mass * 1.5:
        findings.append({"rule": "DSN-08", "level": "warning", "file": "robot.yaml",
                         "msg": "负载 %.1fkg 超过自重 %.1fkg 的 1.5 倍；结构/驱动/制动都要重算" % (payload, mass)})
    if motion and mass > 0:
        accel = 0.5
        force = mass * accel + mass * G * CRR
        out["traction_force_n"] = round(force, 1)
    return out


def _thermal_review(project, power, findings):
    mech = _mech(project)
    volume_l = _num(mech.get("enclosure_l"))
    loss_w = 0.0
    for c in _components(project):
        if not _is_actuator(c):
            continue
        current = _num(c.get("rated_current_ma")) or _num(c.get("stall_current_ma")) / 3.0
        voltage = _num(_get(project.data, "power", "source_voltage_v"), 12.0)
        loss_w += current / 1000.0 * voltage * 0.3
    out = {
        "estimated_loss_w": round(loss_w, 1) if loss_w else None,
        "enclosure_l": volume_l or None,
        "verdict": "unknown",
        "assumption": "按执行器额定电流 × 电压 × 30% 损耗估算；不含主控/降压损耗",
    }
    if loss_w <= 0:
        findings.append({"rule": "DSN-09", "level": "info", "file": "robot.yaml",
                         "msg": "缺少 rated_current_ma/stall_current_ma，无法估算发热；封闭外壳需做 10 分钟温升测试"})
    elif volume_l > 0:
        density = loss_w / volume_l
        out["verdict"] = "hot" if density > 10 else "ok"
        if density > 10:
            findings.append({"rule": "DSN-09", "level": "warning", "file": "robot.yaml",
                             "msg": "封闭空间散热密度 %.1fW/L 偏高；加通风/金属导热/降额，并做温升测试" % density})
    return out


def _cost_review(project, findings):
    total = project.total_cost()
    budget = project.budget
    pct = (total / budget * 100.0) if budget else 0.0
    priced = [c for c in _components(project) if _num(c.get("price")) > 0]
    with_source = [c for c in priced if str(c.get("source", "")).strip()]
    drivers = []
    for c in sorted(priced, key=lambda x: -_num(x.get("price")) * max(1, _int(x.get("qty"), 1)))[:5]:
        drivers.append({
            "id": str(c.get("id")), "part": str(c.get("part")),
            "line_cny": round(_num(c.get("price")) * max(1, _int(c.get("qty"), 1)), 1),
        })
    if budget and total > budget * 1.5:
        findings.append({"rule": "DSN-06", "level": "error", "file": "robot.yaml",
                         "msg": "总价 %d 元超过预算 150%%（%d 元）；必须减配或提高预算后再冻结 BOM" % (total, budget)})
    elif budget and total > budget * 1.15:
        findings.append({"rule": "DSN-06", "level": "warning", "file": "robot.yaml",
                         "msg": "总价 %d 元超过预算 15%%（%d 元）；列出要砍的 nice-to-have" % (total, budget)})
    if priced and len(with_source) < len(priced):
        findings.append({"rule": "DSN-07", "level": "warning", "file": "robot.yaml",
                         "msg": "%d/%d 个元件没有采购链接/来源；开源可复现要求 source 可点开" % (
                             len(priced) - len(with_source), len(priced))})
    return {
        "total_cny": total,
        "budget_cny": budget,
        "used_pct": round(pct, 1),
        "shipping_cny": _num(_get(project.data, "cost", "shipping_cny")),
        "quote_date": str(_get(project.data, "cost", "quote_date", default="") or ""),
        "top_drivers": drivers,
        "price_coverage": "%d/%d" % (len(with_source), len(priced)),
        "needed_cut_cny": max(0, total - int(budget * 1.15)) if budget else 0,
    }


def _safety_review(project):
    # Use the same user-facing text the consistency gate uses. Scanning the raw
    # manifest would match English keys/substrings ("happy" contains "app")
    # and raise false privacy/network flags.
    text = _safety_text(project)
    flags = []
    for terms, key, title, requirement in SAFETY_FLAGS:
        if _term_hit(terms, text):
            flags.append({"key": key, "title": title, "requirement": requirement})
    return flags


DESIGN_CHECK_RULES = {"DSN-01", "DSN-02", "DSN-03", "DSN-04", "DSN-09", "DSN-11"}


def design_issues(project):
    """Findings that check.py does not already produce (avoid duplicate noise)."""
    findings = []
    _torque_review(project, findings)
    _power_review(project, findings)
    _mechanical_review(project, findings)
    _thermal_review(project, None, findings)
    _cost_review(project, findings)
    return [f for f in findings if f["rule"] in DESIGN_CHECK_RULES]


def design_payload(project):
    findings = []
    torque = _torque_review(project, findings)
    power = _power_review(project, findings)
    mech = _mechanical_review(project, findings)
    thermal = _thermal_review(project, power, findings)
    cost = _cost_review(project, findings)
    battery = _battery(project)
    if not battery or str(battery.get("chemistry", "none")).lower() in ("", "none", "无"):
        findings.append({"rule": "DSN-10", "level": "info", "file": "robot.yaml",
                         "msg": "没有电池参数：若用市电/适配器，确认断电与隔离；若用电池，补 chemistry/mah/cells"})
    if mech["mass_kg"] is None:
        findings.append({"rule": "DSN-11", "level": "warning", "file": "robot.yaml",
                         "msg": "缺少质量数据：加 mechanical.mass_kg 或给 BOM 元件 mass_g，否则扭矩/制动无法核算"})
    wire = None
    if power.get("peak_current_a"):
        size = _wire(power["peak_current_a"])
        wire = {
            "battery_awg": size["awg"],
            "battery_mm2": size["mm2"],
            "note": "按峰值电流、30cm 以内、温升 30K 粗算；长线/高温再降额，连接器额定值单独核对",
        }
    errors = [f for f in findings if f["level"] == "error"]
    warnings = [f for f in findings if f["level"] == "warning"]
    return {
        "ok": not errors,
        "project": str(project.root),
        "torque": torque,
        "power": power,
        "mechanical": mech,
        "thermal": thermal,
        "cost": cost,
        "safety": _safety_review(project),
        "wire": wire,
        "findings": findings,
        "stats": {"errors": len(errors), "warnings": len(warnings), "infos": len(findings) - len(errors) - len(warnings)},
    }


def render_text(payload):
    lines = [
        "设计核算：%s" % ("✅ 无阻断" if payload["ok"] else "⛔ 有阻断项"),
        "扭矩：需要 %s kg·cm ｜ 现有 %s ｜ 余量 %s" % (
            payload["torque"]["required_kgcm"], payload["torque"]["available_kgcm"], payload["torque"]["margin"]),
        "电源：%s ｜ 续航 %s h ｜ 持续 %s A / 峰值 %s A ｜ %s C" % (
            payload["power"]["source_voltage_v"], payload["power"]["runtime_h"],
            payload["power"]["continuous_current_a"], payload["power"]["peak_current_a"], payload["power"]["c_rate"]),
        "成本：%d / %d 元（%s%%）｜ 价格覆盖 %s" % (
            payload["cost"]["total_cny"], payload["cost"]["budget_cny"], payload["cost"]["used_pct"], payload["cost"]["price_coverage"]),
        "质量：%s kg（%s）｜ 驱动 %s ｜ 轮径 %s mm" % (
            payload["mechanical"]["mass_kg"], payload["mechanical"]["mass_source"], payload["mechanical"]["drive_count"], payload["mechanical"]["wheel_diameter_mm"]),
    ]
    if payload["wire"]:
        lines.append("线径：电池主线 AWG%s（约 %s mm²）" % (payload["wire"]["battery_awg"], payload["wire"]["battery_mm2"]))
    for f in payload["findings"]:
        mark = {"error": "✗", "warning": "!", "info": "i"}.get(f["level"], "-")
        lines.append("%s [%s] %s" % (mark, f["rule"], f["msg"]))
    for k in ("torque", "power", "thermal"):
        assumption = payload[k].get("assumption")
        if assumption:
            lines.append("假设：%s" % assumption)
    if payload["safety"]:
        lines.append("安全旗标：" + "、".join(f["title"] for f in payload["safety"]))
    return "\n".join(lines)
