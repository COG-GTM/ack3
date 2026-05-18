"""Filter by matching the first line of file content."""

from __future__ import annotations

import re

from ack_grep.filter import Filter

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ack_grep.file import AckFile


class FirstLineMatchFilter(Filter):
    """Matches files whose first line matches a regex."""

    def __init__(self, pattern: str) -> None:
        self.pattern_str = pattern.strip("/")
        try:
            self.regex = re.compile(self.pattern_str)
        except re.error:
            from ack_grep import die

            die(f"Invalid regex '{self.pattern_str}' in firstlinematch filter")
            raise

    def filter(self, file: AckFile) -> bool:
        first_line = file.firstliney()
        return self.regex.search(first_line) is not None

    def to_string(self) -> str:
        return f"firstlinematch:/{self.pattern_str}/"

    def inspect(self) -> str:
        return f"FirstLineMatchFilter({self.pattern_str})"


Filter.register_filter("firstlinematch", FirstLineMatchFilter)
