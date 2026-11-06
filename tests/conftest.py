import shutil
import subprocess
import sys
from pathlib import Path

import pytest

LOGSUM_SOURCE = Path(__file__).resolve().parents[1] / "examples" / "logsum"
PACKAGE_DATA_DECLARATION = '[tool.setuptools.package-data]\nlogsum = ["data/*.json"]\n'

def build_logsum(build_root, remove_package_data=False):
    source_copy = build_root / "source"
    shutil.copytree(
        LOGSUM_SOURCE,
        source_copy,
        ignore=shutil.ignore_patterns("build", "dist", "*.egg-info", "__pycache__"),
    )
    if remove_package_data:
        pyproject = source_copy / "pyproject.toml"
        text = pyproject.read_text(encoding="utf-8")
        assert PACKAGE_DATA_DECLARATION in text
        pyproject.write_text(text.replace(PACKAGE_DATA_DECLARATION, ""), encoding="utf-8")

    output_dir = build_root / "dist"
    subprocess.run(
        [sys.executable, "-m", "build", "--wheel", "--outdir", str(output_dir), str(source_copy)],
        check=True,
        capture_output=True,
        text=True,
    )
    return next(output_dir.glob("*.whl"))

@pytest.fixture(scope="session")
def logsum_wheel(tmp_path_factory):
    return build_logsum(tmp_path_factory.mktemp("logsum-build"))

@pytest.fixture(scope="session")
def broken_logsum_wheel(tmp_path_factory):
    return build_logsum(tmp_path_factory.mktemp("logsum-broken-build"), remove_package_data=True)