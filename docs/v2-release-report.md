# Robot Forge v2.0 发布报告

- 版本：2.0.0
- 日期：2026-11-11
- 状态：发布候选（Release Candidate），插件自验收通过
- 适用宿主：DeepSeek Harness（DSH）
- 许可证：MIT

## 1. 交付摘要

Robot Forge 不是提示词合集，而是“机器人项目的门禁层”：模型说“做完了”不算数，只有渲染一致、检查通过、真实命令退出码为 0、需求追踪覆盖、独立盲审记录、审计评分达标，才允许生成发布包。

v2.0 把 v1.1.3 的“契约 + 门禁 + 证据 + 双蓝本”骨架扩展为完整研发流水线：

| 维度 | v1.1.3 | v2.0 |
| --- | --- | --- |
| 形态覆盖 | 2 个蓝本 | 11 个具体配方 + freeform |
| 模型工具 | 7 | 12（新增 intake/design/trace/review/package） |
| 工作阶段 | 5 | 7（接单→定案→架构→建造→证明→盲审→发布） |
| 参考手册 | 5 篇 | 11 篇 |
| 检查规则 | S1–S14、D1–D10 | 再增 CST-01–14 跨产物规则、DSN-01–11 设计核算规则 |
| 设计能力 | 无 | 扭矩/转速/爬坡/续航/C-rate/线径 AWG/散热/成本八类核算 |
| 跨产物一致性 | 部分 | 固件引脚↔清单、总线初始化、协议 token、需求↔验证↔证据、BOM↔文档、安全↔合规 |
| 盲审 | 只出报告 | 盲审包 + 独立结论记录 forge/review.json，audit 强制校验 |
| 发布包 | zip | 可复现 zip + RELEASE.json + SHA256SUMS + 独立 .sha256 |
| 评测 | 6 例 | 12 例 |
| 测试 | 1 套 host 测试 | host 全链路 + 21 个 Python 引擎测试 |
| 开源工程 | 基础 | CI 矩阵、SECURITY、CoC、SUPPORT、ROADMAP、issue/PR 模板、验收手册、版本锁步 |

当前插件共 179 个文件、约 0.8 MB：Python 47、JavaScript 3、Markdown 81、JSON 7、YAML 5。

## 2. 结构编排

    plugins/robot-forge/
    ├── index.js                     Host 入口：12 工具、系统提示、/forge
    ├── lib/run.js                   Python 启动器、项目发现、JSON/错误封装、取消
    ├── lib/tools.js                 12 个模型可见工具的 schema 与渲染
    ├── cordis.patch.yml             DSH bundle：挂载 skill / 工具 / 提示
    ├── skills/robot-forge/
    │   ├── SKILL.md                 按需加载：七阶段、12 工具、机器门、红线
    │   ├── references/              11 篇专家手册（唯一真相源）
    │   ├── scripts/forgekit/        intake/design/consistency/report/model/
    │   │                            check/render/api/cli/validate 等
    │   └── templates/               wheel-rover 与 desktop-companion 两个完整蓝本
    ├── prompts/roles/               planner/hardware/embedded/software/sim/
    │                                verifier/reviewer/integrator + README
    ├── evals/                       12 个行为评测 + 确定性判分器
    ├── tests/                       host 测试 + Python 引擎测试
    ├── docs/                        design / acceptance / CONTRIBUTING / 本报告
    ├── .github/                     CI、issue 模板、PR 模板
    ├── SECURITY.md / CODE_OF_CONDUCT.md / SUPPORT.md / ROADMAP.md
    └── README.md / CHANGELOG.md / LICENSE

### 七阶段编排

| 阶段 | 动作 | 退出条件 | 工具 |
| --- | --- | --- | --- |
| A 接单 | 解析愿望、形态、预算、安全旗标 | 12 配方/freeform、≤3 问且每问有默认、must/nice/不做 | rf_intake |
| B 定案 | 选最近蓝本，写一页方案与契约 | 目录完整、占位符可替换、预算口径清楚 | rf_blueprints / rf_new |
| C 架构 | 机械/电子/电源/固件/软件/仿真 | render 成功、check 0 error、design 0 阻断 | rf_design / rf_check |
| D 建造 | 按域实现，Lead 合并 | check --deep 0 error、必需文档齐全 | rf_check |
| E 证明 | 真实命令 + 证据 + 追踪矩阵 | verify 全 required 通过、must 100% 有 measured/manual | rf_verify / rf_trace / rf_evidence |
| F 盲审 | 独立评审者按包复核 | pass、无未解决 blocker、≥70、与当前构建一致 | rf_review |
| G 发布 | 审计 + 可复现打包 | 0 error、覆盖 100%、≥85、有效盲审、release | rf_audit / rf_package |

