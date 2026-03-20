"""Allow ``python -m square``."""

from __future__ import annotations

from square.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
