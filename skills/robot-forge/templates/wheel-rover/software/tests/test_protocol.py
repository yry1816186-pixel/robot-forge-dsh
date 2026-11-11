import pytest

from robotd import protocol


def test_velocity_encodes_line():
    assert protocol.encode_velocity(200, -300) == "V 200 -300\n"


def test_velocity_rejects_non_integer():
    with pytest.raises(protocol.ProtocolError):
        protocol.encode_velocity("fast", 0)


def test_velocity_rejects_out_of_range():
    with pytest.raises(protocol.ProtocolError):
        protocol.encode_velocity(401, 0)
    with pytest.raises(protocol.ProtocolError):
        protocol.encode_velocity(0, -1201)


def test_limits_are_inclusive():
    assert protocol.encode_velocity(400, 1200) == "V 400 1200\n"
    assert protocol.encode_velocity(-400, -1200) == "V -400 -1200\n"


def test_split_lines_keeps_tail():
    lines, tail = protocol.split_lines("OK\nT 0 0 400 0 7800\nT 0")
    assert lines == ["OK", "T 0 0 400 0 7800"]
    assert tail == "T 0"


def test_split_lines_handles_crlf():
    lines, tail = protocol.split_lines("OK\r\nPING\r\n")
    assert lines == ["OK", "PING"]
    assert tail == ""


def test_parse_ok():
    assert protocol.parse_reply("OK") == {"kind": "ok"}


def test_parse_err():
    assert protocol.parse_reply("ERR 6") == {"kind": "err", "code": 6}


def test_parse_telemetry():
    t = protocol.parse_reply("T 12 -3 410 15 7810")
    assert t["kind"] == "telemetry"
    assert t["enc_l"] == 12
    assert t["enc_r"] == -3
    assert t["dist_mm"] == 410
    assert t["yaw_mdeg"] == 15
    assert t["batt_mv"] == 7810


@pytest.mark.parametrize("line", ["", "HELLO", "T 1 2 3", "T a b c d e", "ERR x", "ERR"])
def test_parse_rejects_garbage(line):
    with pytest.raises(protocol.ProtocolError):
        protocol.parse_reply(line)


def test_describe_error():
    assert "obstacle" in protocol.describe_error(6)
    assert "error 99" in protocol.describe_error(99)
