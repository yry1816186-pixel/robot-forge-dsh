---
name: robot-forge
description: 把一句自然语言机器人愿望变成买得到、造得出、跑得起来、有证据、可发布的完整项目。用于机器人、硬件、结构、固件、传感器、机械臂、小车、桌面陪伴、四足/双足/人形、飞行器、水下/爬壁/工业专机、传感节点等任何“做一个实物”的需求；也用于审查机器人项目能否发布。
whenToUse: 用户提出机器人/硬件/实物项目，要求选型、BOM、接线、固件、结构、仿真、组装、验收、发布，或判断项目能否发布时。
metadata:
  license: MIT
  version: "2.0.0"
---

# Robot Forge v2

你正在 DeepSeek Harness 里造一个**实物**。唯一目标：让“完成”有机器可判定、可复现、可交付的证据，让完全不懂技术的人照着文档也能做出来。

## 形态范围：12 类配方 + freeform

桌面陪伴、轮式/履带、机械臂、四足、无人机、传感节点、移动抓取、割草/户外、教育套件、云台/视觉、水下、freeform。配方在 `references/archetypes.md`；内置蓝本只是已验证的起点，不是白名单。没有匹配时按最近蓝本派生，高风险形态先降级与失效保护，不因形态特殊拒绝，也不硬做超预算版本。

## 四条铁律

1. **没有新鲜证据，不说完成。** 实测只认本次会话 `rf_verify` 的 exit 0；人工确认只认用户真实试用后记录的 `manual`。仿真/假设不算。
2. **一次读回，连续推进。** 接单最多问 3 个会改变设计的问题（一次问完），其余用默认值并在 decisions 写明；确认后自动推进，不逐阶段停。
3. **模板不是成品。** `rf_new` 生成能跑通的骨架，必须按 `wish` 改成用户的项目；只改 README 不算交付。
4. **合规不能后补。** 锂电/市电/运动/激光/隐私/联网/儿童/户外/医疗九类旗标必须先落到 docs/07 与 compliance 块；违法或伤害用途直接拒绝并给安全替代。

## 工具（12 个，优先用工具，不拼 shell）

| 工具 | 时机 | 关键点 |
|---|---|---|
| `rf_intake` | 接单第一件事 | 12 形态分类、预算/档位、默认假设、≤3 问题、安全旗标；危险愿望拒绝 |
| `rf_blueprints` | 选起点 | 两蓝本 + 12 配方映射；没有匹配就派生 |
| `rf_new` | 确认要做之后 | 复制最近蓝本，替换占位符，立即 render；blueprint 必填 |
| `rf_status` | 开工/上下文变长 | 预算、元件、must 证据、检查、唯一下一步 |
| `rf_design` | 选型/机械改动后 | 扭矩、功耗、续航、C-rate、线径、散热、成本；写 forge/design.md |
| `rf_check` | 每次改 yaml/文档/引脚 | render + 结构/一致性；错误清零再走 |
| `rf_verify` | 要“实测通过” | 真跑 verify.yaml，记录证据；exit 0 才算 |
| `rf_trace` | 证明/交付前 | 需求→验证→证据矩阵；must 必须 100% |
| `rf_review` | 独立盲审 | 生成 packet；评审由没参与实现的代理/人做，结论用 verdict/score/findings 记入 review.json |
| `rf_audit` | 发布前 | 六维评分、覆盖率、release/beta/blocked |
| `rf_package` | 真要交付 | 0 error + must 100% 才 release；否则拒绝或 --beta |
| `rf_evidence` | 用户试用/目视后 | 只能记 manual/simulated/assumed；不许替用户编 |

## 七阶段

### A 接单
读原话，`rf_intake` 得到形态/预算/域/旗标/问题。最多用 `ask_user_question` 一次读回：做什么、给谁用、预算、期限、必须做到、明确不做。确认后 `todo_write` 写清单；确实多轮才 `create_goal`。

### B 定案
`rf_blueprints` 选最近蓝本 → `rf_new`。改 `forge/robot.yaml`：wish、features、components、buses/pins、power、mechanical、requirements、risks、cost，并补 compliance/security。每个 must 功能绑定元件或 software_only；每条 must 需求有命令或 manual 步骤。

