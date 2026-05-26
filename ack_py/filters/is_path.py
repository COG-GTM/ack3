"""Filter based on exact file path match."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ack_py.filters.base import Filter

if TYPE_CHECKING:
    from ack_py.ack_file import AckFile


class IsPathFilter(Filter):
    """Matches files whose full path matches exactly."""

    groupname = "IsPathGroup"

    def __init__(self, path: str) -> None:
        self.path = path

    def filter(self, file: AckFile) -> bool:
        return file.name == self.path

    def inspect(self) -> str:
        return f"IsPathFilter - {self.path}"

    def to_string(self) -> str:
        return self.path

    def create_group(self) -> IsPathGroup:
        return IsPathGroup()


class IsPathGroup(Filter):
    """Groups multiple IsPathFilters for fast lookup."""

    def __init__(self) -> None:
        self._paths: set[str] = set()

    def add(self, f: IsPathFilter) -> None:
        self._paths.add(f.path)

    def filter(self, file: AckFile) -> bool:
        return file.name in self._paths
