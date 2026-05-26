#!/usr/bin/env python3
"""ack - grep-like source code search tool.

Main CLI entry point. Ported from the Perl `ack` script.
"""

from __future__ import annotations

import argparse
import os
import re
import shlex
import subprocess
import sys

import ack_py
import ack_py.filters.extension  # noqa: F401
import ack_py.filters.firstlinematch  # noqa: F401
import ack_py.filters.is_filter  # noqa: F401
import ack_py.filters.is_path  # noqa: F401
import ack_py.filters.match  # noqa: F401
from ack_py.ack_file import AckFile
from ack_py.ack_files import AckFiles
from ack_py.config_defaults import options_clean
from ack_py.config_finder import find_config_files
from ack_py.filters.base import Filter
from ack_py.filters.collection import CollectionFilter
from ack_py.filters.default import DefaultFilter
from ack_py.filters.is_path import IsPathFilter
from ack_py.output import (
    ack_print,
    ack_print_blank_line,
    ack_say,
    ack_warn,
    colored,
    get_color,
    get_ors,
    output_to_pipe,
    set_ors,
    set_output_fh,
)
from ack_py.regex_builder import build_all_regexes

# ---------------------------------------------------------------------------
# Type mappings: type_name -> list of Filter objects
# ---------------------------------------------------------------------------
mappings: dict[str, list[Filter]] = {}


# ---------------------------------------------------------------------------
# Easter eggs
# ---------------------------------------------------------------------------

def _thpppt(arg: str) -> None:
    y = "_   /|,\\\\\'!.x',=(www)=,   U   "
    y = y.replace(",", "\n").replace("x", "O").replace("!", "o").replace("w", "_")
    print(f"{y} ack {arg}!")
    sys.exit(0)


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

def _load_ackrc_options(path: str) -> list[str]:
    """Read an ackrc file and return the options as a list of strings."""
    try:
        with open(path) as f:
            lines = f.readlines()
    except OSError:
        return []

    result: list[str] = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        result.extend(shlex.split(line))
    return result


def _collect_all_options(argv: list[str]) -> list[str]:
    """Gather options from defaults, ackrc files, and command line."""
    # Check for --noenv
    noenv = "--noenv" in argv

    all_opts: list[str] = []

    # 1. Defaults
    ignore_defaults = "--ignore-ack-defaults" in argv
    if not ignore_defaults:
        all_opts.extend(options_clean())

    # 2. Config files
    if not noenv:
        config_files = find_config_files()
        for cfg in config_files:
            path = str(cfg["path"])
            if os.path.isfile(path):
                file_opts = _load_ackrc_options(path)
                is_project = cfg.get("project", False)
                # Certain options are forbidden in ackrc files
                for opt in file_opts:
                    if opt in ("--output", "--match"):
                        raise SystemExit(f"ack: Option {opt} is forbidden in .ackrc files.")
                    if is_project and opt == "--pager":
                        raise SystemExit("ack: Option --pager is forbidden in project .ackrc files.")
                all_opts.extend(file_opts)

    # 3. Command line
    all_opts.extend(argv)

    return all_opts


# ---------------------------------------------------------------------------
# Argument parsing helpers
# ---------------------------------------------------------------------------

def _process_type_definitions(opts: list[str]) -> list[str]:
    """Extract --type-add, --type-set, --type-del from options, register them, and return remaining options."""
    remaining: list[str] = []
    i = 0
    while i < len(opts):
        opt = opts[i]
        if opt.startswith("--type-add="):
            _handle_type_add(opt[len("--type-add="):])
        elif opt == "--type-add" and i + 1 < len(opts):
            i += 1
            _handle_type_add(opts[i])
        elif opt.startswith("--type-set="):
            _handle_type_set(opt[len("--type-set="):])
        elif opt == "--type-set" and i + 1 < len(opts):
            i += 1
            _handle_type_set(opts[i])
        elif opt.startswith("--type-del="):
            _handle_type_del(opt[len("--type-del="):])
        elif opt == "--type-del" and i + 1 < len(opts):
            i += 1
            _handle_type_del(opts[i])
        elif opt.startswith("--ignore-directory=") or opt.startswith("--ignore-dir="):
            remaining.append(opt)
        elif opt.startswith("--noignore-directory=") or opt.startswith("--noignore-dir="):
            remaining.append(opt)
        elif opt.startswith("--ignore-file="):
            remaining.append(opt)
        else:
            remaining.append(opt)
        i += 1
    return remaining


def _parse_filter_spec(spec: str) -> tuple[str, Filter]:
    """Parse a type specification like 'python:ext:py' or 'python=py'."""
    # Format: name:filter_type:args
    m = re.match(r"^(\w+):(\w+):(.*)$", spec)
    if m:
        type_name, filter_type, args_str = m.group(1), m.group(2), m.group(3)
        args = [a for a in args_str.split(",") if a]
        return type_name, Filter.create_filter(filter_type, *args)

    # ack1-style: name=ext1,ext2
    m = re.match(r"^(\w+)=(.*)$", spec)
    if m:
        type_name, exts_str = m.group(1), m.group(2)
        exts = [e.lstrip(".") for e in exts_str.split(",") if e]
        return type_name, Filter.create_filter("ext", *exts)

    raise SystemExit(f"ack: Invalid filter specification '{spec}'")


def _handle_type_add(spec: str) -> None:
    type_name, filt = _parse_filter_spec(spec)
    mappings.setdefault(type_name, []).append(filt)


def _handle_type_set(spec: str) -> None:
    type_name, filt = _parse_filter_spec(spec)
    mappings[type_name] = [filt]


