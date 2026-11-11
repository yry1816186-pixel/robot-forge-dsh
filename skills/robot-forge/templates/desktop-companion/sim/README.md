# sim

不接硬件也能跑的验证脚本。

| 脚本 | 验证什么 | 需要 |
|---|---|---|
| check_reach.py | 两个轴的角度范围在机构包络内，俯仰到极限时头不撞身 | 无 |
| check_power.py | 每条电源轨的峰值不超供，整机成本不超预算 | 无 |
| play.py | 在 MuJoCo 里查看动作 | mujoco |

~~~bash
python sim/check_reach.py
python sim/check_power.py
python sim/play.py        # 可选，需要 pip install mujoco
~~~

两个检查脚本都以退出码表示结果：0 通过，1 失败。它们读 forge/robot.yaml 与 hardware/cad/dims.json，所以改设计后不用改脚本。

MuJoCo 场景只用于观察动作节奏，不作为验收依据；验收以 check_* 与实机测试为准。
