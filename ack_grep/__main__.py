"""Main entry point for ack - code search tool."""

from __future__ import annotations

import os
import re
import stat
import sys
from typing import IO, Any

import ack_grep
from ack_grep.config_loader import process_args
from ack_grep.file import AckFile
from ack_grep.files import AckFiles
from ack_grep.filter.collection import CollectionFilter

# ANSI color support
try:
    HAS_COLOR = True
except ImportError:
    HAS_COLOR = False

# ANSI escape codes
RESET = "\033[0m"
BOLD = "\033[1m"

# Default colors
COLOR_MAP = {
    "black": "\033[30m",
    "red": "\033[31m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "blue": "\033[34m",
    "magenta": "\033[35m",
    "cyan": "\033[36m",
    "white": "\033[37m",
    "bold": "\033[1m",
    "on_black": "\033[40m",
    "on_red": "\033[41m",
    "on_green": "\033[42m",
    "on_yellow": "\033[43m",
    "on_blue": "\033[44m",
    "on_magenta": "\033[45m",
    "on_cyan": "\033[46m",
    "on_white": "\033[47m",
}


def colorize(text: str, color_spec: str) -> str:
    """Apply ANSI color codes to text."""
    if not color_spec:
        return text

    codes = []
    for part in color_spec.split():
        part_lower = part.lower()
        if part_lower in COLOR_MAP:
            codes.append(COLOR_MAP[part_lower])
        elif part_lower.startswith("rgb"):
            digits = part_lower[3:]
            if len(digits) == 3 and all(c in "012345" for c in digits):
                r, g, b = int(digits[0]), int(digits[1]), int(digits[2])
                code = 16 + 36 * r + 6 * g + b
                codes.append(f"\033[38;5;{code}m")

    if not codes:
        return text

    return "".join(codes) + text + RESET


def _build_descend_filter(opt: dict) -> Any:
    """Build a directory filter function."""
    idirs = opt.get("idirs", [])

    direct_filters = CollectionFilter()
    inverse_filters = CollectionFilter()

    for f in idirs:
        if f.is_inverted():
            inverse_filters.add(f)
        else:
            direct_filters.add(f)

    has_direct = bool(direct_filters.filters)
    has_inverse = bool(inverse_filters.filters)

    def descend_filter(dirpath: str) -> bool:
        basename = os.path.basename(dirpath)
        dummy = AckFile(basename)

        if has_inverse and inverse_filters.filter(dummy):
            return True

        if has_direct and direct_filters.filter(dummy):
            return False

        return True

    return descend_filter


def _build_file_filter(opt: dict) -> Any:
    """Build a file filter function."""
    direct_filters = CollectionFilter()
    inverse_filters = CollectionFilter()

    for f in opt.get("filters", []):
        if f.is_inverted():
            inverse_filters.add(f)
        else:
            direct_filters.add(f)

    ifiles_filters = opt.get("ifiles")
    has_direct = bool(direct_filters.filters)
    has_inverse = bool(inverse_filters.filters)

    def file_filter(filepath: str, dirpath: str | None = None) -> bool:
        if os.path.islink(filepath) and not opt.get("follow", False):
            pass

        try:
            mode = os.stat(filepath).st_mode
            if stat.S_ISFIFO(mode):
                return False
            if not os.access(filepath, os.R_OK):
                if ack_grep.report_bad_filenames:
                    ack_grep.warn(f"{filepath}: cannot open file for reading")
                return False
        except OSError:
            return False

        file = AckFile(filepath)

        if ifiles_filters and ifiles_filters.filter(file):
            return False

        match_found = has_direct and direct_filters.filter(file)

        if not has_direct:
            match_found = True

        if match_found and has_inverse and inverse_filters.filter(file):
            match_found = False

        return match_found

    return file_filter


def get_file_id(filename: str) -> str:
    """Returns a unique identifier for a file."""
    if ack_grep.is_windows:
        return filename.replace("/", "\\")
    else:
        try:
            st = os.stat(filename)
            return f"{st.st_dev}:{st.st_ino}"
        except OSError:
            return filename


class SearchState:
    """Holds mutable state for the search engine."""

    def __init__(self, opt: dict) -> None:
        self.opt = opt
        self.re_match: re.Pattern | None = None
        self.re_not: re.Pattern | None = None
        self.re_hilite: re.Pattern | None = None
        self.re_scan: re.Pattern | None = None
        self.opt_range_start: re.Pattern | None = None
        self.opt_range_end: re.Pattern | None = None
        self.using_ranges = False
        self.match_colno: int | None = None
        self.has_printed_from_any_file = False

        self.opt_show_filename = opt.get("show_filename", True)
        self.opt_heading = opt.get("heading", True)
        self.opt_break = opt.get("break", True)
        self.opt_color = opt.get("color", False)
        self.opt_column = opt.get("column", False)
        self.opt_underline = opt.get("underline", False)
        self.opt_output = opt.get("output")
        self.opt_passthru = opt.get("passthru", False)
        self.opt_v = opt.get("v", False)
        self.opt_p = opt.get("p")
        self.opt_m = opt.get("m")
        self.opt_1 = opt.get("1", False)
        self.opt_A = opt.get("A") or 0
        self.opt_B = opt.get("B") or 0

        self.color_filename = os.environ.get("ACK_COLOR_FILENAME", "bold green")
        self.color_match = os.environ.get("ACK_COLOR_MATCH", "black on_yellow")
        self.color_lineno = os.environ.get("ACK_COLOR_LINENO", "bold yellow")
        self.color_colno = os.environ.get("ACK_COLOR_COLNO", "bold yellow")

        if opt.get("range_start"):
            try:
                self.opt_range_start = re.compile(opt["range_start"])
            except re.error as e:
                ack_grep.die(f"Invalid range-start regex: {e}")
        if opt.get("range_end"):
            try:
                self.opt_range_end = re.compile(opt["range_end"])
            except re.error as e:
                ack_grep.die(f"Invalid range-end regex: {e}")

        self.using_ranges = self.opt_range_start is not None or self.opt_range_end is not None


def file_loop_normal(state: SearchState, files: AckFiles) -> int:
    """Main search loop for normal mode."""
    n_before = 0 if state.opt_output else (state.opt_B or 0)
    n_after = 0 if state.opt_output else (state.opt_A or 0)
    is_tracking_context = n_before > 0 or n_after > 0

    nmatches = 0
    while True:
        file = files.next()
        if file is None:
            break

        needs_line_scan = True
        if not state.opt_passthru and not state.opt_v:
            if state.re_scan and file.may_be_present(state.re_scan):
                file.reset()
            elif state.re_scan:
                needs_line_scan = False

        if needs_line_scan:
            nmatches += print_matches_in_file(state, file, n_before, n_after, is_tracking_context)

        if state.opt_1 and nmatches:
            break

    return nmatches


def print_matches_in_file(
    state: SearchState,
    file: AckFile,
    n_before: int,
    n_after: int,
    is_tracking_context: bool,
) -> int:
    """Search and print matches in a single file."""
    filename = file.name
    fh = file.open()
    if fh is None:
        if ack_grep.report_bad_filenames:
            ack_grep.warn(f"{filename}: cannot open")
        return 0

    display_filename = filename
    if state.opt_show_filename and state.opt_heading and state.opt_color:
        display_filename = colorize(filename, state.color_filename)

    max_count = state.opt_m if state.opt_m else -1

    if is_tracking_context:
        return pmif_context(state, fh, filename, display_filename, max_count, n_before, n_after)
    elif state.opt_passthru:
        return pmif_passthru(state, fh, filename, display_filename, max_count)
    elif state.opt_v:
        return pmif_opt_v(state, fh, filename, display_filename, max_count)
    else:
        return pmif_normal(state, fh, filename, display_filename, max_count)


def _range_setup(state: SearchState) -> bool:
    """Set up range tracking. Returns initial in_range value."""
    if state.using_ranges:
        return state.opt_range_start is None
    return True


def pmif_normal(
    state: SearchState,
    fh: IO[str],
    filename: str,
    display_filename: str,
    max_count: int,
) -> int:
    """Normal matching without context."""
    in_range = _range_setup(state)
    has_printed_from_this_file = False
    nmatches = 0
    last_match_lineno = 0

    for lineno, line in enumerate(fh, 1):
        line = line.rstrip("\r\n")

        if state.using_ranges and not in_range and state.opt_range_start and state.opt_range_start.search(line):
            in_range = True

        if in_range:
            state.match_colno = None
            m = state.re_match.search(line) if state.re_match else None
            is_match = m is not None
            if is_match and state.re_not:
                is_match = not state.re_not.search(line)

            if is_match:
                if m:
                    state.match_colno = m.start() + 1
                if not has_printed_from_this_file:
                    if state.opt_break and state.has_printed_from_any_file:
                        ack_grep.print_blank_line()
                    if state.opt_show_filename and state.opt_heading:
                        ack_grep.say(display_filename)

                if state.opt_p is not None and state.opt_p > 0:
                    if last_match_lineno:
                        if lineno > last_match_lineno + state.opt_p:
                            ack_grep.print_blank_line()
                    elif not state.opt_break and state.has_printed_from_any_file:
                        ack_grep.print_blank_line()

                print_line_with_options(state, filename, line, lineno, ":")
                has_printed_from_this_file = True
                nmatches += 1
                max_count -= 1
                last_match_lineno = lineno

        if state.using_ranges and in_range and state.opt_range_end and state.opt_range_end.search(line):
            in_range = False

        if max_count == 0:
            break

    return nmatches


def pmif_context(
    state: SearchState,
    fh: IO[str],
    filename: str,
    display_filename: str,
    max_count: int,
    n_before: int,
    n_after: int,
) -> int:
    """Matching with before/after context."""
    in_range = _range_setup(state)
    has_printed_from_this_file = False
    nmatches = 0
    after_context_pending = 0
    printed_lineno = 0
    is_first_match = True

    before_buf: list[str | None] = [None] * n_before if n_before else []
    before_pos = 0

    for lineno, line in enumerate(fh, 1):
        line = line.rstrip("\r\n")

        if state.using_ranges and not in_range and state.opt_range_start and state.opt_range_start.search(line):
            in_range = True

        state.match_colno = None

        does_match = False
        if in_range and state.re_match:
            m = state.re_match.search(line)
            does_match = m is not None
            if does_match and state.re_not:
                does_match = not state.re_not.search(line)
            if state.opt_v:
                does_match = not does_match
            elif does_match and m:
                state.match_colno = m.start() + 1

        if does_match and max_count != 0:
            if not has_printed_from_this_file:
                if state.opt_break and state.has_printed_from_any_file:
                    ack_grep.print_blank_line()
                if state.opt_show_filename and state.opt_heading:
                    ack_grep.say(display_filename)

            # Print context separator
            before_unprinted = lineno - printed_lineno - 1
            if not is_first_match and (not printed_lineno or before_unprinted > n_before):
                ack_grep.say("--")

            # Print before-context
            if n_before and before_unprinted > 0:
                show_count = min(before_unprinted, n_before)
                for offset in range(show_count, 0, -1):
                    idx = (before_pos - offset + n_before) % n_before
                    ctx_line = before_buf[idx]
                    if ctx_line is not None:
                        _print_line_with_options_no_color(state, filename, ctx_line, lineno - offset, "-")
                        printed_lineno = lineno - offset

            print_line_with_options(state, filename, line, lineno, ":")
            printed_lineno = lineno
            has_printed_from_this_file = True
            nmatches += 1
            max_count -= 1
            after_context_pending = n_after
            is_first_match = False
        else:
            if after_context_pending > 0:
                _print_line_with_options_no_color(state, filename, line, lineno, "-")
                printed_lineno = lineno
                after_context_pending -= 1
            elif n_before > 0:
                before_buf[before_pos] = line
                before_pos = (before_pos + 1) % n_before

        if state.using_ranges and in_range and state.opt_range_end and state.opt_range_end.search(line):
            in_range = False

        if max_count == 0 and after_context_pending == 0:
            break

    return nmatches


def pmif_passthru(
    state: SearchState,
    fh: IO[str],
    filename: str,
    display_filename: str,
    max_count: int,
) -> int:
    """Passthru mode - print all lines, highlighting matches."""
    in_range = _range_setup(state)
    has_printed_from_this_file = False
    nmatches = 0

    for lineno, line in enumerate(fh, 1):
        line = line.rstrip("\r\n")

        if state.using_ranges and not in_range and state.opt_range_start and state.opt_range_start.search(line):
            in_range = True

        state.match_colno = None
        m = state.re_match.search(line) if state.re_match else None
        does_match = m is not None
        if does_match and state.re_not:
            does_match = not state.re_not.search(line)

        if in_range and does_match:
            if m:
                state.match_colno = m.start() + 1
            if not has_printed_from_this_file:
                if state.opt_break and state.has_printed_from_any_file:
                    ack_grep.print_blank_line()
                if state.opt_show_filename and state.opt_heading:
                    ack_grep.say(display_filename)
            print_line_with_options(state, filename, line, lineno, ":")
            has_printed_from_this_file = True
            nmatches += 1
            max_count -= 1
        else:
            if state.opt_break and not has_printed_from_this_file and state.has_printed_from_any_file:
                ack_grep.print_blank_line()
            _print_line_with_options_no_color(state, filename, line, lineno, "-")
            has_printed_from_this_file = True

        if state.using_ranges and in_range and state.opt_range_end and state.opt_range_end.search(line):
            in_range = False

        if max_count == 0:
            break

    return nmatches


def pmif_opt_v(
    state: SearchState,
    fh: IO[str],
    filename: str,
    display_filename: str,
    max_count: int,
) -> int:
    """Inverted matching."""
    in_range = _range_setup(state)
    has_printed_from_this_file = False
    nmatches = 0

    for lineno, line in enumerate(fh, 1):
        line = line.rstrip("\r\n")

        if state.using_ranges and not in_range and state.opt_range_start and state.opt_range_start.search(line):
            in_range = True

        if in_range:
            m = state.re_match.search(line) if state.re_match else None
            does_match = m is not None
            if does_match and state.re_not:
                does_match = not state.re_not.search(line)

            if not does_match:
                if not has_printed_from_this_file:
                    if state.opt_break and state.has_printed_from_any_file:
                        ack_grep.print_blank_line()
                    if state.opt_show_filename and state.opt_heading:
                        ack_grep.say(display_filename)
                state.match_colno = None
                print_line_with_options(state, filename, line, lineno, ":")
                has_printed_from_this_file = True
                nmatches += 1
                max_count -= 1

        if state.using_ranges and in_range and state.opt_range_end and state.opt_range_end.search(line):
            in_range = False

        if max_count == 0:
            break

    return nmatches


def print_line_with_options(
    state: SearchState,
    filename: str,
    line: str,
    lineno: int,
    separator: str,
    skip_coloring: bool = False,
) -> None:
    """Print a line with filename, line number, coloring, etc."""
    state.has_printed_from_any_file = True

    line_parts: list[str] = []

    if state.opt_show_filename and filename:
        if state.opt_color:
            disp_filename = colorize(filename, state.color_filename)
            disp_lineno = colorize(str(lineno), state.color_lineno)
        else:
            disp_filename = filename
            disp_lineno = str(lineno)

        if state.opt_heading:
            line_parts.append(disp_lineno)
        else:
            line_parts.extend([disp_filename, disp_lineno])

        if state.opt_column:
            colno = state.match_colno or 0
            colno_str = str(colno) if colno else ""
            if state.opt_color and colno_str:
                colno_str = colorize(colno_str, state.color_colno)
            if colno_str:
                line_parts.append(colno_str)

    if state.opt_output and not skip_coloring:
        for m in state.re_match.finditer(line) if state.re_match else []:
            output = state.opt_output
            output = output.replace(r"\g<0>", m.group(0))
            output = output.replace("$&", m.group(0))
            output = output.replace("$_", line)
            output = output.replace("$f", filename)
            for i, g in enumerate(m.groups(), 1):
                if g is not None:
                    output = output.replace(f"${i}", g)
            ack_grep.say(separator.join(line_parts + [output]))
    else:
        underline = ""

        if state.opt_underline and not skip_coloring and state.re_hilite:
            for m in state.re_hilite.finditer(line):
                match_start = m.start()
                match_end = m.end()
                match_length = match_end - match_start
                if match_length <= 0:
                    continue
                spaces_needed = match_start - len(underline)
                underline += " " * max(0, spaces_needed)
                underline += "^" * match_length

        if state.opt_color and not skip_coloring and state.re_hilite:
            offset = 0
            colored_line = line
            for m in state.re_hilite.finditer(line):
                match_start = m.start() + offset
                match_end = m.end() + offset
                match_length = match_end - match_start
                if match_length <= 0:
                    continue
                substring = colored_line[match_start:match_end]
                substitution = colorize(substring, state.color_match)
                colored_line = colored_line[:match_start] + substitution + colored_line[match_end:]
                offset += len(substitution) - len(substring)

            if offset > 0:
                colored_line += f"{RESET}\033[K"
            line = colored_line

        line_parts.append(line)
        ack_grep.say(separator.join(line_parts))

        if underline:
            prefix_parts = line_parts[:-1]
            if prefix_parts:
                spaces = len(separator.join(prefix_parts)) + 1
                ack_grep.print_line(" " * spaces)
            ack_grep.say(underline)


def _print_line_with_options_no_color(
    state: SearchState,
    filename: str,
    line: str,
    lineno: int,
    separator: str,
) -> None:
    """Print a context line without match coloring."""
    print_line_with_options(state, filename, line, lineno, separator, skip_coloring=True)


def count_matches_in_file(state: SearchState, file: AckFile, bail: bool = False) -> int:
    """Count matches in a file without printing them."""
    nmatches = 0

    fh = file.open()
    if fh is None:
        if ack_grep.report_bad_filenames:
            ack_grep.warn(f"{file.name}: cannot open")
        return 0

    if not state.opt_v and state.re_scan:
        if not file.may_be_present(state.re_scan):
            return 0

    file.reset()

    in_range = _range_setup(state)

    for line in fh:
        line = line.rstrip("\r\n")

        if state.using_ranges and not in_range and state.opt_range_start:
            if state.opt_range_start.search(line):
                in_range = True

        if in_range:
            is_match = state.re_match.search(line) is not None if state.re_match else False
            if is_match and state.re_not:
                is_match = not state.re_not.search(line)

            if is_match ^ state.opt_v:
                nmatches += 1
                if bail:
                    return nmatches

        if state.using_ranges and in_range and state.opt_range_end:
            if state.opt_range_end.search(line):
                in_range = False

    return nmatches


def file_loop_count(state: SearchState, files: AckFiles) -> int:
    """File loop for -c (count) mode."""
    total = 0
    sep = "\0" if state.opt.get("print0") else "\n"

    while True:
        file = files.next()
        if file is None:
            break

        nmatches = count_matches_in_file(state, file)

        if state.opt_show_filename:
            if state.opt_color:
                fn = colorize(file.name, state.color_filename)
            else:
                fn = file.name
            ack_grep.print_line(f"{fn}:{nmatches}{sep}")
        else:
            ack_grep.print_line(f"{nmatches}{sep}")

        total += nmatches

        if state.opt_1 and total:
            break

    return total


def file_loop_list(state: SearchState, files: AckFiles, want_match: bool) -> int:
    """File loop for -l or -L mode."""
    total = 0
    sep = "\0" if state.opt.get("print0") else "\n"

    while True:
        file = files.next()
        if file is None:
            break

        nmatches = count_matches_in_file(state, file, bail=True)
        has_match = nmatches > 0

        if has_match == want_match:
            if state.opt.get("show_types"):
                ack_grep.show_types(file)
            else:
                ack_grep.print_line(file.name + sep)
            total += 1

            if state.opt_1:
                break

    return total


def file_loop_files_only(state: SearchState, files: AckFiles) -> int:
    """File loop for -f (list files only) mode."""
    total = 0
    sep = "\0" if state.opt.get("print0") else "\n"

    while True:
        file = files.next()
        if file is None:
            break

        if state.opt.get("show_types"):
            ack_grep.show_types(file)
        else:
            ack_grep.print_line(file.name + sep)
        total += 1

    return total


def file_loop_g(state: SearchState, files: AckFiles) -> int:
    """File loop for -g mode (list files matching pattern)."""
    total = 0
    sep = "\0" if state.opt.get("print0") else "\n"

    while True:
        file = files.next()
        if file is None:
            break

        if state.re_match and state.re_match.search(file.name):
            if state.re_not and state.re_not.search(file.name):
                continue

            if state.opt_color and state.re_hilite:
                display = file.name
                for m in state.re_hilite.finditer(file.name):
                    pass  # Would need to highlight in filename
                display = state.re_hilite.sub(
                    lambda m: colorize(m.group(0), state.color_match), file.name
                )
                ack_grep.print_line(display + sep)
            else:
                ack_grep.print_line(file.name + sep)
            total += 1

    return total


def main(argv: list[str] | None = None) -> None:
    """Main entry point."""
    ack_grep.ORIGINAL_PROGRAM_NAME = sys.argv[0]

    opt = process_args(argv)

    # Set up suppress errors
    if opt.get("s"):
        ack_grep.report_bad_filenames = False

    # Set up print0
    if opt.get("print0"):
        ack_grep.ors = "\0"

    # Determine if we're interactive
    is_interactive = sys.stdout.isatty()

    # Color defaults
    if opt.get("color") is None:
        opt["color"] = is_interactive and not ack_grep.is_windows

    # Heading/break defaults
    if opt.get("heading") is None:
        opt["heading"] = is_interactive
    if opt.get("break") is None:
        opt["break"] = is_interactive

    # Show filename defaults
    if "show_filename" not in opt:
        start_paths = opt.get("_start_paths", [])
        if len(start_paths) == 1 and os.path.isfile(start_paths[0]):
            opt["show_filename"] = False
        else:
            opt["show_filename"] = True
    if opt.get("H"):
        opt["show_filename"] = True
    if opt.get("h"):
        opt["show_filename"] = False

    # Build search state
    state = SearchState(opt)

    # Build regex if needed
    if opt.get("regex") and not opt.get("f"):
        state.re_match, state.re_not, state.re_hilite, state.re_scan = ack_grep.build_all_regexes(
            opt["regex"], opt
        )
    elif not opt.get("f") and not opt.get("regex"):
        if not opt.get("g"):
            ack_grep.die("No regular expression found.")

    # Build file iterator
    start_paths = opt.get("_start_paths", [])

    opt["file_filter"] = _build_file_filter(opt)
    opt["descend_filter"] = _build_descend_filter(opt)

    if opt.get("files_from"):
        files = AckFiles.from_file(opt, opt["files_from"])
        if files is None:
            sys.exit(1)
    elif not start_paths and ack_grep.is_filter_mode:
        files = AckFiles.from_stdin()
    elif not start_paths:
        start_paths = ["."]
        files = AckFiles.from_argv(opt, start_paths)
    else:
        files = AckFiles.from_argv(opt, start_paths)

    # Set up pager
    if opt.get("pager") and not ack_grep.output_to_pipe:
        ack_grep.set_up_pager(opt["pager"])

    # Run the appropriate file loop
    try:
        if opt.get("f"):
            nmatches = file_loop_files_only(state, files)
        elif opt.get("g"):
            if opt.get("regex"):
                state.re_match, state.re_not, state.re_hilite, state.re_scan = ack_grep.build_all_regexes(
                    opt["regex"], opt
                )
            nmatches = file_loop_g(state, files)
        elif opt.get("l"):
            nmatches = file_loop_list(state, files, want_match=True)
        elif opt.get("L"):
            nmatches = file_loop_list(state, files, want_match=False)
        elif opt.get("c"):
            nmatches = file_loop_count(state, files)
        else:
            nmatches = file_loop_normal(state, files)
    except (BrokenPipeError, KeyboardInterrupt):
        pass
    except IOError as e:
        import errno
        if e.errno == errno.EPIPE:
            pass
        else:
            raise

    ack_grep.exit_from_ack(nmatches)


if __name__ == "__main__":
    main()
