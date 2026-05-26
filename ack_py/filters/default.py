"""Default filter that accepts all regular (non-binary) files."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ack_py.filters.base import Filter

if TYPE_CHECKING:
    from ack_py.ack_file import AckFile


class DefaultFilter(Filter):
    """Accepts all files (used when no type filters are active)."""

    def filter(self, file: AckFile) -> bool:
        return True

    def inspect(self) -> str:
        return "DefaultFilter"

    def to_string(self) -> str:
        return "Default (all files)"
