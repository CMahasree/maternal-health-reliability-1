#!/usr/bin/env python3
"""One-command end-to-end validation: data → experiments → tests."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(cmd: list[str]) -> None:
    print(f"\n>>> {' '.join(cmd)}")
    subprocess.run(cmd, cwd=str(ROOT), check=True)


def main() -> None:
    py = sys.executable
    run([py, str(ROOT / "scripts" / "generate_data.py")])
    run([py, str(ROOT / "experiments" / "run_experiments.py")])
    run([py, "-m", "pytest", "tests/", "-v"])
    print("\nAll checks passed. Launch dashboard with: python scripts/run_dashboard.py")


if __name__ == "__main__":
    main()
