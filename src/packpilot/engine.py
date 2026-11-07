from __future__ import annotations

import json
from pathlib import Path

from packpilot.models import CaseResult, ProcessResult, TestCase, TestSuite, VerificationReport
from packpilot.process import TIMEOUT, run_command

PASSED = "passed"
FAILED = "failed"

EXIT_CODE_MISMATCH = "exit_code_mismatch"
INVALID_JSON = "invalid_json"
STDOUT_MISMATCH = "stdout_mismatch"
STDERR_MISMATCH = "stderr_mismatch"


def check_result(case: TestCase, process: ProcessResult) -> tuple[str, str] | None:
    expected = case.expect
    if process.failure == TIMEOUT:
        return process.failure, f"command did not finish within {case.timeout_seconds} seconds"
    if process.failure is not None:
        return process.failure, f"command could not be run: {process.stderr}"

    if process.exit_code != expected.exit_code:
        return (
            EXIT_CODE_MISMATCH,
            f"expected exit code {expected.exit_code}, got {process.exit_code}",
        )

    if expected.stdout_json is not None:
        try:
            actual_json = json.loads(process.stdout)
        except json.JSONDecodeError as e:
            return INVALID_JSON, f"stdout is not valid JSON: {e}"
        if _canonical(actual_json) != _canonical(expected.stdout_json):
            return (
                STDOUT_MISMATCH,
                f"expected stdout JSON {_canonical(expected.stdout_json)}, "
                f"got {_canonical(actual_json)}",
            )
    if expected.stdout_contains is not None and expected.stdout_contains not in process.stdout:
        return STDOUT_MISMATCH, f"stdout does not contain {expected.stdout_contains!r}"

    if expected.stderr_contains is not None and expected.stderr_contains not in process.stderr:
        return STDERR_MISMATCH, f"stderr does not contain {expected.stderr_contains!r}"

    return None


def run_case(
    case: TestCase,
    command_prefix: list[str],
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> CaseResult:
    process = run_command(
        [*command_prefix, *case.args],
        stdin=case.stdin,
        timeout_seconds=case.timeout_seconds,
        cwd=cwd,
        env=env,
    )
    problem = check_result(case, process)
    reason, detail = problem if problem is not None else (None, None)

    return CaseResult(
        name=case.name,
        args=case.args,
        expected=case.expect,
        actual_exit_code=process.exit_code,
        actual_stdout=process.stdout,
        actual_stderr=process.stderr,
        duration_seconds=process.duration_seconds,
        status=PASSED if problem is None else FAILED,
        reason=reason,
        detail=detail,
    )


def run_suite(
    suite: TestSuite,
    command_prefix: list[str],
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> VerificationReport:
    results = [run_case(case, command_prefix, cwd=cwd, env=env) for case in suite.cases]
    passed = sum(1 for result in results if result.status == PASSED)

    return VerificationReport(
        schema_version=suite.schema_version,
        cases=results,
        summary={"passed": passed, "failed": len(results) - passed},
    )


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True)
