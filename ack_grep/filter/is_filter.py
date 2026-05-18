"""Filter by exact filename match."""

from __future__ import annotations

import os

from ack_grep.filter import Filter

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ack_grep.file import AckFile


class IsFilter(Filter):
    """Matches files by exact basename."""

    def __init__(self, filename: str) -> None:
        self.filename = filename

    def filter(self, file: AckFile) -> bool:
        return file.basename == self.filename

    def to_string(self) -> str:
        return f"is:{self.filename}"

    def inspect(self) -> str:
        return f"IsFilter({self.filename})"


class IsGroupFilter(Filter):
    """Groups multiple IsFilter instances."""

    def __init__(self) -> None:
        self.filenames: set[str] = set()
        self.filters: list[IsFilter] = []

    def add(self, is_filter: IsFilter) -> None:
        self.filters.append(is_filter)
        self.filenames.add(is_filter.filename)

    def filter(self, file: AckFile) -> bool:
        return file.basename in self.filenames

    def to_string(self) -> str:
        return "is:" + ",".join(sorted(self.filenames))


class IsPathFilter(Filter):
    """Matches files by exact path."""

    def __init__(self, filename: str) -> None:
        self.filename = filename

    def filter(self, file: AckFile) -> bool:
        return file.name == self.filename or os.path.basename(file.name) == self.filename

    def to_string(self) -> str:
        return f"is:{self.filename}"

    def inspect(self) -> str:
        return f"IsPathFilter({self.filename})"


class IsPathGroupFilter(Filter):
    """Groups multiple IsPathFilter instances."""

    def __init__(self) -> None:
        self.paths: set[str] = set()
        self.filters: list[IsPathFilter] = []

    def add(self, path_filter: IsPathFilter) -> None:
        self.filters.append(path_filter)
        self.paths.add(path_filter.filename)

    def filter(self, file: AckFile) -> bool:
        return file.name in self.paths


Filter.register_filter("is", IsFilter)
