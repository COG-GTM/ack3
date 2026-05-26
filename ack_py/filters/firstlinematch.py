"""Filter based on first line of file content."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from ack_py.filters.base import Filter

if TYPE_CHECKING:
    from ack_py.ack_file import AckFile


class FirstLineMatchFilter(Filter):
    """Matches files whose first line matches a regex."""

    def __init__(self, pattern: str) -> None:
        pattern = pattern.strip("/")
        self._regex = re.compile(pattern, re.IGNORECASE)

    def filter(self, file: AckFile) -> bool:
        return bool(self._regex.search(file.firstliney))

    def inspect(self) -> str:
        return f"FirstLineMatchFilter - {self._regex.pattern}"

    def to_string(self) -> str:
        return f"First line matches /{self._regex.pattern}/"


Filter.register_filter("firstlinematch", FirstLineMatchFilter)