def _handle_type_del(name: str) -> None:
    mappings.pop(name, None)


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ack",
        description="Search for PATTERN in source code files.",
        add_help=False,
    )

    # Searching
    p.add_argument("pattern", nargs="?", default=None)
    p.add_argument("paths", nargs="*", default=[])
    p.add_argument("-i", "--ignore-case", action="store_true", default=False)
    p.add_argument("-I", "--no-ignore-case", action="store_true", default=False)
    p.add_argument("-S", "--smart-case", action="store_true", default=False)
    p.add_argument("--nosmart-case", "--no-smart-case", action="store_true", default=False, dest="no_smart_case")
    p.add_argument("-v", "--invert-match", action="store_true", default=False)
    p.add_argument("-w", "--word-regexp", action="store_true", default=False)
    p.add_argument("-Q", "--literal", action="store_true", default=False)
    p.add_argument("--match", dest="match_pattern", default=None)
    p.add_argument("--and", dest="and_patterns", action="append", default=[])
    p.add_argument("--or", dest="or_patterns", action="append", default=[])
    p.add_argument("--not", dest="not_patterns", action="append", default=[])
    p.add_argument("--range-start", default=None)
    p.add_argument("--range-end", default=None)

    # File actions
    p.add_argument("-f", action="store_true", default=False, dest="list_files")
    p.add_argument("-g", action="store_true", default=False, dest="list_files_matching")

    # Output
    p.add_argument("-l", "--files-with-matches", action="store_true", default=False)
    p.add_argument("-L", "--files-without-matches", action="store_true", default=False)
    p.add_argument("-c", "--count", action="store_true", default=False)
    p.add_argument("-m", "--max-count", type=int, default=None)
    p.add_argument("-1", action="store_true", default=False, dest="one_match")
    p.add_argument("-o", action="store_true", default=False, dest="only_matching")
    p.add_argument("--output", default=None)
    p.add_argument("--passthru", action="store_true", default=False)
    p.add_argument("-H", "--with-filename", action="store_true", default=None, dest="show_filename")
    p.add_argument("-h", "--no-filename", action="store_true", default=False, dest="hide_filename")
    p.add_argument("--column", action="store_true", default=False)
    p.add_argument("--nocolumn", action="store_true", default=False)
    p.add_argument("-A", "--after-context", type=int, default=0)
    p.add_argument("-B", "--before-context", type=int, default=0)
    p.add_argument("-C", "--context", type=int, default=None)
    p.add_argument("--print0", action="store_true", default=False)
    p.add_argument("-s", action="store_true", default=False, dest="suppress_errors")
    p.add_argument("-p", "--proximate", type=int, default=None)
    p.add_argument("-P", action="store_true", default=False, dest="no_proximate")

    # Presentation
    p.add_argument("--heading", action="store_true", default=None)
    p.add_argument("--noheading", action="store_true", default=False)
    p.add_argument("--break", action="store_true", default=None, dest="file_break")
    p.add_argument("--nobreak", action="store_true", default=False)
    p.add_argument("--group", action="store_true", default=False)
    p.add_argument("--nogroup", action="store_true", default=False)
    p.add_argument("--underline", action="store_true", default=False)
    p.add_argument("--nounderline", action="store_true", default=False)
    p.add_argument("--color", "--colour", action="store_true", default=None)
    p.add_argument("--nocolor", "--nocolour", action="store_true", default=False)
    p.add_argument("--color-filename", default=None)
    p.add_argument("--color-match", default=None)
    p.add_argument("--color-lineno", default=None)
    p.add_argument("--color-colno", default=None)
    p.add_argument("--pager", default=None, nargs="?", const="")
    p.add_argument("--nopager", action="store_true", default=False)
    p.add_argument("--flush", action="store_true", default=False)

    # File finding
    p.add_argument("--sort-files", action="store_true", default=False)
    p.add_argument("--show-types", action="store_true", default=False)
    p.add_argument("--files-from", default=None)
    p.add_argument("-x", action="store_true", default=False, dest="files_from_stdin")

    # File inclusion/exclusion
    p.add_argument("--ignore-directory", "--ignore-dir", action="append", default=[], dest="ignore_dirs")
    p.add_argument("--noignore-directory", "--noignore-dir", action="append", default=[], dest="noignore_dirs")
    p.add_argument("--ignore-file", action="append", default=[], dest="ignore_files")
    p.add_argument("-r", "-R", "--recurse", action="store_true", default=True)
    p.add_argument("-n", "--no-recurse", action="store_true", default=False)
    p.add_argument("--follow", action="store_true", default=False)
    p.add_argument("--nofollow", action="store_true", default=False)

    # Type selection
    p.add_argument("-t", "--type", action="append", default=[], dest="types")
    p.add_argument("-T", action="append", default=[], dest="notypes")
    p.add_argument("-k", "--known-types", action="store_true", default=False)

    # Miscellaneous
    p.add_argument("--version", action="store_true", default=False)
    p.add_argument("--help", action="store_true", default=False)
    p.add_argument("--help-types", action="store_true", default=False)
    p.add_argument("--help-colors", action="store_true", default=False)
    p.add_argument("--help-rgb-colors", action="store_true", default=False)
    p.add_argument("--man", action="store_true", default=False)
    p.add_argument("--env", action="store_true", default=True)
    p.add_argument("--noenv", action="store_true", default=False)
    p.add_argument("--ackrc", default=None)
    p.add_argument("--ignore-ack-defaults", action="store_true", default=False)
    p.add_argument("--create-ackrc", action="store_true", default=False)
    p.add_argument("--dump", action="store_true", default=False)
    p.add_argument("--filter", action="store_true", default=None, dest="force_filter")
    p.add_argument("--nofilter", action="store_true", default=False)
    p.add_argument("--thpppt", action="store_true", default=False)
    p.add_argument("--bar", action="store_true", default=False)
    p.add_argument("--cathy", action="store_true", default=False)
    p.add_argument("--debug", action="store_true", default=False)

    return p


# ---------------------------------------------------------------------------
# File filtering compilation
# ---------------------------------------------------------------------------

def _create_is_filter(args_str: str) -> list[Filter]:
    """Create is filters, adding IsPathFilter when args contain path separators."""
    filters: list[Filter] = []
    for arg in args_str.split(","):
        if not arg:
            continue
        filters.append(Filter.create_filter("is", arg))
        if os.sep in arg or "/" in arg:
            filters.append(IsPathFilter(arg))
    return filters


def _compile_ignore_dir_filters(
    ignore_dir_specs: list[str],
    noignore_dir_specs: list[str],
) -> list[Filter]:
    """Build ignore-directory filters from --ignore-dir and --noignore-dir specs."""
    filters: list[Filter] = []
    for spec in ignore_dir_specs:
        # spec is like "is:.git" or just ".git"
        if ":" not in spec:
            spec = "is:" + spec
        filter_type, args_str = spec.split(":", 1)
        if filter_type == "is":
            filters.extend(_create_is_filter(args_str))
        else:
            f = Filter.create_filter(filter_type, *args_str.split(","))
            filters.append(f)

    # noignore dirs invert
    for spec in noignore_dir_specs:
        if ":" not in spec:
            spec = "is:" + spec
        filter_type, args_str = spec.split(":", 1)
        if filter_type == "is":
            for f in _create_is_filter(args_str):
                filters.append(f.invert())
        else:
            f = Filter.create_filter(filter_type, *args_str.split(","))
            filters.append(f.invert())

    return filters


