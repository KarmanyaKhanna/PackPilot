import json
from datetime import datetime, timedelta

from packpilot.engine import FAILED, PASSED
from packpilot.models import CaseResult, ExpectedResult, SetupResult, VerificationReport
from packpilot.report import build_report, print_summary, report_passed, write_report

TARGET = {"wheel_filename": "logsum-0.1.0-py3-none-any.whl", "wheel_sha256": "abc123"}

def make_results(status=PASSED, reason=None, detail=None, stderr=""):
    case = CaseResult(
        name="sample",
        args=["--json"],
        expected=ExpectedResult(exit_code=0),
        actual_exit_code=0 if status == PASSED else 1,
        actual_stdout="",
        actual_stderr=stderr,
        duration_seconds=0.1,
        status=status,
        reason=reason,
        detail=detail,
    )
    summary = {"passed": 1, "failed": 0} if status == PASSED else {"passed": 0, "failed": 1}
    return VerificationReport(schema_version=1, cases=[case], summary=summary)

def passed_setup():
    return SetupResult(status=PASSED, duration_seconds=1.5)

def failed_setup():
    return SetupResult(
        status=FAILED,
        duration_seconds=1.5,
        reason="install_failed",
        detail="pip said no",
    )

def test_report_contains_the_required_identity_and_environment():
    report = build_report("wheel", TARGET, passed_setup(), make_results())
    assert report["schema_version"] == 1
    assert report["target_type"] == "wheel"
    assert report["target"] == TARGET
    assert set(report["environment"]) == {
        "os",
        "architecture",
        "runner_python_version",
        "runner_python_executable",
    }

def test_timestamp_is_utc():
    report = build_report("wheel", TARGET, passed_setup(), make_results())
    timestamp = datetime.fromisoformat(report["timestamp"])
    assert timestamp.utcoffset() == timedelta(0)

def test_case_evidence_is_included():
    results = make_results(FAILED, "exit_code_mismatch", "expected 0, got 1", "boom\n")
    case = build_report("wheel", TARGET, passed_setup(), results)["cases"][0]
    assert case["name"] == "sample"
    assert case["args"] == ["--json"]
    assert case["expected"]["exit_code"] == 0
    assert case["actual_exit_code"] == 1
    assert case["actual_stderr"] == "boom\n"
    assert case["reason"] == "exit_code_mismatch"
    assert case["detail"] == "expected 0, got 1"

def test_setup_failure_has_details_and_no_cases():
    report = build_report("wheel", TARGET, failed_setup(), None)
    assert report["setup"]["reason"] == "install_failed"
    assert report["setup"]["detail"] == "pip said no"
    assert report["cases"] == []
    assert report["summary"] == {"passed": 0, "failed": 0}

def test_report_passed_requires_setup_and_all_cases_to_pass():
    assert report_passed(build_report("wheel", TARGET, passed_setup(), make_results()))
    failed_case = make_results(FAILED, "stdout_mismatch", "different")
    assert not report_passed(build_report("wheel", TARGET, passed_setup(), failed_case))
    assert not report_passed(build_report("wheel", TARGET, failed_setup(), None))

def test_write_report_creates_folders_and_valid_json(tmp_path):
    report = build_report("wheel", TARGET, passed_setup(), make_results())
    path = tmp_path / "nested" / "reports" / "wheel.json"
    write_report(report, path)
    assert json.loads(path.read_text(encoding="utf-8")) == report

def test_print_summary_uses_stderr_only(capsys):
    results = make_results(FAILED, "exit_code_mismatch", "expected 0, got 1", "boom\n")
    print_summary(build_report("wheel", TARGET, passed_setup(), results))
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "FAIL sample: exit_code_mismatch: expected 0, got 1" in captured.err
    assert "stderr: boom" in captured.err
    assert "0 passed, 1 failed" in captured.err