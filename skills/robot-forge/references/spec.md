# 交付契约 v2.0（唯一真相源）

> 本文件定义“什么算做完了”。`SKILL.md`、`index.js`、`lib/tools.js`、`scripts/forgekit/` 与所有蓝本都以本文件为准。
> 规则变了先改这里，再同步 `scripts/forgekit/check.py`、`consistency.py`、`design.py` 与 `references/quality.md`。
> 适用对象：任何有工具调用能力的大模型。你不需要背规则；`rf_check` 会把违反项变成带文件与规则的错误。

---

## 1. 完成的定义

一个项目只有同时通过六道机器门与一次人工盲审，才算可发布：

| 门 | 问题 | 机器判据 |
|---|---|---|
| 买得到 | BOM 能否一次买齐？ | 每行真实型号/数量/单价/采购关键词；总额 ≤预算×1.15 或 decisions 有理由；替代料 |
| 造得出 | 零基础能否照做？ | 必需文件齐全；`check` 0 error；每步有“应该看到什么”；固件/软件可编译启动 |
| 算得对 | 扭矩/续航/电源/线径/散热够不够？ | `rf_design` 无 error；`forge/design.md` 存在且与清单一致 |
| 跑得起来 | 验证命令是否真跑？ | `rf_verify` required 全 exit 0；证据新鲜 |
| 证得了 | 每条 must 是否有证据？ | `rf_trace` must 100% measured/manual；`check --deep` 0 error |
| 说得清 | 陌生人能否复现？ | 文档/链接/生成块/中文可读性；`rf_review` 无 blocker |
| 发得出 | 包是否完整可校验？ | `rf_audit` ≥85 且 release；`rf_package` 产出 zip + SHA256 |

**用户语言版（写进 README）：** 买得到、装得上、算得对、跑得起来、说得清、真得住、发得出。

**机器语言版（发布门）：**

```text
python tools/forge.py check --deep   → exit 0，0 error
python tools/forge.py verify         → exit 0，全部 required 通过
python tools/forge.py trace          → must 覆盖 100%
python tools/forge.py review         → 无 blocker
python tools/forge.py audit          → 0 error，覆盖 100%，score ≥85，release
python tools/forge.py package        → zip + RELEASE.json + SHA256SUMS
```

只过前几道、最后一两道未闭环 → 只能发 **Beta**，README 状态矩阵与 `docs/09` 逐条列未验证项。**不允许**把 Beta 写成“完成”。

**反面定义（任意一条就不算完成）：**
- 只有架构图与 Markdown，没有能编译的固件/能启动的软件；
- 引脚表、BOM、代码里的引脚三处不一致；
- 性能数字没有测试/实测记录；
- 用 mock/仿真冒充实物实测；
- 把“计划做”写成“已做”，或留 TODO/待补/占位符；
- 用 `echo ok`/`true`/`sleep 1` 冒充验证命令；
- 设计核算缺失或有 error 却直接写证据；
- 没有 trace/review-packet 就宣称可发布。

---

## 2. 交付物目录

`[g]` = 由 `rf_check`/`forge.py render` 生成，**禁止手写**；其余由你编写。路径相对项目根。

