# 贡献指南

Robot Forge 是 DeepSeek Harness 的原生 bundle。每个部件都可以单独改进：一个更好的蓝本、一条更准的检查、一段更清楚的文档，都会直接放大所有下游模型的表现。先读 <code>docs/design.md</code> 了解为什么这样设计，再按下面的约定提交。

## 开发环境

- Python **3.10+**；插件引擎只用标准库，测试可选 <code>pytest</code>；
- Node **20+**（DSH 自带 Node；Host 插件是纯 ESM，无运行时依赖）；
- 可选：<code>pytest</code>、<code>build123d</code>、<code>mujoco</code>、<code>pio</code>、<code>kicad-cli</code>。

四条必跑命令：

    # 1) bundle 结构、清单、patch、skill、模板、缓存、版本锁步
    python scripts/validate_plugin.py

    # 2) Host 工具运行时（真实调用 Python 门禁，覆盖 12 个工具）
    node --test tests/plugin.test.mjs

    # 3) Python 引擎单测（intake/design/consistency/report）
    python -m pytest tests/ -q

    # 4) 两个蓝本从零生成 → design → check → verify → audit
    python skills/robot-forge/scripts/forge.py selftest

迭代时可用 <code>selftest --quick</code> 跳过 verify。提交前三条必须全绿；缺可选工具导致的 SKIP 不算失败，但 PR 里要写清。

## 目录与所有权

    package.json                 DSH bundle 清单：name/version/type/exports/dsh.bundle.patch
    cordis.patch.yml             插入 Host 插件 + skill-filesystem
    index.js                     Host 入口：apply/inject、12 个工具、系统提示、/forge
    lib/tools.js                 工具定义（schema、输出、execute）
    lib/run.js                   Python 子进程、项目定位、JSON 解析
    locale/zh.json en.json       插件页标题/描述
    icon.svg                     插件图标（原创，≤256 KiB）
    skills/robot-forge/          SKILL.md + references + templates + Python 引擎
    prompts/roles/               给 subagent 的只读提示词模板（不是自动加载的 agent）
    evals/                       12 条提示词 + 确定性判据
    tests/plugin.test.mjs        Host 工具运行时测试
    tests/test_engine.py         Python 引擎单测
    docs/design.md               设计依据（改架构时同步）
    docs/CONTRIBUTING.md
    docs/acceptance.md           发布验收标准
    SECURITY.md / CODE_OF_CONDUCT.md / SUPPORT.md / ROADMAP.md

一条 PR 尽量只动一个域。跨域改动（例如改 <code>robot.yaml</code> 字段）必须同时更新：<code>model.py</code>、<code>check.py</code>、<code>references/spec.md</code>、模板、selftest，缺一不可。

## Host 插件规则

