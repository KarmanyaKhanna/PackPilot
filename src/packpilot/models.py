from __future__ import annotations

from dataclasses import dataclass, field

@dataclass(frozen=True)
class ExpectedResult:
    exit_code: int
    stdout_json: dict | None = None
    stdout_contains: str | None = None
    stderr_contains: str | None = None

@dataclass(frozen=True)
class TestCase:
    name: str
    args: list[str]
    stdin: str
    timeout_seconds: float
    expect: ExpectedResult

@dataclass(frozen=True)
class TestSuite:
    schema_version: int
    entrypoint: str
    cases: list[TestCase]

@dataclass
class ProcessResult:
    exit_code: int | None
    stdout: str
    stderr: str
    duration_seconds: float
    failure: str | None = None

@dataclass
class CaseResult:
    name: str
    args: list[str]
    expected: ExpectedResult
    actual_exit_code: int | None
    actual_stdout: str
    actual_stderr: str
    duration_seconds: float
    status: str
    reason: str | None = None

@dataclass
class VerificationReport:
    schema_version: int
    cases: list[CaseResult] = field(default_factory=list)
    summary: dict[str, int] = field(default_factory=dict)