```text
README.md                      首页：一句话、图位、3 分钟上手、状态矩阵、文档地图、限制
LICENSE                        默认 MIT；GPL/AGPL 依赖时换兼容许可并说明
CHANGELOG.md                   当前版本必须有记录（## [x.y.z]）
.gitignore                     忽略 __pycache__/.pytest_cache/.pio/build/dist/*.log
docs/
  00-总览.md               [g]  一句话/能力/边界/系统结构（arch-graph）
  01-物料清单.md           [g]  按类别、替代料、采购提示、到货检查（bom-table/bom-total）
  02-组装指南.md               工具、打印参数、编号步骤、≥3 个检查点（assembly-parts）
  03-接线表.md             [g]  总线表、引脚表、供电表、上电顺序
  04-固件说明.md               工具链、烧录、首次日志、代码结构、协议
  05-软件说明.md               安装、运行、配置、接大模型、卸载
  06-使用手册.md               首次/日常/维护，≥3 个 ###
  07-安全与隐私.md             按旗标写：电池/市电/运动/激光/隐私/联网/儿童/户外/医疗
  08-故障排查.md               症状→原因→处理，≥8 条
  09-验证报告.md           [g]  结论、复现命令、需求证据矩阵、未验证清单
  10-常见问题.md               ≥6 个 ###
diagrams/architecture.svg|wiring.svg|assembly.svg   [g]
hardware/
  bom.csv                  [g]
  cad/*.py                     build123d 参数化源码（cad 域必需）
  cad/dims.json                尺寸/质量/公差（与 robot.yaml 一致）
  stl/                         可选：导出的打印件
firmware/                      firmware 域必需
  platformio.ini               [env:...]；建议加 [env:native]
  include/config.h
  src/main.cpp                 以及按职责拆分的 .h/.cpp
  test/test_*.cpp              至少一个可跑单测
software/                      software 域必需
  pyproject.toml
  robotd/main.py               入口；单文件 ≤400 行
  tests/test_*.py              默认不依赖硬件
sim/                           sim 域必需
  scene.xml 或 *.py            场景/运动学/功耗脚本
  README.md                    怎么跑、算什么、不模拟什么
tools/
  forge.py                     [g] 项目内启动器
  forgekit/                    [g] 固化工具链
forge/
  robot.yaml                   单一事实源（§4）
  verify.yaml                  可执行验收（§5）
  plan.md                      阶段计划、关键路径、里程碑
  decisions.md                 关键决策与取舍（含被推翻的）
  research.md                  选型调研与来源（quick 可 5 条）
  design.md               [g]  设计核算：扭矩/功率/续航/线径/散热/成本
  trace.md                [g]  需求→验证→证据追踪矩阵
  review-packet.md/.json  [g]  盲审包（复现命令、证据、模板、哈希）
  review.json                  盲审结论（verdict/score/findings）
  evidence.jsonl               证据账本（§7）
```

**按域裁剪：** `project.domains` ∈ `hardware/cad/firmware/software/sim`。未声明域不要求目录，但 `decisions.md` 写“为什么不需要”。`docs/`、`forge/`、README/LICENSE/CHANGELOG 永远必需。

**借力上游：** 直接用成熟栈（Betaflight、ArduPilot、xiaozhi-esp32、LeRobot、ROS 2 包）时，`firmware/` 可只放配置与改动，但必须：① `docs/04` 写上游、锁版本/commit、烧录；② `decisions.md` 说明为何不自写；③ `architecture.firmware` 标 `external:<name>`；④ 许可证兼容。

---

## 3. DSH 工具与命令行（唯一稳定接口）

项目根运行；`--project <dir>` 可指定。退出码：0 通过，1 有阻断，2 用法/内部错误。
DSH 会话优先用工具（schema/超时/取消/结构化结果）；CLI 是同一引擎的兜底。

| 工具 | 作用 | 关键约束 |
|---|---|---|
| `rf_intake` | 愿望→形态/预算/域/旗标/问题 | 先分类再建项目；≤3 问，带默认 |
| `rf_blueprints` | 列蓝本 | 蓝本不是形态白名单 |
| `rf_new` | 生成完整项目 | `blueprint` 必填；不从空目录手搓 |
| `rf_status` | 状态 + 唯一下一步 | 开工/上下文变长先跑 |
| `rf_check` | 自动 render + check | 0 error 才继续；`--deep` 发布前 |
| `rf_design` | 扭矩/功耗/续航/线径/散热/成本 | 写 `forge/design.md`；error 先改选型 |
| `rf_verify` | 真跑 verify.yaml 并记账 | required exit 0 才算实测 |
| `rf_audit` | 六维评分 + 发布判定 | ≥85 且 release 才可发 |
| `rf_trace` | 需求→验证→证据矩阵 | must 100% |
| `rf_review` | 生成盲审包；可记录独立结论 | 盲审者独立复跑；记录时必填 verdict/score/reviewer，pass 不得有 blocker |
| `rf_package` | 打包 + 校验和 | 先 audit；Beta 需 `--beta` |
| `rf_evidence` | 人工/仿真/假设证据 | 不许编造 manual |

