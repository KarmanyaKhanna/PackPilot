# PackPilot

[![CI](https://github.com/KarmanyaKhanna/PackPilot/actions/workflows/ci.yml/badge.svg)](https://github.com/KarmanyaKhanna/PackPilot/actions/workflows/ci.yml)

PackPilot checks that an **installed** command-line package behaves the way its tests promise. It runs one JSON test suite against a Python wheel or a snap and writes a JSON report of what actually happened.

Source tests can pass while the package you ship is broken. A test run from a checkout can read files that never made it into the package. PackPilot only runs the installed command, from a folder outside the checkout, so that mistake shows up as a failure.

PackPilot verifies the behaviour a suite describes. It does not certify a package as compatible or secure in general.

## Tested support

Only these combinations have been run. Anything else is untested.

| Target | Environment | How | Result |
| --- | --- | --- | --- |
| Wheel | GitHub Actions `ubuntu-24.04`, x86_64, Python 3.12 | CI, on every push | 7 passed |
| Wheel | Ubuntu 24.04.5 VM, arm64, Python 3.12.3 | Manual, 2026-11-07 | 7 passed |
| Wheel | macOS 26.0, arm64, Python 3.13.0 | Manual, during development | 7 passed |
| Snap (strict) | Ubuntu 24.04.5 VM, arm64, snapd 2.78 | Manual, 2026-11-07 | 7 passed |

The VM ran under Multipass 1.16.4 on macOS. The snap was built with Snapcraft 9.2.1 and LXD 5.21.9, on the `core24` base.

**CI does not test the snap.** The snap integration test is skipped there, and the log says so. The snap results come from the manual VM runs above. The snap has not been built or tested on amd64.

## Requirements

- Python 3.12 or newer. PackPilot and the demo app use only the standard library at runtime.
- For snaps: Ubuntu with snapd, and the snap already installed. Building the snap needs Snapcraft and LXD.

## Install

```bash
git clone https://github.com/KarmanyaKhanna/PackPilot.git
cd PackPilot
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
packpilot --help
```

## Five-minute walkthrough

The repo includes `logsum`, a small app that counts log severities from stdin, and a shared suite in `examples/cases.json`.

**1. Build the demo wheel and verify it.**

```bash
python -m build --wheel --outdir dist/demo examples/logsum
packpilot verify wheel dist/demo/logsum-0.1.0-py3-none-any.whl \
  --cases examples/cases.json \
  --report reports/wheel.json
echo "exit code: $?"
```

PackPilot creates a fresh venv, installs the wheel, runs the 7 cases and prints `7 passed, 0 failed`. The exit code is 0.

**2. Look at the report.**

```bash
python -c "
import json
r = json.load(open('reports/wheel.json'))
print(r['target'])
print(r['setup']['status'], r['summary'])
"
```

The report records the wheel's filename and SHA-256, the OS and architecture, and each case's actual exit code, stdout and stderr.

**3. Break the package and watch PackPilot catch it.**

This builds a wheel that leaves out the app's data file. The Python code is the same.

```bash
BROKEN=$(mktemp -d)
git archive HEAD examples/logsum | tar -x -C "$BROKEN"
sed -i.bak '/^\[tool.setuptools.package-data\]/,/^logsum = \[/d' "$BROKEN/examples/logsum/pyproject.toml"
python -m build --wheel --outdir "$BROKEN/dist" "$BROKEN/examples/logsum"
packpilot verify wheel "$BROKEN/dist/logsum-0.1.0-py3-none-any.whl" \
  --cases examples/cases.json \
  --report reports/wheel-broken.json
echo "exit code: $?"
```

The wheel installs without errors, but PackPilot reports `2 passed, 5 failed` and exits 1. Each failure's stderr names the missing `severities.json`. `git archive` makes a clean copy; copying the folder instead could bring along an old `build/` directory that still contains the file and hides the defect.

[docs/packaging-failure.md](docs/packaging-failure.md) explains this failure and its fix.

## Verifying the snap (Ubuntu only)

PackPilot doesn't install, remove or connect snaps. It runs a snap that's already installed, so it never needs `sudo`.

Build and install the demo snap. The recipe in `examples/logsum/snap/snapcraft.yaml` targets arm64 only.

```bash
cd examples/logsum
snapcraft pack
sudo snap install --dangerous ./packpilot-logsum_0.1.0_arm64.snap
cd ../..
```

`--dangerous` allows a local snap that the store hasn't signed. It gets a local revision such as `x1`.

Then verify it against the same suite as the wheel:

```bash
packpilot verify snap packpilot-logsum.logsum \
  --cases examples/cases.json \
  --report reports/snap.json
```

The target is the installed `snap-name.app-name` command, not the `.snap` file. The app name must match the suite's `entrypoint`.

**VM state:** the snap stays installed between cases and runs; PackPilot doesn't reinstall it for each case. `logsum` only reads stdin and writes stdout, so it has no interface connections (`snap connections packpilot-logsum` lists none) and keeps no state. To reset, remove the snap with `sudo snap remove packpilot-logsum` and install it again.

## Test suite format

```json
{
  "schema_version": 1,
  "entrypoint": "logsum",
  "cases": [
    {
      "name": "invalid_severity",
      "args": ["--json"],
      "stdin": "INVALID example\n",
      "timeout_seconds": 5,
      "expect": { "exit_code": 2, "stderr_contains": "line 1" }
    }
  ]
}
```

| Field | Rules |
| --- | --- |
| `schema_version` | Must be `1`. |
| `entrypoint` | The command to run: a plain name, not a path. |
| `cases[].name` | Nonempty and unique. |
| `cases[].args` | List of strings. Passed directly, never through a shell. |
| `cases[].stdin` | String sent to the command's stdin. |
| `cases[].timeout_seconds` | Positive, finite number. |
| `expect.exit_code` | Required. Must match exactly. |
| `expect.stdout_json` | Optional. Stdout must parse as JSON and equal this object. Key order and whitespace don't matter. |
| `expect.stdout_contains` | Optional substring of stdout. Can't be combined with `stdout_json`. |
| `expect.stderr_contains` | Optional substring of stderr. |

The whole suite is checked before anything is installed or run. Missing or unknown fields are rejected, and the error message names the field.

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | Setup succeeded and every case passed. |
| 1 | Verification failed: a case failed, or the wheel didn't install. |
| 2 | No valid run: bad arguments, an invalid suite, a missing wheel, a snap that isn't installed, a snap app that doesn't match the suite, or a venv that couldn't be created. |

PackPilot's exit code is separate from the app's. A case that expects the app to exit 2 passes when it does.

## Failure reasons

Each failed case in the report has one reason:

| Reason | Meaning |
| --- | --- |
| `install_failed` | The wheel didn't install (setup failure; no cases run). |
| `command_not_found` | The command couldn't be started. |
| `timeout` | The command didn't finish within `timeout_seconds`. |
| `exit_code_mismatch` | The exit code differed from `expect.exit_code`. |
| `invalid_json` | `stdout_json` was expected but stdout wasn't JSON. |
| `stdout_mismatch` | Stdout didn't match `stdout_json` or `stdout_contains`. |
| `stderr_mismatch` | Stderr didn't contain `stderr_contains`. |

Checks run in that order, and the first failure is reported. PackPilot records evidence, not a diagnosis: the reason says what differed, and the captured stderr usually says why.

## Timeouts

- Each case has its own `timeout_seconds`. When it runs out, Python stops the process PackPilot started. The case fails with `timeout`, any output produced so far is kept, and the remaining cases still run.
- Only that process is stopped. Any child processes it started are not cleaned up. `logsum` starts none.
- Setup steps have their own limits: 120 seconds each for creating the venv and installing the wheel, and 30 seconds for `snap info`.
- Case timeouts are tested against a plain Python process. They haven't been tested against a snap.

## Reports

With `--report PATH`, PackPilot writes a JSON report with sorted keys. It contains:

- The schema version, a UTC timestamp and the target type.
- The target's identity: the wheel filename and SHA-256, or the snap name, version, revision and confinement.
- The OS, the CPU architecture, and the Python that ran PackPilot. For snaps, this is not the Python inside the snap.
- The setup status and duration, with installation output if it failed.
- Each case's arguments, expected values, actual exit code, stdout, stderr, duration, status and reason.
- Pass and fail counts.

Progress and failures are printed to stderr; the report is the only machine-readable output. Reports include local paths such as temporary folders and the Python location, so check them before publishing.

## Architecture

```text
cli.py ──> cases.py      load and validate the suite
   │
   ├──> runners/wheel.py  temp venv + pip install --no-index --no-deps
   ├──> runners/snap.py   check snapd, then run `snap run snap.app`
   │         │
   │         └─ both return a RunTarget: command prefix, working folder, environment
   │
   ├──> engine.py  run each case, compare against expect
   │       └──> process.py  subprocess with timeout, classify failures
   │
   └──> report.py  build, print and write the report
```

Adding a package type means adding a runner. The engine doesn't change: the snap runner was added without touching it.

Design decisions:

- **A fresh venv for every wheel run.** Nothing already installed on the machine can make the test pass.
- **`--no-index --no-deps`.** Only the given wheel is installed, and nothing is downloaded. This limits PackPilot to dependency-free wheels like the demo.
- **The venv's own command, by absolute path.** If the wheel doesn't create its console script, the case fails with `command_not_found` instead of running a command with the same name from elsewhere on the machine.
- **Run from a temporary folder, without `PYTHONPATH` or `PYTHONHOME`.** The source checkout can't leak into the test.
- **Validate the whole suite first.** A typo in case 7 is found before anything is installed.
- **Exact exit codes.** In the packaging demo, a case that expected exit 2 got exit 1; a check for "any failure" would have passed it.

## Limitations

- Wheels must have no dependencies.
- A venv is not a sandbox. Cases run as your user, with your environment apart from `PYTHONPATH` and `PYTHONHOME`. Only run suites and packages you trust.
- PackPilot reads the human-readable output of `snap info --verbose`. A future snapd could change that format. PackPilot would then report the snap as not installed, rather than passing it.
- Stdout and stderr are held in memory in full. Keep test inputs and outputs small.

## Development

```bash
python -m pytest -q -rs
ruff check . && ruff format --check .
```

`-rs` shows why tests were skipped. `tests/test_snap_integration.py` runs only where the `packpilot-logsum` snap is installed.
