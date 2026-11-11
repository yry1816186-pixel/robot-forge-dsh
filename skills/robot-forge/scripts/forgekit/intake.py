"""Wish intake: turn one sentence into a decision-complete robot brief.

The goal is not to chat. It is to produce, in one pass, the smallest set of
decisions that lets the build start: archetype, budget, domains, must/nice
requirements, safety flags, and at most three questions that actually change
the design. Everything else is filled with a declared default so a beginner is
never blocked by an empty page.

No network access and no third-party packages: this module must run inside the
vendored project copy too.
"""

from __future__ import annotations

import json
import re
from pathlib import Path


# --- archetype recipes -----------------------------------------------------
# Twelve reachable families. Each entry is deliberately concrete: a weak model
# can copy these defaults, a strong model can deviate with a written reason.
ARCHETYPES = [
    {
        "id": "wheel-rover",
        "name": "差速轮式小车 / 巡检底盘",
        "aliases": ["小车", "轮式", "巡检", "agv", "底盘", "差速", "避障", "slam", "ros", "遥控车", "搬运车", " rover", "car"],
        "one_liner": "两轮差速 + 万向轮，超声/ToF 避障，串口协议，主机侧可接 ROS2 或遥测。",
        "blueprint": "wheel-rover",
        "domains": ["hardware", "firmware", "software", "sim"],
        "budget": 300,
        "actuation": "双直流减速电机 + TB6612/DRV8833",
        "power": "2S 18650 7.4V，5V/6V 双降压",
        "mcu": "ESP32-S3",
        "parts": ["ESP32-S3 开发板", "TB6612FNG", "N20/TT 减速电机 ×2", "18650 ×2 + 电池盒", "VL53L0X 或 HC-SR04", "MPU6050", "OLED 0.96\"", "降压模块"],
        "buses": ["i2c", "uart"],
        "software": "Python 主机 + 行协议；可选 ROS2 桥",
        "safety": ["锂电池", "运动部件"],
        "benchmarks": ["空载直线 1m 偏差 < 5cm", "30cm 前停障", "续航 ≥ 45min", "断联 1s 内停车"],
        "must": ["差速运动与停障", "串口协议可复现", "电池与保险", "急停/断联保护"],
        "nice": ["OLED 状态", "IMU 航向", "ROS2 桥", "无线遥测"],
        "decisions": ["轮径/轮距写进 motion 与固件常量", "超声 Trig/Echo 5V 必须分压", "电机与主控分开供电"],
    },
    {
        "id": "desktop-companion",
        "name": "桌面陪伴机器人",
        "aliases": ["陪伴", "桌面", "情绪", "对话", "语音助手", "聊天机器人", "宠物", "表情", "小豆", "companion"],
        "one_liner": "ESP32-S3 + 麦克风/功放 + 双舵机 + 屏幕，离线唤醒、表情状态机、隐私优先。",
        "blueprint": "desktop-companion",
        "domains": ["hardware", "cad", "firmware", "software", "sim"],
        "budget": 400,
        "actuation": "2× MG90S 云台（水平/俯仰）",
        "power": "5V 3A USB-C 或 2S 锂电",
        "mcu": "ESP32-S3",
        "parts": ["ESP32-S3 N8R8", "INMP441 I2S 麦克风", "MAX98357A + 小喇叭", "GC9A01 圆屏", "MG90S ×2", "VL53L0X", "TTP223 ×2", "5V 3A 电源"],
        "buses": ["i2s", "spi", "i2c", "pwm"],
        "software": "固件行为状态机 + 可选主机语音服务",
        "safety": ["锂电池", "运动部件", "麦克风/摄像头隐私"],
        "benchmarks": ["唤醒到回应 < 2s（在线）", "断网仍可本地表情/短句", "舵机堵转 1s 内卸力", "麦克风有物理断电或明确指示"],
        "must": ["唤醒词与隐私边界", "表情/动作状态机", "断网降级", "堵转保护"],
        "nice": ["触摸互动", "距离感知", "OTA", "多语言"],
        "decisions": ["音频走 I2S 避免模拟底噪", "屏幕与 I2S 分核/分时", "舵机独立 5V 供电"],
    },
    {
        "id": "arm",
        "name": "桌面/轻载机械臂",
        "aliases": ["机械臂", "抓取", "夹爪", "舵机臂", "so-101", "lerobot", "6轴", "三轴", "pick", "arm"],
        "one_liner": "3–6 自由度舵机臂，位置/电流限幅，示教+回放，可选 LeRobot 数据采集。",
        "blueprint": "wheel-rover",
        "domains": ["hardware", "cad", "firmware", "software", "sim"],
        "budget": 700,
        "actuation": "STS3215 串行总线舵机（或 MG996R 方案）",
        "power": "6–7.4V 5A 独立舵机电源",
        "mcu": "ESP32-S3 / 总线舵机 USB 适配器",
        "parts": ["STS3215 ×3–6", "总线舵机控制板", "铝型材/3D 打印臂体", "独立 6V 5A 电源", "急停开关", "桌面夹具"],
        "buses": ["ttl-bus", "uart"],
        "software": "Python 逆解/回放 + 示教脚本",
        "safety": ["运动部件", "夹伤风险", "锂电/市电"],
        "benchmarks": ["重复定位 ±2mm（轻载）", "夹持 200g 不掉", "碰撞/超电流 200ms 内停", "断电保持力矩可释放"],
        "must": ["关节限位与软限位", "电流/温度保护", "示教回放可复现", "急停"],
        "nice": ["视觉抓取", "LeRobot 数据集", "力控", "ROS2 MoveIt"],
        "decisions": ["先做 3–4 轴，别一步到 6 轴", "总线舵机优于 PWM 舵机", "结构件用铝型材+打印件混合"],
    },
    {
        "id": "quadruped",
        "name": "四足机器人",
        "aliases": ["四足", "机器狗", "quadruped", "spot", "足式", "步态", "unitree"],
        "one_liner": "12 自由度四足，位置/力矩控制，步态与自平衡；预算高、周期长，先仿真后实机。",
        "blueprint": "wheel-rover",
        "domains": ["hardware", "cad", "firmware", "software", "sim"],
        "budget": 6000,
        "actuation": "12× 总线舵机/准直驱电机",
        "power": "6S 锂电 22.2V，BMS + 预充",
        "mcu": "ESP32-S3（舵机版）或 STM32 + 上位机",
        "parts": ["总线舵机 ×12", "金属腿/碳纤板", "6S 电池 + BMS", "急停/预充", "IMU", "遥控"],
        "buses": ["ttl-bus", "uart", "i2c"],
        "software": "Python 步态 + 仿真（MuJoCo）优先",
        "safety": ["高压锂电", "大扭矩运动", "夹伤/击打"],
        "benchmarks": ["站立 30s 不摔", "trot 0.2m/s 直线 2m", "跌倒自停", "单腿失效可安全趴下"],
        "must": ["仿真先通过", "失能与急停", "电池高压防护", "关节限位"],
        "nice": ["遥控", "台阶", "视觉跟随"],
        "decisions": ["预算 < 5000 不做四足", "先 8 自由度再 12", "必须有物理急停"],
    },
    {
        "id": "drone",
        "name": "多旋翼无人机",
        "aliases": ["无人机", "四轴", "穿越机", "fpv", "航拍", "drone", "uav", "飞控"],
        "one_liner": "不二开飞控：Betaflight/ArduPilot/PX4 + 合规机架；本插件负责载荷、地面站、测试与合规。",
        "blueprint": "wheel-rover",
        "domains": ["hardware", "software", "sim"],
        "budget": 1500,
        "actuation": "成品飞控 + 电调 + 无刷电机",
        "power": "4S/6S LiPo，分电板 + 防火花",
        "mcu": "成品飞控（不自行写姿态环）",
        "parts": ["机架", "飞控", "电调 ×4", "电机 ×4", "桨", "LiPo + 充电器", "遥控/图传"],
        "buses": ["uart", "i2c", "can"],
        "software": "MAVLink/地面站/日志分析",
        "safety": ["高能锂电", "高速桨叶", "空域合规"],
        "benchmarks": ["悬停 3min", "失控保护触发", "日志可回放", "桨叶护罩/场地隔离"],
        "must": ["不自研飞控", "失控保护", "实名/空域合规", "桨叶与人员隔离"],
        "nice": ["图传", "RTK", "自动航线"],
        "decisions": ["室内先上护罩/小桨", "先买套件再改", "飞行日志必须落盘"],
    },
    {
        "id": "sensor-node",
        "name": "环境传感节点",
        "aliases": ["传感器", "温湿度", "土壤", "气象", "监测", "iot", "esp32-c3", "低功耗", "sensor"],
        "one_liner": "ESP32-C3/ESPHome + BME280/土壤探头，深睡眠 + MQTT/Home Assistant。",
        "blueprint": "wheel-rover",
        "domains": ["hardware", "firmware", "software"],
        "budget": 120,
        "actuation": "无（可选继电器/阀）",
        "power": "USB 5V 或 18650 + 太阳能",
        "mcu": "ESP32-C3",
        "parts": ["ESP32-C3", "BME280", "土壤湿度探头", "TP4056/太阳能", "防水盒", "18650"],
        "buses": ["i2c", "adc"],
        "software": "ESPHome/MQTT + 简单看板",
        "safety": ["锂电池", "户外防水", "市电（如用电源）"],
        "benchmarks": ["7 天不重启", "数据与本地屏一致", "断网缓存 ≥ 1h", "深睡眠电流 < 1mA"],
        "must": ["探头校准", "断网缓存", "防水/防凝露", "低功耗预算"],
        "nice": ["太阳能", "本地屏", "OTA"],
        "decisions": ["户外用成品防水盒", "土壤探头易腐蚀，选可换的", "先用 ESPHome 别手写 WiFi"],
    },
    {
        "id": "differential-drive-mobile-manipulator",
        "name": "移动抓取平台",
        "aliases": ["移动抓取", "agv 机械臂", "复合机器人", "mobile manipulator", "小车加机械臂", "物流"],
        "one_liner": "差速底盘 + 轻载臂 + 视觉；先固定工位抓取，再上车。",
        "blueprint": "wheel-rover",
        "domains": ["hardware", "cad", "firmware", "software", "sim"],
        "budget": 1800,
        "actuation": "差速底盘 + 3–4 轴臂",
        "power": "24V 或 6S，底盘/臂分路",
        "mcu": "ESP32-S3 + 上位机",
        "parts": ["底盘套件", "总线舵机臂", "深度相机", "24V 电源", "急停", "激光/ToF"],
        "buses": ["uart", "i2c", "usb"],
        "software": "ROS2 导航 + 抓取节点",
        "safety": ["高压/大电流", "运动夹伤", "视觉隐私"],
        "benchmarks": ["定点抓取 10 次 ≥ 8 次", "导航重复到点 ±5cm", "急停 500ms", "人靠近降速"],
        "must": ["分路供电", "急停", "人机距离降速", "固定工位先验收"],
        "nice": ["视觉伺服", "自动充电", "调度接口"],
        "decisions": ["先不做全自主", "抓取用固定工装降低难度", "底盘与臂电源隔离"],
    },
    {
        "id": "lawn-mower",
        "name": "户外割草/履带作业机",
        "aliases": ["割草", "履带", "越野", "农业", "喷洒", "户外作业", "mower", "tracked"],
        "one_liner": "履带/轮式底盘 + 切割/作业头，重点在防护、急停、雨雾与边界。",
        "blueprint": "wheel-rover",
        "domains": ["hardware", "cad", "firmware", "software"],
        "budget": 2500,
        "actuation": "履带/大轮 + 有刷/无刷驱动",
        "power": "24V 锂电/铅酸，主接触器",
        "mcu": "ESP32-S3 + 工业驱动",
        "parts": ["履带底盘", "驱动器", "24V 电池", "急停/钥匙", "边界传感器", "防护罩"],
        "buses": ["uart", "can", "i2c"],
        "software": "遥控优先 + 边界/避障",
        "safety": ["高能电池", "旋转刀片", "户外/雨水", "公众安全"],
        "benchmarks": ["刀片防护罩不可徒手触及", "急停 < 300ms", "倾角 > 20° 停机", "遥控失联停机"],
        "must": ["刀片全防护", "双通道急停", "倾覆保护", "户外 IP 等级"],
        "nice": ["RTK 边界", "自动回充", "雨量传感"],
        "decisions": ["公众场景必须有人值守", "先遥控再自动", "刀片电机独立断电"],
    },
    {
        "id": "education-kit",
        "name": "教育/入门套件",
        "aliases": ["教育", "学习", "套件", "microbit", "micropython", "scratch", "学生", "教学", "入门"],
        "one_liner": "MicroPython/图形化 + 安全低压，重点是课程、可重复实验与低成本。",
        "blueprint": "wheel-rover",
        "domains": ["hardware", "firmware", "software"],
        "budget": 150,
        "actuation": "TT 电机/舵机（低压）",
        "power": "4×AA 或 USB 5V",
        "mcu": "ESP32-C3 / micro:bit",
        "parts": ["主控板", "扩展板", "TT 电机", "AA 电池盒", "传感器套件", "结构件"],
        "buses": ["i2c", "pwm", "adc"],
        "software": "MicroPython 课程 + 图形化",
        "safety": ["小零件吞咽", "低压安全"],
        "benchmarks": ["30 分钟第一课可跑", "短路不发热", "代码可复现", "套件清单 100% 可买"],
        "must": ["低压供电", "防反接", "课程步骤", "教师安全提示"],
        "nice": ["图形化", "扩展包", "课堂管理"],
        "decisions": ["不用 220V", "电池盒加防反接", "先单传感器再加"],
    },
    {
        "id": "camera-gimbal",
        "name": "云台/视觉跟踪",
        "aliases": ["云台", "摄像头", "跟踪", "人脸", "视觉", "gimbal", "ptz", "摄像"],
        "one_liner": "双轴云台 + 摄像头，本地推理/跟踪，隐私与网络边界优先。",
        "blueprint": "desktop-companion",
        "domains": ["hardware", "cad", "firmware", "software"],
        "budget": 500,
        "actuation": "2× 总线舵机/无刷云台",
        "power": "5V/12V 独立",
        "mcu": "ESP32-S3 / 上位机",
        "parts": ["摄像头模块", "双轴云台", "舵机 ×2", "ESP32-S3", "5V 3A", "遮光罩"],
        "buses": ["i2c", "pwm", "usb"],
        "software": "本地人脸/目标跟踪 + 可选 RTSP",
        "safety": ["隐私", "网络", "运动部件"],
        "benchmarks": ["跟踪延迟 < 150ms", "丢失目标回中", "默认不录云", "物理隐私挡片"],
        "must": ["隐私默认最小化", "网络鉴权", "限位", "断电归位"],
        "nice": ["RTSP", "本地 AI", "手机查看"],
        "decisions": ["视频不出内网", "默认不存人脸", "舵机独立供电"],
    },
    {
        "id": "underwater",
        "name": "水下/涉水机器人",
        "aliases": ["水下", "rov", "潜水", "船", "水质", "防水的", "underwater", "boat"],
        "one_liner": "ROV/水面船，密封、浮力、推进器与失联上浮是生死线。",
        "blueprint": "wheel-rover",
        "domains": ["hardware", "cad", "firmware", "software"],
        "budget": 2000,
        "actuation": "无刷推进器 ×2–4",
        "power": "4S 锂电，舱内",
        "mcu": "ESP32-S3（舱内）+ 脐带/无线",
        "parts": ["推进器", "密封舱", "O 圈", "4S 电池", "漏水传感", "配重"],
        "buses": ["uart", "i2c", "pwm"],
        "software": "遥控 + 姿态/深度保持",
        "safety": ["高压锂电", "溺水/失联", "密封失效"],
        "benchmarks": ["1m 水深 30min 无渗漏", "漏水 1s 断电上浮", "失联自动上浮", "推进器防护罩"],
        "must": ["漏水检测", "失联上浮", "双重密封", "池试验收"],
        "nice": ["定深", "水质传感", "图传"],
        "decisions": ["先在桶/池测试", "密封舱做负压测试", "电池放独立舱"],
    },
    {
        "id": "freeform",
        "name": "自由形态（未命中配方）",
        "aliases": [],
        "one_liner": "没有命中十二类配方：先按最近蓝本裁剪，并把未知量写成 assumptions，不许留空。",
        "blueprint": "wheel-rover",
        "domains": ["hardware", "firmware", "software"],
        "budget": 500,
        "actuation": "待定（先选成品执行器）",
        "power": "待定（先按 5V/12V 成品电源）",
        "mcu": "ESP32-S3",
        "parts": ["控制器", "执行器", "传感器", "电源", "结构件"],
        "buses": ["i2c"],
        "software": "Python 主机 + 串口/HTTP",
        "safety": ["运动部件", "用电安全"],
        "benchmarks": ["最小可动", "安全停机", "一条端到端路径"],
        "must": ["最小可动原型", "安全停机", "成本不超预算"],
        "nice": ["远程控制", "数据记录"],
        "decisions": ["先做最小闭环", "未知量写 assumptions", "优先成品模块"],
    },
]

