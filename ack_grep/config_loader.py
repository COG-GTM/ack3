"""Configuration loader - processes command-line arguments and ackrc files."""

from __future__ import annotations

import argparse
import os
import re
import sys
from typing import Any

import ack_grep
from ack_grep import config_default, config_finder
from ack_grep.filter import Filter
from ack_grep.filter.collection import CollectionFilter
from ack_grep.filter.default import DefaultFilter
from ack_grep.filter.is_filter import IsPathFilter

# Ensure filter types are registered
import ack_grep.filter.extension  # noqa: F401
import ack_grep.filter.firstlinematch  # noqa: F401
import ack_grep.filter.match  # noqa: F401


def _process_filter_spec(spec: str) -> tuple[str, Filter]:
    """Parse a filter specification like 'python:ext:py'."""
    m = re.match(r"^(\w+):(\w+):(.*)", spec)
    if m:
        type_name, filter_type, arguments = m.group(1), m.group(2), m.group(3)
        return (type_name, Filter.create_filter(filter_type, *arguments.split(",")))

    m = re.match(r"^(\w+)=(.*)", spec)
    if m:
        type_name, extensions = m.group(1), m.group(2)
        exts = [e.lstrip(".") for e in extensions.split(",")]
        return (type_name, Filter.create_filter("ext", *exts))

    ack_grep.die(f"Invalid filter specification '{spec}'")
    raise SystemExit(2)


def _process_ackrc_line(line: str, opt: dict) -> None:
    """Process a single line from an ackrc file."""
    line = line.strip()
    if not line or line.startswith("#"):
        return

    if line.startswith("--type-add="):
        spec = line[len("--type-add="):]
        type_name, filt = _process_filter_spec(spec)
        if type_name not in ack_grep.mappings:
            ack_grep.mappings[type_name] = []
        ack_grep.mappings[type_name].append(filt)

    elif line.startswith("--type-set="):
        spec = line[len("--type-set="):]
        type_name, filt = _process_filter_spec(spec)
        ack_grep.mappings[type_name] = [filt]

    elif line.startswith("--type-del="):
        type_name = line[len("--type-del="):]
        ack_grep.mappings.pop(type_name, None)

    elif line.startswith("--ignore-directory=") or line.startswith("--ignore-dir="):
        prefix = "--ignore-directory=" if line.startswith("--ignore-directory=") else "--ignore-dir="
        dir_spec = line[len(prefix):]
        _process_ignore_dir(dir_spec, opt, inverted=False)

    elif line.startswith("--noignore-directory=") or line.startswith("--noignore-dir="):
        prefix = "--noignore-directory=" if line.startswith("--noignore-directory=") else "--noignore-dir="
        dir_spec = line[len(prefix):]
        _process_ignore_dir(dir_spec, opt, inverted=True)

    elif line.startswith("--ignore-file="):
        file_spec = line[len("--ignore-file="):]
        _process_ignore_file(file_spec, opt)


def _process_ignore_dir(dir_spec: str, opt: dict, inverted: bool) -> None:
    """Process --ignore-directory or --noignore-directory."""
    dir_spec = dir_spec.rstrip("/").rstrip("\\")
    if ":" not in dir_spec:
        dir_spec = "is:" + dir_spec

    filter_type, _, args = dir_spec.partition(":")

    if filter_type == "firstlinematch":
        ack_grep.die(f'Invalid filter specification "{filter_type}" for ignore-dir')

    filt = Filter.create_filter(filter_type, *args.split(","))
    collection = CollectionFilter()
    collection.add(filt)

    if filter_type == "is":
        collection.add(IsPathFilter(args))

    if "idirs" not in opt:
        opt["idirs"] = []

    if inverted:
        opt["idirs"].append(collection.invert())
    else:
        opt["idirs"].append(collection)


def _process_ignore_file(file_spec: str, opt: dict) -> None:
    """Process --ignore-file=FILTER:ARGS."""
    filter_type, _, args = file_spec.partition(":")
    filt = Filter.create_filter(filter_type, *args.split(",") if args else [])

    if "ifiles" not in opt or opt["ifiles"] is None:
        opt["ifiles"] = CollectionFilter()
    opt["ifiles"].add(filt)