def _compile_ignore_file_filters(ignore_file_specs: list[str]) -> CollectionFilter | None:
    """Build ignore-file filters from --ignore-file specs."""
    if not ignore_file_specs:
        return None
    coll = CollectionFilter()
    for spec in ignore_file_specs:
        filter_type, args_str = spec.split(":", 1)
        if filter_type == "is":
            for f in _create_is_filter(args_str):
                coll.add(f)
        else:
            f = Filter.create_filter(filter_type, *args_str.split(","))
            coll.add(f)
    return coll


def _compile_type_filters(
    types: list[str],
    notypes: list[str],
    known_types: bool,
) -> list[Filter]:
    """Build type filters from -t, -T, and -k options."""
    filters: list[Filter] = []

    for t in types:
        t_clean = t.removeprefix("no")
        if t.startswith("no"):
            if t_clean in mappings:
                for f in mappings[t_clean]:
                    filters.append(f.invert())
            else:
                raise SystemExit(f"ack: Unknown type '{t_clean}'")
        else:
            if t in mappings:
                filters.extend(mappings[t])
            else:
                raise SystemExit(f"ack: Unknown type '{t}'")

    for t in notypes:
        if t in mappings:
            for f in mappings[t]:
                filters.append(f.invert())
        else:
            raise SystemExit(f"ack: Unknown type '{t}'")

    if known_types:
        for type_filters in mappings.values():
            filters.extend(type_filters)

    return filters


def _compile_descend_filter(
    idir_filters: list[Filter],
) -> callable | None:
    """Build the filter that decides whether to descend into a directory."""
    if not idir_filters:
        return None

    has_inverted = any(f.is_inverted() for f in idir_filters)
    if has_inverted:
        return None  # Cannot skip entire trees if we have --noignore-dir

    def _filter(dirpath: str) -> bool:
        f = AckFile(dirpath)
        return not any(filt.filter(f) for filt in idir_filters)

    return _filter


def _compile_file_filter(
    type_filters: list[Filter],
    idir_filters: list[Filter],
    ifile_filter: CollectionFilter | None,
    start_set: set[str],
    opt_g: bool = False,
    re_match: re.Pattern[str] | None = None,
    re_not: re.Pattern[str] | None = None,
    opt_v: bool = False,
    report_bad: bool = True,
) -> callable:
    """Build the filter that decides whether to search a file."""
    direct = CollectionFilter()
    inverse = CollectionFilter()
    for f in type_filters:
        if f.is_inverted():
            inverse.add(f.invert())
        else:
            direct.add(f)

    # If no direct (non-inverted) type filters, use default
    has_direct = any(not f.is_inverted() for f in type_filters)
    if not has_direct:
        direct.add(DefaultFilter())

    # Build noignore-dir aware filter
    has_idir_inverted = any(f.is_inverted() for f in idir_filters)
    def _filter(filepath: str) -> bool:
        # Command-line files always pass
        if _get_file_id(filepath) in start_set:
            return True

        # -g mode: filter by filename regex
        if opt_g and re_match is not None:
            match = bool(re_match.search(filepath))
            if match and re_not is not None:
                match = not re_not.search(filepath)
            if match:
                if opt_v:
                    return False
            else:
                if not opt_v:
                    return False

        # Check noignore-dir handling
        if has_idir_inverted:
            dirpath = os.path.dirname(filepath)
            parts = dirpath.split(os.sep)
            is_ignoring = False
            for i in range(len(parts)):
                partial = os.sep.join(parts[: i + 1]) or os.sep
                dir_file = AckFile(partial)
                for filt in idir_filters:
                    if filt.is_inverted():
                        inner = filt.invert()
                        if inner.filter(dir_file):
                            is_ignoring = False
                    else:
                        if filt.filter(dir_file):
                            is_ignoring = True
            if is_ignoring:
                return False

        # Ignore named pipes
        try:
            import stat
            if stat.S_ISFIFO(os.stat(filepath).st_mode):
                return False
        except OSError:
            pass

        # Check readability
        if not os.access(filepath, os.R_OK):
            if report_bad:
                ack_warn(f"{filepath}: cannot open file for reading")
            return False

        file = AckFile(filepath)

        # Apply ignore-file filter
        if ifile_filter is not None and ifile_filter.filter(file):
            return False

        # Apply type filters
        match_found = direct.filter(file)
        if match_found and inverse.filter(file):
            match_found = False

        return match_found

    return _filter


def _get_file_id(filepath: str) -> str:
    """Return a unique id for a file, for dedup purposes."""
    if sys.platform == "win32":
        return os.path.normpath(filepath)
    try:
        st = os.stat(filepath)
        return f"{st.st_dev}:{st.st_ino}"
    except OSError:
        return filepath


# ---------------------------------------------------------------------------
# Search helpers
# ---------------------------------------------------------------------------

def _filetypes(file: AckFile) -> list[str]:
    """Return the list of type names matching a file."""
    matches = []
    for type_name, filters in mappings.items():
        for f in filters:
            if f.filter(file.clone()):
                matches.append(type_name)
                break
    return sorted(matches)


# ---------------------------------------------------------------------------
# Search loops
# ---------------------------------------------------------------------------

def _file_loop_fg(
    files: AckFiles,
    opts: argparse.Namespace,
    re_match: re.Pattern[str] | None,
    re_not: re.Pattern[str] | None,
) -> int:
    """List files (-f or -g mode)."""
    nmatches = 0
    ors = get_ors()
    while True:
        file = files.next()
        if file is None:
            break
        if opts.show_types:
            types = _filetypes(file)
            arrow = " => " if types else " =>"
            ack_say(f"{file.name}{arrow}{','.join(types)}")
        elif opts.list_files_matching:
            use_color = opts._use_color
            if use_color:
                display = colored(file.name, get_color("ACK_COLOR_FILENAME"))
            else:
                display = file.name
            ack_print(display)
            ack_print(ors)
        else:
            ack_say(file.name)
        nmatches += 1
        if opts.max_count is not None and nmatches >= opts.max_count:
            break
    return nmatches


