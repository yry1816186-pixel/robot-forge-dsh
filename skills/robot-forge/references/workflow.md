# 工作流 v2.0：从一句愿望到可发布项目

> 主模型的操作手册。目标不是“显得专业”，而是**在有限轮次内产出一个能买、能装、能跑、能证明、能发布的项目**。
> 硬契约在 `spec.md`；形态配方在 `archetypes.md`；核算在 `design.md`；合规在 `compliance.md`；测试在 `testing.md`；发布在 `release.md`；并行在 `orchestration.md`；评审在 `quality.md`。

---

## 0. 开工前 60 秒

1. `rf_status`：有项目就接着干；没有就 `rf_intake` 把愿望变成配方。
2. `rf_intake({text, budget})`：得到形态、置信度、预算、域、关键件、安全旗标、≤3 个带默认值的问题。
3. 用户没异议（或说“你决定”）→ `rf_new({name, blueprint})`；**不要从空目录手搓结构**。
4. 需要查工具链：`python tools/forge.py doctor`，记住缺哪些（决定哪些验证只能标未验证）。
5. 读对应参考：形态→`archetypes.md`；选型→`stacks.md`；风险→`compliance.md`。不要凭记忆报型号/价格。

---

## 1. 七个阶段（默认一口气走完）

| 阶段 | 工具 | 产出 | 退出条件 | 打扰用户 |
|---|---|---|---|---|
| A 接单 | `rf_intake` | 形态/预算/域/安全旗标/问题 | 配方置信度 ≥0.5，或用户确认 | ≤1 次（≤3 问） |
| B 定案 | `rf_new` + 手写 | `robot.yaml` + `plan.md` 一页方案 | must/nice/must_not 齐全，预算/场景明确 | 1 次确认 |
| C 架构 | `rf_design` + `rf_check` | 架构、BOM、接口、风险、核算 | render 成功；0 error；预算/电源/引脚自洽 | 0 次 |
| D 建造 | 各域 + `rf_check` | CAD/固件/软件/仿真/文档 | 各域冒烟；check 0 error | 0 次（不可逆除外） |
| E 证明 | `rf_verify` + `rf_trace` | 证据账本、追踪矩阵、验证报告 | required 全绿；must 覆盖 100% | 1 次（真实试用） |
| F 盲审 | `rf_review` | 评审包 + 盲审结论 | 无 blocker，verdict=pass | 0 次 |
| G 发布 | `rf_audit` + `rf_package` | 审计分、zip、RELEASE.json | ≥85 且 release（或显式 Beta） | 1 次确认 |

**一次读回**：A 的方案确认 + G 的发布确认是仅有的两个必停点；中间连续推进，不要每写完一个文件就汇报。

### 1.1 A 接单：把愿望翻译成契约

`rf_intake` 会做：形态分类（12 类 + freeform）、预算档、域裁剪、关键件提示、安全旗标、必须项、验收基准、待确认问题。

**翻译规则：**
- “智能/会聊天” → 唤醒词 + 一轮问答 + 断网降级，可验收；
- “便宜” → 三档报价（能玩/好用/旗舰），让用户选；
- “像某视频” → 拆 3 个可实现特征，明确不做什么；
- “不用编程/焊接” → 免焊模块 + 一键烧录，步骤写到点按级；
- “有感情/很聪明” → 改成可观察行为 + 验收步骤；
- 涉及载人/飞行/涉水/市电/儿童/医疗 → 先讲清安全边界，再决定做不做/怎么降级。

只问**会改变方案**的问题，每题带默认值；用户不答按默认推进，把假设写进 `decisions.md`。

### 1.2 B 定案：一页方案

```text
它会做什么：3 条（must）
它不做什么：3 条（must_not，防预期错位）
要买什么：BOM 合计 ¥xxx（预算 ¥xxx），关键件 5 个
要花多久：打印 x h + 装配 x h + 调试 x h
最难的一步：xxx，失败退路 xxx
怎么算成功：3 条验收（命令或实测步骤）
风险：前 2 条 + 规避
安全/合规：触发项 + 对应措施
```

