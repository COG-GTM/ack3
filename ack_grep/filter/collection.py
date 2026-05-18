"""Collection filter that groups multiple filters."""

from __future__ import annotations

from ack_grep.filter import Filter
from ack_grep.filter.extension import ExtensionFilter, ExtensionGroupFilter
from ack_grep.filter.is_filter import IsFilter, IsGroupFilter, IsPathFilter, IsPathGroupFilter
from ack_grep.filter.match import MatchFilter, MatchGroupFilter

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ack_grep.file import AckFile


class CollectionFilter(Filter):
    """Groups multiple filters of different types."""

    def __init__(self) -> None:
        self.filters: list[Filter] = []
        self._extension_group: ExtensionGroupFilter | None = None
        self._is_group: IsGroupFilter | None = None
        self._is_path_group: IsPathGroupFilter | None = None
        self._match_group: MatchGroupFilter | None = None

    def add(self, new_filter: Filter) -> None:
        if isinstance(new_filter, ExtensionFilter):
            if self._extension_group is None:
                self._extension_group = ExtensionGroupFilter()
                self.filters.append(self._extension_group)
            self._extension_group.add(new_filter)
        elif isinstance(new_filter, IsFilter):
            if self._is_group is None:
                self._is_group = IsGroupFilter()
                self.filters.append(self._is_group)
            self._is_group.add(new_filter)
        elif isinstance(new_filter, IsPathFilter):
            if self._is_path_group is None:
                self._is_path_group = IsPathGroupFilter()
                self.filters.append(self._is_path_group)
            self._is_path_group.add(new_filter)
        elif isinstance(new_filter, MatchFilter):
            if self._match_group is None:
                self._match_group = MatchGroupFilter()
                self.filters.append(self._match_group)
            self._match_group.add(new_filter)
        else:
            self.filters.append(new_filter)

    def filter(self, file: AckFile) -> bool:
        return any(f.filter(file) for f in self.filters)

    def to_string(self) -> str:
        return " or ".join(f.to_string() for f in self.filters)

    def inspect(self) -> str:
        return f"CollectionFilter({', '.join(f.inspect() for f in self.filters)})"