SAFETY_FLAGS = [
    (("锂电", "锂电池", "lipo", "18650", "电池"), "battery", "电池安全", "docs/07 必须有：过充/过放/短路/穿刺/热失控、保险丝、充电器与存放"),
    (("220", "市电", "插座", "交流"), "mains", "市电安全", "docs/07 必须有：隔离、漏保、接地、防水接头、断电挂牌；建议改用成品电源"),
    (("机械臂", "舵机", "电机", "夹爪", "履带", "桨", "运动"), "motion", "运动/夹伤", "docs/07 必须有：限位、急停、断电泄力、人员隔离、失联停机"),
    (("激光", "lidar", "雷达"), "laser", "激光安全", "docs/07 必须有：激光等级、护目、避免直视、扫描区隔离"),
    (("摄像头", "相机", "麦克风", "录音", "人脸"), "privacy", "隐私", "docs/07 必须有：最小采集、本地优先、物理遮挡、告知与删除"),
    (("wifi", "wifi", "蓝牙", "联网", "云端", "app"), "network", "联网安全", "docs/07 必须有：鉴权、默认密码变更、OTA 签名、最小暴露面"),
    (("儿童", "学生", "教育", "课堂"), "children", "儿童/教学", "docs/07 必须有：小零件、低压、教师监护、防误吞"),
    (("户外", "下雨", "雨水", "防水", "涉水", "水下", "船体", "船舶"), "outdoor", "户外/涉水", "docs/07 必须有：IP 等级、排水、防凝露、失联回收"),
    (("医疗", "康复", "诊断"), "medical", "医疗边界", "医疗用途需持证评估；本插件只做工程原型，不做诊断/治疗声明"),
]

