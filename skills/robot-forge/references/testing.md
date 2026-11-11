# 测试与证据策略 v2.0

> 机器人项目的“测试”不是跑一遍 pytest 就完了：协议、运动学、功率、固件、结构、装配、真实试用各有各的证据。
> 目标：每一条 must 需求都能指向一个**可复现**的验证命令或**真实发生**的人工步骤，且证据不过期。

---

## 1. 测试金字塔（机器人版）

| 层 | 范围 | 速度 | 证据等级 | 例子 |
|---|---|---|---|---|
| L1 单元 | 纯函数/协议/状态机 | ms | measured（命令 exit 0） | 差速混控、命令解析、限位 |
| L2 集成 | 多模块 + mock 硬件 | s | measured | robotd + fake serial；固件 native |
| L3 仿真 | 运动学/动力学/功耗 | s–min | simulated→measured（脚本 exit 0） | check_kinematics、MuJoCo |
| L4 硬件在环 | 真板 + 真传感器 | min | measured + 人工确认 | 串口跑通、舵机限位 |
| L5 整机 | 装配后真实场景 | h | manual | 30 cm 停障、续航、装配 |
| L6 现场 | 用户环境 | 天 | manual（真实试用） | 7 天不重启、儿童场景 |

**规则**：L1/L2 必须自动化；L3 尽量脚本化；L4/L5/L6 必须由人执行并记录 note。没有 L4–L6 的 must 需求不能算“可发布”。

## 2. verify.yaml 契约

```yaml
version: 1
commands:
  - id: software-tests
    run: python -m pytest software/tests -q
    req: [REQ-001, REQ-007]
    required: true
    timeout: 120
    needs: [python]
```

- `id` 唯一、短横线；`run` 是 shell 命令，必须在项目根或 `cwd` 下可执行；
- `req` 映射到需求；每条 must 需求至少被一个 `required: true` 命令覆盖，或明确 manual；
- `needs` 只能是白名单工具（python/pio/arduino-cli/node/npm/kicad-cli/openscad/ffmpeg 等）；缺工具标 SKIP/FAIL，不算通过；
- `required: false` 是可选增强（如固件 native 测试），失败不能拖垮发布，但要在文档写清；
- 禁止 `true`、`echo`、`sleep`、`exit 0`、`python -c pass` 这类空跑；CST-08 会拦。

## 3. 各域最低测试

### 软件（Python）
- 协议编解码：合法/非法/超长/半包/粘包；错误码；
- 运动学：正解/逆解/限幅/零速/边界；
- 状态机：正常迁移、非法迁移、超时降级；
- 隐私：默认不采集、关闭即停、删除接口；
- mock 串口/网络：无硬件也能跑；覆盖率不是目标，**行为断言**才是。

### 固件（C++/PlatformIO）
- native 环境跑纯逻辑（协议/混控/限位），不依赖 Arduino；
- `test_*` 覆盖非法输入、边界值、堵转/超时；
- 真实环境只做冒烟：烧录、串口握手、引脚电平；
- 中断/看门狗/内存不得靠“看起来对”。

### 硬件/结构
- 接线表 vs 固件引脚一致性（CST-01/02）；
- 电源轨峰值、极性、保险丝；
- 结构：公差试片、装配顺序、工具可达；
- 3D 打印件：壁厚、层高、螺丝孔预埋。

### 仿真
- 输入/输出单位写清（mm vs m、度 vs 弧度）；
- 断言用范围而非精确值；记录随机种子；
- 仿真通过只能标 simulated，不能标 measured。

### 人工
- 写清前置条件、步骤、通过判据、失败处理；
- `rf_evidence` 的 note 必须含“谁/哪台/何时/怎么确认”；
- 拍照/日志存 `docs/assets` 或 `evidence/`，路径写 artifact。

## 4. 假绿封堵（10 类）

| 假绿 | 识别 | 正确做法 |
|---|---|---|
| 空跑命令 | run=true/echo/exit 0 | 真跑测试；CST-08 拦截 |
| 只断言 True | assert True / 无断言 | 断言具体值/状态 |
| 跳过失败测试 | skip/xfail 无理由 | 修实现或写清阻塞原因 |
| 改测试变绿 | 测试与实现同时改 | 先修实现；测试变更要评审 |
| 仿真当实测 | 证据 level=simulated 却写实测 | 重新真跑，或标 simulated |
| 过期证据 | 源码改了但证据未重跑 | 重新 verify（指纹校验） |
| 人工编造 | 模型写 manual 无 note | 只能用户真实试用后记录 |
| 只跑子集 | verify --only 后说全过 | partial 明确列出未跑项 |
| 环境缺工具 | 把 SKIP 当 PASS | 安装工具或标未验证 |
| 只测 happy path | 无非法/边界用例 | 补负向/边界/并发 |

## 5. 证据等级与覆盖

| level | 含义 | 计入 must 覆盖 |
|---|---|---|
| measured | 本次 `rf_verify` 命令 exit 0，记 command/exit | ✅ |
| manual | 用户真实试用/目视确认，带 note | ✅ |
| simulated | 仿真/脚本但非实物 | ❌（只能辅助） |
| assumed | 假设/估算 | ❌ |

- 证据带源码指纹；验证后改代码 → 证据过期（D4），必须重跑；
- 每条 must 需求要有至少 1 条 measured/manual；发布要求 100%；
- 证据只追加不删；纠错写新证据并在 note 说明替代哪条。

## 6. 测试计划模板

```markdown
## 测试计划
| 需求 | 层级 | 方法 | 命令/步骤 | 通过判据 | 证据 |
|---|---|---|---|---|---|
| REQ-001 | L1 | pytest | pytest software/tests -q | 12 passed | measured |
| REQ-004 | L5 | 人工 | 30cm 纸板挡车 | 0.5s 内停稳 | manual |
```

放进 `docs/09-验证报告.md` 或 `forge/test-plan.md`；`rf_trace` 会生成矩阵。

## 7. CI（可选但推荐）

```yaml
# .github/workflows/ci.yml 的核心步骤
- python -m pytest software/tests -q
- python tools/forge.py check --deep
- python tools/forge.py verify --no-record
```

CI 只证明软件/结构，不证明实物；发布仍要 L5/L6 人工证据。矩阵：Ubuntu/Windows × Python 3.11/3.12/3.13；固件 job 单独装 PlatformIO。

## 8. 失败排查顺序

1. 读完整错误与退出码，不猜；
2. 复现最小命令；
3. 区分环境（缺工具/权限）与代码（断言/逻辑）；
4. 两次修不好 → 读 spec 规则或把原文交用户；
5. 修复后重跑**全套**，不只跑失败项；
6. 记录到 docs/09 与 risks，避免同类问题再犯。
