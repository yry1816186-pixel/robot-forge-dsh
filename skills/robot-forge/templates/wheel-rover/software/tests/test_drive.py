import pytest

from robotd import drive


def test_straight():
    left, right = drive.mix(0.2, 0.0)
    assert left == pytest.approx(0.2)
    assert right == pytest.approx(0.2)


def test_spin_in_place_has_opposite_wheels():
    left, right = drive.mix(0.0, 1.0)
    assert left < 0 < right
    assert abs(left) == pytest.approx(abs(right))


def test_left_turn_faster_right_wheel():
    left, right = drive.mix(0.2, 1.0)
    assert right > left


def test_clamp_preserves_direction():
    left, right = drive.mix(0.4, 1.2, max_wheel_mps=0.3)
    assert max(abs(left), abs(right)) == pytest.approx(0.3)
    assert right > left


def test_zero_command():
    assert drive.mix(0.0, 0.0) == (0.0, 0.0)


def test_invalid_parameters():
    with pytest.raises(ValueError):
        drive.mix(0.1, 0.1, wheel_base_m=0)
    with pytest.raises(ValueError):
        drive.mix(0.1, 0.1, max_wheel_mps=0)


def test_wheel_speeds_from_mm_units():
    left, right = drive.wheel_speeds_mps(200, 0)
    assert left == pytest.approx(0.2)
    assert right == pytest.approx(0.2)


def test_turning_radius():
    assert drive.turning_radius_m(0.2, 0.0) is None
    assert drive.turning_radius_m(0.2, 1.0) == pytest.approx(0.2)


def test_projected_stop_distance():
    distance = drive.projected_stop_mm(0.4)
    assert 50 < distance < 300


def test_projected_stop_rejects_negative():
    with pytest.raises(ValueError):
        drive.projected_stop_mm(-0.1)


def test_clamp_command():
    assert drive.clamp_command(999, -2000) == (400, -1200)
    assert drive.clamp_command(100, 100) == (100, 100)