def _count_matches_in_file(
    file: AckFile,
    re_match: re.Pattern[str],
    re_not: re.Pattern[str] | None,
    re_scan: re.Pattern[str] | None,
    opt_v: bool,
    range_start: re.Pattern[str] | None,
    range_end: re.Pattern[str] | None,
    using_ranges: bool,
    bail: bool = False,
) -> int:
    """Count matching lines in a file."""
    nmatches = 0

    fh = file.open()
    if fh is None:
        return 0

    if not opt_v:
        if not file.may_be_present(re_scan):
            file.close()
            return 0

    file.reset()

    in_range = not using_ranges or (range_start is None and range_end is not None)

    try:
        for raw_line in fh:
            try:
                line = raw_line.decode("utf-8", errors="replace").rstrip("\n").rstrip("\r")
            except Exception:
                continue

            if using_ranges and not in_range and range_start is not None and range_start.search(line):
                in_range = True

            if in_range:
                is_match = bool(re_match.search(line))
                if is_match and re_not is not None:
                    is_match = not re_not.search(line)
                if is_match != opt_v:  # XOR
                    nmatches += 1
                    if bail:
                        break

            if using_ranges and in_range and range_end is not None and range_end.search(line):
                in_range = False
    except Exception:
        pass

    file.close()
    return nmatches


def _file_loop_c(
    files: AckFiles,
    opts: argparse.Namespace,
    re_match: re.Pattern[str],
    re_not: re.Pattern[str] | None,
    re_scan: re.Pattern[str] | None,
) -> int:
    """Count mode (-c)."""
    nmatched_files = 0
    total_count = 0
    use_color = opts._use_color
    show_filename = opts._show_filename

    while True:
        file = files.next()
        if file is None:
            break

        count = _count_matches_in_file(
            file, re_match, re_not, re_scan, opts.invert_match,
            opts._range_start_re, opts._range_end_re, opts._using_ranges,
        )
        if count:
            nmatched_files += 1

        if not show_filename:
            total_count += count
            continue

        if not opts.files_with_matches or count > 0:
            if show_filename:
                display = file.name
                if use_color:
                    display = colored(display, get_color("ACK_COLOR_FILENAME"))
                ack_say(f"{display}:{count}")
            else:
                ack_say(str(count))

    if not show_filename:
        ack_say(str(total_count))

    return nmatched_files


def _file_loop_lL(
    files: AckFiles,
    opts: argparse.Namespace,
    re_match: re.Pattern[str],
    re_not: re.Pattern[str] | None,
    re_scan: re.Pattern[str] | None,
) -> int:
    """List matching/non-matching files (-l or -L)."""
    nmatches = 0

    while True:
        file = files.next()
        if file is None:
            break

        is_match = _count_matches_in_file(
            file, re_match, re_not, re_scan, opts.invert_match,
            opts._range_start_re, opts._range_end_re, opts._using_ranges,
            bail=True,
        )

        show = (opts.files_without_matches and not is_match) or (not opts.files_without_matches and is_match)
        if show:
            ack_say(file.name)
            nmatches += 1
            if opts.one_match:
                break
            if opts.max_count is not None and nmatches >= opts.max_count:
                break

    return nmatches


