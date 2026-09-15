"""Compatibility entry point for agents preferring a script-like command."""

import sys
from pathlib import Path

if __package__:
    from .cli import main
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from sandbox.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
