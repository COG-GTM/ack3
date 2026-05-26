"""Output helpers: ANSI coloring and print functions."""

from __future__ import annotations

import os
import sys

# ANSI color codes
_COLORS: dict[str, str] = {
    "black": "30",
    "red": "31",
    "green": "32",
    "yellow": "33",
    "blue": "34",
    "magenta": "35",
    "cyan": "36",
    "white": "37",
    "on_black": "40",
    "on_red": "41",
    "on_green": "42",
    "on_yellow": "43",
    "on_blue": "44",
    "on_magenta": "45",
    "on_cyan": "46",
    "on_white": "47",
    "bold": "1",
    "dark": "2",
    "italic": "3",
    "underline": "4",
    "blink": "5",
    "reverse": "7",
    "concealed": "8",
}


def colored(text: str, color_spec: str) -> str:
    """Apply ANSI coloring to text. color_spec is space-separated color names."""
    if not color_spec:
        return text
    codes = []
    for part in color_spec.split():
        part_lower = part.lower()
        if part_lower in _COLORS:
            codes.append(_COLORS[part_lower])
        elif part_lower.startswith("rgb"):
            digits = part_lower[3:]
            if len(digits) == 3 and all(c in "012345" for c in digits):
                r, g, b = int(digits[0]), int(digits[1]), int(digits[2])
                code = 16 + 36 * r + 6 * g + b
                codes.append(f"38;5;{code}")
    if not codes:
        return text
    return f"\033[{';'.join(codes)}m{text}\033[0m"


def output_to_pipe() -> bool:
    """Return True if stdout is not a TTY (i.e. output is piped)."""
    return not sys.stdout.isatty()


# Default colors
_default_colors = {
    "ACK_COLOR_MATCH": "black on_yellow",
    "ACK_COLOR_FILENAME": "bold green",
    "ACK_COLOR_LINENO": "bold yellow",
    "ACK_COLOR_COLNO": "bold yellow",
}


def get_color(name: str) -> str:
    """Get color spec from env or defaults."""
    return os.environ.get(name, _default_colors.get(name, ""))


# Output file handle
_fh = sys.stdout
_ors = "\n"


def set_ors(ors: str) -> None:
    global _ors
    _ors = ors


def get_ors() -> str:
    return _ors


def set_output_fh(fh: object) -> None:
    global _fh
    _fh = fh


def get_output_fh() -> object:
    return _fh


def ack_print(*args: str) -> None:
    try:
        print(*args, end="", file=_fh, flush=True)
    except BrokenPipeError:
        sys.exit(0)


def ack_say(*args: str) -> None:
    try:
        print(*args, end=_ors, file=_fh, flush=True)
    except BrokenPipeError:
        sys.exit(0)


def ack_print_blank_line() -> None:
    try:
        print("", file=_fh, flush=True)
    except BrokenPipeError:
        sys.exit(0)


def ack_warn(*args: str) -> None:
    print("ack:", *args, file=sys.stderr)
