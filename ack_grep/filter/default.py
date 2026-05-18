"""Default filter - accepts text files, rejects binary."""

from __future__ import annotations

import os

from ack_grep.filter import Filter

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ack_grep.file import AckFile


class DefaultFilter(Filter):
    """Accepts text files, rejects binary files."""

    def filter(self, file: AckFile) -> bool:
        try:
            if file.name == "-":
                return True

            if not os.path.isfile(file.name):
                return False

            with open(file.name, "rb") as f:
                chunk = f.read(8192)

            if b"\x00" in chunk:
                return False

            return True
        except (OSError, IOError):
            return False

    def to_string(self) -> str:
        return "default:is_text"

    def inspect(self) -> str:
        return "DefaultFilter"