def _file_loop_normal(
    files: AckFiles,
    opts: argparse.Namespace,
    re_match: re.Pattern[str],
    re_not: re.Pattern[str] | None,
    re_hilite: re.Pattern[str],
    re_scan: re.Pattern[str] | None,
) -> int:
    """Normal search loop — print matching lines with optional context."""
    use_color = opts._use_color
    show_filename = opts._show_filename
    heading = opts._heading
    file_break = opts._break
    opt_column = opts.column and not opts.nocolumn
    opt_underline = opts.underline and not opts.nounderline
    opt_output = opts.output
    opt_passthru = opts.passthru
    opt_v = opts.invert_match
    opt_p = opts.proximate
    opt_A = opts.after_context
    opt_B = opts.before_context
    range_start = opts._range_start_re
    range_end = opts._range_end_re
    using_ranges = opts._using_ranges

    is_tracking_context = opt_A > 0 or opt_B > 0
    nmatches = 0
    has_printed_from_any_file = False

    if opt_output:
        opt_A = opt_B = 0
        is_tracking_context = False

    while True:
        file = files.next()
        if file is None:
            break

        # Pre-scan optimization
        if not opt_passthru and not opt_v:
            if not file.may_be_present(re_scan):
                continue
            file.reset()

        fh = file.open()
        if fh is None:
            if not opts.suppress_errors:
                ack_warn(f"{file.name}: cannot open file for reading")
            continue

        filename = file.name
        display_filename = filename
        if show_filename and heading and use_color:
            display_filename = colored(filename, get_color("ACK_COLOR_FILENAME"))

        has_printed_from_this_file = False
        last_match_lineno = 0
        lineno = 0
        in_range = not using_ranges or (range_start is None and range_end is not None)

        # Context tracking
        before_context_buf: list[str | None] = [None] * opt_B if opt_B else []
        before_context_pos = 0
        after_context_pending = 0
        printed_lineno = 0
        is_first_match = True

        max_count = opts.max_count if opts.max_count is not None else -1

        try:
            for raw_line in fh:
                lineno += 1
                try:
                    line = raw_line.decode("utf-8", errors="replace").rstrip("\n").rstrip("\r")
                except Exception:
                    continue

                if using_ranges and not in_range and range_start is not None and range_start.search(line):
                    in_range = True

                match_colno = None
                does_match = False

                if in_range:
                    m = re_match.search(line)
                    does_match = bool(m)
                    if does_match and re_not is not None:
                        does_match = not re_not.search(line)
                    if opt_v:
                        does_match = not does_match
                    elif does_match and m is not None:
                        match_colno = m.start() + 1

                if opt_passthru and in_range:
                    m = re_match.search(line)
                    is_passthru_match = bool(m)
                    if is_passthru_match and re_not is not None:
                        is_passthru_match = not re_not.search(line)
                    if is_passthru_match:
                        if m is not None:
                            match_colno = m.start() + 1
                        if not has_printed_from_this_file:
                            if file_break and has_printed_from_any_file:
                                ack_print_blank_line()
                            if show_filename and heading:
                                ack_say(display_filename)
                        _print_line(
                            filename, line, lineno, ":", use_color, show_filename,
                            heading, opt_column, match_colno, re_hilite, opt_underline, opt_output,
                        )
                        has_printed_from_this_file = True
                        has_printed_from_any_file = True
                        nmatches += 1
                        max_count -= 1
                    else:
                        if file_break and not has_printed_from_this_file and has_printed_from_any_file:
                            ack_print_blank_line()
                        _print_line(
                            filename, line, lineno, "-", use_color, show_filename,
                            heading, False, None, None, False, None, skip_coloring=True,
                        )
                        has_printed_from_this_file = True
                        has_printed_from_any_file = True
                elif does_match and max_count != 0:
                    if not has_printed_from_this_file:
                        if file_break and has_printed_from_any_file:
                            ack_print_blank_line()
                        if show_filename and heading:
                            ack_say(display_filename)

                    # Proximate blank lines
                    if opt_p is not None and opt_p > 0:
                        if last_match_lineno and lineno > last_match_lineno + opt_p:
                            ack_print_blank_line()
                        elif not last_match_lineno and not file_break and has_printed_from_any_file:
                            ack_print_blank_line()

                    # Context handling
                    if is_tracking_context:
                        before_unprinted = lineno - printed_lineno - 1
                        if not is_first_match and (not printed_lineno or before_unprinted > opt_B):
                            ack_say("--")
                        if before_unprinted > opt_B:
                            before_unprinted = opt_B
                        while before_unprinted > 0:
                            idx = (before_context_pos - before_unprinted + opt_B) % opt_B
                            ctx_line = before_context_buf[idx]
                            if ctx_line is not None:
                                _print_line(
                                    filename, ctx_line, lineno - before_unprinted, "-",
                                    use_color, show_filename, heading, False, None, None, False, None,
                                )
                                printed_lineno = lineno - before_unprinted
                            before_unprinted -= 1

                    _print_line(
                        filename, line, lineno, ":", use_color, show_filename,
                        heading, opt_column, match_colno, re_hilite, opt_underline, opt_output,
                    )
                    printed_lineno = lineno
                    has_printed_from_this_file = True
                    has_printed_from_any_file = True
                    nmatches += 1
                    max_count -= 1
                    last_match_lineno = lineno
                    after_context_pending = opt_A
                    is_first_match = False
                else:
                    if is_tracking_context:
                        if after_context_pending > 0:
                            _print_line(
                                filename, line, lineno, "-", use_color, show_filename,
                                heading, False, None, None, False, None,
                            )
                            printed_lineno = lineno
                            after_context_pending -= 1
                        elif opt_B > 0:
                            before_context_buf[before_context_pos] = line
                            before_context_pos = (before_context_pos + 1) % opt_B

                if using_ranges and in_range and range_end is not None and range_end.search(line):
                    in_range = False

                if max_count == 0 and after_context_pending == 0:
                    break
        except Exception:
            pass

        file.close()
        if opts.one_match and nmatches:
            break

    return nmatches


