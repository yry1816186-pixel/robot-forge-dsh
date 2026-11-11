import pytest

from robotd.teleop import line_for_key, line_for_script_command


def test_forward_key():
    assert line_for_key("w") == "V 150 0\n"


def test_turn_keys():
    assert line_for_key("a") == "V 0 700\n"
    assert line_for_key("d") == "V 0 -700\n"


def test_uppercase_key():
    assert line_for_key("W") == "V 150 0\n"


def test_unknown_key_is_none():
    assert line_for_key("x") is None


def test_script_commands():
    assert line_for_script_command("forward") == "V 150 0\n"
    assert line_for_script_command("back") == "V -150 0\n"
    assert line_for_script_command("left") == "V 0 700\n"
    assert line_for_script_command("right") == "V 0 -700\n"
    assert line_for_script_command("stop") == "S\n"
    assert line_for_script_command("ping") == "PING\n"


def test_script_rejects_unknown():
    with pytest.raises(ValueError):
        line_for_script_command("jump")
