在 wheel-rover 蓝本上改：超声 trig 从 GPIO 11 改到 GPIO 21，echo 保持 12。固件 config.h、docs/03 的引脚表、forge/robot.yaml 的 pins 必须三处同步，别只改文档。改完跑 check，证明没有 GPIO 冲突、没有跨产物不一致。
