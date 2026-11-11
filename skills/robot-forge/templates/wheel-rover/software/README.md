# robotd

主机侧遥控与安全监督。没有硬件时用 `--mock` 跑通协议与状态机。

```bash
python -m pip install -e .
python -m pytest tests -q
python -m robotd.main --mock --script "forward,left,stop"
```

真机：

```bash
python -m robotd.main --port COM5
```

安全边界：本程序只负责发命令与收遥测；30cm 自动停车、心跳超时停车在固件里。主机崩溃不应导致车继续跑。
