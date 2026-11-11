# 全栈工程核算 v2.0（扭矩 / 功率 / 续航 / 线径 / 散热 / 成本）

> 目标：在买件之前，用可复算的数字回答“够不够、热不热、跑多久、线会不会烧、预算超不超”。
> `rf_design` 会按本文件公式计算并写 `forge/design.md`；核算**不替代实测**，实测证据以 `forge/evidence.jsonl` 为准。
> 文中常数与 `forgekit/design.py` 一致：G=9.81、CRR=0.03、DRIVE_MARGIN=1.5、CONVERTER_EFF=0.85。

---

## 1. 先补全输入

| 字段 | 位置 | 缺失后果 |
|---|---|---|
| 整机质量 `mechanical.mass_kg` | robot.yaml | 无法算扭矩/加速度，DSN-11 |
| 轮径/轮距 | `mechanical.dims` 或 `motion` | 无法算轮速/转弯半径 |
| 驱动数 `mechanical.drive_count` | robot.yaml | 按元件 actuator 数量猜，可能少算 |
| 执行器 `torque_kgcm`、`rated_current_ma`、`stall_current_ma` | components | DSN-02/DSN-09，只能做定性判断 |
| 电源轨电压/最大电流 | `power.rails` | 无法算余量与续航 |
| 电池容量/节数 | `power.battery` | 无法算 Wh、C-rate、续航 |
| 负载/臂展 | `mechanical.payload_kg`/`reach_m` | 机械臂扭矩只能估 |

**原则**：宁可写“估计值 + 来源”，也不要留空。缺规格时去 datasheet 找堵转扭矩/额定电流，并在 `decisions` 写“取堵转的 1/3 作为连续值”。

---

## 2. 轮式/履带：扭矩与加速度

### 2.1 所需扭矩

```text
F = (m + payload) × g × (sinθ + Crr × cosθ) × margin      [N]
T_total = F × r                                           [N·m]
T_per_motor = T_total / n                                 [N·m]
T_kgcm = T_per_motor × 10.197
```

- m：整机质量 kg；payload：额外负载 kg；θ：最大坡度（室内 0°，无障碍坡 0–3°）；
- Crr：滚阻系数，硬地轮胎 0.02–0.04，地毯 0.05–0.08；默认 0.03；
- margin：驱动余量，默认 1.5（起步/坡道/电池衰减）；
- r：轮半径 m（轮径 mm ÷ 2000）；n：驱动电机数。

**判定**：`available < required` → DSN-01 error；`available/required < 1.2` → warning；无 torque 数据 → DSN-02 warning。
**示例**（wheel-rover）：m=1.05、r=0.0325、n=2、θ=0、margin=1.5 → F≈0.46 N，T≈0.0075 N·m，即 **0.08 kg·cm**；MG90S 级别的 0.8 kg·cm 余量 10×，TT 电机堵转 0.8 kg·cm 也够。

### 2.2 速度与加速度

```text
v_max = π × D × RPM / 60                 [m/s]（D 为轮径 m）
a_max = (T_per_motor × n / r − F_resist) / (m + payload)   [m/s²]
t_0→v = v_target / a_max
```

- 要求 `v_max ≥ mechanical.limits.max_linear_mps`，否则换减速比或轮径；
- 室内小车 `a_max ≥ 0.5 m/s²` 才不至于“起步肉”；急停距离按 `v²/(2a)` 估算，必须小于 `stop_distance_mm`；
- 爬坡能力：`sinθ_max = (T×n/r)/((m+payload)g) − Crr`，据此写“能上多陡的坡”。

### 2.3 差速转弯

```text
v_left  = v − ω × b / 2
v_right = v + ω × b / 2
R = v / ω（ω≠0）
```

b 为轮距；任一轮速超 `v_max` 就限幅并在文档写清“最大角速度随线速度下降”。30 cm 停障要同时满足：传感器刷新 + 控制周期 + 制动距离；控制 50 Hz 时单周期 20 ms。

---

## 3. 机械臂/云台：关节扭矩

```text
T_joint = payload × g × reach × margin / (n × gear_ratio)    [N·m]
T_kgcm  = T_joint × 10.197
```

- reach：负载重心到关节的最大水平距离 m；多关节臂按最不利姿态逐关节算；
- 舵机 `torque_kgcm` 取“堵转扭矩的 1/3–1/2”作为连续值，不要拿堵转值当额定；
- 静态保持还要加臂自重项：`T = (payload + link_mass/2) × g × reach`；
- 云台只需克服偏心负载与线缆阻力，但必须留 2× 余量抵消风阻/惯量。

**判定**：任何关节 `available/required < 1.2` 不选该舵机；没有 `torque_kgcm` 就查 datasheet，查不到换型号。

---

## 4. 电源、续航与 C-rate