def _print_line(
    filename: str | None,
    line: str,
    lineno: int,
    separator: str,
    use_color: bool,
    show_filename: bool,
    heading: bool,
    opt_column: bool,
    match_colno: int | None,
    re_hilite: re.Pattern[str] | None,
    opt_underline: bool,
    opt_output: str | None,
    skip_coloring: bool = False,
) -> None:
    """Format and print a single output line."""
    line_parts: list[str] = []

    if show_filename and filename is not None:
        if use_color:
            disp_filename = colored(filename, get_color("ACK_COLOR_FILENAME"))
            disp_lineno = colored(str(lineno), get_color("ACK_COLOR_LINENO"))
        else:
            disp_filename = filename
            disp_lineno = str(lineno)

        if heading:
            line_parts.append(disp_lineno)
        else:
            line_parts.extend([disp_filename, disp_lineno])

        if opt_column and match_colno is not None:
            colno_str = str(match_colno)
            if use_color:
                colno_str = colored(colno_str, get_color("ACK_COLOR_COLNO"))
            line_parts.append(colno_str)

    if opt_output is not None and not skip_coloring:
        # --output mode: for each match, print the output expression
        for m in re_hilite.finditer(line) if re_hilite else []:
            output = opt_output
            # Replace $& with the match
            output = output.replace("$&", m.group(0))
            # Replace $1..$9
            for i in range(1, 10):
                try:
                    val = m.group(i) or ""
                except (IndexError, re.error):
                    val = ""
                output = output.replace(f"${i}", val)
            ack_say(separator.join([*line_parts, output]))
        return

    # Underline computation (before highlighting changes string length)
    underline = ""
    if opt_underline and not skip_coloring and re_hilite is not None:
        for m in re_hilite.finditer(line):
            match_start = m.start()
            match_length = m.end() - m.start()
            if match_length <= 0:
                continue
            spaces_needed = match_start - len(underline)
            underline += " " * spaces_needed
            underline += "^" * match_length

    # Highlighting
    if use_color and not skip_coloring and re_hilite is not None:
        color_match = get_color("ACK_COLOR_MATCH")
        parts: list[str] = []
        last_end = 0
        for m in re_hilite.finditer(line):
            if m.end() - m.start() <= 0:
                continue
            parts.append(line[last_end : m.start()])
            parts.append(colored(m.group(0), color_match))
            last_end = m.end()
        parts.append(line[last_end:])
        line = "".join(parts)
        line += "\033[0m\033[K"

    line_parts.append(line)
    ack_say(separator.join(line_parts))

    if underline:
        # Print underline aligned with the line content
        prefix_parts = line_parts[:-1]
        if prefix_parts:
            # Calculate prefix length without ANSI codes
            raw_prefix = separator.join(prefix_parts)
            clean_prefix = re.sub(r"\033\[[^m]*m", "", raw_prefix)
            ack_print(" " * (len(clean_prefix) + 1))
        ack_say(underline)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    if argv is None:
        argv = sys.argv[1:]

    # Check for easter eggs before any parsing
    for arg in argv:
        if arg == "--":
            break
        if re.match(r"^--th[pt]+t+$", arg):
            _thpppt(arg)
        if arg == "--bar":
            print("I say, is that a alarm that is going off?  Well!  I suppose we have to deal with it!")
            sys.exit(0)
        if arg == "--cathy":
            print("CHOCOLATE!!! CHOCOLATE!!! CHOCOLATE!!!")
            sys.exit(0)

    all_opts = _collect_all_options(argv)

    # Process type definitions first (they modify the mappings dict)
    remaining_opts = _process_type_definitions(all_opts)

    # Now split --ignore-dir=X and --ignore-file=X from remaining_opts into dedicated lists
    final_opts: list[str] = []
    extra_ignore_dirs: list[str] = []
    extra_noignore_dirs: list[str] = []
    extra_ignore_files: list[str] = []

    for opt in remaining_opts:
        if opt.startswith("--ignore-directory=") or opt.startswith("--ignore-dir="):
            val = opt.split("=", 1)[1]
            extra_ignore_dirs.append(val)
        elif opt.startswith("--noignore-directory=") or opt.startswith("--noignore-dir="):
            val = opt.split("=", 1)[1]
            extra_noignore_dirs.append(val)
        elif opt.startswith("--ignore-file="):
            val = opt.split("=", 1)[1]
            extra_ignore_files.append(val)
        else:
            final_opts.append(opt)

    parser = _build_parser()

    # Custom parsing to handle -t TYPE and -T TYPE
    preprocessed: list[str] = []
    i = 0
    while i < len(final_opts):
        arg = final_opts[i]
        if arg == "-t" and i + 1 < len(final_opts):
            preprocessed.extend(["--type", final_opts[i + 1]])
            i += 2
        elif arg == "-T" and i + 1 < len(final_opts):
            preprocessed.extend(["-T", final_opts[i + 1]])
            i += 2
        else:
            preprocessed.append(arg)
            i += 1

    try:
        opts = parser.parse_args(preprocessed)
    except SystemExit:
        raise

    # Merge the extra ignore lists
    opts.ignore_dirs.extend(extra_ignore_dirs)
    opts.noignore_dirs.extend(extra_noignore_dirs)
    opts.ignore_files.extend(extra_ignore_files)

    # Handle info-display options
    if opts.version:
        print(f"ack {ack_py.__version__}")
        print(f"Running under Python {sys.version.split()[0]} at {sys.executable}")
        print()
        print(ack_py.COPYRIGHT)
        print()
        print("This program is free software. You may modify or distribute it")
        print("under the terms of the Artistic License v2.0.")
        sys.exit(0)

    if opts.help:
        _show_help()
        sys.exit(0)

    if opts.help_types:
        _show_help_types()
        sys.exit(0)

    if opts.help_colors:
        _show_help_colors()
        sys.exit(0)

    if opts.create_ackrc:
        from ack_py.config_defaults import options
        print("--ignore-ack-defaults")
        for line in options():
            print(line)
        sys.exit(0)

    if opts.man:
        _show_help()
        sys.exit(0)

    # Handle group/nogroup shorthand
    if opts.group:
        opts.heading = True
        opts.file_break = True
    if opts.nogroup:
        opts.noheading = True
        opts.nobreak = True

    # Resolve context
    if opts.context is not None:
        opts.after_context = opts.context
        opts.before_context = opts.context

    # Resolve print0
    if opts.print0:
        set_ors("\0")

    # Resolve pattern
    # For -f mode, there is no pattern; any positional arg is a path.
    # For -g mode, the first positional is a pattern (filter regex), rest are paths.
    if opts.list_files:
        # -f mode: no pattern needed; push pattern back as path if it exists
        if opts.pattern is not None:
            opts.paths.insert(0, opts.pattern)
        opt_regex = None
    elif opts.list_files_matching:
        # -g mode: pattern is the filter regex
        opt_regex = opts.match_pattern or opts.pattern
    else:
        opt_regex = opts.match_pattern or opts.pattern

    if opts.only_matching and opt_regex is None:
        opt_regex = opts.pattern
        opts.output = "$&"

    # Handle --output from -o
    if opts.only_matching and opts.output is None:
        opts.output = "$&"

    # Determine if we need a regex
    need_regex = not opts.list_files

    if need_regex and opt_regex is None:
        if opts.paths:
            opt_regex = opts.paths.pop(0)
        elif not opts.list_files and not opts.list_files_matching:
            _show_help()
            sys.exit(1)

    # Resolve color
    use_color = opts.color
    if opts.nocolor:
        use_color = False
    if use_color is None and not opts.list_files_matching:
        use_color = not output_to_pipe()
    if use_color is None:
        use_color = not output_to_pipe()
    opts._use_color = use_color

    # Set env colors from CLI
    if opts.color_match:
        os.environ["ACK_COLOR_MATCH"] = opts.color_match
    if opts.color_filename:
        os.environ["ACK_COLOR_FILENAME"] = opts.color_filename
    if opts.color_lineno:
        os.environ["ACK_COLOR_LINENO"] = opts.color_lineno
    if opts.color_colno:
        os.environ["ACK_COLOR_COLNO"] = opts.color_colno

    # Resolve heading and break
    heading = opts.heading
    if opts.noheading:
        heading = False
    if heading is None:
        heading = not output_to_pipe()
    opts._heading = heading

    file_break = opts.file_break
    if opts.nobreak:
        file_break = False
    if file_break is None:
        file_break = not output_to_pipe()
    opts._break = file_break

    # Resolve show_filename
    show_filename = opts.show_filename
    if opts.hide_filename:
        show_filename = False
    opts._show_filename = show_filename  # May still be None, resolved after files setup

    # No proximate
    if opts.no_proximate:
        opts.proximate = 0

    # Resolve smart-case
    if opts.no_ignore_case:
        opts.ignore_case = False
        opts.smart_case = False
    if opts.no_smart_case:
        opts.smart_case = False

    # Show types requires -f or -g
    if opts.show_types and not (opts.list_files or opts.list_files_matching):
        raise SystemExit("ack: --show-types can only be used with -f or -g.")

    # Build range regexes
    opts._range_start_re = None
    opts._range_end_re = None
    if opts.range_start:
        try:
            opts._range_start_re = re.compile(opts.range_start)
        except re.error as e:
            raise SystemExit(f"ack: Invalid regex for --range-start: {e}") from None
    if opts.range_end:
        try:
            opts._range_end_re = re.compile(opts.range_end)
        except re.error as e:
            raise SystemExit(f"ack: Invalid regex for --range-end: {e}") from None
    opts._using_ranges = opts._range_start_re is not None or opts._range_end_re is not None

    # Build regexes
    re_match: re.Pattern[str] | None = None
    re_not: re.Pattern[str] | None = None
    re_hilite: re.Pattern[str] | None = None
    re_scan: re.Pattern[str] | None = None

    if opt_regex is not None:
        re_match, re_not, re_hilite, re_scan = build_all_regexes(
            opt_regex,
            and_patterns=opts.and_patterns or None,
            or_patterns=opts.or_patterns or None,
            not_patterns=opts.not_patterns or None,
            ignore_case=opts.ignore_case,
            smart_case=opts.smart_case,
            literal=opts.literal,
            word_regexp=opts.word_regexp,
        )

    # Build file filters
    idir_filters = _compile_ignore_dir_filters(opts.ignore_dirs, opts.noignore_dirs)
    ifile_filter = _compile_ignore_file_filters(opts.ignore_files)
    type_filters = _compile_type_filters(opts.types, opts.notypes, opts.known_types)

    descend_filter = _compile_descend_filter(idir_filters)

    # Determine files to search
    report_bad = not opts.suppress_errors
    is_filter_mode = not sys.stdin.isatty() and not opts.paths and opts.files_from is None and not opts.list_files

    if opts.files_from_stdin:
        opts.files_from = "-"

    if is_filter_mode and opts.files_from is None:
        files = AckFiles.from_stdin()
        if opt_regex is None:
            raise SystemExit("ack: No regular expression found.")
    elif opts.files_from is not None:
        files_obj = AckFiles.from_file(opts.files_from, sort_files=opts.sort_files)
        if files_obj is None:
            sys.exit(1)
        files = files_obj
    else:
        start = opts.paths if opts.paths else ["."]
        for target in start:
            if not os.path.exists(target) and report_bad:
                ack_warn(f"{target}: No such file or directory")

        start_ids = {_get_file_id(s) for s in start if os.path.exists(s)}

        # Resolve show_filename if not explicitly set
        if opts._show_filename is None:
            if len(start) == 1 and os.path.isfile(start[0]):
                opts._show_filename = False
            else:
                opts._show_filename = True
        show_filename = opts._show_filename

        file_filter = _compile_file_filter(
            type_filters, idir_filters, ifile_filter, start_ids,
            opt_g=opts.list_files_matching,
            re_match=re_match, re_not=re_not, opt_v=opts.invert_match,
            report_bad=report_bad,
        )
        files = AckFiles.from_argv(
            start,
            file_filter=file_filter,
            descend_filter=descend_filter,
            follow_symlinks=opts.follow and not opts.nofollow,
            sort_files=opts.sort_files,
            no_recurse=opts.no_recurse,
        )

    if opts._show_filename is None:
        opts._show_filename = True

    # Set up pager
    pager_proc = None
    if not opts.nopager and opts.pager is not None:
        pager_cmd = (
            opts.pager
            or os.environ.get("ACK_PAGER_COLOR")
            or os.environ.get("ACK_PAGER")
            or os.environ.get("PAGER", "")
        )
        if pager_cmd and not output_to_pipe():
            try:
                pager_proc = subprocess.Popen(pager_cmd, shell=True, stdin=subprocess.PIPE, text=True)
                set_output_fh(pager_proc.stdin)
            except OSError:
                pass

    # Dispatch to the appropriate loop
    if opts.list_files or opts.list_files_matching:
        nmatches = _file_loop_fg(files, opts, re_match, re_not)
    elif opts.count:
        nmatches = _file_loop_c(files, opts, re_match, re_not, re_scan)
    elif opts.files_with_matches or opts.files_without_matches:
        nmatches = _file_loop_lL(files, opts, re_match, re_not, re_scan)
    else:
        nmatches = _file_loop_normal(files, opts, re_match, re_not, re_hilite, re_scan)

    # Cleanup pager
    if pager_proc is not None:
        try:
            pager_proc.stdin.close()
        except Exception:
            pass
        pager_proc.wait()

    sys.exit(0 if nmatches else 1)


