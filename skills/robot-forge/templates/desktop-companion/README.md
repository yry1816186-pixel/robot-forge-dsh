# {{NAME}}

桌面陪伴机器人：会看人、会转头、会用表情回应，默认不联网。它不追求像人，追求的是「放在桌上不突兀，叫它会理你」。

- 预计材料费：**¥264 左右**（含运费与备件，明细见 [docs/01-物料清单.md](docs/01-物料清单.md)）
- 预计制作时间：**两个周末**，其中打印约 6 小时，装配约 2 小时
- 难度：入门偏中。需要会拧螺丝、插杜邦线；不需要焊贴片，不需要写代码
- 主控：ESP32-S3（自带 Wi-Fi 与 USB，但本项目默认不联网）

## 当前状态

<!-- forge:begin status-matrix -->
<!-- forge:end status-matrix -->

状态含义：✅ 已经实际跑通或有人工确认记录；🟡 只在仿真里验证过；⚪ 还没有验证；⛔ 已知有问题。**⚪ 不是失败，是诚实的待办。** 每条 must 需求的证据都在 [docs/09-验证报告.md](docs/09-验证报告.md)。

## 快速开始

拿到全部零件之后，按这个顺序做，每一步都有对应的检查点：

1. **买**：照着 [docs/01-物料清单.md](docs/01-物料清单.md) 下单，型号不要换；要换先看 [docs/10-常见问题.md](docs/10-常见问题.md)。
2. **打**：用 [docs/02-组装指南.md](docs/02-组装指南.md) 里的参数打印外壳，先打一个 20 mm 的测试块量公差。
3. **接**：按 [docs/03-接线表.md](docs/03-接线表.md) 插线。**上电之前不要装外壳**，先让板子裸奔测试。
4. **烧**：按 [docs/04-固件说明.md](docs/04-固件说明.md) 烧固件，串口能看到启动日志就成功了一半。
5. **装**：按 [docs/02-组装指南.md](docs/02-组装指南.md) 装配，三个检查点全部通过再往下走。
6. **用**：按 [docs/05-软件说明.md](docs/05-软件说明.md) 装主机软件，先跑无硬件的模拟模式，再接真机。
7. **验**：在项目根目录运行下面的命令，它会跑测试并把结果写进验证报告。

~~~bash
python tools/forge.py verify
~~~

看到全部必需项通过，再看 [docs/09-验证报告.md](docs/09-验证报告.md) 里还有哪些 ⚪ 需要你亲手确认。

### 从模板到可发布

~~~bash
python tools/forge.py design --write   # 先算清楚：扭矩、续航、线径、散热、成本
python tools/forge.py check            # 结构/引脚/电源/跨产物一致性
python tools/forge.py verify           # 真跑命令，记录证据与来源指纹
python tools/forge.py trace --write    # must 需求覆盖率
python tools/forge.py review           # 盲审包（含复现命令与机器发现）
python tools/forge.py audit            # 六维分：release / beta / blocked
python tools/forge.py package          # 只有 release/beta 才能打包
~~~

发布级要求：check 0 error、verify 全部 required 退出码 0、must 覆盖率 100%、audit ≥85 且无 blocker。

## 项目结构

~~~text
{{SLUG}}/
├── README.md                 你在这里
├── docs/                     00 总览 → 10 常见问题，按顺序读
├── hardware/
│   ├── bom.csv               物料表（由 robot.yaml 生成，别手改）
│   ├── cad/enclosure.py      外壳源码，改尺寸改这里
│   ├── cad/dims.json         关键尺寸，CAD 与仿真共用
│   └── stl/                  打印文件（运行 CAD 脚本生成）
├── firmware/                 ESP32-S3 固件（PlatformIO）
├── software/                 主机端 Python：协议、人格、模拟串口
├── sim/                      不用买硬件也能跑的自检：运动包络、电源
├── diagrams/                 架构图、接线图、装配图（自动生成）
└── forge/                    项目的单一事实源
    ├── robot.yaml            元件、引脚、电源、需求、风险
    ├── verify.yaml           一键验证命令
    ├── design.md             设计核算：扭矩、功耗、续航、线径、成本
    ├── trace.md              需求 × 命令 × 证据的覆盖矩阵
    ├── review-packet.md/json 可复现盲审包
    ├── evidence.jsonl        每次验证的证据
    ├── decisions.md          为什么这样选
    └── research.md           调研过哪些同类项目
~~~

**只改一个地方**：元件、引脚、电源、需求都写在 forge/robot.yaml，然后运行 ~~~bash python tools/forge.py render ~~~ 重新生成 BOM、接线表、图和验证报告。手改生成块会被检查发现。

## 安全

这是一个放在桌上、用 5V 适配器供电的小机器人，风险不高，但有三件事必须知道：

- **舵机堵转**：头部被手按住超过几秒，舵机会持续出力发热。固件有限流和超时停止，但你测试时不要长时间按住。详见 [docs/07-安全与隐私.md](docs/07-安全与隐私.md)。
- **电源**：只用 5V/3A 的 USB-C 适配器。不要把 5V 轨接到开发板的 3.3V 引脚，会烧主控。
- **隐私**：麦克风默认只在唤醒后采集，采集时灯环常亮；软件默认不联网，没有云端账号。家里有客人时，告诉他们机器人在听什么。

## 文档地图

| 你想做什么 | 看哪份 |
|---|---|
| 先搞懂它能干什么、不能干什么 | [docs/00-总览.md](docs/00-总览.md) |
| 买东西、对型号 | [docs/01-物料清单.md](docs/01-物料清单.md) |
| 打印、装配 | [docs/02-组装指南.md](docs/02-组装指南.md) |
| 插线、查电源 | [docs/03-接线表.md](docs/03-接线表.md) |
| 烧固件 | [docs/04-固件说明.md](docs/04-固件说明.md) |
| 装软件、接大模型 | [docs/05-软件说明.md](docs/05-软件说明.md) |
| 日常怎么用 | [docs/06-使用手册.md](docs/06-使用手册.md) |
| 安全和隐私边界 | [docs/07-安全与隐私.md](docs/07-安全与隐私.md) |
| 不动了、没声音 | [docs/08-故障排查.md](docs/08-故障排查.md) |
| 验证到哪一步了 | [docs/09-验证报告.md](docs/09-验证报告.md) |
| 常见疑问 | [docs/10-常见问题.md](docs/10-常见问题.md) |

## 许可

MIT。你可以做来卖，但请保留 LICENSE，并在说明里写清楚哪些验证做过了、哪些没做。不要拿一个 ⚪ 状态的项目说成「已验证」。
