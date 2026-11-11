# 设计说明：把“做一个机器人”变成可判定的交付

## 1. 问题不是“模型不会写方案”

零基础用户要的不是一份看起来完整的方案，而是一个真的能买、能装、能跑、能证明的实物。大模型在这个任务上有六类稳定失败：

| 失败 | 表现 | 后果 | v2 的封堵 |
|---|---|---|---|
| 幻觉选型 | 写了不存在的型号、引脚、API | 买不到 / 装不上 | `robot.yaml` schema + 型号占位检查 + 来源/EOL |
| 假绿 | 没跑测试写“全部通过” | 用户信了，实际坏的 | `rf_verify` 只认退出码；证据带指纹会过期 |
| 跳步 | 直接写代码，不定义验收 | 做完了不知道算不算完成 | must/nice/forbidden + trace 覆盖率 |
| 过设计 | 50 元需求上云、上 App、上数据库 | 预算爆炸、装不起来 | 预算 115%/150% + 域裁剪 + 形态默认值 |
| 占位符 | “型号待定”“参数待补” | 交付物不可执行 | 占位符/空实现/假测试扫描 |
| 自评通过 | 实现者自己说“没问题” | 问题留到用户手里 | 独立盲审包 + 六维评分 + 发布包 |

提示词能降低概率，不能给出判据。**判据必须是可执行文件、退出码和证据链。** 这是本插件的第一原则。

## 2. 为什么做成 DSH bundle，而不是技能包

DSH 提供了几个关键能力，只有原生 bundle 才能全部用上：

- **工具注册**：`ctx.tools.register` 把能力变成模型可见的 typed tool，带 JSON schema、参数校验、超时、取消和结构化结果；模型不必记 shell 语法。
- **Skill registry**：`@deepseek-ai/dsh-skill-filesystem` 把 `SKILL.md` 按需加载，正文不常驻上下文；references 在需要时再读。
- **PTC**：注册的工具同样进入 `run_code` 的 SDK，模型可以在一个程序里串起“生成 → 核算 → 检查 → 验证 → 打包”，而不是来回对话。
- **子代理**：独立 context 做只读验证/盲审，实现者不能自审。
- **人机回环**：`ask_user_question` 一次读回，`present` 交付文件，`todo_write`/`create_goal` 管长任务。
- **Patch**：`cordis.patch.yml` 把 Host 插件和 skill provider 挂进 profile；安装/启停交给 Plugin Manager，不手改用户配置。

如果只发一份 prompt 或 Claude Code 风格的 markdown agents，DSH 的工具体系、PTC、取消、结构化结果都用不上，弱模型仍然靠“自觉”。

## 3. 结构

```text
package.json / cordis.patch.yml
    │
    ├── index.js  ── 12 个 rf_* 工具 + 系统提示 + /forge
    │      └── lib/tools.js  参数 schema / 输出 render / execute
    │      └── lib/run.js    Python 子进程 / 项目定位 / JSON 解析
    │
    └── skills/robot-forge/
           ├── SKILL.md            七阶段、12 工具、机器门、红线
           ├── references/         11 篇：spec/workflow/quality/blueprints/stacks/
           │                       archetypes/design/compliance/testing/release/orchestration
           ├── templates/          desktop-companion / wheel-rover
           └── scripts/forgekit/   intake/design/consistency/report/render/check/api/cli/selftest
```

只有一个事实源：`forge/robot.yaml`。BOM、接线、电源、图、README 状态表、docs/09 验收报告都由 `render` 从它派生。模型改 YAML，工具重算；不要手写生成块。

## 4. 为什么是 12 个工具，而不是一个万能工具

| 工具 | 本质 | 失败时 |
|---|---|---|
| `rf_intake` | 愿望 → 形态/预算/默认值/安全旗标 | 违法/伤害 → 拒绝并给安全替代 |
| `rf_blueprints` | 选型目录 | 没有蓝本 → 按配方派生，不假装有 |
| `rf_new` | 生成完整项目 | `blueprint` 必填；目录非空 → 报错，不覆盖 |
| `rf_status` | 状态投影 + 唯一下一步 | 无项目 → 明确说“先创建” |
| `rf_check` | render + S/CST/DSN 规则 | 返回规则 ID、文件、可操作消息 |
| `rf_design` | 设计核算 | 缺参数 → 明确缺什么，不算“通过” |
| `rf_verify` | 真跑 verify.yaml，写证据 | 必需命令失败 → 非零；缺工具 → SKIP |
| `rf_audit` | 六维评分 + 发布判定 | 不通过 → release/beta/blocked |
| `rf_trace` | 需求 × 命令 × 证据矩阵 | must 未覆盖 → 覆盖率 < 100% |
| `rf_review` | 可复现盲审包 | 机器发现与证据一起交给独立评审 |
| `rf_package` | zip + RELEASE.json + SHA256SUMS | 有 error/blocked 拒绝 |
| `rf_evidence` | 人工/仿真/假设证据 | 只记录，不冒充实测 |

设计取舍：

- **一个工具做一件事**，不做“万能 forge”大参数；模型更容易选对。
- **rf_check 自动 render**：弱模型经常忘 render；让工具替它做，检查的是最新状态。
- **rf_verify 不接受模型传“通过”**：通过只来自子进程退出码；模型只能选择跑哪些命令。
- **rf_audit 的结论由代码给出**：0 error + coverage 100% + score ≥85 才是 release。
- **工具返回 `next`**：下一步是唯一动作，不是一段建议；弱模型不需要自己规划。
- **可取消/超时**：长验证不会卡死会话；`exec.signal` 会杀子进程。

## 5. 四层检查器