# ---------------------------------------------------------------------------
# Help display functions
# ---------------------------------------------------------------------------

def _show_help() -> None:
    print(f"""Usage: ack [OPTION]... PATTERN [FILES OR DIRECTORIES]

Search for PATTERN in each source file in the tree from the current
directory on down.  If any files or directories are specified, then
only those files and directories are checked.  ack may also search
STDIN, but only if no file or directory arguments are specified,
or if one of them is "-".

Default switches may be specified in an .ackrc file. If you want no dependency
on the environment, turn it off with --noenv.

File select actions:
  -f                            Only print the files selected, without
                                searching.  The PATTERN must not be specified.
  -g                            Same as -f, but only select files matching
                                PATTERN.

File listing actions:
  -l, --files-with-matches      Print filenames with at least one match
  -L, --files-without-matches   Print filenames with no matches
  -c, --count                   Print filenames and count of matching lines

Searching:
  -i, --ignore-case             Ignore case distinctions in PATTERN
  -S, --[no]smart-case          Ignore case distinctions in PATTERN,
                                only if PATTERN contains no upper case.
  -I, --no-ignore-case          Turns on case-sensitivity in PATTERN.
  -v, --invert-match            Invert match: select non-matching lines
  -w, --word-regexp             Force PATTERN to match only whole words
  -Q, --literal                 Quote all metacharacters; PATTERN is literal
  --range-start PATTERN         Specify PATTERN as the start of a match range.
  --range-end PATTERN           Specify PATTERN as the end of a match range.
  --match PATTERN               Specify PATTERN explicitly. Typically omitted.
  --and PATTERN                 Specifies PATTERN that MUST also be found on
                                the line for a match to occur. Repeatable.
  --or PATTERN                  Specifies PATTERN that MAY also be found on
                                the line for a match to occur. Repeatable.
  --not PATTERN                 Specifies PATTERN that must NOT be found on
                                the line for a match to occur. Repeatable.

Search output:
  --output=expr                 Output the evaluation of expr for each line
                                (turns off text highlighting)
  -o                            Show only the part of a line matching PATTERN
                                Same as --output='$&'
  --passthru                    Print all lines, whether matching or not
  -m, --max-count=NUM           Stop searching in each file after NUM matches
  -1                            Stop searching after one match of any kind
  -H, --with-filename           Print the filename for each match (default:
                                on unless explicitly searching a single file)
  -h, --no-filename             Suppress the prefixing filename on output
  --[no]column                  Show the column number of the first match

  -A NUM, --after-context=NUM   Print NUM lines of trailing context after
                                matching lines.
  -B NUM, --before-context=NUM  Print NUM lines of leading context before
                                matching lines.
  -C [NUM], --context[=NUM]     Print NUM lines (default 2) of output context.

  --print0                      Print null byte as separator between filenames,
                                only works with -f, -g, -l, -L or -c.

  -s                            Suppress error messages about nonexistent or
                                unreadable files.

File presentation:
  --pager=COMMAND               Pipes all ack output through COMMAND.
  --nopager                     Do not send output through a pager.
  --[no]heading                 Print a filename heading above each file's
                                results.  (default: on when used interactively)
  --[no]break                   Print a break between results from different
                                files.  (default: on when used interactively)
  --group                       Same as --heading --break
  --nogroup                     Same as --noheading --nobreak
  -p, --proximate=LINES         Separate match output with blank lines unless
                                they are within LINES lines from each other.
  --[no]underline               Print a line of carets under the matched text.
  --[no]color, --[no]colour     Highlight the matching text (default: on unless
                                output is redirected)
  --color-filename=COLOR
  --color-match=COLOR
  --color-colno=COLOR
  --color-lineno=COLOR          Set the color for filenames, matches, line and
                                column numbers.
  --flush                       Flush output immediately.

File finding:
  --sort-files                  Sort the found files lexically.
  --show-types                  Show which types each file has.
  --files-from=FILE             Read the list of files to search from FILE.
  -x                            Read the list of files to search from STDIN.

File inclusion/exclusion:
  --[no]ignore-dir=name         Add/remove directory from list of ignored dirs
  --[no]ignore-directory=name   Synonym for ignore-dir
  --ignore-file=FILTER:ARGS     Add filter for ignoring files.
  -r, -R, --recurse             Recurse into subdirectories (default: on)
  -n, --no-recurse              No descending into subdirectories
  --[no]follow                  Follow symlinks.  Default is off.

File type inclusion/exclusion:
  -t X, --type=X                Include only X files, where X is a filetype,
                                e.g. python, html, markdown, etc
  -T X, --type=noX              Exclude X files, where X is a filetype.
  -k, --known-types             Include only files of types that ack recognizes.
  --help-types                  Display all known types, and how they're defined.

File type specification:
  --type-set=TYPE:FILTER:ARGS   Files with the given ARGS applied to the given
                                FILTER are recognized as being of type TYPE.
                                This replaces an existing definition for TYPE.
  --type-add=TYPE:FILTER:ARGS   Files with the given ARGS applied to the given
                                FILTER are recognized as being type TYPE.
  --type-del=TYPE               Removes all filters associated with TYPE.

Miscellaneous:
  --version                     Display version & copyright
  --[no]env                     Ignore environment variables and global ackrc
                                files.  --env is legal but redundant.
  --ackrc=filename              Specify an ackrc file to use
  --ignore-ack-defaults         Ignore default definitions included with ack.
  --create-ackrc                Outputs a default ackrc for your customization
                                to standard output.
  --dump                        Dump information on which options are loaded
                                and where they're defined.
  --[no]filter                  Force ack to treat standard input as a pipe
                                (--filter) or tty (--nofilter)
  --help                        This help
  --man                         Print the manual.
  --help-types                  Display all known types, and how they're defined.
  --help-colors                 Show a list of possible color combinations.
  --thpppt                      Bill the Cat
  --bar                         The warning admiral
  --cathy                       Chocolate! Chocolate! Chocolate!

Exit status is 0 if match, 1 if no match.

ack's home page is at https://beyondgrep.com/

This is version {ack_py.__version__} of ack (Python port).""")


