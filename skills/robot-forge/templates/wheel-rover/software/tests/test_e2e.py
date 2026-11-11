from robotd.link import MockLink
from robotd.main import run_script


def test_script_drives_mock():
    link = MockLink()
    assert run_script(link, "forward,left,stop") == 0
    assert link.linear_mm_s == 0
    assert link.angular_mrad_s == 0


def test_forward_sets_motion():
    link = MockLink()
    assert link.send("V 150 0") == "OK"
    assert link.linear_mm_s == 150


def test_stop_clears_motion():
    link = MockLink()
    link.send("V 150 0")
    assert link.send("S") == "OK"
    assert link.moving is False


def test_obstacle_blocks_forward():
    link = MockLink(distance_mm=200)
    assert link.send("V 150 0") == "ERR 6"
    assert link.moving is False


def test_obstacle_allows_backward():
    link = MockLink(distance_mm=200)
    assert link.send("V -100 0") == "OK"


def test_unknown_command():
    assert MockLink().send("FLY 1 2") == "ERR 2"


def test_overspeed_rejected():
    assert MockLink().send("V 900 0") == "ERR 5"


def test_bad_argument_count():
    assert MockLink().send("V 100") == "ERR 3"


def test_bad_argument_value():
    assert MockLink().send("V fast 0") == "ERR 4"


def test_telemetry_shape():
    link = MockLink(distance_mm=432, battery_mv=7700)
    frames = []
    for _ in range(4):
        frames.extend(link.poll())
    assert frames, "mock should emit telemetry"
    assert frames[0].startswith("T ")


def test_script_unknown_returns_2():
    link = MockLink()
    assert run_script(link, "forward,jump") == 2