机器门不是建议：rf_check 0 error、--deep 0 error、rf_verify exit 0、rf_trace must 100%、rf_review 有效 pass、rf_audit ≥85 且无 blocker，缺一不可 release；否则只能是 beta 或 blocked。

## 3. 12 个工具

| 工具 | 作用 | 关键输出 |
| --- | --- | --- |
| rf_intake | 自然语言愿望 → 形态/预算/域/安全旗标/问题 | archetype、confidence、assumptions、≤3 questions、safe_alternatives |
| rf_blueprints | 列出最接近的可运行蓝本 | blueprint、cost、time、domains、tags |
| rf_new | 从蓝本生成完整 0→1 项目 | 目录、vendored 引擎、render 结果 |
| rf_status | 进度、预算、需求、证据概览 | 组件/需求/证据/下一步 |
| rf_check | 渲染 + L1–L4 检查 | issues、stats、next |
| rf_design | 扭矩/续航/C-rate/线径/散热/成本 | 数值 + forge/design.md + 阻断项 |
| rf_verify | 执行 verify.yaml 命令并记证据 | pass/fail/skip、measured/assumed、指纹 |
| rf_audit | 六维评分与发布级别 | score、scorecard、release_level、verdict |
| rf_trace | 需求→验证→证据追踪矩阵 | forge/trace.md、coverage、must 列表 |
| rf_review | 盲审包；可记录独立结论 | packet SHA256、review.json 状态 |
| rf_package | 可复现发布包 | zip、SHA256SUMS、RELEASE.json |
| rf_evidence | 追加人工/仿真/假设证据 | 证据账本、四态等级、指纹 |

所有工具统一返回 {ok, text, data}，错误带可执行的下一步；/forge status|next|check 提供不打扰模型的人工入口。

## 4. 能力覆盖矩阵

图例：✅ 机器强制；◐ 有模板/参考但需人工判断；— 不适用。

