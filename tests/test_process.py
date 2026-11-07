import sys

from packpilot.process import COMMAND_NOT_FOUND, TIMEOUT, run_command


def python_command(code):
    return [sys.executable, "-c", code]


def test_captures_stdout_and_stderr_separately():
    code = "import sys; print('to stdout'); print('to stderr', file=sys.stderr)"
    result = run_command(python_command(code), stdin="", timeout_seconds=10)
    assert result.exit_code == 0
    assert result.stdout == "to stdout\n"
    assert result.stderr == "to stderr\n"
    assert result.failure is None


def test_passes_stdin_to_the_command():
    code = "import sys; print(sys.stdin.read().upper(), end='')"
    result = run_command(python_command(code), stdin="hello", timeout_seconds=10)
    assert result.stdout == "HELLO"


def test_nonzero_exit_is_not_a_failure():
    result = run_command(python_command("raise SystemExit(2)"), stdin="", timeout_seconds=10)
    assert result.exit_code == 2
    assert result.failure is None


def test_missing_executable_is_classified(tmp_path):
    missing = tmp_path / "no-such-command"
    result = run_command([str(missing)], stdin="", timeout_seconds=10)
    assert result.exit_code is None
    assert result.failure == COMMAND_NOT_FOUND


def test_timeout_is_classified_and_keeps_partial_output():
    code = "import time; print('started', flush=True); time.sleep(30)"
    result = run_command(python_command(code), stdin="", timeout_seconds=1)
    assert result.exit_code is None
    assert result.failure == TIMEOUT
    assert result.stdout == "started\n"
    assert result.duration_seconds < 10


def test_runs_in_the_requested_directory(tmp_path):
    code = "import os; print(os.getcwd())"
    result = run_command(python_command(code), stdin="", timeout_seconds=10, cwd=tmp_path)
    assert result.stdout.strip() == str(tmp_path.resolve())


def test_undecodable_output_does_not_crash():
    code = "import sys; sys.stdout.buffer.write(b'bad \\xff byte')"
    result = run_command(python_command(code), stdin="", timeout_seconds=10)
    assert result.exit_code == 0
    assert result.stdout == "bad \ufffd byte"
