# 发布、打包与维护 v2.0

> 发布不是“压缩一个 zip”：它要回答三件事——**别人能不能复现**、**别人敢不敢用**、**出了问题找谁**。
> 交付物遵循 `rf_package` 的约定：先 `rf_audit`，release 需 0 error + must 覆盖 100% + 总分 ≥85；否则只能 Beta 或 blocked。

---

## 1. 版本号

- 语义化：`MAJOR.MINOR.PATCH`（项目版本与插件版本分开）；
- MAJOR：接口/协议/装配不兼容；MINOR：新增功能且向后兼容；PATCH：修 bug/文档；
- 硬件也要版本：`hardware/cad` 与 BOM 变更写 `CHANGELOG`，标“rev B”；
- 每个发布写日期、变更、已知问题、升级步骤；不要复用已发布版本号。

## 2. 发布前清单

### 机器门（必须全绿）
- [ ] `rf_check` 0 error；
- [ ] `rf_check --deep` 0 error；
- [ ] `rf_verify` 全部 required 通过，且证据新鲜；
- [ ] `rf_trace` 每条 must 100% 有 measured/manual 证据；
- [ ] `rf_review` 盲审通过，无 blocker；
- [ ] `rf_audit` ≥85 且 release_level=release（Beta 需显式 `--beta`）。

### 人读材料
- [ ] README：一句话、图、BOM 总价、时间、难度、快速开始、限制；
- [ ] docs/00–10 齐全，图纸/接线/装配/测试可照着做；
- [ ] LICENSE + 第三方许可证清单；
- [ ] CHANGELOG 含本版本；
- [ ] 安全与合规页（docs/07）覆盖所有旗标；
- [ ] 已知问题与未验证项写清楚，不用“应该”“大概”。

### 可复现
- [ ] 固定依赖版本（Python/Node/PlatformIO/库）；
- [ ] 提供 `verify.yaml`，别人一条命令能跑软件测试；
- [ ] 提供 BOM 采购链接/关键词与替代料；
- [ ] STL/STEP 可直接切片/修改；参数化 CAD 有说明；
- [ ] 演示素材（照片/视频）真实，不摆拍关键功能。

## 3. 打包

```bash
python tools/forge.py package            # release
python tools/forge.py package --beta     # 允许 Beta
python tools/forge.py package --out dist # 指定目录
```

产物：
- `dist/<slug>-<version>.zip`（或 `-beta`）：源码、文档、CAD、固件、软件、仿真、forge 记录；
- `RELEASE.json`：逐文件 SHA256、分数、六维 scorecard、源码指纹、生成时间；
- `SHA256SUMS` 与 `.sha256`：校验下载完整性；
- 排除：`.git`、缓存、`node_modules`、`.pio`、`dist`、临时文件。

发布页同时给出：zip、SHA256、BOM 总价、时间、难度、许可证、支持渠道。

## 4. 发布渠道

- GitHub Release（主）：tag `v<version>`，附 zip + SHA256 + release notes；
- 国内镜像/网盘：保留同一 SHA256，注明来源；
- 插件市场/合集：只在插件自身发布时使用，不与项目产物混淆；
- 演示：30–90 s 视频 + 3–5 张关键照片（整机/接线/界面/测试）。

## 5. Beta 与“不可发布”

| 状态 | 条件 | 对外说法 |
|---|---|---|
| release | 0 error、100% 覆盖、≥85、盲审过 | 可复现参考设计 |
| beta | 有未验证 must，或分数 70–84 | 明确列出未验证项与风险 |
| blocked | 有 error / 覆盖率 <100% / <70 | 不对外称“完成”，只做开发预览 |

Beta 不是“免责牌”：安全相关 must（急停、限位、电池保护）不允许 Beta 放行。

## 6. 维护

- Issue 模板：现象/复现/期望/环境/证据；安全漏洞走私密渠道（SECURITY.md）；
- 每季度复核：价格、EOL、依赖安全公告、标准更新；
- 破坏性变更：先 deprecate 一个 minor，再移除；写迁移说明；
- 收集真实使用证据（L6），更新 docs/09 与风险表；
- 不静默改已发布 tag；修订发新 patch。

## 7. 交接

给下一位维护者/用户：
1. `forge/robot.yaml` 是唯一事实源，先读它；
2. `forge/decisions.md` 记录为什么这样选；
3. `forge/trace.md` 看需求→证据；
4. `docs/08-测试与验证.md` 看怎么复现；
5. 变更后重跑 `check`/`verify`，证据会因指纹变化自动过期。

## 8. 发布说明模板

```markdown
## v1.2.0 — 2026-11-11
### 新增
- ...
### 修复
- ...
### 已知问题
- ...（影响/规避/计划）
### 验证
- check: 0 error；deep: 0 error；verify: 5/5；audit: 91（release）
### 升级
- 重新打印 X 件；替换 Y 型号；重跑 verify
```