| 命令 | 作用 |
|---|---|
| `forge.py doctor` | 探测 Python/工具链/项目 needs |
| `forge.py intake "..." [--budget N] [--json]` | 愿望分类与方案提示 |
| `forge.py new <名字> --blueprint <slug> [--dir D] [--slug S] [--force]` | 从蓝本生成项目 |
| `forge.py render` / `render --check` | 重算生成物 / 只判过期 |
| `forge.py check [--deep] [--json]` | 结构 S1–S14 + 交付 D1–D10 + 跨文件 CST + 设计 DSN |
| `forge.py design [--write] [--json]` | 设计核算 |
| `forge.py verify [--only a,b] [--no-record] [--json]` | 执行验收并记账 |
| `forge.py trace [--write] [--json]` | 追踪矩阵 |
| `forge.py review [--no-write] [--verdict pass|needs_revision|reject] [--score N] [--reviewer X] [--findings JSON|@file] [--json]` | 生成盲审包；记录独立评审结论 |
| `forge.py audit [--json]` | 六维评分/发布判定 |
| `forge.py package [--beta] [--out dist] [--json]` | 发布 zip + RELEASE.json + SHA256 |
| `forge.py status` / `next` / `blueprints` | 状态/下一步/蓝本 |
| `forge.py evidence --req ... --claim ... --level ... --note ...` | 记人工/仿真/假设证据 |
| `forge.py selftest` | 插件自测（所有蓝本生成+check+verify） |

**路径：** 插件在 `<plugin>/skills/robot-forge/`；新项目把 `forgekit` 复制到 `tools/forgekit/`，可脱离插件独立开源。

---

## 4. `forge/robot.yaml`：单一事实源

**原则：任何出现在两处以上的数字/字符串只在这里出现一次。** 引脚、I2C 地址、型号、尺寸、质量、价格、需求 ID、风险 ID 都是。`render` 注入文档；`check` 抓漂移。

```yaml
schema: 1
project:
  name: 小豆
  slug: xiaodou-companion        # ^[a-z0-9][a-z0-9-]{1,40}$
  version: 0.1.0
  one_liner: 会转头、会做表情、能听会说的桌面小伙伴
  blueprint: desktop-companion   # 或 freeform
  gear: standard                 # quick | standard | flagship
  domains: [hardware, cad, firmware, software, sim]
  budget_cny: 400
  license: MIT
  repo: ""
wish:
  user: 独居的上班族
  story: 下班回家会转头看我、聊两句、提醒喝水；不要一直录我
  must: [转头看向我, 中文语音对话, 断网也能应一声]
  nice: [摸头有反应]
  must_not: [摄像头常开, 强制云账号, 深夜自动说话]
  size_mm: [100, 90, 150]
  environment: 书桌
  skill_level: zero
architecture:
  summary: 主机跑交互，ESP32-S3 跑动作与传感器，USB 串口协议连接
  mcu: esp32-s3
  host: pc                       # none | rpi | pc | phone
  firmware: platformio-arduino   # 或 external:<name>
  host_stack: python311
  transport: usb-serial
  features:
    - {id: F1, name: 表情与动作, how: 2 自由度头 + 圆屏, components: [servo_pan, servo_tilt, display]}
components:
  - id: mcu
    role: controller
    part: 微雪 ESP32-S3-DEV-KIT-N8R8
    qty: 1
    interface: usb
    price_cny: 45
    source: 淘宝/微雪商城，搜「ESP32-S3-DEV-KIT-N8R8」
    note: 板载 8MB Flash / 8MB PSRAM
  - id: servo_pan
    role: actuator
    part: MG90S 金属齿轮舵机
    qty: 1
    interface: pwm
    rail: v5
    typical_ma: 100
    peak_ma: 700
    stall_current_ma: 700
    torque_kgcm: 1.8
    mass_g: 13
    price_cny: 9.5
    source: 淘宝「MG90S 金属齿」
buses:
  - {id: i2s-mic, type: i2s, pins: {sck: 4, ws: 5, sd: 6}}
  - {id: i2c, type: i2c, pins: {sda: 18, scl: 1}, speed: 400k}
pins:
  - {id: pan-pwm, function: pwm, pin: 15, connect: servo_pan, note: 50Hz}
power:
  source: 5V 3A USB 适配器
  battery: {chemistry: none, mah: 0, cells: 0}
  rails:
    - {id: v5, name: 5V, voltage: 5, max_ma: 3000}
    - {id: v33, name: 3.3V, voltage: 3.3, max_ma: 800}
  consumers:
    - {component: mcu, rail: v33, typical_ma: 120, peak_ma: 350}
    - {component: servo_pan, rail: v5, typical_ma: 100, peak_ma: 700}
mechanical:
  envelope_mm: [100, 90, 150]
  mass_kg: 0.6                  # 核算必需；没有就写估计值+来源
  drive_count: 0                # 轮式/履带写驱动数
  payload_kg: 0                 # 机械臂/云台写负载
  reach_m: 0                    # 机械臂最大臂展
  parts:
    - {id: head_shell, name: 头部外壳, process: fdm, material: PETG, file: hardware/cad/enclosure.py, qty: 1}
  fasteners: [M3x8 自攻螺丝 ×8, M2x6 ×4]
  tools: [十字螺丝刀, 内六角 2mm, 电烙铁]
  limits: [头部俯仰 0-60°, 水平 ±80°]
software:
  daemon: robotd
  protocol_version: 1
  host: {entry: software/robotd/main.py, language: python}
  entrypoints:
    - {name: mock, run: "python -m robotd --mock", desc: 无硬件演示}
    - {name: serve, run: "python -m robotd --port auto", desc: 接真机}
behavior:
  persona: 安静、好奇、不黏人；被叫名字才转向
  states: [sleep, idle, listen, think, speak, error]
  expressions: [眨眼, 歪头, 呼吸灯]
requirements:
  - {id: REQ-001, text: 模拟模式闭环：收到一句文本会回一句, priority: must, verify: "python -m pytest software/tests -q", note: 覆盖 F1/F3}
  - {id: REQ-002, text: 唤醒后 1.5m 内主动抬头, priority: must, verify: "manual: 按 docs/06 在 1.5m 处叫名字 10 次，≥8 次抬头"}
risks:
  - {id: RISK-001, hazard: 舵机堵转过热, sev: 3, lik: 3, mitigation: 软件限流 + 5s 堵转断电, verify: "manual: 手按住头部 5s，观察是否断电"}
compliance:                      # 有安全旗标时必写
  standards: ["GB 31241-2022（参考）", "GB 4943.1（参考）"]
  labels: ["工程原型，非玩具/非医疗器械", "儿童需成人监护"]
  limits: ["室内使用", "不防水", "不载人"]
  note: 自检清单不是认证
security:                        # 联网/隐私时必写
  threats: ["串口被占用", "局域网未授权访问"]
  auth: "配对码 + 令牌"
  ota: "签名 + 可回滚"
  data: "默认本地，不保存原始音视频"
cost:
  target_cny: 400
  shipping_cny: 15
  quote_date: "2026-11"
```

