# 蓝本与形态配方 v2.0

> 蓝本 = **完整可运行的项目模板**，不是代码片段。它负责“从 0 到 1 有骨架”；配方（`archetypes.md`）负责“这个形态该有什么”。
> 当前内置 2 个蓝本、12 类配方 + freeform；没有完全匹配时，从最近蓝本派生，**不要假装有 freeform 生成命令**。

---

## 1. 内置蓝本

| 蓝本 | 一句话 | 预算 | 工期 | 域 | 适合改造 |
|---|---|---:|---|---|---|
| `wheel-rover` | 2 轮差速 + 超声避障 + IMU + OLED + 串口遥控 | ¥261 | 2 个周末 | hardware/cad/firmware/software/sim | 小车、巡检、跟随、传感节点带轮 |
| `desktop-companion` | ESP32-S3 + 双舵机 + 麦克风/功放 + 圆屏 + 触摸 | ¥264 | 2 个周末 | hardware/cad/firmware/software/sim | 桌面陪伴、语音助手、表情头、云台 |

两个蓝本都含：完整 `robot.yaml`/`verify.yaml`、可编译固件、可跑 Python 软件与测试、参数化 CAD、仿真脚本、11 篇文档、forge 计划/决策/调研/证据。

**它们证明的是工程链路，不是性能上限**：先跑通，再按配方换件/加域。

---

## 2. 12 类配方 → 起点

| 配方 | 起点蓝本 | 关键改造 | 典型预算 |
|---|---|---|---:|
| wheel-rover 差速车 | wheel-rover | 换电机/驱动/轮径；加编码器/IMU | ¥260–800 |
| differential-drive-mobile-manipulator 移动抓取 | wheel-rover | 加机械臂域、舵机/总线舵机、夹爪、负载核算 | ¥800–3000 |
| arm 桌面机械臂 | desktop-companion | 换 3–6 轴结构、总线舵机、运动学、限位 | ¥700–4000 |
| camera-gimbal 视觉云台 | desktop-companion | 换无刷/舵机云台、摄像头、跟踪状态机 | ¥400–1500 |
| quadruped 四足 | wheel-rover（仅软件/仿真） | 12 舵机、步态、IMU、电源；结构重做 | ¥3000–15000 |
| drone 无人机 | 不自研飞控 | 用 Betaflight/ArduPilot/PX4 成品机架 | ¥1500–8000 |
| lawn-mower 割草 | wheel-rover | 户外/防水/刀片安全/边界；高风险 | ¥2000–10000 |
| sensor-node 传感节点 | wheel-rover（裁域） | 去运动，加低功耗/无线/MQTT | ¥80–400 |
| education-kit 教育套件 | desktop-companion | 低压、防呆、教师手册、课程 | ¥150–600 |
| underwater 水下 | wheel-rover（仅参考） | 密封/浮力/推进器/系绳；高风险 | ¥3000–20000 |
| freeform 其他 | 最近蓝本 | 见 §4 | 按需求 |

配方细节（关键件、域、必须项、验收基准、证据、坑）见 `archetypes.md`；选型与版本见 `stacks.md`。

---

## 3. 形态 → 起点映射（速查）

```text
会走 + 轮子            → wheel-rover
会走 + 腿              → wheel-rover 的软件/仿真 + 重做结构（高风险）
桌面 + 说话/表情        → desktop-companion
桌面 + 抓取/挥动        → arm（从 desktop 派生）
会看 + 会转             → camera-gimbal（从 desktop 派生）
只传感 + 上报           → sensor-node（wheel-rover 裁域）
教学 + 套件             → education-kit（desktop 简化）
户外 + 割草/喷洒        → lawn-mower（高风险，先做安全）
水里/船                → underwater（高风险，先做密封）
飞行                   → 买成品飞控，不写飞控
其他                   → freeform 九步
```

---

## 4. freeform 九步（没有配方时）

1. **选最近蓝本**：按“有无运动/有无交互/有无显示”选，不按名字；
2. **改 robot.yaml**：name/slug/one_liner/story/must/domains/budget；
3. **裁域**：不要的域从 domains 删掉，decisions 写原因；
4. **换关键件**：controller/actuator/sensor/power 四类先定，再补辅料；
5. **改需求**：每条 must 有 verify（命令或 manual 步骤），删掉做不到的；
6. **改固件/软件**：先让 `--mock` 与 native 测试过，再接硬件；
7. **改 CAD/文档**：参数化脚本先能导出，再调尺寸；
8. **跑全套**：`check` → `design` → `verify` → `trace` → `review` → `audit`；
9. **重命名与清理**：删示例名/引脚/上游 README 残留，跑 S12/S13。

**最低交付 7 项：** README、BOM、装配、接线、固件或软件入口、验证命令、安全页。缺一项就不算“完整项目”。

---

## 5. 新增蓝本（贡献者）

**目录：** `skills/robot-forge/templates/<slug>/`，必须能通过 `new` 生成并自测。

**元数据 `blueprint.json`：** name/slug/one_liner/cost_cny/time/difficulty/domains/needs/tags；slug 必须等于目录名。

**占位符：** 只允许 `{{NAME}}`、`{{SLUG}}`、`{{DATE}}`、`{{BLUEPRINT}}`。

**预算口径：** 元件小计 + 运费；不含工具/打印机；写 `quote_date`。

**验收（缺一不可）：**
1. `new` exit 0；
2. `check` 0 error；`render --check` 无过期；
3. `verify` required 通过（缺工具的命令标 optional + needs）；
4. `design` 无 error；`audit` ≥85 且 must 100%（做不到就 README 标 Beta）；
5. 无 TODO/占位；链接存在；至少 1 个会真实失败的测试；
6. `selftest` 全绿。

**设计原则：** 零基础可照做；安全默认；价格真实；每一步有“应该看到什么”；不依赖作者本机路径/私有服务。

---

## 6. 常见坑

1. 把蓝本当“形态白名单”，用户要机械臂却硬套小车；
2. 只改名字不改引脚/协议，烧录后不动；
3. 删域不写 decisions，后来者不知道为什么没有 CAD；
4. 预算只算主件，漏电源/线材/紧固件/运费；
5. 用 optional 掩盖必须验证的固件测试；
6. 文档写“支持”，但没有对应需求/证据；
7. 保留示例项目名/上游 README；
8. 先写 10 篇文档再写代码，最后全漂移；
9. 高风险形态（四足/飞行/水下/割草）不做安全边界就开工；
10. 发布前不跑 `audit`/`package`，只给源码目录。

---

## 7. 路线图（不假装已内置）

| 候选蓝本 | 价值 | 前置 |
|---|---|---|
| so101-arm | 桌面机械臂，LeRobot 生态 | 结构/运动学/总线舵机测试 |
| sensor-node | 低功耗环境节点 | 深睡眠/无线/MQTT 证据 |
| line-follower | 教学入门 | 循迹传感器/赛道测试 |
| camera-gimbal | 视觉跟踪 | 云台控制/隐私边界 |

新增蓝本按 §5 验收；未内置前，用最近蓝本 + 配方派生，并在 README 说明差异。
