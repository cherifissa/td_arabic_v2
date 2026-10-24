"""File I/O helpers (JSON, CSV, text, bytes) with atomic writes.

Every save goes through a temporary file followed by ``os.replace``: an
interruption during the write never corrupts the existing file.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

import pandas as pd


def _atomic_write(path: Path, write_fn, mode: str = "w") -> None:
    """Write a file atomically.

    Args:
        path: Destination file; parent folders are created if needed.
        write_fn: Callable receiving the open temporary file and writing to it.
        mode: ``"w"`` for UTF-8 text, ``"wb"`` for bytes.

    Raises:
        BaseException: Any error raised by ``write_fn`` is re-raised after the
            temporary file has been removed.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    kwargs = {"encoding": "utf-8", "newline": ""} if "b" not in mode else {}
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, mode, **kwargs) as f:
            write_fn(f)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def read_json(path: Path, default: Any = None) -> Any:
    """Load a JSON file.

    Args:
        path: File to read.
        default: Value returned when the file does not exist.

    Returns:
        The decoded JSON value, or ``default``.

    Raises:
        json.JSONDecodeError: If the file exists but is not valid JSON.
    """
    path = Path(path)
    if not path.exists():
        return default
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: Any) -> None:
    """Atomically write ``data`` as pretty-printed UTF-8 JSON.

    Args:
        path: Destination file.
        data: JSON-serialisable value.
    """
    _atomic_write(path, lambda f: json.dump(data, f, ensure_ascii=False, indent=2))


def write_text(path: Path, text: str) -> None:
    """Atomically write a UTF-8 text file.

    Args:
        path: Destination file.
        text: Content to write.
    """
    _atomic_write(path, lambda f: f.write(text))


def write_bytes(path: Path, data: bytes) -> None:
    """Atomically write a binary file.

    Args:
        path: Destination file.
        data: Bytes to write.
    """
    _atomic_write(path, lambda f: f.write(data), mode="wb")


def read_csv(path: Path, **kwargs) -> pd.DataFrame:
    """Read a CSV as text only (no type inference).

    Args:
        path: CSV file to read.
        **kwargs: Extra arguments forwarded to ``pandas.read_csv``.

    Returns:
        A DataFrame whose cells are all strings; missing values are ``""``.

    Raises:
        FileNotFoundError: If the file does not exist.
    """
    return pd.read_csv(path, dtype=str, keep_default_na=False, **kwargs)


def write_csv(path: Path, df: pd.DataFrame) -> None:
    """Atomically write a DataFrame as CSV, without the index.

    Args:
        path: Destination file.
        df: Data to write.
    """
    _atomic_write(path, lambda f: df.to_csv(f, index=False))
