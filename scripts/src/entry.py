"""PyInstaller entry point (kept separate so the bundled module is not named
``papermaker.py``, which would shadow the package itself)."""

from papermaker.cli import main

raise SystemExit(main())
