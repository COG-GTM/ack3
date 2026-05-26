"""File iterator/finder for ack."""

from __future__ import annotations

import os
import sys
from collections.abc import Callable, Iterator
from typing import TextIO

from ack_py.ack_file import AckFile


class AckFiles:
    """Factory for creating iterators over AckFile objects."""

    def __init__(self, iterator: Iterator[str]) -> None:
        self._iter = iterator

    def next(self) -> AckFile | None:
        try:
            filepath = next(self._iter)
            return AckFile(filepath)
        except StopIteration:
            return None

    @classmethod
    def from_argv(
        cls,
        start: list[str],
        file_filter: Callable[[str], bool] | None = None,
        descend_filter: Callable[[str], bool] | None = None,
        follow_symlinks: bool = False,
        sort_files: bool = False,
        no_recurse: bool = False,
    ) -> AckFiles:
        def _walk() -> Iterator[str]:
            for path in start:
                if os.path.isfile(path):
                    yield path
                elif os.path.isdir(path):
                    if no_recurse:
                        entries = sorted(os.listdir(path)) if sort_files else os.listdir(path)
                        for entry in entries:
                            fullpath = os.path.join(path, entry)
                            if os.path.isfile(fullpath):
                                if file_filter is None or file_filter(fullpath):
                                    yield fullpath
                    else:
                        yield from _walk_dir(path, file_filter, descend_filter, follow_symlinks, sort_files)

        return cls(_walk())

    @classmethod
    def from_file(cls, filename: str, sort_files: bool = False) -> AckFiles | None:
        try:
            fh: TextIO
            if filename == "-":
                fh = sys.stdin
            else:
                fh = open(filename, "r")  # noqa: SIM115
        except OSError as e:
            print(f"ack: {e}", file=sys.stderr)
            return None

        def _iter() -> Iterator[str]:
            try:
                for line in fh:
                    line = line.rstrip("\n").rstrip("\r")
                    if line:
                        yield line
            finally:
                if filename != "-":
                    fh.close()

        return cls(_iter())

    @classmethod
    def from_stdin(cls) -> AckFiles:
        _called = False

        def _iter() -> Iterator[str]:
            nonlocal _called
            if not _called:
                _called = True
                yield "-"

        return cls(_iter())


def _walk_dir(
    root: str,
    file_filter: Callable[[str], bool] | None,
    descend_filter: Callable[[str], bool] | None,
    follow_symlinks: bool,
    sort_files: bool,
) -> Iterator[str]:
    """Recursively walk a directory yielding files."""
    try:
        entries = os.listdir(root)
    except OSError:
        return

    if sort_files:
        entries.sort()

    dirs: list[str] = []
    files: list[str] = []

    for entry in entries:
        fullpath = os.path.join(root, entry)

        if not follow_symlinks and os.path.islink(fullpath):
            continue

        if os.path.isdir(fullpath):
            dirs.append(fullpath)
        elif os.path.isfile(fullpath):
            files.append(fullpath)

    for filepath in files:
        if file_filter is None or file_filter(filepath):
            yield filepath

    for dirpath in dirs:
        if descend_filter is None or descend_filter(dirpath):
            yield from _walk_dir(dirpath, file_filter, descend_filter, follow_symlinks, sort_files)
