"""Filter based on exact filename match."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from ack_py.filters.base import Filter

if TYPE_CHECKING:
    from ack_py.ack_file import AckFile


class IsFilter(Filter):
    """Matches files whose basename matches exactly."""

    groupname = "IsGroup"

    def __init__(self, filename: str) -> None:
        self.filename = filename

    def filter(self, file: AckFile) -> bool:
        return os.path.basename(file.name) == self.filename

    def inspect(self) -> str:
        return f"IsFilter - {self.filename}"

    def to_string(self) -> str:
        return self.filename

    def create_group(self) -> IsGroup:
        return IsGroup()


class IsGroup(Filter):
    """Groups multiple IsFilters for fast lookup."""

    def __init__(self) -> None:
        self._filenames: set[str] = set()

    def add(self, f: IsFilter) -> None:
        self._filenames.add(f.filename)

    def filter(self, file: AckFile) -> bool:
        return os.path.basename(file.name) in self._filenames


Filter.register_filter("is", IsFilter)