BLOCK_TERMS = [
    ("武器", "武器化"),
    ("爆炸", "爆炸物"),
    ("投毒", "投毒"),
    ("偷拍", "偷拍"),
    ("偷窥", "偷窥"),
    ("针孔", "偷拍"),
    ("赌博", "赌博"),
]

# Context-sensitive blocks: legitimate uses (face tracking on a gimbal, anti-jamming,
# safety guards) must not be rejected, while the harmful use is still caught.
BLOCK_PATTERNS = [
    (r"(?:跟踪|尾随|盯梢)[^。；，,]{0,10}(?:他人|别人|邻居|女友|男友|妻子|丈夫|孩子|学生|陌生人|目标人)", "跟踪他人"),
    (r"(?:信号|通信|无线电|gps|wifi|蓝牙)[^。；，,]{0,6}干扰", "信号干扰"),
    (r"(?:伤害|攻击|袭击)[^。；，,]{0,6}(?:人|他人|动物)", "伤害"),
    (r"破解[^。；，,]{0,6}(?:门锁|密码|账户|支付|监控)", "破解"),
]


def _norm(text):
    return re.sub(r"\s+", " ", str(text or "")).strip().lower()


def classify(text):
    """Keyword scoring over the 12 recipes; returns a deterministic ranking."""
    low = _norm(text)
    scores = []
    for arch in ARCHETYPES:
        if arch["id"] == "freeform":
            continue
        hits = [a for a in arch["aliases"] if a and a.lower() in low]
        score = sum(3 if len(a) >= 3 else 2 for a in hits)
        if arch["name"].lower() in low:
            score += 4
        scores.append((score, arch, hits))
    scores.sort(key=lambda row: (-row[0], row[1]["id"]))
    best_score, best, hits = scores[0]
    runner = scores[1][1] if len(scores) > 1 else None
    if best_score <= 0:
        return {
            "archetype": "freeform",
            "confidence": 0.25,
            "matched": [],
            "runner_up": None,
            "scores": {},
        }
    total = sum(s for s, _, _ in scores if s > 0)
    return {
        "archetype": best["id"],
        "confidence": round(min(0.95, 0.45 + best_score / max(1, total) * 0.5), 2),
        "matched": hits,
        "runner_up": runner["id"] if runner else None,
        "scores": {a["id"]: s for s, a, _ in scores if s > 0},
    }