def _load_defaults(opt: dict) -> None:
    """Load the default ack configuration."""
    for line in config_default.options_clean():
        _process_ackrc_line(line, opt)


def _load_config_file(path: str, opt: dict, is_project: bool = False) -> list[str]:
    """Load an ackrc file. Returns any unrecognized lines."""
    extra_args: list[str] = []
    try:
        with open(path, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("--"):
                    _process_ackrc_line(line, opt)
                else:
                    extra_args.append(line)
    except (OSError, IOError):
        pass
    return extra_args


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for ack."""
    parser = argparse.ArgumentParser(
        prog="ack",
        description="Search for PATTERN in source files.",
        add_help=False,
    )

    # Searching
    parser.add_argument("pattern", nargs="?", default=None)
    parser.add_argument("files", nargs="*", default=[])
    parser.add_argument("-i", "--ignore-case", action="store_true", default=False)
    parser.add_argument("-S", "--smart-case", action="store_true", default=False)
    parser.add_argument("-I", "--no-ignore-case", action="store_true", default=False)
    parser.add_argument("-v", "--invert-match", action="store_true", default=False)
    parser.add_argument("-w", "--word-regexp", action="store_true", default=False)
    parser.add_argument("-Q", "--literal", action="store_true", default=False)
    parser.add_argument("--match", dest="match_pattern", default=None)
    parser.add_argument("--range-start", default=None)
    parser.add_argument("--range-end", default=None)
    parser.add_argument("--not", dest="not_patterns", action="append", default=[])
    parser.add_argument("--and", dest="and_patterns", action="append", default=[])
    parser.add_argument("--or", dest="or_patterns", action="append", default=[])

    # File select / listing
    parser.add_argument("-f", action="store_true", default=False, dest="f")
    parser.add_argument("-g", action="store_true", default=False, dest="g")
    parser.add_argument("-l", "--files-with-matches", action="store_true", default=False, dest="l")
    parser.add_argument("-L", "--files-without-matches", action="store_true", default=False, dest="L")
    parser.add_argument("-c", "--count", action="store_true", default=False)

    # Output control
    parser.add_argument("-1", action="store_true", default=False, dest="one")
    parser.add_argument("-m", "--max-count", type=int, default=None)
    parser.add_argument("-H", "--with-filename", action="store_true", default=None, dest="with_filename")
    parser.add_argument("-h", "--no-filename", action="store_true", default=None, dest="no_filename")
    parser.add_argument("--column", action="store_true", default=False)
    parser.add_argument("--no-column", action="store_true", default=False, dest="nocolumn")
    parser.add_argument("-o", action="store_true", default=False, dest="o_flag")
    parser.add_argument("--output", default=None)
    parser.add_argument("--passthru", action="store_true", default=False)

    # Context
    parser.add_argument("-A", "--after-context", type=int, default=None)
    parser.add_argument("-B", "--before-context", type=int, default=None)
    parser.add_argument("-C", "--context", type=int, default=None)

    # Display
    parser.add_argument("--color", "--colour", action="store_true", default=None, dest="color")
    parser.add_argument("--nocolor", "--nocolour", action="store_true", default=False, dest="nocolor")
    parser.add_argument("--heading", action="store_true", default=None, dest="heading")
    parser.add_argument("--noheading", action="store_true", default=False)
    parser.add_argument("--break", action="store_true", default=None, dest="do_break")
    parser.add_argument("--nobreak", action="store_true", default=False)
    parser.add_argument("--group", action="store_true", default=False)
    parser.add_argument("--nogroup", action="store_true", default=False)
    parser.add_argument("-p", "--proximate", type=int, default=None)
    parser.add_argument("-P", action="store_true", default=False, dest="no_proximate")
    parser.add_argument("--underline", action="store_true", default=False)
    parser.add_argument("--nounderline", action="store_true", default=False)
    parser.add_argument("--print0", action="store_true", default=False)
    parser.add_argument("-s", action="store_true", default=False, dest="suppress_errors")
    parser.add_argument("--flush", action="store_true", default=False)
    parser.add_argument("--pager", default=None)
    parser.add_argument("--nopager", action="store_true", default=False)

    # Color settings
    parser.add_argument("--color-filename", default=None)
    parser.add_argument("--color-match", default=None)
    parser.add_argument("--color-lineno", default=None)
    parser.add_argument("--color-colno", default=None)

    # File finding
    parser.add_argument("--sort-files", action="store_true", default=False)
    parser.add_argument("--show-types", action="store_true", default=False)
    parser.add_argument("--files-from", default=None)
    parser.add_argument("-x", action="store_true", default=False, dest="files_from_stdin")

    # File filtering
    parser.add_argument("--ignore-dir", "--ignore-directory", action="append", default=[], dest="ignore_dirs_cli")
    parser.add_argument("--noignore-dir", "--noignore-directory", action="append", default=[], dest="noignore_dirs_cli")
    parser.add_argument("--ignore-file", action="append", default=[], dest="ignore_files_cli")
    parser.add_argument("-r", "-R", "--recurse", action="store_true", default=True, dest="recurse")
    parser.add_argument("-n", "--no-recurse", action="store_true", default=False, dest="no_recurse")
    parser.add_argument("--follow", action="store_true", default=False)
    parser.add_argument("--nofollow", action="store_true", default=False)

    # File type
    parser.add_argument("-t", "--type", action="append", default=[], dest="type_include")
    parser.add_argument("-T", action="append", default=[], dest="type_exclude")
    parser.add_argument("-k", "--known-types", action="store_true", default=False)
    parser.add_argument("--type-add", action="append", default=[], dest="type_add_cli")
    parser.add_argument("--type-set", action="append", default=[], dest="type_set_cli")
    parser.add_argument("--type-del", action="append", default=[], dest="type_del_cli")

    # Miscellaneous
    parser.add_argument("--help", action="store_true", default=False, dest="show_help")
    parser.add_argument("--help-types", action="store_true", default=False)
    parser.add_argument("--version", action="store_true", default=False)
    parser.add_argument("--env", action="store_true", default=True, dest="use_env")
    parser.add_argument("--noenv", action="store_true", default=False)
    parser.add_argument("--ackrc", default=None)
    parser.add_argument("--ignore-ack-defaults", action="store_true", default=False)
    parser.add_argument("--create-ackrc", action="store_true", default=False)
    parser.add_argument("--dump", action="store_true", default=False)
    parser.add_argument("--filter", action="store_true", default=None, dest="force_filter")
    parser.add_argument("--nofilter", action="store_true", default=False)
    parser.add_argument("--man", action="store_true", default=False)
    parser.add_argument("--debug", action="store_true", default=False)
    parser.add_argument("--thpppt", action="store_true", default=False)
    parser.add_argument("--bar", action="store_true", default=False)
    parser.add_argument("--cathy", action="store_true", default=False)

    return parser


def process_args(argv: list[str] | None = None) -> dict[str, Any]:
    """Process all argument sources and return the final options dict."""
    if argv is None:
        argv = sys.argv[1:]

    # Pre-scan for easter eggs and --noenv
    env_is_usable = True
    for arg in argv:
        if arg == "--":
            break
        if re.match(r"^--th[pt]+t+$", arg):
            ack_grep.thpppt(arg)
        if arg == "--bar":
            ack_grep.ackbar()
        if arg == "--cathy":
            ack_grep.cathy()
        if arg == "--env":
            env_is_usable = True
        if arg == "--noenv":
            env_is_usable = False

    if env_is_usable and os.environ.get("ACK_OPTIONS"):
        ack_grep.warn("WARNING: ack no longer uses the ACK_OPTIONS environment variable.  Use an ackrc file instead.")

    opt: dict[str, Any] = {
        "idirs": [],
        "ifiles": None,
        "filters": [],
        "and": [],
        "or": [],
        "not": [],
    }

    # Load defaults
    ignore_defaults = "--ignore-ack-defaults" in argv
    if not ignore_defaults:
        _load_defaults(opt)

    # Load config files
    if env_is_usable:
        ackrc_arg = None
        for i, arg in enumerate(argv):
            if arg.startswith("--ackrc="):
                ackrc_arg = arg[len("--ackrc="):]
            elif arg == "--ackrc" and i + 1 < len(argv):
                ackrc_arg = argv[i + 1]

        if ackrc_arg:
            if not os.path.isfile(ackrc_arg):
                ack_grep.die(f"Unable to load ackrc '{ackrc_arg}': file not found")
            _load_config_file(ackrc_arg, opt)
        else:
            config_files = config_finder.find_config_files()
            for config in config_files:
                if os.path.isfile(config["path"]):
                    _load_config_file(
                        config["path"],
                        opt,
                        is_project=config.get("project", False),
                    )

    # Process CLI type-add/type-set/type-del
    for spec in _extract_type_args(argv, "--type-add"):
        type_name, filt = _process_filter_spec(spec)
        if type_name not in ack_grep.mappings:
            ack_grep.mappings[type_name] = []
        ack_grep.mappings[type_name].append(filt)

    for spec in _extract_type_args(argv, "--type-set"):
        type_name, filt = _process_filter_spec(spec)
        ack_grep.mappings[type_name] = [filt]

    for spec in _extract_type_args(argv, "--type-del"):
        ack_grep.mappings.pop(spec, None)

    # Parse CLI args (strip out the type args we already processed)
    clean_argv = _strip_type_args(argv)

    parser = build_parser()
    try:
        args, remaining = parser.parse_known_args(clean_argv)
    except SystemExit:
        sys.exit(2)

    # Handle help/version/special early exits
    if args.show_help:
        ack_grep.show_help()
        sys.exit(0)

    if args.version:
        ack_grep.print_line(ack_grep.get_version_statement())
        sys.exit(0)

    if args.help_types:
        ack_grep.show_help_types()
        sys.exit(0)

    if args.create_ackrc:
        print("--ignore-ack-defaults")
        for line in config_default.options():
            print(line)
        sys.exit(0)

    if args.man:
        ack_grep.show_help()
        sys.exit(0)

    # Process ignore dirs/files from CLI
    for d in args.ignore_dirs_cli:
        _process_ignore_dir(d, opt, inverted=False)
    for d in args.noignore_dirs_cli:
        _process_ignore_dir(d, opt, inverted=True)
    for f in args.ignore_files_cli:
        _process_ignore_file(f, opt)

    # Process type includes/excludes
    for t in args.type_include:
        type_name = t
        if type_name.startswith("no"):
            type_name = type_name[2:]
            if type_name in ack_grep.mappings:
                filters = ack_grep.mappings[type_name]
                opt["filters"].extend(f.invert() for f in filters)
        else:
            if type_name in ack_grep.mappings:
                opt["filters"].extend(ack_grep.mappings[type_name])
            else:
                ack_grep.die(f"Unknown type '{type_name}'")

    for t in args.type_exclude:
        type_name = t
        if type_name.startswith("no"):
            type_name = type_name[2:]
        if type_name in ack_grep.mappings:
            filters = ack_grep.mappings[type_name]
            opt["filters"].extend(f.invert() for f in filters)

    if args.known_types:
        for filters in ack_grep.mappings.values():
            opt["filters"].extend(filters)

    # Map parsed args to opt dict
    opt["1"] = args.one
    opt["m"] = args.max_count
    if args.one and opt["m"] is None:
        opt["m"] = 1
    opt["A"] = args.after_context
    opt["B"] = args.before_context
    if args.context is not None:
        opt["A"] = opt["A"] if opt["A"] is not None else args.context
        opt["B"] = opt["B"] if opt["B"] is not None else args.context
    opt["c"] = args.count
    opt["f"] = args.f
    opt["g"] = args.g
    opt["l"] = args.l
    opt["L"] = args.L
    opt["v"] = args.invert_match
    opt["i"] = args.ignore_case
    opt["S"] = args.smart_case
    opt["w"] = args.word_regexp
    opt["Q"] = args.literal
    opt["passthru"] = args.passthru
    opt["print0"] = args.print0
    opt["s"] = args.suppress_errors
    opt["debug"] = args.debug
    opt["sort_files"] = args.sort_files
    opt["show_types"] = args.show_types
    opt["follow"] = args.follow and not args.nofollow
    opt["n"] = args.no_recurse
    opt["files_from"] = args.files_from
    if args.files_from_stdin:
        opt["files_from"] = "-"

    # Output
    opt["output"] = args.output
    if args.o_flag:
        opt["output"] = r"\g<0>"

    # Regex
    opt["regex"] = args.match_pattern
    opt["range_start"] = args.range_start
    opt["range_end"] = args.range_end

    # AND/OR/NOT
    opt["and"] = args.and_patterns or []
    opt["or"] = args.or_patterns or []
    opt["not"] = args.not_patterns or []

    # Display
    opt["underline"] = args.underline and not args.nounderline
    opt["column"] = args.column and not args.nocolumn

    # Color
    if args.nocolor:
        opt["color"] = False
    elif args.color is not None:
        opt["color"] = args.color
    else:
        opt["color"] = None

    # Heading/break
    if args.nogroup:
        opt["heading"] = False
        opt["break"] = False
    elif args.group:
        opt["heading"] = True
        opt["break"] = True
    else:
        opt["heading"] = True if args.heading else None
        opt["break"] = True if args.do_break else None
        if args.noheading:
            opt["heading"] = False
        if args.nobreak:
            opt["break"] = False

    # Proximate
    opt["p"] = args.proximate
    if args.no_proximate:
        opt["p"] = 0

    # Pager
    if args.nopager:
        opt["pager"] = None
    elif args.pager:
        opt["pager"] = args.pager
    else:
        opt["pager"] = os.environ.get("ACK_PAGER_COLOR") or os.environ.get("ACK_PAGER")

    # Flush
    if args.flush:
        pass  # Python flushes differently; handled in main

    # Show filename
    opt["H"] = args.with_filename
    opt["h"] = args.no_filename
    if args.with_filename:
        opt["show_filename"] = True
    elif args.no_filename:
        opt["show_filename"] = False

    # Color settings
    if args.color_filename:
        os.environ["ACK_COLOR_FILENAME"] = args.color_filename
    if args.color_match:
        os.environ["ACK_COLOR_MATCH"] = args.color_match
    if args.color_lineno:
        os.environ["ACK_COLOR_LINENO"] = args.color_lineno
    if args.color_colno:
        os.environ["ACK_COLOR_COLNO"] = args.color_colno

    # Pattern from positional args
    if opt["regex"] is None and not opt["f"]:
        if args.pattern is not None:
            opt["regex"] = args.pattern
            opt["_start_paths"] = args.files
        else:
            opt["_start_paths"] = []
    else:
        start = []
        if args.pattern is not None:
            start.append(args.pattern)
        start.extend(args.files)
        opt["_start_paths"] = start

    # Default filter
    if not any(not f.is_inverted() for f in opt["filters"]):
        opt["filters"].append(DefaultFilter())

    return opt


def _extract_type_args(argv: list[str], prefix: str) -> list[str]:
    """Extract --type-add=X or --type-add X style args."""
    results = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg.startswith(prefix + "="):
            results.append(arg[len(prefix) + 1:])
        elif arg == prefix and i + 1 < len(argv):
            results.append(argv[i + 1])
            i += 1
        i += 1
    return results


def _strip_type_args(argv: list[str]) -> list[str]:
    """Remove --type-add/set/del args from argv."""
    result = []
    skip_next = False
    for i, arg in enumerate(argv):
        if skip_next:
            skip_next = False
            continue
        if any(
            arg.startswith(p + "=") or arg == p
            for p in ("--type-add", "--type-set", "--type-del")
        ):
            if "=" not in arg and i + 1 < len(argv):
                skip_next = True
            continue
        # Also skip --ignore-ack-defaults, --ackrc, --env, --noenv (already handled)
        if arg in ("--ignore-ack-defaults",):
            continue
        if arg.startswith("--ackrc"):
            if "=" not in arg and i + 1 < len(argv):
                skip_next = True
            continue
        result.append(arg)
    return result
