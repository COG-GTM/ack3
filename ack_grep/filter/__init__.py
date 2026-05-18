"""Filter system for file type matching."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ack_grep.file import AckFile

_filter_types: dict[str, type] = {}


class Filter:
    """Abstract base class for file filters."""

    @classmethod
    def create_filter(cls, filter_type: str, *args: str) -> Filter:
        if filter_type in _filter_types:
            return _filter_types[filter_type](*args)
        allowed = ", ".join(sorted(_filter_types.keys()))
        from ack_grep import die

        die(f"Unknown filter type '{filter_type}'.  Type must be one of: {allowed}.")
        raise SystemExit(2)

    @classmethod
    def register_filter(cls, name: str, filter_class: type) -> None:
        _filter_types[name] = filter_class

    def filter(self, file: AckFile) -> bool:
        raise NotImplementedError

    def invert(self) -> Filter:
        return InverseFilter(self)

    def is_inverted(self) -> bool:
        return False

    def to_string(self) -> str:
        return "(unimplemented to_string)"

    def __str__(self) -> str:
        return self.to_string()

    def inspect(self) -> str:
        return type(self).__name__


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

    def to_string(self) -> str:
        return f"NOT ({self._filter.to_string()})"

    def inspect(self) -> str:
        return f"InverseFilter({self._filter.inspect()})"
