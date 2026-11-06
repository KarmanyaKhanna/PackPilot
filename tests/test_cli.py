import hashlib
import json
import sys
from pathlib import Path
import pytest

from packpilot import cli
from packpilot.cli import main

EXAMPLE_CASES = Path(__file__).resolve().parents[1] / "examples" / "cases.json"

def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))

def write_suite(tmp_path, expected_info_count):
    suite = {
        "schema_version": 1,
        "entrypoint": "logsum",
        "cases": [
            {
                "name": "counts_info",
                "args": ["--json"],
                "stdin": "INFO service started\n",
                "timeout_seconds": 5,
                "expect": {
                    "exit_code": 0,
                    "stdout_json": {"INFO": expected_info_count, "WARNING": 0, "ERROR": 0},
                },
            }
        ],
    }
    path = tmp_path / "suite.json"
    path.write_text(json.dumps(suite), encoding="utf-8")
    return path

def test_passing_wheel_exits_zero_and_writes_a_report(logsum_wheel, tmp_path, capsys):
    report_path = tmp_path / "reports" / "wheel.json"
    exit_code = main(
        ["verify", "wheel", str(logsum_wheel), "--cases", str(EXAMPLE_CASES), "--report", str(report_path)]
    )
    assert exit_code == 0

    report = read_json(report_path)
    assert report["target_type"] == "wheel"
    assert report["target"]["entrypoint"] == "logsum"
    assert report["target"]["wheel_filename"] == logsum_wheel.name
    assert report["target"]["wheel_sha256"] == hashlib.sha256(logsum_wheel.read_bytes()).hexdigest()
    assert report["setup"]["status"] == "passed"
    assert report["summary"] == {"passed": 7, "failed": 0}

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "7 passed, 0 failed" in captured.err

def test_report_is_optional(logsum_wheel, tmp_path):
    suite = write_suite(tmp_path, expected_info_count=1)
    assert main(["verify", "wheel", str(logsum_wheel), "--cases", str(suite)]) == 0

def test_failed_case_exits_one_and_keeps_the_evidence(logsum_wheel, tmp_path, capsys):
    suite = write_suite(tmp_path, expected_info_count=99)
    report_path = tmp_path / "wheel.json"
    exit_code = main(
        ["verify", "wheel", str(logsum_wheel), "--cases", str(suite), "--report", str(report_path)]
    )
    assert exit_code == 1

    case = read_json(report_path)["cases"][0]
    assert case["status"] == "failed"
    assert case["reason"] == "stdout_mismatch"
    assert json.loads(case["actual_stdout"]) == {"INFO": 1, "WARNING": 0, "ERROR": 0}
    assert "FAIL counts_info" in capsys.readouterr().err

def test_install_failure_exits_one_and_is_reported(tmp_path, capsys):
    wheel = tmp_path / "logsum-0.1.0-py3-none-any.whl"
    wheel.write_bytes(b"this is not a zip file")
    suite = write_suite(tmp_path, expected_info_count=1)
    report_path = tmp_path / "wheel.json"
    exit_code = main(["verify", "wheel", str(wheel), "--cases", str(suite), "--report", str(report_path)])
    assert exit_code == 1

    report = read_json(report_path)
    assert report["setup"]["status"] == "failed"
    assert report["setup"]["reason"] == "install_failed"
    assert "invalid" in report["setup"]["detail"]
    assert report["cases"] == []
    assert "SETUP FAILED" in capsys.readouterr().err

def test_invalid_suite_exits_two_before_any_install(tmp_path, monkeypatch, capsys):
    def fail_if_called(*args):
        pytest.fail("the wheel should not be installed for an invalid suite")

    monkeypatch.setattr(cli, "installed_wheel", fail_if_called)
    wheel = tmp_path / "logsum-0.1.0-py3-none-any.whl"
    wheel.write_bytes(b"unused")
    suite = tmp_path / "suite.json"
    suite.write_text("{not valid json", encoding="utf-8")
    report_path = tmp_path / "wheel.json"

    exit_code = main(["verify", "wheel", str(wheel), "--cases", str(suite), "--report", str(report_path)])

    assert exit_code == 2
    assert not report_path.exists()
    assert "packpilot: error:" in capsys.readouterr().err

def test_missing_wheel_exits_two(tmp_path, capsys):
    suite = write_suite(tmp_path, expected_info_count=1)
    exit_code = main(["verify", "wheel", str(tmp_path / "missing.whl"), "--cases", str(suite)])
    assert exit_code == 2
    assert "wheel file not found" in capsys.readouterr().err

def test_venv_failure_exits_two(tmp_path, monkeypatch, capsys):
    wheel = tmp_path / "logsum-0.1.0-py3-none-any.whl"
    wheel.write_bytes(b"unused")
    suite = write_suite(tmp_path, expected_info_count=1)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "no-such-python"))
    exit_code = main(["verify", "wheel", str(wheel), "--cases", str(suite)])
    assert exit_code == 2
    assert "create venv failed" in capsys.readouterr().err

def test_unwritable_report_path_exits_two(logsum_wheel, tmp_path, capsys):
    suite = write_suite(tmp_path, expected_info_count=1)
    blocker = tmp_path / "a-file"
    blocker.write_text("", encoding="utf-8")
    exit_code = main(
        ["verify", "wheel", str(logsum_wheel), "--cases", str(suite), "--report", str(blocker / "wheel.json")]
    )
    assert exit_code == 2
    assert "could not write report" in capsys.readouterr().err

@pytest.mark.parametrize(
    "argv",
    [
        [],
        ["verify"],
        ["verify", "wheel"],
        ["verify", "wheel", "some.whl"],
    ],
)
def test_incomplete_commands_exit_two(argv):
    with pytest.raises(SystemExit) as error:
        main(argv)
    assert error.value.code == 2

def test_version_exits_zero(capsys):
    with pytest.raises(SystemExit) as error:
        main(["--version"])
    assert error.value.code == 0
    assert "packpilot 0.1.0" in capsys.readouterr().out