def _arch(arch_id):
    for arch in ARCHETYPES:
        if arch["id"] == arch_id:
            return arch
    return ARCHETYPES[-1]


def _budget(text, arch):
    m = re.search(r"(\d{2,6})\s*(?:元|块|rmb|cny|人民币)", _norm(text))
    if m:
        return int(m.group(1)), "用户指定"
    m = re.search(r"(?:预算|budget)\D{0,6}(\d{2,6})", _norm(text))
    if m:
        return int(m.group(1)), "用户指定"
    return int(arch["budget"]), "配方默认"


def _gear(budget, arch):
    base = max(1, int(arch["budget"]))
    if budget <= 0:
        return "quick"
    if budget < base * 0.6:
        return "quick"
    if budget > base * 3:
        return "flagship"
    return "standard"


def _term_hit(terms, low):
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


def _risk_flags(text, arch):
    low = _norm(text) + " " + " ".join(arch["safety"]).lower()
    flags = []
    for terms, key, title, requirement in SAFETY_FLAGS:
        if _term_hit(terms, low):
            flags.append({"key": key, "title": title, "requirement": requirement})
    return flags


def _blocked(text):
    low = _norm(text)
    hits = [label for term, label in BLOCK_TERMS if term in low]
    for pattern, label in BLOCK_PATTERNS:
        if re.search(pattern, low) and label not in hits:
            hits.append(label)
    return hits


