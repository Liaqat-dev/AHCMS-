"""Install the backend's dependencies with pip, reading them from pyproject.toml.

``uv sync`` is the primary path (see scripts/setup.ps1 and the Makefile); this is
the fallback for machines without uv, so a stock Python install still works.
Dependencies are declared only in pyproject.toml, so there is no requirements.txt
here to drift out of sync with it.

Usage (from an activated virtualenv):
    python scripts/pip_sync.py [--dev]
"""

from __future__ import annotations

import subprocess
import sys
import tomllib
from pathlib import Path

PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"


def main() -> int:
    config = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    packages: list[str] = list(config["project"]["dependencies"])
    if "--dev" in sys.argv:
        packages += config.get("dependency-groups", {}).get("dev", [])

    print(f"==> Installing {len(packages)} packages into {sys.prefix}")
    return subprocess.call(
        [sys.executable, "-m", "pip", "install", "--upgrade", *packages]
    )


if __name__ == "__main__":
    raise SystemExit(main())
