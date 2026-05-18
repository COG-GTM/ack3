"""Filter by regex match on filename."""

from __future__ import annotations

import re

from ack_grep.filter import Filter

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ack_grep.file import AckFile


class MatchFilter(Filter):
    """Matches files whose basename matches a regex."""

    def __init__(self, pattern: str) -> None:
        self.pattern_str = pattern.strip("/")
        try:
            self.regex = re.compile(self.pattern_str, re.IGNORECASE)
        except re.error:
            from ack_grep import die

            die(f"Invalid regex '{self.pattern_str}' in match filter")
            raise

    def filter(self, file: AckFile) -> bool:
        return self.regex.search(file.basename) is not None

    def to_string(self) -> str:
        return f"match:/{self.pattern_str}/"

    def inspect(self) -> str:
        return f"MatchFilter({self.pattern_str})"


class MatchGroupFilter(Filter):
    """Groups multiple MatchFilter instances."""

    def __init__(self) -> None:
        self.filters: list[MatchFilter] = []

    def add(self, match_filter: MatchFilter) -> None:
        self.filters.append(match_filter)

    def filter(self, file: AckFile) -> bool:
        return any(f.filter(file) for f in self.filters)


Filter.register_filter("match", MatchFilter)