### 4.1 每轨电流

```text
I_typ(rail) = Σ consumer.typical_ma
I_peak(rail) = Σ consumer.peak_ma
余量 = 1 − I_peak / rail.max_ma
```

- `peak > 90%` → S6 error（必然掉压）；`typ > 70%` → warning；建议峰值 ≤80%；
- 所有 consumer 的 `rail` 必须存在；执行器堵转电流按峰值算，不能按额定；
- 降压模块效率按 0.85 折算到电池侧：`P_batt = P_rail / 0.85`。

### 4.2 电池与续航

```text
Wh = mAh / 1000 × V_nominal
I_batt_typ = Σ(rail.voltage × rail.typical_ma) / V_batt / 0.85
runtime_h = Wh × 0.85 / (V_batt × I_batt_typ)
C_rate = I_peak_batt / (mAh / 1000)
```

- 2S 18650 2000 mAh = 7.4 V × 2 Ah = **14.8 Wh**；0.85 为可用容量系数；
- `C_rate > 1` 对普通 18650 已偏高，`> 2` 基本不可用；动力电芯才看 5C 以上；
- 续航低于目标 80% → DSN-03 error；没有电池 → DSN-10；
- 续航是“典型负载”，不是峰值；文档要写“测试条件 + 实测值”。

### 4.3 上电与保护

- 电池 → 保险丝/船型开关 → 降压 → 负载；保险丝按峰值 ×1.5 选，慢断；
- 大电容预充：≥470 µF 的轨加 10 Ω 预充电阻或热插拔电路；
- 反接保护：理想二极管/MOS 防反接；至少做防呆插头 + 丝印；
- 上电顺序：主控先起、执行器后使能；断电相反；写进 docs/03。

---

## 5. 线径与连接器

按峰值电流、30 cm 以内、温升 30 K 粗算（`design.py` 的 AWG_TABLE）：

| 峰值电流 A | AWG | 截面积 mm² |
|---:|---:|---:|
| ≤5 | 20 | 0.52 |
| ≤10 | 18 | 0.82 |
| ≤15 | 16 | 1.31 |
| ≤25 | 14 | 2.08 |
| ≤35 | 12 | 3.31 |
| ≤50 | 10 | 5.26 |
| ≤70 | 8 | 8.37 |

- 电机线按堵转电流选，不能按额定；长线/高温再降一档；
- 连接器额定值单独核对（XT30 30 A、XT60 60 A、JST-XH 3 A）；
- 信号线与功率线分开走，避免共阻抗耦合；星形接地，主控/驱动/传感器共地。

---

## 6. 散热

```text
P_loss ≈ Σ(actuator.rated_current_ma / 1000 × rail.voltage) × 0.3   [W]
功率密度 = P_loss / enclosure_volume_L                            [W/L]
```

- 密度 >10 W/L → DSN-09 warning：加通风孔、金属底板、降额或改外置驱动；
- 封闭塑料盒按 5 W/L 保守；连续堵转按 stall current 算最坏；
- 实测：满负载 10 min，测驱动/电机/降压外壳温升；>60 K 必须改散热；
- 电池远离发热件；锂电工作温度 0–45 °C，充电 0–45 °C。

---

## 7. 成本

```text
total = Σ(component.price_cny × qty) + cost.shipping_cny
used% = total / budget × 100
```

- >115% → S7 warning；>150% → S7 error；
- 报价日期写 `cost.quote_date`，价格是快照，采购前复核；
- 预留 10% 备件/损耗（烧驱动、断线、运费）；
- 超出时先砍“nice”功能与外观件，不砍安全件（保险丝、保护板、急停）。

---

## 8. 设计评审清单

- [ ] 质量有来源（称重/规格书/BOM 估算），不是拍的；
- [ ] 每个执行器有扭矩/电流；每个电源轨峰值 ≤80%；
- [ ] 续航按典型负载算过，且写明测试条件；
- [ ] 线径按峰值选，连接器额定值核对过；
- [ ] 散热有最坏工况估算或实测计划；
- [ ] 成本含运费/备件，未超预算 115%；
- [ ] 安全件（保险丝、保护板、急停、限位、护罩）没有因为省钱被删；
- [ ] 所有假设写进 `decisions` / `assumptions`，可被后来者复核。

## 9. 常见错误

1. 拿舵机**堵转扭矩**当额定，长期工作烧毁；
2. 用额定电流算峰值，降压模块一启动就掉压复位；
3. 续航按电池标称容量算，忽略 0.85 可用系数与降压损耗；
4. 电机线与信号线同规格，电机启动时主控复位；
5. 只算总功率不看单轨，5 V 轨被舵机拉垮；
6. 机械臂只算负载不算臂自重；
7. 成本漏运费、工具、备件与失败重买；
8. 把“仿真通过”写成“实测通过”。