### 4.1 字段规则

| 字段 | 规则 |
|---|---|
| `schema` | 必须为 1 |
| `project.slug` | `^[a-z0-9][a-z0-9-]{1,40}$`；同时是目录/仓库名 |
| `project.gear` | quick 单晚 / standard 周末 / flagship 数周；决定文档与验证强度 |
| `project.budget_cny` | >0；总价 >×1.5 error，>×1.15 warn |
| `wish.story` | ≥20 字；谁、什么场景、最想解决的一件事 |
| `wish.must` | ≥1 条；用户语言，不是技术指标 |
| `architecture.features[].components` | 元件 id 列表；纯软件能力写 `software_only: true` |
| `components[]` | 必填 id/role/part/qty/price_cny；part 必须真实可买（占位型号 error） |
| `components[].interface` | usb/i2c/spi/uart/pwm/adc/gpio/i2s/bus-servo/camera/display/none |
| `components[].address` | i2c 必填（0x29）；bus-servo 必填；其它留空 |
| `components[].rail` | 必须是 rails 的 id；有功耗的元件必须登记 consumers |
| `components[].torque_kgcm` | 执行器扭矩；没有则 DSN-02，核算只能定性 |
| `components[].rated_current_ma/stall_current_ma` | 额定/堵转电流；散热与线径用 |
| `buses[].pins` | 键=信号，值=整数 GPIO；存在、不冲突、避开保留脚 |
| `buses[].controller` | 默认 mcu；必须是 components 的 id |
| `pins[]` | {id,function,pin,connect,note}；LED/按键/PWM 等独立信号 |
| `power.rails[]` | id/name/voltage/max_ma；电压电流 >0 |
| `power.consumers[]` | component/rail/typical_ma/peak_ma；typical ≤ peak |
| `mechanical.mass_kg` | 整机质量；缺失 DSN-11 |
| `mechanical.drive_count` | 驱动执行器数；缺省按 actuator 数猜 |
| `mechanical.parts[].file` | 必须存在；cad 域用 .py，也接受 .step/.stl |
| `requirements[].verify` | 可执行命令或 `manual: <可复现步骤>`；must 仅 manual warn |
| `risks[]` | id/hazard/sev/lik/mitigation/verify；sev×lik≥12 必须有 mitigation+verify |
| `compliance` | 有旗标时必须有；standards/labels/limits/note |
| `security` | 联网项目必须有；threats/auth/ota/data |
| `cost.shipping_cny` | 运费；总额 = 元件小计 + 运费 |
| `cost.quote_date` | 报价快照日期 |

