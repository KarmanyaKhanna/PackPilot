import sys

import pytest

from packpilot.engine import (
    EXIT_CODE_MISMATCH,
    FAILED,
    INVALID_JSON,
    PASSED,
    STDERR_MISMATCH,
    STDOUT_MISMATCH,
    check_result,
    run_case,
    run_suite,
)
from packpilot.models import ExpectedResult, ProcessResult, TestCase, TestSuite
from packpilot.process import COMMAND_NOT_FOUND, TIMEOUT


def make_case(name="sample", args=None, stdin="", timeout_seconds=10, **expect):
    expect.setdefault("exit_code", 0)
    return TestCase(
        name=name,
        args=args or [],
        stdin=stdin,
        timeout_seconds=timeout_seconds,
        expect=ExpectedResult(**expect),
    )


def make_process(exit_code=0, stdout="", stderr="", failure=None):
    return ProcessResult(
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        duration_seconds=0.1,
        failure=failure,
    )


def test_json_comparison_ignores_key_order_and_whitespace():
    case = make_case(stdout_json={"INFO": 1, "ERROR": 2})
    process = make_process(stdout='{ "ERROR": 2,\n  "INFO": 1 }\n')
    assert check_result(case, process) is None


def test_expected_nonzero_exit_passes():
    case = make_case(exit_code=2, stderr_contains="line 1")
    process = make_process(exit_code=2, stderr="error on line 1\n")
    assert check_result(case, process) is None


def test_exit_code_mismatch_explains_both_values():
    reason, detail = check_result(make_case(exit_code=0), make_process(exit_code=1))
    assert reason == EXIT_CODE_MISMATCH
    assert "expected exit code 0" in detail
    assert "got 1" in detail


def test_invalid_json_is_distinct_from_wrong_json():
    case = make_case(stdout_json={"INFO": 1})
    reason, _ = check_result(case, make_process(stdout="not json"))
    assert reason == INVALID_JSON


@pytest.mark.parametrize(
    "stdout",
    ['{"INFO": 2}', '{"INFO": true}', '{"INFO": 1, "ERROR": 0}', "[1]", "{}"],
)
def test_wrong_json_is_a_stdout_mismatch(stdout):
    case = make_case(stdout_json={"INFO": 1})
    reason, _ = check_result(case, make_process(stdout=stdout))
    assert reason == STDOUT_MISMATCH


def test_empty_expected_json_is_still_checked():
    case = make_case(stdout_json={})
    reason, _ = check_result(case, make_process(stdout='{"INFO": 1}'))
    assert reason == STDOUT_MISMATCH


def test_stdout_contains_mismatch():
    case = make_case(stdout_contains="usage")
    reason, detail = check_result(case, make_process(stdout="nothing useful"))
    assert reason == STDOUT_MISMATCH
    assert "usage" in detail


def test_stderr_contains_mismatch():
    case = make_case(stderr_contains="line 1")
    reason, detail = check_result(case, make_process(stderr="other error"))
    assert reason == STDERR_MISMATCH
    assert "line 1" in detail


@pytest.mark.parametrize("failure", [COMMAND_NOT_FOUND, TIMEOUT])
def test_process_failure_is_reported_as_the_reason(failure):
    reason, _ = check_result(make_case(), make_process(exit_code=None, failure=failure))
    assert reason == failure


def test_run_case_keeps_the_evidence_when_it_fails():
    code = "import sys; print('out'); print('err', file=sys.stderr); raise SystemExit(3)"
    result = run_case(make_case(exit_code=0), [sys.executable, "-c", code])
    assert result.status == FAILED
    assert result.reason == EXIT_CODE_MISMATCH
    assert result.actual_exit_code == 3
    assert result.actual_stdout == "out\n"
    assert result.actual_stderr == "err\n"


def test_run_case_appends_case_args_to_the_prefix():
    code = "import json, sys; print(json.dumps({'args': sys.argv[1:]}))"
    case = make_case(args=["--json", "two words"], stdout_json={"args": ["--json", "two words"]})
    result = run_case(case, [sys.executable, "-c", code])
    assert result.status == PASSED
    assert result.reason is None


def test_run_suite_continues_after_a_failure_and_counts_results():
    suite = TestSuite(
        schema_version=1,
        entrypoint="fake",
        cases=[
            make_case(name="fails_first", exit_code=1),
            make_case(name="passes_second", exit_code=0),
        ],
    )
    report = run_suite(suite, [sys.executable, "-c", "pass"])
    assert [case.name for case in report.cases] == ["fails_first", "passes_second"]
    assert [case.status for case in report.cases] == [FAILED, PASSED]
    assert report.summary == {"passed": 1, "failed": 1}
