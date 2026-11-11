## 动机

<!-- 解决什么问题？关联 issue：Fixes # -->

## 改了什么

<!-- 按文件/模块列出；跨域改动请说明契约同步 -->

- [ ] 引擎（`forgekit/`）
- [ ] Host（`index.js` / `lib/`）
- [ ] SKILL / references
- [ ] 模板 / 蓝本
- [ ] 评测 / 测试
- [ ] 文档 / 工程化

## 怎么验证

<!-- 贴命令与关键输出；不要只写“本地通过” -->

```text
python scripts/validate_plugin.py
python -m pytest tests/ -q
node --test tests/plugin.test.mjs
python skills/robot-forge/scripts/forge.py selftest
```

生成项目冒烟（如适用）：

```text
new → design --write → check → verify → trace --write → review → audit → package
```

## 契约影响

- [ ] 未改 `robot.yaml` / `verify.yaml` / 证据账本 / 工具签名
- [ ] 已同步 `references/spec.md`、`model.py`、`check.py`、模板、selftest
- [ ] 已同步 12 工具清单与 `scripts/validate_plugin.py`
- [ ] 已同步四处版本（package.json / `forgekit/__init__.py` / SKILL / CHANGELOG）

## 安全与合规

- [ ] 不涉及安全旗标
- [ ] 涉及：已更新 `docs/07` 术语、`compliance` 说明与验收条目
- [ ] 无密钥、令牌、隐私数据、临时项目、缓存

## 已知限制

<!-- 没测什么、缺什么工具、哪些形态未覆盖 -->