**role 枚举：** controller（必须有且唯一）、actuator、sensor、audio、display、power、structure、cable、fastener、tool、other。

**MCU 保留脚（S4 拦）：** esp32-s3 禁止 0、19、20、26–37、45、46。可用 1–18、21–25、38–44、47、48。

**事实源纪律：** 改引脚只改 robot.yaml → render → 改固件 config 对齐；文档正文不手写引脚号（D1 抓）。

---

## 5. `forge/verify.yaml`：可执行验收

```yaml
version: 1
commands:
  - id: software-tests
    name: 主机软件单测
    run: python -m pytest software/tests -q
    required: true
    needs: [pytest]
    req: [REQ-001]
  - id: sim-reach
    run: python sim/check_reach.py
    required: true
    req: [REQ-003]
  - id: self-check
    run: python tools/forge.py check
    required: true
  - id: firmware-tests
    run: pio test -e native
    cwd: firmware
    required: false
    needs: [pio]
    req: [REQ-002]
```

规则：
- required true 必须真跑、exit 0；缺 needs 工具 = FAIL（127），不算通过。
- required false 缺工具 = SKIP；工具已装且跑了非零仍 FAIL（可选测试失败不能当通过）。
- 禁止 echo/true/sleep/exit 0 空跑；D2 拦截。
- cwd 可选，必须在项目内，不能 `..` 逃出。
- req 字符串或列表；成功自动记 measured + 指纹；源码一改旧证据过期。
- needs 只认 python/pytest/pio/node/npm/pnpm/git/kicad-cli/openscad/ffmpeg/mujoco/build123d/serial/esptool。
- 默认超时 600s；慢命令写 timeout: 1800；旧 timeout_s 兼容。
- must 需求必须被 required 命令覆盖，或在 requirements 写 manual 步骤。

---

## 6. `render` 的边界

成对标记包住自动数据；只改块内，块外不动；缺结束标记报错且不写。

```markdown
<!-- forge:begin bom-table -->
（render 生成，勿手改）
<!-- forge:end bom-table -->
```

**11 个块：** status-matrix（README）、arch-graph（docs/00）、bom-table/bom-total（docs/01）、assembly-parts（docs/02）、bus-table/pinout/power-table（docs/03）、req-evidence/evidence-log/unverified-list（docs/09）。

**整文件生成：** hardware/bom.csv、diagrams/architecture.svg、wiring.svg、assembly.svg；docs/01/03/09/00 与 README 只有块内被替换。

**D1 会重渲染并逐字节对比**；手改生成块/文件 → error；修复是改 robot.yaml 后 render。

---

## 7. 证据账本 `forge/evidence.jsonl`

一行一条 JSON，只追加：

```json
{"id":"E-20261111-153000-123","at":"2026-11-11T15:30:00+08:00","req":"REQ-001","claim":"模拟模式 39 个单测通过","kind":"test","command":"python -m pytest software/tests -q","exit":0,"level":"measured","artifact":"software/tests","note":""}
```

- level：measured（本机真跑）｜manual（真人按步骤确认）｜simulated（仿真/静态）｜assumed（假设）。
- kind：test|command|benchmark|inspection|manual。
- verify 自动追加 measured；失败记 assumed 且 exit 非 0；evidence 手工记 manual/simulated/assumed。
- fingerprint：measured/manual 写源码指纹；源码/固件/CAD/仿真/robot.yaml/verify.yaml 一改即过期。docs/README/BOM/证据本身不算源码。
- manual 必须 note：谁、哪台实物、怎么确认。
- artifact 必须是项目内存在的相对路径。
- **红线**：无 measured/manual 时，README/docs 不得出现“已实测/实测通过/已通过实机测试/实机验证通过/已通过验证”。D8 扫。

