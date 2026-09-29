#!/usr/bin/env python3
"""One-command launcher for the Streamlit dashboard."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    data_file = ROOT / "data" / "simulated_readings.csv"
    if not data_file.exists():
        print("Generating dataset...")
        subprocess.run([sys.executable, str(ROOT / "scripts" / "generate_data.py")], check=True)

    dashboard = ROOT / "dashboard" / "app.py"
    env = {"PYTHONPATH": str(ROOT / "src")}
    import os
    full_env = {**os.environ, **env}
    subprocess.run(
        [sys.executable, "-m", "streamlit", "run", str(dashboard), "--server.headless", "true"],
        env=full_env,
        cwd=str(ROOT),
    )


if __name__ == "__main__":
    main()
