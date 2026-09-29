#!/usr/bin/env python3
"""Generate simulated dataset."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from maternal_reliability.data.generator import save_dataset


def main() -> None:
    data_dir = ROOT / "data"
    readings_path, labels_path = save_dataset(data_dir)
    print(f"Generated: {readings_path}")
    print(f"Generated: {labels_path}")


if __name__ == "__main__":
    main()