**四态：** ✅ 有 measured exit 0；🟡 只有 simulated；⚪ 只有 manual/assumed 或无证据；⛔ risks 未闭合。

---

## 8. 规则表（与代码一一对应）

### 8.1 结构/交付规则

| ID | 级别 | 规则 |
|---|---|---|
| S1 | error/warn | schema=1；project 必填；slug 合法；gear/domains 合法；story≥20；must 非空；features 有 how；有硬件域必须有 components；有固件域必须有 controller；组件字段齐全 |
| S2 | error | feature/component/bus/rail/requirement id 全局唯一 |
| S3 | error/warn | 引用存在；采购渠道缺失 warn |
| S4 | error | GPIO 不重复、不占保留脚、必须是整数 |
| S5 | error | 总线地址/舵机 ID 不重复 |
| S6 | error/warn | 电压/电流 >0；typical≤peak；峰值>90% error；典型>70% warn；续航<1h warn |
| S7 | error/warn | 总价 >预算×1.5 error；>×1.15 warn |
| S8 | error | feature 元件存在；无 components 且非 software_only 报错 |
| S9 | error/warn | 需求有 verify；像命令或 manual:；must 仅 manual warn；命令必须出现在 verify.yaml 或以 req 列出 |
| S10 | error | risk sev/lik 1–5；sev×lik≥12 必须有 mitigation+verify |
| S11 | error | 电池/市电/运动/激光/隐私触发时 docs/07 有对应关键词 |
| S12 | error | 无 TODO/FIXME/TBD/待补/待定/占位/{{...}} |
| S13 | error | README/docs 相对链接存在 |
| S14 | error | 元件 part 不是占位型号 |
| D1 | error | 生成块/文件与 render 逐字节一致 |
| D2 | error/warn | 必需文件/域文件/状态文件/research.md(standard+) 齐全；verify 命令合法 |
| D3 | error/warn | 必需章节关键词；docs/02 ≥3 检查点；docs/06 ≥3 ###；docs/10 ≥6 ###（warn） |
| D4 | error(deep)/warn | 证据 JSON 合法、id 唯一、level 合法、measured exit=0；must 无证据默认 warn，deep/audit error |
| D5 | error/warn | .py 可编译；json/yaml 可解析；C/C++ 花括号平衡；platformio 有 [env:] |
| D6 | error | bom.csv 有数据行+合计行，合计与清单一致 |
| D7 | warn | README/docs 中文占比 <45% |
| D8 | error | 无 measured/manual 却宣称“已实测/已通过验证” |
| D9 | error/warn | LICENSE 有效（≥100 字符）；CHANGELOG 含当前版本 |
| D10 | warn | docs/01 出现每个元件型号；deep 时 measured 无 command、must 未闭环逐条列 |

### 8.2 跨产物一致性（CST，总是跑）

| ID | 级别 | 检查 |
|---|---|---|
| CST-01 | error | 固件里出现的 GPIO 必须在 robot.yaml 声明 |
| CST-02 | warn | robot.yaml 声明但固件没用（可能漏接） |
| CST-03 | error | 固件 Wire.begin 地址/引脚与 I2C 定义不一致 |
| CST-04 | warn | 主机协议 token 没在固件出现（协议漂移） |
| CST-05 | error/warn | must 需求未映射 verify 命令 error；仅 optional warn |
| CST-06 | info | verify 命令没有 req 映射 |
| CST-07 | error/warn | 疑似密钥入库（AKIA/ghp_/sk-/私钥/password=） |
| CST-08 | error/warn | 无测试 error；测试数 < min_tests warn；assert 过少 warn |
| CST-09 | warn/error | 元件无 source warn；EOL 件 error；交期 >30 天 warn |
| CST-10 | warn | 有安全旗标但无 compliance 块 |
| CST-11 | warn | docs/07 缺触发项关键词 |
| CST-12 | warn | 联网但无 security 块 |
| CST-13 | warn | BOM 元件未出现在 docs/01 |
| CST-14 | info | 功能未绑定元件（确认纯软件还是漏写） |

### 8.3 设计核算（DSN，check --deep 与 design）

