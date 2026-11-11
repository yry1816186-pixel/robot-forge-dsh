# 发布验收标准（v2.0）

这份文档是 Robot Forge 插件自身的“出厂验收”，不是生成项目的验收。生成项目的验收由 `rf_audit`、`rf_trace`、`rf_review` 判定。

目标：任何人拿到这个仓库，按本文档逐条执行，都能得到**可复现的通过/不通过结论**。不接受“看起来没问题”。

---

## 1. 验收环境

| 项 | 要求 |
|---|---|
| 操作系统 | Windows 10/11 或 Ubuntu 22.04+ |
| Python | 3.11 / 3.12 / 3.13（矩阵），最低 3.10 |
| Node.js | 22 / 24（矩阵） |
| DSH | 0.2.x bundle/patch 契约 |
| 网络 | 运行测试不需要；安装依赖需要 |
| 可选工具 | PlatformIO、build123d、MuJoCo（缺失时对应验证 SKIP，不算通过） |

在干净 clone 中执行，不依赖本机已有项目或缓存。

---

## 2. 结构与版本

```bash
python scripts/validate_plugin.py
```

**必须**：0 error，0 warning。

覆盖：

- `package.json` 名称 `robot-forge-dsh`、版本 `2.0.2`、ESM、exports、`dsh.bundle.patch`；
- `cordis.patch.yml` 插入 Host 插件与 `@deepseek-ai/dsh-skill-filesystem`，包路径从 profile 解析；
- Host 文件语法、`export function apply`、`export const inject`、`systemPrompt.section`；
- **12 个 `rf_*` 工具**齐全；
- `icon.svg`、`locale/zh.json`、`locale/en.json` 有标题/描述；
- `SKILL.md` frontmatter 字段合法、≤8192 字符、**11 篇 references** 齐全；
- 两个蓝本 `blueprint.json` 必填字段、slug=目录名；
- `docs/design.md`、`docs/CONTRIBUTING.md`、`docs/acceptance.md`、`SECURITY.md`、`CODE_OF_CONDUCT.md`、`tests/plugin.test.mjs` 存在；
- 无 `__pycache__` / `.pytest_cache` / `.ruff_cache` / `.mypy_cache`；
- **P047 版本锁步**：`package.json`、`forgekit/__init__.py`、`SKILL.md metadata.version`、`CHANGELOG.md` 四处一致。

---

## 3. Host 运行时（12 工具）

```bash
node --test tests/plugin.test.mjs
```

**必须**：全部通过，且测试真实创建临时项目、真实调用 Python 引擎，不 mock 门禁结果。

覆盖：

- apply 注册 12 工具 + 1 systemPrompt section + /forge；
- 每个工具 schema 合法、render 返回 text；
- `rf_intake` 形态分类与预算；
- `rf_new` 缺 blueprint 拒绝、slug 穿越拒绝；
- `rf_check` 0 error、deep 语义；
- `rf_design` 生成 `forge/design.md` 且含扭矩/续航；
- `rf_verify` 全量/子集/可选失败/空跑/cwd 越界/过期指纹；
- `rf_trace` 生成 `forge/trace.md`，must 覆盖可读；
- `rf_review` 生成 packet + SHA256；带 verdict 时记录 `forge/review.json`；改源码后 review 失效、audit 回到 beta/blocked；
- `rf_audit` 六维分与 release_level；
- `rf_package` 拒绝 blocked、允许/拒绝 beta；
- `rf_evidence` manual 无 note 拒绝、未知 REQ 拒绝、measured 拒绝；
- dispose 清理全部注册。

---

## 4. Python 引擎单测

```bash
python -m pytest tests/ -q
```

**必须**：全部通过。覆盖：

- `intake`：12 形态分类、预算覆盖、安全旗标、阻断用途、≤3 问题；
- `design`：扭矩公式、缺质量、续航、C-rate、线径 AWG、预算、散热；
- `consistency`：GPIO 冲突、I2C 不一致、需求未映射、密钥、测试质量、安全文档术语；
- `report`：trace 覆盖率、review 包哈希、review 记录/失效、package 拒绝条件。

---

## 5. 蓝本全量自检

```bash
python skills/robot-forge/scripts/forge.py selftest
```

**必须**：两蓝本均 check 0 error、verify 通过、design 0 阻断、audit 可解释、selftest exit 0。