def _questions(text, arch, flags, budget_given):
    low = _norm(text)
    out = []
    if not any(k in low for k in ("室内", "室外", "桌面", "地面", "户外", "水上", "水下", "工厂", "家里", "教室")):
        out.append(
            {
                "id": "environment",
                "question": "它主要在什么环境使用：桌面/室内地面/户外/涉水？（决定防护、动力与合规）",
                "default": "室内平整地面，常温干燥",
            }
        )
    if arch["id"] in ("wheel-rover", "arm", "quadruped", "mobile-manipulator"):
        if not any(k in low for k in ("遥控", "自动", "自主", "跟随", "示教", "抓取")):
            out.append(
                {
                    "id": "autonomy",
                    "question": "第一版要“遥控/固定动作”还是“自主感知决策”？（自主会显著增加周期与预算）",
                    "default": "先遥控/固定动作跑通，再逐步加自主",
                }
            )
    if arch["id"] in ("desktop-companion", "camera-gimbal"):
        if not any(k in low for k in ("本地", "离线", "云", "在线", "不联网")):
            out.append(
                {
                    "id": "cloud",
                    "question": "语音/视觉允许联网吗？还是必须本地离线？（隐私、延迟、成本取舍）",
                    "default": "默认本地优先；离线可用的短句/表情保底，联网功能显式开启",
                }
            )
    if not budget_given:
        out.append(
            {
                "id": "budget",
                "question": "预算上限大约多少元？（不含工具与运费；决定选型档位）",
                "default": "%d 元（配方默认，含 15%% 浮动）" % int(arch["budget"]),
            }
        )
    return out[:3]


