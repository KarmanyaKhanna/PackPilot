from __future__ import annotations

import subprocess
import time
import os
from pathlib import Path
from packpilot.models import ProcessResult

COMMAND_NOT_FOUND = "command_not_found"
TIMEOUT = "timeout"
_REMOVED_ENV_VARS = ("PYTHONPATH", "PYTHONHOME")

def run_command(
        args: list[str],
        stdin: str,
        timeout_seconds: float,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
) -> ProcessResult:
    start = time. monotonic()
    try:
        completed = subprocess.run(
            args,
            input=stdin,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=timeout_seconds,
            shell=False,
            cwd=cwd,
            env=env,
        )
    except FileNotFoundError as e:
        return ProcessResult(
            exit_code=None,
            stdout="",
            stderr=str(e),
            duration_seconds=time.monotonic() - start,
            failure=COMMAND_NOT_FOUND,
        )
    except subprocess.TimeoutExpired as e:
        return ProcessResult(
            exit_code=None,
            stdout=_as_text(e.stdout),
            stderr=_as_text(e.stderr),
            duration_seconds=time.monotonic() - start,
            failure=TIMEOUT,
        )

    return ProcessResult(
        exit_code=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        duration_seconds=time.monotonic() - start,
    )

def clean_environment() -> dict[str, str]:
    env = dict(os.environ)
    for name in _REMOVED_ENV_VARS:
        env.pop(name, None)
    return env

def _as_text(output: str | bytes | None) -> str:
    if output is None:
        return ""
    if isinstance(output, bytes):
        return output.decode("utf-8", errors="replace")
    return output
    