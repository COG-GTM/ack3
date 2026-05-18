"""Filter by file extension."""

from __future__ import annotations

from ack_grep.filter import Filter

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ack_grep.file import AckFile


class ExtensionFilter(Filter):
    """Matches files by their extension."""

    def __init__(self, *extensions: str) -> None:
        self.extensions = set(ext.lstrip(".").lower() for ext in extensions)

    def filter(self, file: AckFile) -> bool:
        name = file.basename
        dot = name.rfind(".")
        if dot < 0:
            return False
        ext = name[dot + 1 :].lower()
        return ext in self.extensions

    def to_string(self) -> str:
        return "ext:" + ",".join(sorted(self.extensions))

    def inspect(self) -> str:
        return f"ExtensionFilter({','.join(sorted(self.extensions))})"


class ExtensionGroupFilter(Filter):
    """Groups multiple extension filters."""

    def __init__(self) -> None:
        self.extensions: set[str] = set()
        self.filters: list[ExtensionFilter] = []

    def add(self, ext_filter: ExtensionFilter) -> None:
        self.filters.append(ext_filter)
        self.extensions.update(ext_filter.extensions)

    def filter(self, file: AckFile) -> bool:
        name = file.basename
        dot = name.rfind(".")
        if dot < 0:
            return False
        ext = name[dot + 1 :].lower()
        return ext in self.extensions

    def to_string(self) -> str:
        return "ext:" + ",".join(sorted(self.extensions))


Filter.register_filter("ext", ExtensionFilter)