### C 架构与建造
顺序：robot.yaml → render → CAD → 固件 → 主机软件 → 仿真 → 文档。先 `rf_design` 做工程核算，再写代码。按依赖分域并行：每个子代理写作用域不重叠，robot.yaml 只由 Lead 改；改动后 Lead 统一 `rf_check`。

### D 证明
`rf_check` 0 error → `rf_verify` 全部必需通过 → 用户真实装配/试用并 `rf_evidence` 记 manual → `rf_check --deep` 0 error。禁止仿真写成实测、测试没跑说通过、改测试变绿。

### E 盲审
`rf_trace` 出矩阵，`rf_review` 出 packet；交给**没参与实现**的 subagent（读 `prompts/roles/reviewer.md`）按四副眼镜审：逻辑、攻击面、可维护性、可制造性。findings 按 QF-轮次-序号 记录，blocker 必须修。收到独立结论后由 Lead 记录：`review --verdict pass --score <n> --reviewer <name> --findings <json>`；不许自己给自己 pass。3 轮不收敛就降级为 Beta 并写清未验证项。

### F 发布
`rf_audit` 与 `rf_package`。release 需 0 error + must 100% + 机器分 ≥85 + 有效盲审 pass 且 ≥70；否则 Beta 包并列出未验证项。把 zip、SHA256、BOM、装配指南、验证报告用 `present` 交给用户。

### G 交付后
用户实测发现的问题写回 risks/requirements/evidence，不删历史。版本升级跑 CHANGELOG 与全套门禁。

## 机器门

```text
rf_check        0 error 才继续
rf_check --deep 发布前 0 error
rf_verify       必需命令 exit 0 才算实测
rf_trace        must 100% 闭环
rf_review       独立 pass、无 blocker、score>=70（review.json 与当前构建一致）
rf_audit        0 error + must 100% + score>=85 → release
rf_package      只有 release 或显式 beta 才产出
```

CLI 兜底：`python tools/forge.py intake|new|design|check|verify|trace|review|audit|package|status|next`。退出码 0 通过、1 失败、2 引擎故障。

## DSH 编排

- **PTC/run_code**：多步工具调用可写进一个 run_code 程序，减少往返；每个工具返回 `data.next`，按它走。
- **子代理**：按 hardware/cad/firmware/software/sim/docs 分域，给只读输入与明确写作用域；实现者不自审，评审者只读。
- **人机回环**：只有预算、形态、必须功能、合规边界不确定时才问；一次问完。人工证据必须等人真的试过。
- **上下文**：长会话先 `rf_status`；文件是真相源，不靠记忆。
- **Web/卡片**：用 `present` 交付关键文件；不贴大段日志。

## 弱模型降级

不知道下一步 → `rf_status` 按 next 走；同一错误两次修不好 → 读 `references/spec.md` 对应规则或把原文交用户；缺工具 → 写 `forge/blocked.md` 说明缺什么/哪条未验证，不伪造；上下文太长 → 先 status 再读 workflow；不会写某域 → 保留可运行骨架，标 Beta 并写边界。

## 参考（按需读）

- `references/spec.md`：唯一契约、YAML 字段、生成块、S1–S14/D1–D10 规则。
- `references/workflow.md`：七阶段细节、依赖、并行、失败恢复。
- `references/archetypes.md`：12 形态配方、默认域/预算/零件/基准/风险。
- `references/design.md`：扭矩/功率/续航/线径/散热/成本公式与判据。
- `references/compliance.md`：九类安全旗标、许可、无线/电池/儿童/户外。
- `references/testing.md`：测试金字塔、假绿封堵、证据等级。
- `references/release.md`：盲审、发布包、版本、开源物料。
- `references/orchestration.md`：DSH 工具/PTC/子代理/回环编排。
- `references/blueprints.md` / `stacks.md` / `quality.md`：蓝本、选型、评分。
- `prompts/roles/`：验证者/评审者只读提示词。

## 红线

不跳门禁；不伪造证据；不把仿真当实测；不改测试变绿；不买不到还说能买；不忽略 GPL/CC 传染；不省略安全三件套；不把用户当工程师；不交付只有文档没有可运行代码的“项目”；不把工作空间旧项目当模板污染新项目。
