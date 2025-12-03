#!/usr/bin/env python3
"""
Unified Brain CLI - Entry point wrapper

This script provides the `brain` command for the Brain Protocol.
It replaces both brain.py and mission.py with a unified interface.

Usage:
    python scripts/brain_cli.py <command> [args]
    # Or if symlinked as 'brain':
    brain <command> [args]
"""

import sys
from pathlib import Path

# Add src/ to path so 'brain' package is importable when run directly
src_dir = Path(__file__).parent.parent
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from brain.cli import main

if __name__ == "__main__":
    main()