补充手工冒烟（每个蓝本）：

```bash
python skills/robot-forge/scripts/forge.py new 验收车 --blueprint wheel-rover --dir <临时目录>
cd <临时目录>
python tools/forge.py design --write
python tools/forge.py check
python tools/forge.py verify
python tools/forge.py trace --write
python tools/forge.py review
python tools/forge.py audit
python tools/forge.py review --verdict pass --score 90 --reviewer 验收评审 --findings "[]"
python tools/forge.py audit
python tools/forge.py package
```

预期：design 0 阻断；check 0 error；verify 全部 required 通过；trace must 100%；记录盲审前 audit 只应 beta（模板未实测时 blocked）；记录 pass 后 audit 才 release；package 在未通过时明确拒绝。

---

## 6. 生成项目质量（人工抽检）

对两个蓝本各抽 3 份文档、2 个代码文件，按下面清单核对：

- [ ] 11 份文档无占位符、无 TODO、无“待补”；
- [ ] BOM 型号、价格、数量、来源与 `robot.yaml` 一致；
- [ ] 引脚表与固件 `config.h` 宏/常量逐个对应；
- [ ] 需求 `REQ-*` 在 `robot.yaml`、`verify.yaml`、docs/09 三处一致；
- [ ] 安全文档覆盖实际安全旗标（电池/运动/隐私/激光等）；
- [ ] 许可证与第三方依赖兼容；
- [ ] 文档里的命令能复制执行，路径存在。

---

## 7. 安全与合规

- [ ] 武器/爆炸/跟踪/偷拍等用途被 `rf_intake` 阻断并给安全替代；
- [ ] 九类安全旗标均有 `docs/07` 术语覆盖与 `compliance` 说明；
- [ ] 无密钥、令牌、私钥提交；
- [ ] 高风险形态（飞行/水下/市电/激光/儿童/医疗）有降级与失效保护说明；
- [ ] `SECURITY.md` 报告渠道可用；
- [ ] 依赖许可无 GPL 传染进 MIT 模板（引用外部 GPL 工具需标注“可选、非捆绑”）。

---

## 8. 开源发布物料

- [ ] README 含定位、七阶段、12 工具、12 形态、安装、快速开始、能力矩阵、限制、许可；
- [ ] CHANGELOG 顶部有 `## [2.0.2]`，且保留 `## [2.0.1]` 与 `## [2.0.0]` 的完整说明；
- [ ] LICENSE（MIT）、SECURITY、CODE_OF_CONDUCT、SUPPORT、ROADMAP；
- [ ] docs/design、docs/CONTRIBUTING、docs/acceptance；
- [ ] issue/PR 模板可用；
- [ ] 无内部路径、个人隐私、测试临时项目、缓存；
- [ ] `npm pack --dry-run` 文件表包含 index.js / lib / cordis.patch.yml / locale / icon.svg / skills / docs / evals / prompts / tests / scripts / README / CHANGELOG / LICENSE。

---

## 9. 评分与判定

| 类别 | 权重 | 通过条件 |
|---|---|---|
| 结构/版本 | 15 | 0 error 0 warning |
| Host 运行时 | 20 | 全部测试通过 |
| Python 引擎 | 20 | 全部测试通过 |
| 蓝本自检 | 20 | 两蓝本全绿 |
| 生成质量抽检 | 10 | 无 blocker，≥90% 条目通过 |
| 安全/合规 | 10 | 无 blocker，全部条目通过 |
| 开源物料 | 5 | 全部条目通过 |

- **可发布**：≥95 分，且无 blocker，且结构/运行时/引擎/蓝本四类全绿。
- **Beta**：≥80 分，无 blocker，允许已知限制但必须写进 README。
- **不可发布**：<80 分，或存在假绿、密钥、法规模糊、版本不一致。

验收人签字：__________  日期：__________

---

## 10. 复现记录模板

```text
版本：
提交：
系统 / Python / Node：
validate_plugin.py：__ 错误 __ 警告
node --test：__ pass __ fail
pytest：__ pass __ fail
selftest：__ 通过 / __ 失败
临时项目冒烟：design __ / check __ / verify __ / trace __ / review __ / audit __ / package __
已知限制：
结论：可发布 / Beta / 不可发布
```
