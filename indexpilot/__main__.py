"""Support ``python -m indexpilot`` in source and installed environments."""

from indexpilot.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