def intake_payload(text, budget=None):
    """Build the complete intake brief. Pure function: same input, same output."""
    raw = str(text or "").strip()
    if len(raw) < 4:
        return {
            "ok": False,
            "error": "愿望太短：至少用一句话说明“谁在什么场景用它做什么”。",
            "questions": [
                {
                    "id": "wish",
                    "question": "请补一句：使用场景 + 一个必须实现的动作 + 预算范围。",
                    "default": "例：家里地面巡检，遇到 30cm 障碍停下，预算 300 元。",
                }
            ],
        }
    blocked = _blocked(raw)
    if blocked:
        return {
            "ok": False,
            "allowed": False,
            "error": "这个愿望涉及高风险/违法用途（%s），不能提供建造方案。" % "、".join(blocked),
            "safe_alternatives": [
                "改为教育演示/安全研究，并去掉真实伤害能力",
                "改为固定场景的监测/告警装置，不涉及跟踪或干扰",
                "先描述你想验证的工程问题，我帮你换成合规原型",
            ],
        }
    cls = classify(raw)
    arch = _arch(cls["archetype"])
    budget_value, budget_source = _budget(raw, arch)
    if budget is not None:
        try:
            budget_value = int(budget)
            budget_source = "命令行指定"
        except (TypeError, ValueError):
            pass
    flags = _risk_flags(raw, arch)
    gear = _gear(budget_value, arch)
    questions = _questions(raw, arch, flags, budget_source == "用户指定")
    must = []
    for i, item in enumerate(arch["must"][:6], 1):
        must.append(
            {
                "id": "REQ-%03d" % i,
                "text": item,
                "priority": "must",
                "verify": "manual: 按 docs/06 验收步骤真实操作并记录结果；可自动化的部分补 pytest 或 sim 脚本",
            }
        )
    nice = [
        {"id": "REQ-%03d" % (len(must) + i), "text": item, "priority": "nice"}
        for i, item in enumerate(arch["nice"][:4], 1)
    ]
    decisions = [
        "形态配方：%s（置信度 %.2f；命中词：%s）" % (arch["name"], cls["confidence"], "、".join(cls["matched"]) or "无"),
        "最近蓝本：%s；先复制再改造，禁止从空目录手写" % arch["blueprint"],
        "预算口径：%d 元（%s，不含工具/运费），超过 115%% 预警、150%% 拒绝" % (budget_value, budget_source),
        "档位：%s；域：%s" % (gear, " / ".join(arch["domains"])),
        "执行器：%s；电源：%s；主控：%s" % (arch["actuation"], arch["power"], arch["mcu"]),
    ]
    for flag in flags:
        decisions.append("安全旗标 %s：%s" % (flag["title"], flag["requirement"]))
    return {
        "ok": True,
        "allowed": True,
        "wish": raw,
        "archetype": arch["id"],
        "archetype_name": arch["name"],
        "one_liner": arch["one_liner"],
        "confidence": cls["confidence"],
        "matched": cls["matched"],
        "runner_up": cls["runner_up"],
        "blueprint": arch["blueprint"],
        "budget_cny": budget_value,
        "budget_source": budget_source,
        "gear": gear,
        "domains": list(arch["domains"]),
        "architecture": {
            "summary": arch["one_liner"],
            "actuation": arch["actuation"],
            "power": arch["power"],
            "mcu": arch["mcu"],
            "comms": "USB 串口（默认）；需要无线时显式加 WiFi/BLE 并写安全边界",
        },
        "parts_hint": list(arch["parts"]),
        "buses_hint": list(arch["buses"]),
        "software_hint": arch["software"],
        "safety": flags,
        "benchmarks": list(arch["benchmarks"]),
        "decisions": decisions,
        "decisions_from_recipe": list(arch["decisions"]),
        "wish_fields": {
            "story": raw,
            "must": must,
            "nice": nice,
            "forbidden": ["武器化", "超出预算 150%", "无证据宣称已实测"],
            "acceptance_hint": "must 全部有 measured/manual 证据；docs/06 可照做；断网/断电/失联均安全",
        },
        "questions": questions,
        "assumptions": [
            "默认单人制作、每周 8–12 小时、有电烙铁与 3D 打印/手工具",
            "默认室内常温干燥；户外/涉水需额外防护与降额",
            "价格为中国大陆 2026-11 电商常见价，下单前复核",
            "默认不含手机 App 与云服务；需要时单独立项",
        ],
        "next": {
            "tool": "rf_new",
            "arguments": {"name": arch["name"], "blueprint": arch["blueprint"]},
            "commands": [
                "python <插件>/skills/robot-forge/scripts/forge.py blueprints",
                "python <插件>/skills/robot-forge/scripts/forge.py new \"%s\" --blueprint %s" % (arch["name"], arch["blueprint"]),
            ],
        },
    }


