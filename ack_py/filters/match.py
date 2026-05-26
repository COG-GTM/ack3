"""Filter based on filename regex match."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from ack_py.filters.base import Filter

if TYPE_CHECKING:
    from ack_py.ack_file import AckFile


class MatchFilter(Filter):
    """Matches files whose basename matches a regex pattern."""

    groupname = "MatchGroup"

    def __init__(self, pattern: str) -> None:
        pattern = pattern.strip("/")
        self._regex = re.compile(pattern, re.IGNORECASE)

    def filter(self, file: AckFile) -> bool:
        return bool(self._regex.search(file.basename))

    def inspect(self) -> str:
        return f"MatchFilter - {self._regex.pattern}"

    def to_string(self) -> str:
        return f"Filename matches {self._regex.pattern}"

    def create_group(self) -> MatchGroup:
        return MatchGroup()


class MatchGroup(Filter):
    """Groups multiple MatchFilters."""

    def __init__(self) -> None:
        self._filters: list[MatchFilter] = []

    def add(self, f: MatchFilter) -> None:
        self._filters.append(f)

    def filter(self, file: AckFile) -> bool:
        return any(f.filter(file) for f in self._filters)


Filter.register_filter("match", MatchFilter)
