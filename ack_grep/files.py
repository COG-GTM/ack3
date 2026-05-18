"""Factory for creating streams of AckFile objects."""

from __future__ import annotations

import os
import sys
from typing import Iterator

import ack_grep
from ack_grep.file import AckFile


class AckFiles:
    """Iterator over files to search."""

    def __init__(self) -> None:
        self._iter: Iterator[str] | None = None

    @classmethod
    def from_argv(cls, opt: dict, start: list[str]) -> AckFiles:
        self = cls()

        file_filter = opt.get("file_filter")
        descend_filter = opt.get("descend_filter")
        follow_symlinks = opt.get("follow", False)
        sort_files = opt.get("sort_files", False)

        if opt.get("n"):
            def _no_descend(dirpath: str) -> bool:
                return False
            descend_filter = _no_descend

        def _walk_files() -> Iterator[str]:
            for start_path in start:
                if os.path.isfile(start_path) or start_path == "-":
                    yield start_path
                    continue

                if not os.path.isdir(start_path):
                    continue

                for dirpath, dirnames, filenames in os.walk(
                    start_path, followlinks=follow_symlinks
                ):
                    if descend_filter is not None:
                        dirnames[:] = [
                            d
                            for d in dirnames
                            if descend_filter(os.path.join(dirpath, d))
                        ]
                    else:
                        dirnames[:] = sorted(dirnames) if sort_files else dirnames

                    if sort_files:
                        dirnames.sort()
                        filenames = sorted(filenames)

                    for filename in filenames:
                        filepath = os.path.join(dirpath, filename)
                        if file_filter is None or file_filter(filepath, dirpath):
                            yield filepath

        self._iter = _walk_files()
        return self

    @classmethod
    def from_file(cls, opt: dict, filename: str) -> AckFiles | None:
        self = cls()
        sort_files = opt.get("sort_files", False)

        try:
            if filename == "-":
                fh = sys.stdin
            else:
                fh = open(filename, "r")
        except (OSError, IOError) as e:
            ack_grep.warn(f"{filename}: {e}")
            return None

        def _read_files() -> Iterator[str]:
            lines = []
            for line in fh:
                line = line.rstrip("\n").rstrip("\r")
                if line:
                    lines.append(line)
            if sort_files:
                lines.sort()
            yield from lines
            if fh is not sys.stdin:
                fh.close()

        self._iter = _read_files()
        return self

    @classmethod
    def from_stdin(cls) -> AckFiles:
        self = cls()
        called = False

        def _stdin_iter() -> Iterator[str]:
            nonlocal called
            if not called:
                called = True
                yield "-"

        self._iter = _stdin_iter()
        return self

    def next(self) -> AckFile | None:
        if self._iter is None:
            return None
        try:
            filepath = next(self._iter)
            return AckFile(filepath)
        except StopIteration:
            return None
