import pytest

from robotd.protocol import ProtocolError, emo, parse_line, pose


@pytest.mark.parametrize(
    "line, name",
    [
        ("EMO happy", "EMO"),
        ("emo HAPPY", "EMO"),
        ("POSE 30 -10", "POSE"),
        ("LED 255 128 0", "LED"),
        ("MIC on", "MIC"),
        ("VOL 60", "VOL"),
        ("TOUCH head", "TOUCH"),
        ("DIST 620", "DIST"),
        ("LEVEL 42", "LEVEL"),
        ("READY", "READY"),
        ("ERR stall", "ERR"),
    ],
)
def test_valid_lines(line, name):
    assert parse_line(line).name == name


@pytest.mark.parametrize(
    "line",
    [
        "",
        "   ",
        "FLY 3",
        "EMO angry",
        "POSE 100 0",
        "POSE 0 90",
        "POSE x y",
        "LED 300 0 0",
        "MIC maybe",
        "VOL 101",
        "DIST 99999",
        "LEVEL 101",
        "TOUCH nose",
        "READY now",
    ],
)
def test_invalid_lines_rejected(line):
    with pytest.raises(ProtocolError):
        parse_line(line)


def test_encoders_round_trip():
    for line in (emo("happy"), pose(10, -5)):
        assert parse_line(line).render() == line


def test_line_length_cap():
    with pytest.raises(ProtocolError):
        parse_line("EMO " + "a" * 200)