1. **L1 结构**：必需文件、文档章节、生成块标记、frontmatter、YAML schema。
2. **L2 跨文件一致性**：BOM ↔ robot.yaml、引脚 ↔ 固件 config.h、协议 ↔ 两端代码、需求 ↔ 验证 ↔ 证据、文档 ↔ 生成块。
3. **L3 物理/成本核算**：电流峰值、电源余量、质量/重心、轮速/转弯半径/刹停距离、续航、扭矩、线径、散热、预算。
4. **L4 安全/合规/供应链**：九类安全旗标、docs/07 术语覆盖、compliance/security 块、EOL/交期、许可证。

L3/L4 不是“仿真通过”，只是把明显不成立的方案提前判死。真正的实测仍要 `rf_verify` 和人工证据。

## 6. 证据四态与指纹

| 级别 | 含义 | 是否计入发布覆盖 |
|---|---|---|
| `measured` | 本次命令真实跑过，exit 0 | 是 |
| `manual` | 人真的试用/目视/装配确认 | 是 |
| `simulated` | 仿真/模型算过 | 否 |
| `assumed` | 假设、未验证 | 否 |

每条 measured/manual 证据记录**来源指纹**。改动源码、固件、CAD、仿真、`robot.yaml`、`verify.yaml` 会让旧证据过期；生成文档、README、BOM、图、forge 笔记不计入指纹，避免自我失效。这是 v1.1.3 的关键修复，v2 保留并扩展到 trace/audit。

## 7. 12 类配方的用意

v1 只有两个蓝本，用户问“机械臂/四足/无人机”时模型只能自由发挥。v2 把 12 类形态的默认预算、域、关键件、总线、软件栈、must 需求、验收基准、证据计划和坑固化成 `references/archetypes.md`，并让 `rf_intake` 做分类与默认值。

配方解决的是“从哪开始、什么不能省、怎么验收”，不是“生成一个假项目”。没有完整蓝本的形态会明确标为派生起点，验证覆盖按实际跑过的命令算。

## 8. 两个内置蓝本的用意

- `desktop-companion`：五域全栈（含参数化 CAD），证明“结构 + 电子 + 固件 + 软件 + 仿真”能在一套契约里跑通，¥264/2 周末。
- `wheel-rover`：故意买成品底盘、删掉 CAD 域，证明另一种形态、删域、电池供电、运动安全也能走同一套契约，¥261/2 周末。

蓝本不是形态白名单。一个蓝本只教一件事。蓝本不是“模板仓库越大越好”，而是“每个都能 selftest 全绿”。宁缺毋滥。

## 9. 七阶段与一次读回

接单 → 定案 → 架构 → 建造 → 证明 → 盲审 → 发布。接单只打扰一次：形态、预算、工期、必须/不做；每个问题都带默认值，用户不答也能继续。之后自动推进；只有不可逆/高风险决策才再问。

这是对 MetaGPT 的 SOP、ChatDev 的原子任务、AutoGen 的人机回环、Cognition 的“不要并行强耦合”的折中：保留阶段产物和角色分工，但砍掉每步都等人的仪式。

## 10. 盲审与假绿封堵

- 实现者不自审；`prompts/roles/verifier.md` 只读复核，`reviewer.md` 盲审评分。
- `rf_review` 生成盲审包：复现命令、需求矩阵、最近证据、机器发现、评审 JSON 模板、包哈希；独立评审者的结论由 Lead 记录到 `forge/review.json`（pass / 无未解决 blocker / ≥70 / 指纹与包哈希一致），`rf_audit` 才允许 release。源码或包一变，结论立即失效。
- 评审只看文件、命令输出、证据，不看实现者自述。
- 10 类假绿：mock 冒充实测、空跑、删断言、断言写死、跳过未声明、指标偷换、只测 happy path、无真机路径、生成物过期、证据时间不对。
- 发现 blocker 直接 FAIL；风格问题最多 minor。

## 11. 与已有工作的关系

- **MetaGPT / ChatDev**：角色 + 结构化产物 + 上游订阅；本插件用蓝本和 references 固化产物，用工具强制执行。
- **AutoGen**：人机回环；本插件把打扰压缩到一次读回。
- **adverse / ai-sdlc**：门禁靠构造、实现者不得自审、确定性裁决；本插件把裁决做成 exit code。
- **Anthropic 上下文工程**：产物落盘传引用、按需加载、2–4 个 teammate；本插件用 references + 子代理。
- **Agent Skills / spec-kit / superpowers**：渐进披露、可执行验收、新鲜证据；本插件用 `SKILL.md` + `rf_verify` 落地。
- **MAST 失败模式**：把“不验证就声称完成”变成机器错误，而不是靠 prompt 提醒。

## 12. 评测

`evals/` 12 例：快乐路径、含糊需求、不可能预算、过设计、假绿、可复现、形态分类、安全拒绝、设计核算、跨产物不一致、盲审包、发布打包。判据优先确定性（文件/退出码/正则/预算/证据条数），人工 rubric 只评机器测不了的。默认 3 次、pass^3；A/B 两组（加载 / 不加载本插件）只报告 Δ，不改加载插件组的退出码。

## 13. 已知限制

- 只有两个可跑通蓝本；其余 10 类是按配方派生的起点，不是现成完整项目。
- 固件原生测试与 CAD 导出依赖可选工具；缺工具时只能 SKIP，不能算实测。
- `manual` 证据仍可能被模型编造；插件能做的是把证据写进可审计文件、要求具体观察，并在审计里暴露覆盖不足。
- 价格/版本是 2026-11 快照。
- 未在所有 DSH 版本/所有 profile 上回归；按 0.2.x bundle/patch 契约编写。
