#!/usr/bin/env python3
"""Manual script to fetch news."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.main import main

if __name__ == "__main__":
    # Default to fetch --all if no args
    if len(sys.argv) == 1:
        sys.argv.extend(["fetch", "--all"])
    main()
