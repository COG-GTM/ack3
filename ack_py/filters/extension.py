"""Filter based on file extension."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from ack_py.filters.base import Filter

if TYPE_CHECKING:
    from ack_py.ack_file import AckFile


class ExtensionFilter(Filter):
    """Matches files by extension."""

    groupname = "ExtensionGroup"

    def __init__(self, *extensions: str) -> None:
        self.extensions = list(extensions)
        exts = "|".join(re.escape(e) for e in self.extensions)
        self._regex = re.compile(rf"[.](?:{exts})$", re.IGNORECASE)

    def filter(self, file: AckFile) -> bool:
        return bool(self._regex.search(file.name))

    def inspect(self) -> str:
        return f"ExtensionFilter - {self._regex.pattern}"

    def to_string(self) -> str:
        return " ".join(f".{e}" for e in self.extensions)

    def create_group(self) -> ExtensionGroup:
        return ExtensionGroup()


class ExtensionGroup(Filter):
    """Groups multiple ExtensionFilters for fast lookup."""

    def __init__(self) -> None:
        self._extensions: set[str] = set()

    def add(self, f: ExtensionFilter) -> None:
        for ext in f.extensions:
            self._extensions.add(ext.lower())

    def filter(self, file: AckFile) -> bool:
        name = file.name.lower()
        dot = name.rfind(".")
        if dot < 0:
            return False
        return name[dot + 1 :] in self._extensions


Filter.register_filter("ext", ExtensionFilter)
