from robotd.main import main


def test_mock_run_prints_full_loop(capsys):
    assert main(["--mock", "--seconds", "0"]) == 0
    output = capsys.readouterr().out
    assert "[boot]" in output
    assert "[face] happy" in output
    assert "[face] alert" in output
    assert "[say]" in output


def test_external_brain_requires_opt_in(monkeypatch, capsys):
    monkeypatch.delenv("ROBOTD_NETWORK", raising=False)
    assert main(["--mock", "--brain", "external", "--brain-url", "http://127.0.0.1:9"]) == 2
    assert "ROBOTD_NETWORK" in capsys.readouterr().err


def test_no_port_means_mock(capsys):
    assert main(["--seconds", "0"]) == 0
    assert "mock mode" in capsys.readouterr().out