def _show_help_types() -> None:
    print("""Usage: ack [OPTION]... PATTERN [FILES OR DIRECTORIES]

The following is the list of filetypes supported by ack.  You can specify a
filetype to include with -t TYPE or --type=TYPE.  You can exclude a
filetype with -T TYPE or --type=noTYPE.

Note that some files may appear in multiple types.  For example, a file
called Rakefile is both Ruby (--type=ruby) and Rakefile (--type=rakefile).
""")
    if not mappings:
        # Load defaults if not already loaded
        for line in options_clean():
            if line.startswith("--type-add="):
                _handle_type_add(line[len("--type-add="):])
            elif line.startswith("--type-set="):
                _handle_type_set(line[len("--type-set="):])

    maxlen = max((len(t) for t in mappings), default=0)
    for type_name in sorted(mappings):
        filters = mappings[type_name]
        ext_list = "; ".join(f.to_string() for f in filters)
        print(f"    {type_name:<{maxlen}} {ext_list}")


def _show_help_colors() -> None:
    print("""ack allows customization of the colors it uses when presenting matches
onscreen.  See the "ACK COLORS" section of the ack manual (ack --man).

Here is a chart of how various color combinations appear: Each of the eight
foreground colors, on each of the eight background colors or no background
color, with and without the bold modifier.
""")
    fg_colors = ["black", "red", "green", "yellow", "blue", "magenta", "cyan", "white"]
    bg_colors = [f"on_{c}" for c in fg_colors]

    cell_width = 7

    def cell(text: str, color_spec: str = "") -> str:
        padded = f"{text:<{cell_width}}"
        return (colored(padded, color_spec) if color_spec else padded) + " "

    print(cell("") + "".join(cell(c) for c in fg_colors))
    print(cell("") + "".join(cell("-" * cell_width) for _ in fg_colors))

    for bg in ["", *bg_colors]:
        print(
            cell("")
            + "".join(cell(c, f"{c} {bg}".strip()) for c in fg_colors)
            + f" {bg}" if bg else cell("") + "".join(cell(c, c) for c in fg_colors)
        )
        print(
            cell("bold")
            + "".join(cell(c, f"bold {c} {bg}".strip()) for c in fg_colors)
            + f" {bg}" if bg else cell("bold") + "".join(cell(c, f"bold {c}") for c in fg_colors)
        )
        print()


if __name__ == "__main__":
    main()
