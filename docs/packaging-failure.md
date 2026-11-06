# Packaging failure demonstration: a missing resource

A wheel can install cleanly and pass its source tests, yet fail as soon as it's used. This demonstration reproduces that failure and shows PackPilot detecting it.

## The defect

`logsum` loads its severity list from `src/logsum/data/severities.json` using `importlib.resources`. Its `pyproject.toml` sets `include-package-data = false`, so that file only reaches the wheel through this declaration:

```toml
[tool.setuptools.package-data]
logsum = ["data/*.json"]
```

The broken build removes only those two lines. The Python code stays the same.

## Why source tests miss it

The source tests import `logsum` from `src/`, where the JSON file always exists. They pass whether or not the file is declared for packaging, so they can't tell whether the wheel is complete.

Installing doesn't catch it either. pip installs what the wheel contains and has no way of knowing that the code needs another file.

## Observed results

Run on macOS 26.0, arm64, with Python 3.13.0 on 2026-11-06. This has not yet been run on Ubuntu.

| Check                                      | Broken wheel       | Fixed wheel        |
| ------------------------------------------ | ------------------ | ------------------ |
| `logsum/data/severities.json` in the wheel | No                 | Yes                |
| Source tests                               | 4 passed           | 4 passed           |
| Wheel installation (`setup.status`)        | passed             | passed             |
| PackPilot cases                            | 2 passed, 5 failed | 7 passed, 0 failed |
| PackPilot exit code                        | 1                  | 0                  |
| Wheel SHA-256                              | `3f1a365b…320c`    | `c95b4738…89c4`    |

Each of the 5 failures was reported as `exit_code_mismatch`, with this on stderr (path shortened):

```text
logsum: application resource error: [Errno 2] No such file or directory: '.../site-packages/logsum/data/severities.json'
```

`help` and `version` passed on the broken wheel because argparse handles those flags and exits before the resource is loaded. A check using only `--help` would have approved this package.

`invalid_severity` expected exit 2 and got exit 1. The program stopped on the missing resource before reading its input, so comparing the exact exit code exposed a failure that a general "did it fail?" check would have accepted.

## Diagnosis

PackPilot reports evidence rather than a root cause. Here, the stderr message names the missing file, and listing the wheel's contents confirms it is absent:

```bash
python -m zipfile -l path/to/logsum-0.1.0-py3-none-any.whl
```

## The fix

Restore the `[tool.setuptools.package-data]` declaration, rebuild from a clean directory, and verify the new wheel against the same suite. Leftover `build/` or `.egg-info` directories can hide this defect, so the broken and fixed builds each start from a clean copy.

## Reproducing it

`tests/test_packaging_failure.py` builds both wheels from clean copies and checks the results above:

```bash
python -m pytest tests/test_packaging_failure.py -v
```
