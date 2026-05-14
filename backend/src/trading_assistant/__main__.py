"""Module entrypoint for `python -m trading_assistant`."""

from __future__ import annotations

import sys

from trading_assistant.cli.main import main


if __name__ == "__main__":
    sys.exit(main())

