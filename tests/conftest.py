import shutil
import subprocess
import sys
from pathlib import Path

import pytest

LOGSUM_SOURCE = Path(__file__).resolve().parents[1] / "examples" / "logsum"

@pytest.fixture(scope="session")
def logsum_wheel(tmp_path_factory):
    build_root = tmp_path_factory.mktemp("logsum-build")
    source_copy = build_root / "source"
    shutil.copytree(
        LOGSUM_SOURCE,
        source_copy,
        ignore=shutil.ignore_patterns("build", "dist", "*.egg-info", "__pycache__"),
    )
    output_dir = build_root / "dist"
    subprocess.run(
        [sys.executable, "-m", "build", "--wheel", "--outdir", str(output_dir), str(source_copy)],
        check=True,
        capture_output=True,
        text=True,
    )
    return next(output_dir.glob("*.whl"))