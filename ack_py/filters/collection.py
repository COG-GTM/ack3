"""Collection filter that groups sub-filters for optimized matching."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ack_py.filters.base import Filter

if TYPE_CHECKING:
    from ack_py.ack_file import AckFile


class CollectionFilter(Filter):
    """Groups filters and optimizes them into fast-lookup groups."""

    def __init__(self) -> None:
        self._groups: dict[str, Filter] = {}
        self._ungrouped: list[Filter] = []

    def filter(self, file: AckFile) -> bool:
        for group in self._groups.values():
            if group.filter(file):
                return True
        for f in self._ungrouped:
            if f.filter(file):
                return True
        return False

    def add(self, f: Filter) -> None:
        groupname = getattr(f, "groupname", None)
        if groupname is not None:
            if groupname not in self._groups:
                self._groups[groupname] = f.create_group()
            self._groups[groupname].add(f)
        else:
            self._ungrouped.append(f)

    def inspect(self) -> str:
        return f"CollectionFilter - {id(self)}"

    def to_string(self) -> str:
        return ", ".join(f"({f})" for f in self._ungrouped)