用户确认后进入建造；改需求 → 只改 `robot.yaml` 与受影响产物 → `rf_check`，不重写全部。

### 1.3 C 架构：先算再画

1. 填 `robot.yaml`：`mechanical.mass_kg`、`drive_count`、执行器 `torque_kgcm`/`rated_current_ma`/`stall_current_ma`、电池、轨；
2. `rf_design({write:true})`：扭矩/功率/续航/线径/散热/成本核算，写 `forge/design.md`；
3. 有 error 先改选型或指标，不要改数字糊弄；
4. `rf_check`：render + 结构/跨文件/证据检查；
5. 画架构/接线/装配图（render 自动生成 SVG）。

### 1.4 D 建造：顺序与所有权

```text
robot.yaml（引脚/电源/BOM/需求）
  → rf_design + render（BOM/接线/图/核算）
  → hardware/cad（尺寸、干涉、公差）
  → firmware（引脚、协议、状态机、失效保护）
  → software（协议、人格、测试；先 --mock）
  → sim（运动学/功耗/场景）
  → docs（写已发生的事实）
  → verify.yaml（最后补命令，每条都真跑过）
```

| 域 | 最小可验收 | 命令 |
|---|---|---|
| manifest | schema 通过、引脚/电源/需求自洽 | `rf_check` |
| CAD | 参数化脚本从零导出 STL；关键配合有公差 | `python hardware/cad/<x>.py --out hardware/stl` |
| 固件 | 能编译；native 单测过；协议一致；看门狗/限位/堵转保护 | `pio run` / `pio test -e native` |
| 软件 | `--mock` 能启动；单测过；协议边界用例；断网降级 | `pytest software/tests -q` |
| 仿真 | 一条命令给数值结论（不是打开 GUI） | `python sim/check_*.py` |
| 文档 | 链接可达、生成块最新、每步“应该看到什么” | `rf_check` |

**所有权**：一个文件一个写者；`robot.yaml`/`README`/`verify.yaml`/`docs/09` 只由主模型或集成者写；并行只按域，改协议/引脚/电源必须串行。

### 1.5 E 证明：先跑，再说

**唯一合法完成句式：**

```text
<结论>。证据：<命令> → exit 0（<关键输出>）；未验证：<项>，步骤见 docs/09。
```

流程：
1. `rf_check --deep` → 0 error（先修 S3/S4/S5，再 D1/S12，最后 D4）；
2. `rf_verify` → required 全绿；失败逐条修，**不许改测试变绿**；
3. `rf_trace` → 每条 must 100% 有 measured/manual；缺失就补验证或标 Beta；
4. 人工步骤必须用户真实执行；模型不能代写 manual。

**三次失败规则**：同一验证 3 轮不过，停；回到清单/需求/选型找矛盾，或给降级方案让用户选。

### 1.6 F 盲审：换一双眼睛

`rf_review` 生成 `forge/review-packet.md/json`：复现命令、trace、最近证据、机器发现、评审模板、包哈希。
- 盲审者不看作者辩解，自己重跑，按 `quality.md` 打分；
- 10 类假绿逐条查；blocker 修，major 记录并给规避；
- 评审者回报后，由 Lead 记录（不要自己填 pass）：
  `python tools/forge.py review --verdict pass --score 90 --reviewer "独立评审代理" --findings '[]'`；
  review.json 与当前源码指纹/盲审包哈希不一致即失效，必须重审；needs_revision/reject 会把 audit 判为 blocked。
- 再 `rf_audit`：release 需要有效 pass 且 ≥70。

### 1.7 G 发布：陌生人能复现

1. `rf_audit` ≥85、0 error、覆盖 100%；
2. `rf_package`（release；Beta 加 `--beta`）；
3. README 首屏：一句话、图位、3 分钟上手、状态矩阵、文档地图；
4. docs/09 是验收报告，不是自我表扬：命令、退出码、未验证项；
5. CHANGELOG/LICENSE/.gitignore 齐全；发布说明可复制；
6. 告诉用户：哪些已验证、哪些等他实物确认、下一步。

