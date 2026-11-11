# robotd

小豆的主机侧大脑。负责串口通信、人格状态与语音链路编排。

~~~bash
python -m pip install -e .
python -m robotd.main --mock --seconds 20
~~~

默认不联网。只有显式设置 ROBOTD_BRAIN=external 且 ROBOTD_NETWORK=1 时才会访问你配置的服务。
