"""Base filter class and filter registry."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ack_py.ack_file import AckFile

_filter_types: dict[str, type[Filter]] = {}


class Filter:
    """Abstract base for file filters."""

    def filter(self, file: AckFile) -> bool:
        raise NotImplementedError

    def invert(self) -> InverseFilter:
        return InverseFilter(self)

    def is_inverted(self) -> bool:
        return False

    def to_string(self) -> str:
        return "(unimplemented to_string)"

    def inspect(self) -> str:
        return type(self).__name__

    @classmethod
    def register_filter(cls, name: str, klass: type[Filter]) -> None:
        _filter_types[name] = klass

    @classmethod
    def create_filter(cls, filter_type: str, *args: str) -> Filter:
        if filter_type in _filter_types:
            return _filter_types[filter_type](*args)
        allowed = ", ".join(sorted(_filter_types))
        raise SystemExit(f"ack: Unknown filter type '{filter_type}'. Type must be one of: {allowed}.")


class InverseFilter(Filter):
    """A filter that inverts another filter."""

    def __init__(self, inner: Filter) -> None:
        self._filter = inner

    @property
    def inner_filter(self) -> Filter:
        return self._filter

    def filter(self, file: AckFile) -> bool:
        return not self._filter.filter(file)

    def invert(self) -> Filter:
        return self._filter

    def is_inverted(self) -> bool:
        return True

    def inspect(self) -> str:
        return f"!{self._filter}"

    def __str__(self) -> str:
        return self.inspect()
