"""Write a file atomically, so a reader never sees a half-written result."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


def atomic_write(path: str | Path, text: str) -> None:
    """Write ``text`` to ``path`` via a temp file + rename in the same directory."""
    path = Path(path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as fh:
            fh.write(text)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
