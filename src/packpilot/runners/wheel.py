from __future__ import annotations

import hashlib
import sys
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from packpilot.models import RunTarget
from packpilot.process import clean_environment, run_command

INSTALL_FAILED = "install_failed"
SETUP_TIMEOUT_SECONDS = 120


class WheelNotFoundError(ValueError):
    pass


class WheelInstallError(RuntimeError):
    pass


class VenvCreationError(RuntimeError):
    pass


def describe_wheel(wheel_path: Path) -> dict[str, str]:
    wheel = wheel_path.resolve()
    if not wheel.is_file():
        raise WheelNotFoundError(f"wheel file not found: {wheel}")
    with wheel.open("rb") as f:
        digest = hashlib.file_digest(f, "sha256")
    return {"wheel_filename": wheel.name, "wheel_sha256": digest.hexdigest()}


@contextmanager
def installed_wheel(wheel_path: Path, entrypoint: str) -> Iterator[RunTarget]:
    wheel = wheel_path.resolve()
    if not wheel.is_file():
        raise WheelNotFoundError(f"wheel file not found: {wheel}")

    env = clean_environment()

    with tempfile.TemporaryDirectory(prefix="packpilot-") as temp_dir:
        root = Path(temp_dir).resolve()
        venv_dir = root / "venv"
        work_dir = root / "work"
        work_dir.mkdir()

        _run_setup_step(
            "create venv",
            [sys.executable, "-m", "venv", str(venv_dir)],
            cwd=work_dir,
            env=env,
            error_type=VenvCreationError,
        )
        _run_setup_step(
            "install wheel",
            [
                str(venv_dir / "bin" / "python"),
                "-m",
                "pip",
                "install",
                "--no-index",
                "--no-deps",
                str(wheel),
            ],
            cwd=work_dir,
            env=env,
            error_type=WheelInstallError,
        )

        yield RunTarget(
            command_prefix=[str(venv_dir / "bin" / entrypoint)],
            cwd=work_dir,
            env=env,
        )


def _run_setup_step(
    step: str,
    args: list[str],
    cwd: Path,
    env: dict[str, str],
    error_type: type[Exception],
) -> None:
    result = run_command(args, stdin="", timeout_seconds=SETUP_TIMEOUT_SECONDS, cwd=cwd, env=env)
    if result.failure is not None or result.exit_code != 0:
        problem = result.failure or f"exit code {result.exit_code}"
        raise error_type(
            f"{step} failed ({problem})\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
