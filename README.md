# Robot Forge for DeepSeek Harness

[![GitHub release](https://img.shields.io/github/v/release/yry1816186-pixel/robot-forge-dsh?color=0b7285&label=release)](https://github.com/yry1816186-pixel/robot-forge-dsh/releases) [![CI](https://github.com/yry1816186-pixel/robot-forge-dsh/actions/workflows/ci.yml/badge.svg)](https://github.com/yry1816186-pixel/robot-forge-dsh/actions/workflows/ci.yml) [![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

把一句“我想要一个机器人”变成**买得到、造得出、跑得起来、有证据、可发布**的完整项目。

> GitHub: <https://github.com/yry1816186-pixel/robot-forge-dsh> · 问题与建议请开 issue，安全漏洞请走私密渠道（见 `SECURITY.md`）。

Robot Forge 是 DeepSeek Harness 的原生 bundle：**12 个模型可见的 `rf_*` 工具**、一个按需加载的 `robot-forge` 技能、**12 类形态配方**、两个可跑通的完整蓝本（起点，不是白名单），以及一套用退出码和证据链说话的 Python 门禁。它不是提示词合集：模型说“做完了”不算数，`rf_verify`、`rf_trace`、`rf_review` 和 `rf_audit` 才算。

> 面向完全不懂技术的用户：用自然语言许愿即可。插件负责把愿望翻译成形态、预算、BOM、接线、固件、软件、结构、仿真、测试、文档、合规边界和可复现发布包；做不到的部分会明确标成未验证，而不是编造通过。

---

## 目录

- [它解决什么问题](#它解决什么问题)
- [七阶段工作流](#七阶段工作流)
- [12 个工具](#12-个工具)
- [12 类形态配方](#12-类形态配方)
- [质量门与六维评分](#质量门与六维评分)
- [安装](#安装)
- [快速开始](#快速开始)
- [能力覆盖矩阵](#能力覆盖矩阵)
- [两个可跑通蓝本](#两个可跑通蓝本)
- [结构与编排](#结构与编排)
- [开发与验证](#开发与验证)
- [限制与诚实边界](#限制与诚实边界)
- [参与贡献](#参与贡献)
- [许可](#许可)

---

## 它解决什么问题

机器人项目最常见的六种失败，不是“不会写代码”，而是：

1. **幻觉选型**：元件不存在、引脚冲突、电压不匹配、买不到。
2. **假绿**：测试没跑、只跑了子集、改了源码还用旧证据，却说“已完成”。
3. **跳步**：没算扭矩就买舵机，没算续航就选电池，装完才发现带不动。
4. **过设计**：零基础用户想要桌面摆件，却生成 Kubernetes + 自研 PCB + 强化学习。
5. **占位交付**：TODO、`pass`、`{{NAME}}`、示例数据混进成品。
6. **自评通过**：实现者给自己打分，没有独立复核，也没有可复现证据。

Robot Forge 用四件事封堵：**单一事实源 `forge/robot.yaml`**、**可执行门禁**、**四态证据链**、**独立盲审 + 可复现发布包**。

---

## 七阶段工作流

| 阶段 | 做什么 | 工具 | 退出条件 |
|---|---|---|---|
| **A 接单** | 把自然语言愿望分类到形态，补默认值，识别安全旗标，最多问 3 个带默认值的问题 | `rf_intake` | 形态/预算/域/验收基准明确，或有一个可执行的默认假设 |
| **B 定案** | 选最近蓝本，生成项目，写一页方案 | `rf_blueprints` → `rf_new` | 需求有 must/nice/forbidden，预算和工期可信 |
| **C 架构** | 算扭矩、转速、电流、续航、线径、散热、成本；定电源树与接口 | `rf_design` | 无阻断级设计发现；`forge/design.md` 生成 |
| **D 建造** | 硬件/BOM/CAD/固件/软件/仿真/文档，按域推进 | `rf_check` | 0 error；warning 都能解释 |
| **E 证明** | 真跑命令，记录 measured/manual 证据，出需求追踪矩阵 | `rf_verify` → `rf_trace` | 全部 required 退出码 0；must 覆盖率 100% |
| **F 盲审** | 生成可复现盲审包，换一个模型/人独立复核并记录结论 | `rf_review` | 独立 pass、无 blocker、≥70；`forge/review.json` 与当前构建一致 |
| **G 发布** | 六维评分、发布判定、打可复现包 | `rf_audit` → `rf_package` | release：0 error + must 100% + ≥85 + 有效盲审 pass≥70；beta：0 error；blocked 不可打包 |

详细协议见 `skills/robot-forge/references/workflow.md`；机器规则见 `references/spec.md`。

---

## 12 个工具

所有工具共享统一返回 `{ ok, text, data }`：`text` 给模型看，`data` 给程序和 UI 用。都接受可选 `project`；省略时从会话工作目录向上找 `forge/robot.yaml`，或找唯一子项目。

| 工具 | 作用 | 关键约束 |
|---|---|---|
| `rf_intake` | 愿望 → 形态/预算/域/安全旗标/≤3 问题 | 每个问题都带默认值，不阻塞；违法/伤害用途直接拒绝并给安全替代 |
| `rf_blueprints` | 列出内置蓝本、预算、工期、难度 | 蓝本不是白名单；无匹配时按配方派生 |
| `rf_new` | 从蓝本生成完整项目 | `blueprint` 必填；不改 `wish` 就交付 = 模板抄袭 |
| `rf_status` | 一页状态 + 唯一下一步 | 每次开始工作、上下文变长后先跑 |
| `rf_check` | 自动 render + 结构/一致性/设计检查 | 0 error 才能继续；warning 要能解释 |
| `rf_design` | 扭矩/续航/电流/线径/散热/成本核算，写 `forge/design.md` | 选型变了必须重跑；核算不替代实测 |
| `rf_verify` | 真跑 `forge/verify.yaml`，记录证据 | 必需命令 exit 0 才算“实测通过”；只跑子集会明确标 partial |
| `rf_audit` | 六维评分、must 覆盖、发布判定 | 不通过只能标 beta/blocked，不能写“可发布” |
| `rf_trace` | 需求 × 命令 × 证据 × 覆盖矩阵，写 `forge/trace.md` | must 覆盖不到 100% 会被发布门拦下 |
| `rf_review` | 独立盲审包（复现命令、追踪、证据、机器发现、评审模板） | 实现者不得给自己出 pass |
| `rf_package` | 打 zip + `RELEASE.json` + `SHA256SUMS` | 有 error 或 blocked 拒绝；未允许 beta 时未验证项拒绝 |
| `rf_evidence` | 记录人工/仿真/假设证据 | 只能在人真的确认后写 `manual`；measured 只能由 verify 产生 |

---

## 12 类形态配方

配方负责“这类机器人通常怎么搭、哪些件不能省、验收看什么”，不是限制形态。没有匹配时用 `freeform` 按最近配方派生。

| 配方 | 一句话 | 默认预算 | 关键域 | 安全旗标 |
|---|---|---|---|---|
| `wheel-rover` | 两轮/四轮差速避障小车 | ¥300 | 硬件/固件/软件/仿真 | battery, motion |
| `desktop-companion` | 桌面陪伴：看人、转头、表情、语音 | ¥400 | 硬件/结构/固件/软件/仿真 | battery, motion, privacy |
| `arm` | 3–6 自由度桌面机械臂 | ¥800 | 硬件/结构/固件/软件/仿真 | motion |
| `quadruped` | 四足/双足/人形 | ¥8,000+ | 全栈 | battery, motion, privacy |
| `drone` | 多旋翼（不自研飞控） | ¥1,500+ | 硬件/固件/软件 | battery, outdoor |
| `sensor-node` | 环境/土壤/气象传感节点 | ¥150 | 硬件/固件/软件 | battery, network |
| `differential-drive-mobile-manipulator` | 移动底盘 + 机械臂 | ¥1,800+ | 全栈 | battery, motion |
| `lawn-mower` | 户外割草/巡检 | ¥3,000+ | 全栈 | battery, motion, outdoor, children |
| `education-kit` | 教学套件/实验平台 | ¥200 | 硬件/固件/软件/文档 | battery, children |
| `camera-gimbal` | 云台/视觉跟踪 | ¥500 | 硬件/固件/软件 | motion, privacy |
| `underwater` | 水下/两栖 | ¥2,500+ | 全栈 | battery, outdoor |
| `freeform` | 以上都不像的专机 | 按需 | 按需裁剪 | 按实际识别 |

每类配方含：适合谁、域裁剪、关键件、总线、软件栈、must 需求、验收基准、证据计划、升级路径、十个坑。见 `references/archetypes.md`。

---

## 质量门与六维评分

### 六道机器门（全过才算 release）

```text
1. rf_check              0 error
2. rf_check --deep       0 error（must 缺证据会升级为 error）
3. rf_verify             全部 required 退出码 0
4. rf_trace              must 覆盖率 100%
5. rf_review             盲审包 + 独立 pass（无 blocker，>=70）
6. rf_audit              0 error + 100% + score ≥ 85
```

### 六维评分（总分 100）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 买得到 | 15 | BOM 型号、价格、来源、替代料、EOL |
| 造得出 | 20 | CAD/结构/公差/装配顺序/工具 |
| 跑得起来 | 25 | 固件/软件/仿真/引脚/电源/协议 |
| 说得清 | 15 | 11 份文档、接线、故障排查、决策记录 |
| 证得了 | 15 | 证据等级、覆盖率、过期检测、可复现 |
| 安全与许可 | 10 | 九类安全旗标、合规块、许可证兼容 |

扣分：每个 error −6，每个 warning −1；`evidenced` 直接按覆盖率折算，避免重复惩罚。判定：

- **release**：0 error + must 覆盖 100% + score ≥ 85。
- **beta**：0 error，但覆盖或分数未达 release；必须显式标注。
- **blocked**：仍有 error，禁止发布。

### 证据四态

| 状态 | 含义 | 产生方式 |
|---|---|---|
| `measured` | 命令真跑过，退出码 0 | 只能由 `rf_verify` 写入 |
| `manual` | 人按步骤确认过 | `rf_evidence`，必须写清谁/怎么确认 |
| `simulated` | 只在仿真/核算里通过 | `rf_evidence`，不计入发布覆盖 |
| `assumed` | 明确假设，未验证 | `rf_evidence`，不计入发布覆盖 |

改动源码、固件、CAD、仿真、`robot.yaml` 或 `verify.yaml` 会让旧证据**过期**（来源指纹变化），必须重跑；这防止“改完还用旧结果”。

---

## 安装

先安装 DeepSeek Harness（本包面向 0.2.x），然后二选一：

**Web（推荐）**：侧栏 **Plugins** → **Install bundle** → 选择本目录（含 `package.json` 和 `cordis.patch.yml`），安装后启用 `robot-forge-dsh` 并重启 Harness。

**CLI**：`dsh plugin` 只负责把包装进 profile；还要把 `robot-forge-dsh` 加入 profile `package.json` 的 `dsh.profile.bundles`，否则不会加载 patch。

```bash
# 1) 从 GitHub Release 的 tarball 安装（推荐，锁定 v2.0.0）
dsh plugin --profile desktop add "https://github.com/yry1816186-pixel/robot-forge-dsh/releases/download/v2.0.0/robot-forge-dsh-2.0.0.tgz"

# 或者从本地目录安装
dsh plugin --profile desktop add "C:/path/to/plugins/robot-forge"
```

然后编辑 profile 的 `package.json`，在 `dsh.profile.bundles` 数组里加入：

```json
"robot-forge-dsh"
```

如果 profile 已有 `node_modules`，再在 profile 目录执行 `pnpm install` 并重启 Harness。

安装后重启 Harness，或在启用 HMR 的 profile 里等配置热加载。确认方式：新会话里应能看到 12 个 `rf_*` 工具和 `robot-forge` 技能；输入 `/forge` 可看当前项目状态。

> 本包未发布到 npm registry；官方发布渠道是 GitHub Releases。安装会修改你的 profile，先在测试 profile 里试更稳。

---

## 快速开始

在 Harness 里直接说：

> 帮我做一个 300 元以内的桌面陪伴机器人，会转头、会做表情，默认不联网。零基础，两个周末能装完。

模型应该：`rf_intake` 解析愿望 → `rf_blueprints` 选起点 → `ask_user_question` 一次读回（≤3 问）→ `rf_new` 创建 → 改 `forge/robot.yaml` → `rf_design` → `rf_check` → `rf_verify` → `rf_trace` → `rf_review` → `rf_audit` → `rf_package`。

也可以直接调用工具：

```json
{"name":"小豆","blueprint":"desktop-companion","dir":"D:/robot"}
```

或只用 Python CLI：

```bash
python skills/robot-forge/scripts/forge.py intake "能避障、能遥控的小车，预算 300"
python skills/robot-forge/scripts/forge.py new 小满 --blueprint wheel-rover --dir /tmp/xiaoman
cd /tmp/xiaoman
python tools/forge.py design --write
python tools/forge.py check
python tools/forge.py verify
python tools/forge.py trace --write
python tools/forge.py review
python tools/forge.py audit
python tools/forge.py package
```

---

## 能力覆盖矩阵

| 全栈能力 | 覆盖方式 | 机器可判定 |
|---|---|---|
| 需求澄清 | intake 12 配方 + 一页方案 + ≤3 问 | ✅ 形态/预算/域/安全旗标 |
| 选型与 BOM | `robot.yaml` 单一事实源 → BOM/采购/替代料 | ✅ 型号占位、预算 115%/150%、来源/EOL |
| 机械与结构 | CAD 脚本、公差表、装配顺序、STL 检查 | ✅ 域文件、尺寸、零件绑定 |
| 电子与接线 | 引脚/总线/电源树/线径/上电顺序 | ✅ GPIO 冲突、保留脚、I2C、总线地址、电流 |
| 固件 | PlatformIO/ESP32 骨架、协议、限位、堵转 | ✅ 编译/单元测试、引脚↔清单、协议 token |
| 主机软件 | Python 包、协议、模拟链路、pytest | ✅ 测试数量/断言/假绿 |
| 仿真 | 运动学、功率、场景脚本 | ✅ 脚本存在 + 退出码 |
| 设计核算 | 扭矩/转速/续航/C-rate/散热/成本 | ✅ DSN-01…11 |
| 跨产物一致 | 固件↔清单↔文档↔需求↔证据 | ✅ CST-01…14 |
| 测试与证据 | verify.yaml + 四态证据 + 指纹过期 | ✅ 覆盖率/过期/假绿 |
| 安全与合规 | 九类旗标 + docs/07 + compliance/security | ✅ 触发词 + 块字段 |
| 供应链 | 来源、价格日期、EOL、替代料 | ✅ 缺 source/EOL/交期 |
| 文档 | 11 份中文文档 + 生成块 | ✅ 章节/标记/链接/语言 |
| 发布 | trace/review/audit/package | ✅ 六道门 + SHA256 |
| 可复现 | 固定引擎、RELEASE.json、SHA256SUMS | ✅ 哈希清单 |

---

## 两个可跑通蓝本

| 蓝本 | 形态 | 预算 | 工期 | 域 |
|---|---|---|---|---|
| `desktop-companion` | 桌面陪伴：ESP32-S3 + 麦克风 + 喇叭 + 圆屏 + 双舵机 + 触摸/测距 | ¥264 | 2 个周末 | 硬件/结构/固件/软件/仿真 |
| `wheel-rover` | 两轮差速避障小车：TB6612 + HC-SR04 + MPU6050 + OLED + 18650 2S | ¥261 | 2 个周末 | 硬件/固件/软件/仿真（买成品底盘，无 CAD） |

两个蓝本都带：可跑的 pytest、固件原生测试、仿真检查脚本、11 份中文文档、`forge/` 状态层、BOM/接线/电源生成块、证据四态。`wheel-rover` 故意删掉 CAD 域，演示另一种形态和“删域”也走同一套契约。

**这两个蓝本是起点，不是白名单。** 机械臂、四足、无人机、水下等按 12 类配方派生；没有现成完整项目时，插件会明确说“这是派生起点”，不会假装已验证。

---

## 结构与编排

```text
index.js + lib/               Host 插件：12 个工具、系统提示、/forge 命令
skills/robot-forge/
  SKILL.md                    按需加载的技能正文（七阶段、12 工具、红线）
  references/                 11 篇参考：spec/workflow/quality/blueprints/stacks/
                              archetypes/design/compliance/testing/release/orchestration
  templates/                  两个完整蓝本
  scripts/forgekit/           Python 引擎：intake/design/consistency/report/render/check/api/cli
cordis.patch.yml              把 Host 插件和 skill-filesystem 挂进 profile
evals/                        12 个行为评测（有/无插件对照）
tests/                        Host 运行时回归 + Python 引擎单测
docs/                         设计说明、贡献指南、验收标准
```

### Python 引擎职责

| 模块 | 职责 |
|---|---|
| `intake.py` | 12 类形态分类、默认值、安全旗标、≤3 问题 |
| `design.py` | 扭矩/续航/电流/线径/散热/成本核算，DSN 规则 |
| `consistency.py` | 固件↔清单↔协议↔需求↔证据↔供应链，CST 规则 |
| `report.py` | trace 矩阵、盲审包、发布 zip + SHA256 |
| `render.py` | 从 `robot.yaml` 生成 BOM/接线/电源/图/文档块 |
| `check.py` | 结构、占位、链接、语法、块、证据、假绿、语言、许可 |
| `api.py` | 工具用 JSON 载荷与“下一步” |
| `cli.py` | 人类 CLI，也是工具后端 |

### DSH 能力利用

| Harness 能力 | Robot Forge 怎么用 |
|---|---|
| 原生工具注册 | 12 个 `rf_*`，带 JSON schema、超时、取消、结构化结果 |
| Agent Skill | `robot-forge` 按需加载；正文、七阶段、红线和 references 在磁盘 |
| PTC 模式 | 注册工具进入 `run_code` SDK，可在一个程序里串“生成→核算→检查→验证→打包” |
| 子代理 | `prompts/roles/verifier.md`、`reviewer.md` 做独立只读复核；实现者不自审 |
| 人机回环 | 接单用 `ask_user_question` 一次读回；交付用 `present` 交 BOM/指南/报告 |
| 目标与计划 | 长任务 `create_goal`，阶段 `todo_write` |
| Web | 插件页标题/描述/图标；失败与未验证项直接出现在工具结果 |

---

## 开发与验证

```bash
# 插件结构 + 清单 + 版本锁步 + 11 篇参考 + 两个蓝本
python scripts/validate_plugin.py

# Host 运行时：真实调用 Python 引擎，覆盖 12 个工具
node --test tests/plugin.test.mjs

# Python 引擎单测：intake/design/consistency/report
python -m pytest tests/ -q

# Python 侧：两个蓝本生成 + check + verify
python skills/robot-forge/scripts/forge.py selftest
```

要求 Python 3.10+。可选：PlatformIO（固件编译）、build123d（CAD 导出）、MuJoCo（场景仿真）、pytest。缺工具不会让 `check` 失败，但对应验证只能 SKIP/标未验证——这是诚实，不是通过。

CI 矩阵：Ubuntu + Windows × Python 3.11/3.12/3.13 × Node 22/24。发布前跑 `docs/acceptance.md` 的验收清单。

---

## 限制与诚实边界

- 内置**两个**可跑通蓝本；其余 10 类是按配方派生的起点，不是现成完整项目。插件会标清哪些验证做过、哪些没做。
- 不替代真实装配、电气安全审查、法规认证和实机测试；插件只能保证“没做到的部分会暴露”。
- 价格、型号、版本是 2026-11 的快照；采购前按 `docs/01-物料清单.md` 复核。
- `rf_evidence` 的 `manual` 仍需要人真正确认；模型可以撒谎，但审计和证据链会把撒谎变成可检查的记录。
- 高风险形态（载人、飞行、水下、市电、激光、儿童）会先做安全确认与降级；不承诺超预算/超能力的版本。
- 未在 npm 发布，也未在全部 DSH 版本上回归；按 0.2.x 的 bundle/patch 契约编写。

---

## 参与贡献

- 贡献流程与新增蓝本验收：`docs/CONTRIBUTING.md`
- 安全漏洞报告：`SECURITY.md`
- 行为准则：`CODE_OF_CONDUCT.md`
- 路线图：`ROADMAP.md`
- 发布验收清单：`docs/acceptance.md`

开源供全国技术爱好者使用和检验。欢迎用真实项目“打脸”：提交一个插件生成的失败案例，比一句“很好”更有价值。

## 许可

MIT。蓝本中的第三方库/工具保留各自许可；生成项目默认 MIT，可自行改。
