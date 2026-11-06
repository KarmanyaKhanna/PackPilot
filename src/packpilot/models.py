from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

@dataclass(frozen=True)
class ExpectedResult:
    exit_code: int
    stdout_json: dict | None = None
    stdout_contains: str | None = None
    stderr_contains: str | None = None

@dataclass(frozen=True)
class TestCase:
    __test__ = False

    name: str
    args: list[str]
    stdin: str
    timeout_seconds: float
    expect: ExpectedResult

@dataclass(frozen=True)
class TestSuite:
    __test__ = False

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
    detail: str | None = None

@dataclass
class VerificationReport:
    schema_version: int
    cases: list[CaseResult] = field(default_factory=list)
    summary: dict[str, int] = field(default_factory=dict)

@dataclass(frozen=True)
class RunTarget:
    command_prefix: list[str]
    cwd: Path
    env: dict[str, str]

@dataclass
class SetupResult:
    status: str
    duration_seconds: float
    reason: str | None = None
    detail: str | None = None