| 全栈能力 | 覆盖 | 主要产物 | 机器门/证据 |
| --- | --- | --- | --- |
| 愿望理解与范围控制 | ✅ | 一页方案、must/nice/不做、假设 | intake 形态/预算/≤3 问；wish.story≥20 |
| 形态与架构选型 | ✅ | robot.yaml、architecture、features | 12 配方映射；S1–S3；CST-14 |
| 机械结构/CAD | ◐ | cad/*.py、STL、装配说明、公差 | cad 文件存在；D1–D10；design 质量/扭矩 |
| 电子与接线 | ✅ | docs/03、pinout、bus/power 表、SVG | S4 冲突/保留脚、S5 地址、CST-01/03、渲染一致 |
| 电源与续航 | ✅ | 电源轨、电池、续航、线径 | S6 轨/峰值/续航、DSN-03/04 |
| BOM 与供应链 | ✅ | hardware/bom.csv、docs/01 | S7 预算、S14 占位型号、CST-09/13、D9 |
| 固件 | ✅ | firmware/、config.h、协议、测试 | platformio.ini/main.cpp/test、CST-01/03/04、S4 |
| 主机软件 | ✅ | software/、协议、pytest | pyproject/main.py/tests、CST-04/08、测试质量 |
| 仿真/控制 | ✅ | sim/ 场景、运动学/功率检查 | 场景+README、verify 命令、S9 映射 |
| 测试与假绿封堵 | ✅ | verify.yaml、12 类假绿规则 | 真命令退出码、TRIVIAL 拦截、断言数、CST-08 |
| 安全与合规 | ✅ | docs/07、compliance/security 块 | S11 触发、CST-07/10/11、audit safety 10 |
| 文档完整性 | ✅ | docs/00–10、README、CHANGELOG、LICENSE | 14 必需文档、12 章节、块标记、D7/D8 |
| 需求追踪 | ✅ | forge/trace.md、REQ 表 | must 100%；CST-05/06 |
| 证据链 | ✅ | forge/evidence.jsonl | measured/manual/simulated/assumed；指纹过期 |
| 独立盲审 | ✅ | review-packet.md/json、review.json | pass/无 blocker/≥70/指纹+包哈希一致 |
| 发布与可复现 | ✅ | dist/*.zip、RELEASE.json、SHA256SUMS | 0 error+100%+≥85+有效盲审；固定 zip 时间 |
| DSH 编排 | ◐ | 系统提示、skill、子代理角色、PTC 参考 | 写作用域不重叠；Lead 合并后复检 |
| 开源工程 | ✅ | CI 矩阵、SECURITY/CoC/SUPPORT/ROADMAP、模板 | validate 0/0、CI 全绿、版本锁步 |

覆盖边界：配方给的是“这类机器人通常怎么搭、哪些件不能省、验收看什么”，不是形态白名单；没有完整蓝本的形态会明确标注为派生起点，不假装已验证。
## 5. 质量验收标准

### 5.1 插件自身出厂验收（docs/acceptance.md）

| 项目 | 权重 | 通过线 |
| --- | --- | --- |
| 结构与版本（validate 0 error 0 warn、四处版本一致） | 15 | 0 错 0 警 |
| Host 12 工具测试 | 20 | 全绿 |
| Python 引擎测试 | 20 | 21/21 |
| 两蓝本全量自检与冒烟 | 20 | check 0 error、verify 通过、release 可达 |
| 生成质量抽检 | 10 | 6 文档 + 4 代码无占位/TODO |
| 安全与合规 | 10 | 越权/伤害用途拒绝、安全旗标落文档 |
| 开源物料 | 5 | npm pack 含 README/LICENSE/SECURITY/CI |
| 总分 | 100 | ≥95 可发布；≥80 Beta；<80 不可发布 |

### 5.2 生成项目验收（六维 100 分）

| 维度 | 分 | 判定 |
| --- | --- | --- |
| 买得到（BOM/价格/来源/替代料） | 15 | 缺来源、EOL、假货风险扣分 |
| 造得出（结构/装配/公差/工具） | 20 | CAD 缺失、装配不可执行扣分 |
| 跑得起来（固件/软件/仿真/真实命令） | 25 | 未验证、命令失败扣分 |
| 说得清（文档/接线/决策/复现） | 15 | 文档缺章、术语不一致扣分 |
| 证得了（需求→验证→证据） | 15 | must 无证据、指纹过期扣分 |
| 安全与许可 | 10 | 锂电/市电/运动/激光/隐私/联网缺口扣分 |

规则：每 error −6、每 warning −1；evidenced 按 must 覆盖率给分；D4 不重复扣。release = 0 error + must 100% + score ≥85 + 有效盲审 pass（无未解决 blocker、≥70、与当前构建一致）；缺盲审或结论过期只能 beta；needs_revision/reject 直接 blocked，且 blocked 不能靠 --beta 绕过。

### 5.3 证据四态

- measured：真实命令执行且退出码为 0，带命令与指纹；
- manual：用户真实试用后记录，必须写 note；
- simulated：仿真/Mock，不替代实测；
- assumed：缺工具或未执行，明确标未验证。

模型不得替用户写 manual；源码或关键产物改变后，旧证据指纹失效，必须重跑。

### 5.4 可复现发布包

- zip 内每个文件的日期、权限、顺序固定；
- RELEASE.json 记录逐文件 SHA256、六维分、release_level、fingerprint；
- SHA256SUMS 覆盖全部文件，另写独立 .sha256；
- 同一构建重复打包 SHA256 必须完全相同（已在 E2E 验证）。

## 6. 相对 v1.1.3 的关键增强点

1. 从 2 个蓝本到 12 形态配方：新增机械臂、四足、无人机、传感节点、移动抓取、割草、教育套件、云台、水下与 freeform，每类给出关键件、必须项、验收基准、安全旗标与常见坑。
2. 从“能生成”到“能算”：design.py 计算轮式扭矩/转速/爬坡、臂关节扭矩、续航、C-rate、AWG 线径、散热密度、成本上限；数值不达标直接阻断，不再靠感觉选型。
3. 从单文件检查到跨产物一致性：CST-01–14 校验固件 GPIO↔robot.yaml、I2C 初始化、主机协议 token↔固件、must↔verify↔证据、BOM↔docs/01、密钥、测试质量、EOL、安全术语。
4. 从“自评”到独立盲审门：review-packet 含复现命令/追踪矩阵/证据/机器发现/哈希；独立评审者给结论，Lead 记录 review.json；audit 只认当前构建的 pass，源码一变即失效。
5. 从“能跑”到“可复现发布”：固定 zip 时间/权限/顺序，RELEASE.json 逐文件哈希，重复打包 SHA 相同；blocked 不能靠 beta 绕过。
6. 从 5 阶段到 7 阶段、7 工具到 12 工具：接单、定案、架构、建造、证明、盲审、发布每阶段都有唯一入口和退出条件；工具只做一件事，返回结构化问题与下一步。
7. 从“提示模型”到“激发 DSH”：systemPrompt 只放红线，细节按需加载 skill；明确 PTC、子代理写作用域、todo/goal、人机回环、present 的用法；弱模型降级路径写入参考。
8. 从“示例评测”到 12 例行为评测：新增形态分类、安全拒绝、设计数值、跨产物不一致、盲审包、发布包、水下 freeform；判据优先确定性，人工 rubric 只评机器测不了的。
9. 从“能测”到“可回归”：21 个 Python 引擎测试 + host 全链路测试，覆盖 review 记录/失效、package 拒绝/确定性、证据过期、路径穿越、cwd 越界、空跑、可选失败。
10. 从“仓库”到“开源项目”：CI（Ubuntu/Windows × Python 3.11–3.13 × Node 22/24）、SECURITY、CoC、SUPPORT、ROADMAP、issue/PR 模板、验收手册、贡献流程、版本锁步校验。
11. 从“文档提到”到“机器可查”：11 篇参考成为唯一真相源，validate 检查 12 工具白名单、11 篇参考、必需文档、SKILL 大小、缓存/占位/版本一致性。
12. 从“可能污染”到“路径安全”：项目路径按相对路径过滤，不再因宿主绝对路径含 build/dist 而跳过整个项目；指纹排除生成物，避免 check 自身导致证据过期。

## 7. 验证证据（本轮实测）

| 命令 | 结果 |
| --- | --- |
| python -B skills/robot-forge/scripts/validate_plugin.py | 0 错误 · 0 警告 |
| python -B skills/robot-forge/scripts/forge.py selftest | 2.0.0；desktop 0 error/10 warn、wheel 0 error/9 warn；两蓝本 verify 通过；自检通过 |
| python -B -m pytest tests -q -p no:cacheprovider | 21 passed（2.54s） |
| node --test tests/plugin.test.mjs | 1 file pass（24.2s） |
| E2E：new→design→verify→manual evidence→trace→review→audit→record pass→audit→package ×2 | 盲审前 beta；记录 pass 后 release；score 97；再生成 packet 仍 release；两次 SHA256 相同 0c15bb4c…0696d4（71 文件，163,506 字节） |
| npm pack --dry-run | 179 文件（含 .github/CI、README/SECURITY/templates/evals），打包体积 301 KB，无缓存目录 |

E2E 关键语义：未记录 blind review 时 audit 只能 beta；记录 pass/90/reviewer 后 release；改源码后 review.valid=false、audit 回到 blocked；不静默发布。

## 8. 已知限制

1. 插件不能替代真实焊接、装配、上电与长时间老化；没有实测证据时它只会标 beta/未验证。
2. 内置完整蓝本仍只有 2 个；其余形态是“配方 + 最近蓝本派生”，深度低于这两个蓝本，不假装已验证。
3. 价格是 2026-11 人民币快照，元器件价格/交期会变；关键件需在下单前复核。
4. 未对所有历史 DSH 版本做回归；engines 要求 dsh >= 0.2.0，CI 覆盖当前 Node/Python 矩阵。
5. 盲审的“独立性”是流程约束（reviewer 角色、Lead 记录、禁止自评），不是密码学身份认证；开源协作中仍需维护者把关。
6. 可复现 zip 依赖文件 mtime 或 SOURCE_DATE_EPOCH；跨机器/跨 checkout 的字节一致需要统一时间源。
7. 高风险形态（无人机、割草、水下、市电、激光）只提供工程与合规参考，不构成法律/安全认证；必须由具备资质的人复核。
8. 12 类配方不是形态白名单；完全未命中的专机走 freeform，能力覆盖取决于最近蓝本与新增验证。

## 9. 快速开始

    dsh plugin add ./plugins/robot-forge

对话示例：

> 做一个能跟着我走、避开障碍、桌面陪伴聊天的小机器人，预算 800，两周内能跑起来。

模型应先加载 robot-forge skill，调用 rf_intake 得到形态/预算/≤3 个带默认值的问题，再 rf_blueprints → rf_new → rf_design → 建造 → rf_verify → rf_trace → rf_review → rf_audit → rf_package。

## 10. 发布检查单

- [x] 版本四处一致（package.json / forgekit / SKILL / CHANGELOG）
- [x] validate 0 错误 0 警告
- [x] 21 个 Python 测试通过
- [x] host 全链路测试通过
- [x] 两蓝本 selftest 通过
- [x] E2E 盲审门与可复现打包验证
- [x] npm pack 文件表检查
- [x] README / design / acceptance / CONTRIBUTING / CHANGELOG 同步
- [x] SECURITY / CoC / SUPPORT / ROADMAP / issue / PR 模板
- [x] 清理 __pycache__ / .pytest_cache