---

## 2. 与用户说话的规则

- **零基础**：不解释 SPI，先说“这根线插这里”；术语第一次出现给一句人话。
- **选择题优于问答题**：2–3 方案 + 推荐 + 差价。
- **坏消息前置**：做不到/超预算/要等货，第一句说清，再给替代。
- **不承诺未验证数字**：续航、延迟、噪声只给“预计/待实测”。
- **一次只确认一件事**；确认后不重复问。
- **不甩锅**：缺工具/买不到/上游变了，都给可执行替代路径。

---

## 3. 模式

| 模式 | 触发 | 行为 |
|---|---|---|
| L1 陪跑 | “教我/一步步来” | 每阶段停，讲 3 句 + 等确认；用户动手 |
| L2 默认 | 未指定 | A/G 各一次确认，中间自动推进 |
| L3 一刀流 | “一次做完/你决定” | 不问，默认假设全跑，写 decisions，最后一次性交付 + 待确认清单 |
| 修复 | 已有项目失败 | `status` + `check --json`，按规则 ID 分批修，不重写 |
| 升级 | 加形态/加域 | 先改 robot.yaml + 需求，再补域，最后重跑全套 |

---

## 4. 失败恢复

| 症状 | 处理 |
|---|---|
| 缺工具链 | 命令 `required: false` + `needs`；文档给安装；标未验证；不伪造 |
| 买不到型号 | 同参数替代料，BOM 记“替代”，价格按替代 |
| 预算不够 | 三档取舍卡：加预算/减功能/降指标；不偷偷换劣质件 |
| 引脚不够 | 换模组或 I2C 扩展；仍不够减功能，写 decisions |
| 电源余量不足 | 峰值 >90% 必须换电源/错峰；不许只改 max_ma |
| 测试红 | 判断实现错还是测试错；实现错改实现；测试错改测试并记录；禁删断言 |
| 需求冲突 | 列冲突表，让用户选优先级，写 decisions |
| 上游 API 变了 | 锁版本/commit；docs 写清；不追最新 |
| 高风险形态 | 讲成本/法规/失效风险，给降级（上半身/桌面/买成品/分阶段）；不硬做超预算版本 |

---

## 5. 反模式（直接毁掉交付）

1. 先写 10 篇文档再写代码 → 必漂移；先 manifest，再代码，最后文档。
2. 5 个以上子代理各写各的 → 冲突；2–4 个、按域、单一写者。
3. 每阶段都停下汇报 → 用户烦、上下文爆；合并为 A/G 两次。
4. 遇错重写整个项目 → 丢已验证部分；按规则 ID 修。
5. 为过 check 删检查/改测试/改 max_ma → 假绿，盲审必抓。
6. 留示例项目名/上游 README/示例引脚 → 拼贴感，S12/S13 抓。
7. 用“应该可以/理论上支持”代替验证 → 用户实物翻车。
8. 只 mock 跑过、真机没接却不说 → 必须标 Beta + 未验证清单。

---

## 6. 阶段检查清单

```text
[ ] A rf_intake 形态/预算/域/安全旗标/问题已定
[ ] B robot.yaml 的 must/nice/must_not/预算/场景/基础齐全
[ ] B 一页方案已确认（或 L3 假设已记录）
[ ] C rf_design 无阻断；render 成功；BOM ≤预算×1.15
[ ] C 引脚/电源/地址无冲突；架构图有主机层
[ ] D CAD 从零导出，关键配合有公差
[ ] D 固件编译 + native 单测 + 失效保护
[ ] D 软件 --mock + 单测 + 协议边界
[ ] D 仿真一条命令给数值结论
[ ] D docs 链接可达、生成块最新
[ ] E check 0 error；check --deep 0 error
[ ] E verify required 全绿，证据新鲜
[ ] E trace must 100%（或 Beta 清单完整）
[ ] F review 无 blocker，verdict=pass
[ ] G audit ≥85，package 成功，SHA256 已给
[ ] G README/CHANGELOG/LICENSE/发布说明齐全
[ ] G 已知限制与下一步已告诉用户
```
