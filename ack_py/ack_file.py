"""File abstraction for ack."""

from __future__ import annotations

import os
import re
import sys
from typing import IO


class AckFile:
    """Represents a single file to be searched."""

    def __init__(self, filename: str) -> None:
        self.filename = filename
        self._fh: IO[bytes] | None = None
        self._basename: str | None = None
        self._firstliney: str | None = None

        if filename == "-":
            self._fh = sys.stdin.buffer

    @property
    def name(self) -> str:
        return self.filename

    @property
    def basename(self) -> str:
        if self._basename is None:
            self._basename = os.path.basename(self.filename)
        return self._basename

    @property
    def firstliney(self) -> str:
        if self._firstliney is None:
            fh = self.open()
            if fh is None:
                self._firstliney = ""
            else:
                try:
                    raw = fh.read(250)
                    text = raw.decode("utf-8", errors="replace")
                    text = re.split(r"[\r\n]", text)[0]
                    self._firstliney = text
                except Exception:
                    self._firstliney = ""
                self.reset()
        return self._firstliney

    def open(self) -> IO[bytes] | None:
        if self._fh is None:
            try:
                self._fh = builtins_open(self.filename, "rb")
            except OSError:
                self._fh = None
        return self._fh

    def may_be_present(self, regex: re.Pattern[str] | None) -> bool:
        """Quick pre-scan: slurp up to 10MB and check if regex matches."""
        if regex is None:
            return True
        fh = self.open()
        if fh is None:
            return False
        try:
            if not os.path.isfile(self.filename):
                return True
            buf = fh.read(10_000_000)
            text = buf.decode("utf-8", errors="replace")
            if len(buf) == 10_000_000 or "\r" in text:
                return True
            return bool(regex.search(text))
        except Exception:
            return False

    def reset(self) -> None:
        if self._fh is not None and self._fh is not sys.stdin.buffer:
            try:
                self._fh.seek(0)
            except OSError:
                pass

    def close(self) -> None:
        if self._fh is not None and self._fh is not sys.stdin.buffer:
            try:
                self._fh.close()
            except OSError:
                pass
            self._fh = None

    def clone(self) -> AckFile:
        return AckFile(self.filename)


# Use a different name to avoid shadowing the builtin.
builtins_open = open