def render_text(payload):
    if not payload.get("ok"):
        lines = ["✗ " + str(payload.get("error", "无法接单"))]
        for alt in payload.get("safe_alternatives", []):
            lines.append("  - " + alt)
        for q in payload.get("questions", []):
            lines.append("  ? %s（默认：%s）" % (q["question"], q.get("default", "")))
        return "\n".join(lines)
    lines = [
        "形态：%s（%s，置信度 %.2f）" % (payload["archetype_name"], payload["archetype"], payload["confidence"]),
        "蓝本：%s ｜ 预算：%d 元（%s）｜ 档位：%s" % (payload["blueprint"], payload["budget_cny"], payload["budget_source"], payload["gear"]),
        "域：%s" % " / ".join(payload["domains"]),
        "一句话：%s" % payload["one_liner"],
        "",
        "关键决策：",
    ]
    lines += ["  - " + d for d in payload["decisions"]]
    lines += ["", "基准（benchmarks）："]
    lines += ["  - " + b for b in payload["benchmarks"]]
    if payload["safety"]:
        lines += ["", "安全旗标（必须写进 docs/07）："]
        lines += ["  - %s：%s" % (f["title"], f["requirement"]) for f in payload["safety"]]
    if payload["questions"]:
        lines += ["", "至多三个会改变设计的问题（有默认值，可先按默认开工）："]
        lines += ["  ? %s\n    默认：%s" % (q["question"], q.get("default", "")) for q in payload["questions"]]
    lines += ["", "下一步：rf_new name=%s blueprint=%s，然后按 SKILL 七阶段推进。" % (payload["archetype_name"], payload["blueprint"])]
    return "\n".join(lines)


if __name__ == "__main__":  # pragma: no cover
    import sys

    print(json.dumps(intake_payload(" ".join(sys.argv[1:])), ensure_ascii=False, indent=2))
