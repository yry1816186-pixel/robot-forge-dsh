# {{NAME}}

一台**能真的跑起来**的两轮差速小车：插上电池，用键盘遥控它前进、后退、转弯；前方 30 cm 有障碍会自动停；OLED 显示电压和距离。

> 目标不是做一台玩具，而是让第一次接触机器人的人完成一次**完整的工程闭环**：买对件 → 接对线 → 烧程序 → 跑起来 → 有证据。

## 这台车适合谁

适合第一次做机器人、想亲手把「能动的车」做出来的人。你不需要会写代码，也不需要会画三维图；需要的是耐心、一把螺丝刀、一个能插杜邦线的桌面，以及按步骤做、不跳步的习惯。它会带你认识主控、电机驱动、电池、传感器和串口，让你知道每个零件为什么在这里。

不适合想直接拿成品去越野、载重或长时间户外运行的人。这台车的定位是室内地面、低速、看得见的安全边界：遇到台阶会停，地毯会打滑，续航和负载都有明确上限。先把这套基础跑通，再谈升级。

## 快速开始

```bash
# 1. 检查环境（Python 3.10+）
python tools/forge.py doctor

# 2. 没有硬件也能先跑主机软件
python -m pytest software/tests -q
python -m robotd.main --mock --script "forward,left,stop"

# 3. 照 docs/02 装配、docs/03 接线、docs/04 烧录
# 4. 真机验证并登记证据
python tools/forge.py verify
```

<!-- forge:begin status-matrix -->
<!-- forge:end status-matrix -->

## 项目结构

```text
{{SLUG}}/
├── docs/            # 00 总览 … 10 常见问题
├── firmware/        # PlatformIO：ESP32-S3 + 纯 C++ 核心库
├── hardware/        # BOM、接线、采购（无自制结构件）
├── software/        # robotd：协议、差速混控、模拟链路、pytest
├── sim/             # 运动学与功率核算（不需要实物）
├── tools/           # forge.py + forgekit（随项目固定版本）
└── forge/           # robot.yaml、verify.yaml、design.md、trace.md、review-packet、证据账本
```

## 七阶段与机器门

从愿望到可发布，按同一套顺序推进；每一步都有可判定的退出条件：

```bash
python tools/forge.py intake "能避障、能遥控的小车，预算 300"        # A 接单：形态/预算/安全旗标
python tools/forge.py new my-rover --blueprint wheel-rover           # B 定案：生成项目
python tools/forge.py design --write                                 # C 架构：扭矩/续航/线径/成本
python tools/forge.py check                                          # D 建造：结构/引脚/电源/一致性
python tools/forge.py verify                                         # E 证明：真跑命令并记证据
python tools/forge.py trace --write                                  #   需求覆盖矩阵
python tools/forge.py review                                         # F 盲审包
python tools/forge.py audit                                          # G 发布判定
python tools/forge.py package                                        #   可复现 zip + SHA256
```

发布级要求：check 0 error、verify 全部 required 退出码 0、must 覆盖率 100%、audit ≥85 且无 blocker，缺一不可。

## 安全

- 2S 18650 是**锂电池**：必须用带保护板的电池组和匹配的平衡充；接线前断电，正负极反接会烧驱动。
- 第一次上电把车架空，确认轮子转向正确再落地。
- 卡住轮子会堵转发热：立即断电，不要用手硬拽。
- 不要把电池放在无人看管的地方充电；鼓包、破皮、发热的电池直接报废。

详见 [docs/07-安全与隐私.md](docs/07-安全与隐私.md)。

## 限制

- 不做室外越野、不承诺爬坡；地毯和门槛会打滑。
- 没有编码器，速度是开环的；直线靠 IMU 修正，长时间仍会漂移。
- 默认不联网；遥控走 USB 串口，不是 Wi-Fi。

## 许可

MIT。第三方库与工具的许可见 [docs/00-总览.md](docs/00-总览.md)。
