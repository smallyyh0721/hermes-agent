#!/usr/bin/env python3
"""ProAgent entry point.

Usage:
    python proagent_run.py [command] [options]

    Commands:
        run       Start interactive chat (default)
        setup     Interactive setup wizard
        model     Configure models
        target    Manage target servers
        inspect   Run one-shot inspection
        status    Show runtime status
        gateway   Start Discord gateway mode
"""

import sys
from pathlib import Path

# Ensure project root is in path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from proagent.cli.main import main

if __name__ == "__main__":
    main()