| ID | 级别 | 检查 |
|---|---|---|
| DSN-01 | error/warn | 执行器扭矩不足 error；余量 <1.2 warn |
| DSN-02 | warn | 执行器缺 torque_kgcm |
| DSN-03 | error | 续航低于目标 80% |
| DSN-04 | error/warn | C-rate 超限 / 接近上限 |
| DSN-05 | error | 电源轨峰值超 max_ma |
| DSN-06 | error/warn | 成本 >×1.5 error / >×1.15 warn |
| DSN-07 | warn | 无 power.source |
| DSN-08 | warn | 负载 >1.5 倍自重 |
| DSN-09 | warn/info | 功率密度 >10 W/L warn；无法估算 info |
| DSN-10 | info | 无电池（市电/有线项目正常） |
| DSN-11 | warn | 无 mechanical.mass_kg，无法核算 |

### 8.4 audit 评分

六维：买得到15、造得出20、跑得起来25、说得清15、证得了15、安全10。每维 error −6、warn −1；D4 不重复扣；evidenced = 15×覆盖率。总分 ≥85 且 0 error 且覆盖 100% → release；0 error → beta；否则 blocked。详见 `quality.md`。

---

## 9. 命名、单位、许可

- 文档中文、`NN-名称.md`；代码/配置全英文小写；Python 包下划线，其余连字符。
- UTF-8 无 BOM、LF；Markdown 一个一级标题；命令给 PowerShell 与 bash 写法，零基础默认 PowerShell。
- 单位：元、毫米、克、毫安、毫秒；价格 2 位小数。
- 许可：默认 MIT；Apache/MIT/BSD 保留 NOTICE；GPL/AGPL 必须同许可并 README 明示；闭源商用禁用 GPL（含 piper1-gpl、部分 Ultralytics）；CAD 可 CERN-OHL-S-2.0，文档 CC-BY-4.0。
- 非商用模型/权重不得写进“开源可商用”交付。

---

## 10. 降级与诚实

允许交付但必须显式标注：

1. 缺工具链 → verify SKIP，README ⚪，docs/04 给安装步骤。
2. 必须实物验证（续航/噪声/温升/夹持力/语音延迟）→ 写实测步骤+记录表，标 ⚪，禁止编数字。
3. 上游不兼容/版本漂移 → decisions 锁版本与替代。
4. 预算/空间冲突 → 取舍卡三选一（加钱/减功能/降指标），不偷偷缩水。
5. 用户要求不可能（¥100 六自由度人形）→ 明确说不可能 + 最近可行方案与差价。

**禁止：** simulated 写成 measured；缺证据写“已验证”；echo 冒充测试；图片占位冒充成品；把计划写成已做；贴上游代码却不跑。

---

## 11. 蓝本契约

蓝本 = 完整可运行项目。`forge.py new` 复制、替换 4 占位符、固化 forgekit、立刻 render。

**占位符：** `{{NAME}}`、`{{SLUG}}`、`{{DATE}}`、`{{BLUEPRINT}}`。

**blueprint.json：**

```json
{
  "name": "桌面陪伴机器人",
  "slug": "desktop-companion",
  "one_liner": "一句话说清它是什么、多少钱",
  "cost_cny": 264,
  "time": "2 个周末（约 12 小时，含打印）",
  "difficulty": "入门偏中（需要电烙铁，不需要焊贴片）",
  "domains": ["hardware", "cad", "firmware", "software", "sim"],
  "needs": ["3D 打印机", "电烙铁", "电脑"],
  "tags": ["桌面", "陪伴", "ESP32-S3"]
}
```

**新蓝本验收（缺一不可）：**
1. `new` exit 0；
2. `check` 0 error；`verify` required 通过；
3. `render --check` 无过期；
4. `audit` 0 error、must 100%、≥85；
5. 无 TODO/占位；链接存在；至少 1 个真实失败测试；
6. `selftest` 全绿。

**禁止：** 写死“待定型号”；假采购链接；用 optional 掩盖必须验证；把用户当工程师。

---

## 12. 反作弊清单（评审必查）

- 只测 mock、无真实路径 → 假绿；
- 断言写死常量 → 假绿；
- 声称编译通过但从未装工具链、也没 skipped → 假绿；
- 仿真写成实物 → 越级；
- 需求 1.5m、验收只测 30cm → 偷换指标；
- BOM 有价格无型号/采购词 → 买不到；
- 文档引脚与清单/固件不一致 → 装不上；
- 故障排查全是“检查连接” → 说不清；
- 上游 README 原文未删项目名 → 拼贴；
- 无 trace/review 直接发 release → 跳门。
