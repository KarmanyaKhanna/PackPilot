from __future__ import annotations

import json
import math
import re
from pathlib import Path

from packpilot.models import ExpectedResult, TestCase, TestSuite

SUPPORTED_SCHEMA_VERSION = 1

_PLAIN_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")

_CASE_ALLOWED_KEYS = {"name", "args", "stdin", "timeout_seconds", "expect"}
_EXPECT_ALLOWED_KEYS = {"exit_code", "stdout_json", "stdout_contains", "stderr_contains"}
_SUITE_ALLOWED_KEYS = {"schema_version", "entrypoint", "cases"}

class SuiteValidationError(ValueError):
    pass

def load_suite(path: Path) -> TestSuite:
    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError as e:
        raise SuiteValidationError(f"could not read suite file {path}: {e}") from e

    try:
        raw = json.loads(raw_text)
    except json.JSONDecodeError as e:
        raise SuiteValidationError(f"suite file {path} is not valid JSON: {e}") from e

    return _parse_suite(raw)

def _parse_suite(raw: dict) -> TestSuite:
    if not isinstance(raw, dict):
        raise SuiteValidationError("suite must be a JSON object")

    unknown = set(raw.keys()) - _SUITE_ALLOWED_KEYS
    if unknown:
        raise SuiteValidationError(f"suite has unknown fields: {sorted(unknown)}")
    missing = _SUITE_ALLOWED_KEYS - set(raw.keys())
    if missing:
        raise SuiteValidationError(f"suite is missing required fields: {sorted(missing)}")

    schema_version = raw["schema_version"]
    if (
        isinstance(schema_version, bool)
        or not isinstance(schema_version, int)
        or schema_version != SUPPORTED_SCHEMA_VERSION
    ):
        raise SuiteValidationError(
            f"unsupported schema version {schema_version!r}, expected {SUPPORTED_SCHEMA_VERSION}"
        )

    entrypoint = raw["entrypoint"]
    if not isinstance(entrypoint, str) or not _PLAIN_NAME.fullmatch(entrypoint):
        raise SuiteValidationError(
            f"suite field 'entrypoint' must be a plain command name, got {entrypoint!r}"
        )

    raw_cases = raw["cases"]
    if not isinstance(raw_cases, list) or not raw_cases:
        raise SuiteValidationError("suite field 'cases' must be a nonempty list")

    cases = [_parse_case(index, raw_case) for index, raw_case in enumerate(raw_cases)]

    seen_names = set()
    for case in cases:
        if case.name in seen_names:
            raise SuiteValidationError(f"duplicate case name: {case.name!r}")
        seen_names.add(case.name)

    return TestSuite(schema_version = schema_version, entrypoint=entrypoint, cases=cases)

def _parse_case(index: int, raw_case: dict) -> TestCase:
    label = f"cases[{index}]"
    if not isinstance(raw_case, dict):
        raise SuiteValidationError(f"{label} must be a JSON object")

    unknown = set(raw_case.keys()) - _CASE_ALLOWED_KEYS
    if unknown:
        raise SuiteValidationError(f"{label} has unknown fields: {sorted(unknown)}")

    missing = _CASE_ALLOWED_KEYS - set(raw_case.keys())
    if missing:
        raise SuiteValidationError(f"{label} is missing required fields: {sorted(missing)}")

    name = raw_case["name"]
    if not isinstance(name, str) or not name.strip():
        raise SuiteValidationError(f"{label} field 'name' must be a nonempty string")
    label = f"case {name!r}"

    args = raw_case["args"]
    if not isinstance(args, list) or not all(isinstance(a, str) for a in args):
        raise SuiteValidationError(f"{label} field 'args' must be a list of strings")

    stdin = raw_case["stdin"]
    if not isinstance(stdin, str):
        raise SuiteValidationError(f"{label} field 'stdin' must be a string")

    timeout_seconds = raw_case["timeout_seconds"]
    if (isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)) or not math.isfinite(timeout_seconds) or timeout_seconds <= 0):
        raise SuiteValidationError(f"{label} field 'timeout_seconds' must be a positive finite number")

    expect = _parse_expect(label, raw_case["expect"])

    return TestCase(
        name=name,
        args=args,
        stdin=stdin,
        timeout_seconds=timeout_seconds,
        expect=expect
    )

def _parse_expect(case_label: str, raw_expect: dict) -> ExpectedResult:
    label = f"{case_label} field 'expect'"
    if not isinstance(raw_expect, dict):
        raise SuiteValidationError(f"{label} must be a JSON object")

    unknown = set(raw_expect.keys()) - _EXPECT_ALLOWED_KEYS
    if unknown:
        raise SuiteValidationError(f"{label} has unknown fields: {sorted(unknown)}")
    if "exit_code" not in raw_expect:
        raise SuiteValidationError(f"{label} is missing required field 'exit_code'")

    exit_code = raw_expect["exit_code"]
    if isinstance(exit_code, bool) or not isinstance(exit_code, int):
        raise SuiteValidationError(f"{label} field 'exit_code' must be an integer")

    stdout_json = raw_expect.get("stdout_json")
    stdout_contains = raw_expect.get("stdout_contains")
    stderr_contains = raw_expect.get("stderr_contains")

    if stdout_json is not None and stdout_contains is not None:
        raise SuiteValidationError(f"{label} cannot set both 'stdout_json' and 'stdout_contains'")
    if stdout_json is not None and not isinstance(stdout_json, dict):
        raise SuiteValidationError(f"{label} field 'stdout_json' must be a JSON object")
    if stdout_contains is not None and not isinstance(stdout_contains, str):
        raise SuiteValidationError(f"{label} field 'stdout_contains' must be a string")
    if stderr_contains is not None and not isinstance(stderr_contains, str):
        raise SuiteValidationError(f"{label} field 'stderr_contains' must be a string")

    return ExpectedResult(
        exit_code=exit_code,
        stdout_json=stdout_json,
        stdout_contains=stdout_contains,
        stderr_contains=stderr_contains
    )