- <code>apply(ctx)</code> 里注册的每个资源都要返回 disposer，并在 <code>apply</code> 的返回值里统一清理；
- 工具定义必须是普通对象：<code>name</code>、<code>description</code>、标准 JSON Schema 的 <code>parameters</code>、<code>output.schema</code>、<code>output.render</code>、<code>execute(args, exec)</code>、<code>timeoutMs</code>；
- <code>execute</code> 必须观察 <code>exec.signal</code>，长命令设置合理 <code>timeoutMs</code>，不要把 15 分钟的命令塞进 30 秒超时；
- 返回值固定为 <code>{ ok, text, data }</code>：<code>text</code> 给模型，<code>data</code> 给程序/UI；失败也返回结构化对象，不要只抛字符串；
- 项目根从 <code>args.project</code> → 会话 <code>agent.session.cwd</code> → 唯一子项目解析；不要猜 <code>process.cwd()</code> 一定是项目；
- 工具名统一 <code>rf_</code> 前缀；新增/删除工具时同步 <code>scripts/validate_plugin.py</code> 的期望集合、README、SKILL；
- 不要 import <code>@deepseek-ai/*</code> 私有包：Host 插件应零运行时依赖，避免 profile 里解析不到；
- 不要在插件里读写 profile 的 <code>cordis.patch.yml</code>；安装/启停交给 Plugin Manager 或 <code>dsh plugin</code>。

## Patch 规则

- 第一行必须是本包 <code>robot-forge-dsh</code> 的 insert，否则安装后没有工具；
- 第二条 insert 是 <code>@deepseek-ai/dsh-skill-filesystem</code>，<code>providerName</code> 用 <code>robot-forge</code>，<code>includeDefaultRoots: false</code>，<code>bundledSkillDir</code> 必须用 <code>createRequire(baseUrl).resolve('robot-forge-dsh/package.json')</code> 解析包路径——不要拼接固定安装前缀；
- 不要在这里插入标准预设已经有的 skill registry / tool executor；重复会冲突；
- 改 patch 后跑 <code>validate_plugin.py</code>；它会把 <code>!!js</code> 去掉后做 YAML 结构校验。

## SKILL.md 与 references

- frontmatter 只用 DSH 认识的字段：<code>name</code>、<code>description</code>、<code>whenToUse</code>、<code>metadata</code>、<code>disable-model-invocation</code>、<code>user-invocable</code>；
- 不要写 <code>disableModelInvocation</code> / <code>modelInvocable</code> / <code>userInvocable</code>，DSH 会显式拒绝；
- 正文 ≤8192 字符（标准预设会裁剪更长的工具结果）；细节放 references；
- 引用路径用相对路径且必须存在；<code>validate_plugin.py</code> 会检查 11 篇 reference 和两个 role prompt；
- 中文为主，专业术语保留英文原词；不要写空泛的“请仔细思考”。

## 新增一个蓝本

蓝本是插件能力的上限证明。**宁缺毋滥**：一个 selftest 全绿的新蓝本，价值高于五个半成品。

### 1. 复制骨架

    cp -r skills/robot-forge/templates/desktop-companion \
          skills/robot-forge/templates/<your-blueprint>

移动形态可从 <code>wheel-rover</code> 起手，它示范了“删掉 CAD 域、买成品底盘”。

### 2. 改 blueprint.json

    {
      "name": "中文展示名",
      "slug": "<blueprint-id>，必须等于目录名",
      "one_liner": "一句话：给谁、做什么、多少钱",
      "cost_cny": 0,
      "time": "2 个周末（约 10 小时）",
      "difficulty": "入门（需要什么工具、不需要什么）",
      "domains": ["hardware", "cad", "firmware", "software", "sim"],
      "needs": ["焊接", "3D 打印"],
      "tags": ["关键词1", "关键词2"]
    }

<code>domains</code> 决定生成哪些域目录，也决定 <code>check</code> 对哪些域做结构校验。

### 3. 保留四个占位符

    {{NAME}}       项目中文名
    {{SLUG}}       项目 slug
    {{DATE}}       YYYY-MM-DD
    {{BLUEPRINT}}  蓝本 id

<code>rf_new</code> 会替换；<code>check</code> 的 S12 会把残留判为 error。

### 4. 改到“另一个项目”

至少改：形态与场景、预算与工期、引脚/总线/电源（与固件 <code>config.h</code> 一致）、需求与验证、文档里的具体事实、CAD 参数与仿真脚本。

### 5. 验收

    python skills/robot-forge/scripts/forge.py new 测试名 --blueprint <id> --dir <临时目录>
    cd <临时目录>
    python tools/forge.py check
    python tools/forge.py verify
    python skills/robot-forge/scripts/forge.py selftest

要求：check 0 error；verify exit 0（缺可选工具 SKIP 不算失败）；selftest 全绿。

### 6. 更新索引

- <code>references/blueprints.md</code> 加“关键词 → 蓝本”；
- 本 README 的蓝本表；
- <code>evals/</code> 若代表新形态，加一条快乐路径用例。

## 评测

- 能确定性判的绝不交给 LLM：文件、glob、退出码、正则、预算、证据条数优先；
- 用例必须能区分“真的跑了”与“说跑了”；
- 人工 rubric 只评机器测不了的东西；
- 默认 3 次、pass^3；报告 A/B 两组（加载 / 不加载本插件），Δ 只报告不改加载插件组的退出码；
- 新增/修改工具时，在 <code>tests/plugin.test.mjs</code> 里加一条真实调用（生成临时项目，不写回仓库）。

## 版本与发布

- 改行为 → 升 <code>package.json</code> 的 <code>version</code>（语义化版本）；
- 同步 <code>forgekit/__init__.py</code>、<code>SKILL.md</code> 的 <code>metadata.version</code>、<code>CHANGELOG.md</code>；<code>validate_plugin.py</code> 的 P047 会检查四处版本一致；
- 同步 <code>CHANGELOG.md</code>（本包根目录）：改了什么/为什么/迁移方式；
- 不提交缓存：<code>__pycache__</code>、<code>.pytest_cache</code>、<code>.ruff_cache</code>、生成的 STL、临时评测项目；
- 若发布到 npm，<code>files</code> 必须包含 <code>index.js</code>、<code>lib</code>、<code>cordis.patch.yml</code>、<code>locale</code>、<code>icon.svg</code>、<code>skills</code>；发布前用 <code>npm pack --dry-run</code> 核对文件表。

## 许可与来源

- 插件代码与文档 MIT；
- 新增第三方代码/资产：PR 写清来源、许可证、是否可商用；
- 禁止把 GPL/AGPL 代码复制进模板；引用 GPL 工具时只写“可选外部工具”；
- 价格、型号、星数、版本号注明快照日期（当前为 2026-11）。

## PR 检查单

- [ ] <code>python scripts/validate_plugin.py</code> 0 error
- [ ] <code>node --test tests/plugin.test.mjs</code> 通过
- [ ] <code>python skills/robot-forge/scripts/forge.py selftest</code> 通过（或说明为何 SKIP）
- [ ] 新蓝本：new → check（0 error）→ verify 全过
- [ ] 改了契约：<code>spec.md</code>、模板、检查器、selftest 同步
- [ ] 版本只改一处（package.json）并写 CHANGELOG
- [ ] PR 描述含：动机、改了什么、怎么验证（贴命令与结果）、已知限制
