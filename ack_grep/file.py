"""Abstracts a file from the filesystem."""

from __future__ import annotations

import builtins as _builtins
import os
import sys
from typing import IO

import ack_grep

_builtin_open = _builtins.open


class AckFile:
    """Represents a file to be searched."""

    def __init__(self, filename: str) -> None:
        self.filename = filename
        self._fh: IO[str] | None = None
        self._basename: str | None = None
        self._firstliney: str | None = None

        if self.filename == "-":
            self._fh = sys.stdin

    @property
    def name(self) -> str:
        return self.filename

    @property
    def basename(self) -> str:
        if self._basename is None:
            self._basename = os.path.basename(self.filename)
        return self._basename

    def open(self) -> IO[str] | None:
        if self._fh is None:
            try:
                self._fh = _builtin_open(self.filename, "r", errors="replace")
            except (OSError, IOError):
                self._fh = None
        return self._fh

    def may_be_present(self, regex) -> bool:
        """Check if a regex could match in this file (optimization)."""
        if regex is None:
            return True

        fh = self.open()
        if fh is None:
            return False

        try:
            if not os.path.isfile(self.filename):
                return True

            fh.seek(0)
            buffer = fh.read(10_000_000)

            if len(buffer) >= 10_000_000 or "\r" in buffer:
                return True

            return regex.search(buffer) is not None
        except (OSError, IOError):
            if ack_grep.report_bad_filenames:
                ack_grep.warn(f"{self.name}: error reading file")
            return False

    def reset(self) -> None:
        if self._fh is not None:
            try:
                if hasattr(self._fh, "seekable") and self._fh.seekable():
                    self._fh.seek(0)
            except (OSError, IOError):
                if ack_grep.report_bad_filenames:
                    ack_grep.warn(f"{self.filename}: error seeking")

    def close(self) -> None:
        if self._fh is not None and self._fh is not sys.stdin:
            try:
                self._fh.close()
            except (OSError, IOError):
                if ack_grep.report_bad_filenames:
                    ack_grep.warn(f"{self.name}: error closing file")
            self._fh = None

    def clone(self) -> AckFile:
        return AckFile(self.name)

    def firstliney(self) -> str:
        if self._firstliney is not None:
            return self._firstliney

        fh = self.open()
        if fh is None:
            if ack_grep.report_bad_filenames:
                ack_grep.warn(f"{self.name}: cannot open")
            self._firstliney = ""
        else:
            try:
                fh.seek(0)
                buffer = fh.read(250)
                if buffer:
                    for sep in ("\r\n", "\r", "\n"):
                        idx = buffer.find(sep)
                        if idx >= 0:
                            buffer = buffer[:idx]
                            break
                else:
                    buffer = ""
                self._firstliney = buffer
                self.reset()
            except (OSError, IOError) as e:
                ack_grep.warn(f"{self.name}: {e}")
                self._firstliney = ""

        return self._firstliney


