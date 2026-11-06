import shutil
import subprocess
import sys
import hashlib
from pathlib import Path

import pytest

from packpilot.engine import run_suite
from packpilot.models import ExpectedResult, TestCase, TestSuite
from packpilot.process import COMMAND_NOT_FOUND, run_command
from packpilot.runners.wheel import (
    VenvCreationError,
    WheelInstallError,
    WheelNotFoundError,
    describe_wheel,
    installed_wheel,
)

LOGSUM_SOURCE = Path(__file__).resolve().parents[1] / "examples" / "logsum"

LOGSUM_SUITE = TestSuite(
    schema_version=1,
    entrypoint="logsum",
    cases=[
        TestCase(
            name="valid_input",
            args=["--json"],
            stdin="INFO service started\nERROR connection failed\n",
            timeout_seconds=5,
            expect=ExpectedResult(
                exit_code=0,
                stdout_json={"INFO": 1, "WARNING": 0, "ERROR": 1},
            ),
        ),
        TestCase(
            name="invalid_severity",
            args=["--json"],
            stdin="INVALID example\n",
            timeout_seconds=5,
            expect=ExpectedResult(exit_code=2, stderr_contains="line 1"),
        ),
    ],
)

def test_real_wheel_passes_the_behavior_suite(logsum_wheel):
    with installed_wheel(logsum_wheel, LOGSUM_SUITE.entrypoint) as target:
        report = run_suite(LOGSUM_SUITE, target.command_prefix, cwd=target.cwd, env=target.env)
    assert report.summary == {"passed": 2, "failed": 0}

def test_installed_app_does_not_import_from_the_checkout(logsum_wheel, monkeypatch):
    monkeypatch.setenv("PYTHONPATH", str(LOGSUM_SOURCE / "src"))
    with installed_wheel(logsum_wheel, "logsum") as target:
        venv_bin = Path(target.command_prefix[0]).parent
        result = run_command(
            [str(venv_bin / "python"), "-c", "import logsum; print(logsum.__file__)"],
            stdin="",
            timeout_seconds=10,
            cwd=target.cwd,
            env=target.env,
        )
    assert result.exit_code == 0
    assert Path(result.stdout.strip()).is_relative_to(venv_bin.parent)

def test_missing_entrypoint_does_not_fall_back_to_a_host_command(logsum_wheel):
    assert shutil.which("ls") is not None
    suite = TestSuite(
        schema_version=1,
        entrypoint="ls",
        cases=[
            TestCase(
                name="host_command",
                args=[],
                stdin="",
                timeout_seconds=5,
                expect=ExpectedResult(exit_code=0),
            )
        ],
    )
    with installed_wheel(logsum_wheel, suite.entrypoint) as target:
        report = run_suite(suite, target.command_prefix, cwd=target.cwd, env=target.env)
    assert report.summary == {"passed": 0, "failed": 1}
    assert report.cases[0].reason == COMMAND_NOT_FOUND

def test_missing_wheel_is_rejected(tmp_path):
    with pytest.raises(WheelNotFoundError, match="not found"):
        with installed_wheel(tmp_path / "missing.whl", "logsum"):
            pytest.fail("should not reach the body")

def test_corrupt_wheel_reports_the_install_failure(tmp_path):
    wheel = tmp_path / "logsum-0.1.0-py3-none-any.whl"
    wheel.write_bytes(b"this is not a zip file")
    with pytest.raises(WheelInstallError, match="install wheel failed") as error:
        with installed_wheel(wheel, "logsum"):
            pytest.fail("should not reach the body")
    assert "stderr:" in str(error.value)

def test_temp_directory_is_removed_after_success(logsum_wheel):
    with installed_wheel(logsum_wheel, "logsum") as target:
        root = target.cwd.parent
        assert root.exists()
    assert not root.exists()

def test_temp_directory_is_removed_after_an_error(logsum_wheel):
    with pytest.raises(RuntimeError, match="boom"):
        with installed_wheel(logsum_wheel, "logsum") as target:
            root = target.cwd.parent
            raise RuntimeError("boom")
    assert not root.exists()

def test_describe_wheel_records_the_filename_and_hash(tmp_path):
    wheel = tmp_path / "sample-0.1.0-py3-none-any.whl"
    wheel.write_bytes(b"sample bytes")
    assert describe_wheel(wheel) == {
        "wheel_filename": wheel.name,
        "wheel_sha256": hashlib.sha256(b"sample bytes").hexdigest(),
    }

def test_describe_wheel_rejects_a_missing_file(tmp_path):
    with pytest.raises(WheelNotFoundError, match="not found"):
        describe_wheel(tmp_path / "missing.whl")

def test_venv_failure_is_a_different_error_from_install_failure(tmp_path, monkeypatch):
    wheel = tmp_path / "sample-0.1.0-py3-none-any.whl"
    wheel.write_bytes(b"sample bytes")
    monkeypatch.setattr(sys, "executable", str(tmp_path / "no-such-python"))
    with pytest.raises(VenvCreationError, match="create venv failed"):
        with installed_wheel(wheel, "logsum"):
            pytest.fail("should not reach the body")