"""ack - a code-searching tool optimized for programmers."""

from __future__ import annotations

import os
import re
import sys

VERSION = "v3.9.0"
COPYRIGHT = "Copyright 2005-2025 Andy Lester."

ORIGINAL_PROGRAM_NAME: str = ""

output_to_pipe: bool = not sys.stdout.isatty()
is_filter_mode: bool = not sys.stdin.isatty() and not sys.stdin.seekable()
is_windows: bool = sys.platform == "win32"

report_bad_filenames: bool = True
ors: str = "\n"

fh = sys.stdout

mappings: dict[str, list] = {}
type_wanted: dict[str, bool] = {}
ignore_dirs: dict[str, bool] = {}
types: dict[str, list] = {}

debug_nopens: int = 0


def warn(*args: object) -> None:
    prog = os.path.basename(sys.argv[0])
    msg = "".join(str(a) for a in args)
    print(f"{prog}: {msg}", file=sys.stderr)


def die(*args: object) -> None:
    prog = os.path.basename(sys.argv[0])
    msg = "".join(str(a) for a in args)
    print(f"{prog}: {msg}", file=sys.stderr)
    sys.exit(2)


def print_line(*args: object) -> None:
    text = "".join(str(a) for a in args)
    fh.write(text)


def say(*args: object) -> None:
    text = "".join(str(a) for a in args)
    fh.write(text + ors)


def print_blank_line() -> None:
    fh.write("\n")


def set_up_pager(command: str) -> None:
    global fh

    if output_to_pipe:
        return

    try:
        import subprocess

        pager = subprocess.Popen(command, shell=True, stdin=subprocess.PIPE, text=True)
        if pager.stdin:
            fh = pager.stdin
    except OSError as e:
        die(f'Unable to pipe to pager "{command}": {e}')


def exit_from_ack(nmatches: int) -> None:
    sys.exit(0 if nmatches else 1)


def thpppt(arg: str) -> None:
    y = "_   /|,\\'!.x',=(www)=,   U   "
    y = y.replace(",", "\n").replace("x", "O").replace("!", "o").replace("w", "_")
    say(f"{y} ack {arg}!")
    sys.exit(0)


def ackbar() -> None:
    x = r""" 6?!I'7!I"?%+!
 3~!I#7#I"7#I!?!+!="+"="+!:!
 2?#I!7!I!?#I!7!I"+"=%+"=#
 1?"+!?*+!=#~"=!+#?"="+!
 0?"+!?"I"?&+!="~!=!~"=!+%="+"
 /I!+!?)+!?!+!=$~!=!~!="+!="+"?!="?!
 .?%I"?%+%='?!=#~$="
 ,,!?%I"?(+$=$~!=#:"~$:!~!
 ,I!?!I!?"I"?!+#?"+!?!+#="~$:!~!:!~!:!,!:!,":#~!
 +I!?&+!="+!?#+$=!~":!~!:!~!:!,!:#,!:!,%:"
 *+!I!?!+$=!+!=!+!?$+#=!~":!~":#,$:",#:!,!:!
 *I!?"+!?!+!=$+!?#+#=#~":$,!:",!:!,&:"
 )I!?$=!~!=#+"?!+!=!+!=!~!="~!:!~":!,'.!,%:!~!
 (=!?"+!?!=!~$?"+!?!+!=#~"=",!="~$,$.",#.!:!=!
 (I"+"="~"=!+&=!~"=!~!,!~!+!=!?!+!?!=!I!?!+"=!.",!.!,":!
 %I$?!+!?!=%+!~!+#~!=!~#:#=!~!+!~!=#:!,%.!,!.!:"
 $I!?!=!?!I!+!?"+!=!~!=!~!?!I!?!=!+!=!~#:",!~"=!~!:"~!=!:",&:" '-/
 $?!+!I!?"+"=!+"~!,!:"+#~#:#,"=!~"=!,!~!,!.",!:".!:! */! !I!t!'!s! !a! !g!r!e!p!!! !/!
 $+"=!+!?!+"~!=!:!~!:"I!+!,!~!=!:!~!,!:!,$:!~".&:"~!,# (-/
 %~!=!~!=!:!.!+"~!:!,!.!,!~!=!:$.!,":!,!.!:!~!,!:!=!.#="~!,!:" ./!
 %=!~!?!+"?"+!=!~",!.!:!?!~!.!:!,!:!,#.!,!:","~!:!=!~!=!:",!~! ./!
 %+"~":!~!=#~!:!~!,!.!~!:",!~!=!~!.!:!,!.",!:!,":!=":!.!,!:!7! -/!
 %~",!:".#:!=!:!,!:"+!:!~!:!.!,!~!,!.#,!.!,$:"~!,":"~!=! */!
 &=!~!=#+!=!~",!.!:",#:#,!.",+:!,!.",!=!+!?!
 &~!=!~!=!~!:"~#:",!.!,#~!:!.!+!,!.",$.",$.#,!+!I!?!
 &~!="~!:!~":!~",!~!=!~":!,!:!~!,!:!,&.$,#."+!?!I!?!I!
 &~!=!~!=!+!,!:!~!:!=!,!:!~&:$,!.!,".!,".!,#."~!+!?$I!
 &~!=!~!="~!=!:!~":!,!~%:#,!:",!.!,#.",#I!7"I!?!+!?"I"
 &+!I!7!:#~"=!~!:!,!:"~$.!=!.!,!~!,$.#,!~!7!I#?!+!?"I"7!
 %7#?!+!~!:!=!~!=!~":!,!:"~":#.!,)7#I"?"I!7&
 %7#I!=":!=!~!:"~$:"~!:#,!:!,!:!~!:#,!7#I!?#7)
 $7$+!,!~!=#~!:!~!:!~$:#,!.!~!:!=!,":!7#I"?#7+=!?!
 $7#I!~!,!~#=!~!:"~!:!,!:!,#:!=!~",":!7$I!?#I!7*+!=!+"
 "I!7$I!,":!,!.!=":$,!:!,$:$7$I!+!?"I!7+?"I!7!I!7!,!
 !,!7%I!:",!."~":!,&.!,!:!~!I!7$I!+!?"I!7,?!I!7',!
 !7(,!.#~":!,%.!,!7%I!7!?#I"7,+!?!7*
7+:!,!~#,"=!7'I!?#I"7/+!7+
77I!+!7!?!7!I"71+!7,"""
    _pic_decode(x)


def cathy() -> None:
    x = r""" 0+!--+!
 0|! "C!H!O!C!O!L!A!T!E!!! !|!
 0|! "C!H!O!C!O!L!A!T!E!!! !|!
 0|! "C!H!O!C!O!L!A!T!E!!! !|!
 0|! $A"C!K!!! $|!
 0+!--+!
 6\! 1:!,!.! !
 7\! /.!M!~!Z!M!~!
 8\! /~!D! "M! !
 4.! $\! /M!~!.!8! +.!M# 4
 0,!.! (\! .~!M!N! ,+!I!.!M!.! 3
 /?!O!.!M!:! '\! .O!.! +~!Z!=!N!.! 4
 ..! !D!Z!.!Z!.! '\! 9=!M".! 6
 /.! !.!~!M".! '\! 8~! 9
 4M!.! /.!7!N!M!.! F
 4.! &:!M! !N"M# !M"N!M! #D!M&=! =
 :M!7!M#:! !~!M!7!,!$!M!:! #.! !O!N!.!M!:!M# ;
 8Z!M"~!N!$!D!.!N!?! !I!N!.! (?!M! !M!,!D!M".! 9
 (?!Z!M!N!:! )=!M!O!8!.!M!+!M! !M!,! !O!M! +,!M!.!M!~!Z!N!M!:! &:!~! 0
 &8!7!.!~!M"D!M!,! &M!?!=!8! !M!,!O! !M!+! !+!O!.!M! $M#~! !.!8!M!Z!.!M! !O!M"Z! %:!~!M!Z!M!Z!.! +
 &:!M!7!,! *M!.!Z!M! !8"M!.!M!~! !.!M!.!=! #~!8!.!M! !7!M! "N!Z#I! !D!M!,!M!.! $."M!,! !M!.! *
 2$!O! "N! !.!M!I! !7" "M! "+!O! !~!M! !d!O!.!7!I!M!.! !.!O!=!M!.! !M",!M!.! %.!$!O!D! +
 1~!O! "M!+! !8!$! "M! "?!O! %Z!8!D!M!?!8!I!O!7!M! #M!.!M! "M",!M! 4
 07!~! ".!8! !.!M! "I!+! !.!M! &Z!D!.!7!=!M! !:!.!M! #:!8"+! !.!+!8! !8! 3
 /~!M! #N! !~!M!$! !.!M! !.!M" &~!M! "~!M!O! "D! $M! !8! "M!,!M!+!D!.! 1
 #.! #?!M!N!.! #~!O! $M!.!7!$! "?" !?!~!M! '7!8!?!M!.!+!M"O! $?"$!D! !.!O! !$!7!I!.! 0
 $,!M!:!O!?! ".! !?!=! $=!:!O! !M! "M! !M! !+!$! (.! +.!M! !M!.! !8! !+"Z!~! $:!M!$! !.! '
 #.!8!.!I!$! $7!I! %M" !=!M! !~!M!D! "7!I! .I!O! %?!=!,!D! !,!M! !D!~!8!~! %D!M! (
 #.!M"?! $=!O! %=!N! "8!.! !Z!M! #M!~! (M!:! #.!M" &O! !M!.! !?!,! !8!.!N!~! $8!N!M!,!.! %
 *$!O! &M!,! "O! !.!M!.! #M! (~!M( &O!.! !7! "M! !.!M!.!M!,! #.!M! !M! &
 )=!8!.! $.!M!O!.! "$!.!I!N! !I!M# (7!M(I! %D"Z!M! "=!I! "M! !M!:! #~!D! '
 )D! &8!N!:! ".!O! !M!="M! "M! (7!M) %." !M!D!."M!.! !$!=! !M!,! +
 (M! &+!.!M! #Z!7!O!M!.!~!8! +,!M#D!?!M#D! #.!Z!M#,!Z!?! !~!N! "N!.! !M! +
 'D!:! %$!D! !?! #M!Z! !8!.! !M"?!7!?!7! '+!I!D! !?!O!:!M!:! ":!M!:! !M!7".!M! "8!+! !:!D! !.!M! *
 %.!O!:! $.!O!+! !D!.! #M! "M!.!+!N!I!Z! "7!M!N!M!N!?!I!7!Z!=!M'D"~! #M!.!8!$! !:! !.!M! "N!?! !,!O! )
 !.!?!M!:!M!I! %8!,! "M!.! #M! "N! !M!.! !M!.! !+!~! !.!M!.! ':!M! $M! $M!Z!$! !M!.! "D! "M! "?!M! (
 !7!8! !+!I! ".! "$!=! ":!$! "+! !M!.! !O! !M!I!M".! !=!~! ",!O! '=!M! $$!,! #N!:! ":!8!.! !D!~! !,!M!.! !:!M!.! &
 !:!,!.! &Z" #D! !.!8!."M!.! !8!?!Z!M!.!M! #Z!~! !?!M!Z!.! %~!O!.!8!$!N!8!O!I!:!~! !+! #M!.! !.!M!.! !+!M! ".!~!M!+! $
 !.! 'D!I! #?!M!.!M!,! !.!Z! !.!8! #M&O!I!?! (~!I!M"." !M!Z!.! !M!N!.! "+!$!.! "M!.! !M!?!.! "8!M! $
 (O!8! $M! !M!.! ".!:! !+!=! #M! #.!M! !+" *$!M":!.! !M!~! "M!7! #M! #7!Z! "M"$!M!.! !.! #
 '$!Z! #.!7!+!M! $.!,! !+!:! #N! #.!M!.!+!M! +D!M! #=!N! ":!O! #=!M! #Z!D! $M!I! %
 $,! ".! $.!M" %$!.! !?!~! "+!7!." !.!M!,! !M! *,!N!M!.$M!?! "D!,! #M!.! #N! +
 ,M!Z! &M! "I!,! "M! %I!M! !?!=!.! (Z!8!M! $:!M!.! !,!M! $D! #.!M!.! )
 +8!O! &.!8! "I!,! !~!M! &N!M! !M!D! '?!N!O!." $?!7! "?!~! #M!.! #I!D!.! (
 3M!,! "N!.! !D" &.!+!M!.! !M":!.":!M!7!M!D! 'M!.! "M!.! "M!,! $I! )
 3I! #M! "M!,! !:! &.!M" ".!,! !.!$!M!I! #.! !:! !.!M!?! "N!+! ".! /
 1M!,! #.!M!8!M!=!.! +~!N"O!Z"~! *+!M!.! "M! 2
 0.!M! &M!.! 8:! %.!M!Z! "M!=! *O!,! %
 0?!$! &N! )." .,! %."M! ":!M!.! 0
 0N!:! %?!O! #.! ..! &,! &.!D!,! "N!I! 0"""
    _pic_decode(x)


def _pic_decode(compressed: str) -> None:
    result = []
    i = 0
    while i < len(compressed):
        if i + 1 < len(compressed):
            ch = compressed[i]
            count = ord(compressed[i + 1]) - 32
            result.append(ch * count)
            i += 2
        else:
            result.append(compressed[i])
            i += 1
    say("".join(result))
    sys.exit(0)


def show_types(file: object) -> None:
    from ack_grep.file import AckFile

    assert isinstance(file, AckFile)
    types_list = filetypes(file)
    arrow = " => " if types_list else " =>"
    say(file.name + arrow + ",".join(types_list))


def filetypes(file: object) -> list[str]:
    from ack_grep.file import AckFile

    assert isinstance(file, AckFile)
    matches = []
    for k, filters in mappings.items():
        for f in filters:
            clone = file.clone()
            if f.filter(clone):
                matches.append(k)
                break

    return sorted(matches)


def is_lowercase(pat: str) -> bool:
    if pat.lower() == pat:
        return True

    cleaned = pat.replace("\\\\", "")

    metachar = re.compile(
        r"\\A|\\B|\\c[a-zA-Z]|\\D|\\G|\\H|\\K|\\N(?:\{.+?\})?|"
        r"\\[pP]\{.+?\}|\\[pP][A-Z]|\\R|\\S|\\V|\\W|\\X|"
        r"\\x[0-9A-Fa-f]{2}|\\Z"
    )
    cleaned = metachar.sub("", cleaned)

    name = r"[_A-Za-z][_A-Za-z0-9]*?"
    cleaned = re.sub(rf"\(\?P<{name}>", "", cleaned)
    cleaned = re.sub(rf"\(\?P={name}\)", "", cleaned)

    return cleaned.lower() == cleaned


def build_regex(pattern: str, opt: dict) -> tuple[re.Pattern | None, re.Pattern | None]:
    regex_is_lc = is_lowercase(pattern)

    if opt.get("Q"):
        pattern = re.escape(pattern)
    else:
        try:
            re.compile(pattern)
        except re.error as e:
            die(f"Invalid regex '{pattern}'\n  {e}")

    scan_str = pattern

    if opt.get("w"):
        ok = True
        if re.match(r"^\\[wd]", pattern):
            pass
        elif not re.match(r"^[\w\(\[\.]", pattern):
            ok = False

        if not re.search(r"[\w\}\)\]\+\*\?\.]$", pattern):
            ok = False
        elif re.search(r"\\[\}\)\]\+\*\?\.]$", pattern):
            ok = False

        if not ok:
            die("-w will not do the right thing if your regex does not begin and end with a word character.")

        if re.match(r"^\w+$", pattern):
            pattern = rf"\b(?:{pattern})\b"
        else:
            pattern = rf"(?:^|\b|\s)(?:{pattern})(?=\s|\b|$)"

    flags = 0
    if opt.get("i") or (opt.get("S") and regex_is_lc):
        flags = re.IGNORECASE

    try:
        regex = re.compile(pattern, flags)
    except re.error as e:
        die(f"Invalid regex '{pattern}':\n  {e}")

    scan_regex = None
    if "$" not in scan_str:
        try:
            scan_regex = re.compile(scan_str, flags | re.MULTILINE)
        except re.error:
            scan_regex = None

    return (regex, scan_regex)


def build_all_regexes(
    opt_regex: str, opt: dict
) -> tuple[re.Pattern | None, re.Pattern | None, re.Pattern | None, re.Pattern | None]:
    re_match = None
    re_not = None
    re_hilite = None
    re_scan = None

    and_parts = opt.get("and", [])
    or_parts = opt.get("or", [])
    not_parts = opt.get("not", [])

    flags = 0
    if opt.get("i") or (opt.get("S") and is_lowercase(opt_regex)):
        flags = re.IGNORECASE

    if and_parts:
        match_parts = []
        hilite_parts = []
        for part in and_parts:
            match, _ = build_regex(part, opt)
            if match:
                match_parts.append(f"(?=.*{match.pattern})")
                hilite_parts.append(match.pattern)

        match, scan = build_regex(opt_regex, opt)
        if match:
            match_parts.append(f".*{match.pattern}")
            hilite_parts.append(match.pattern)

        combined = "".join(match_parts)
        re_match = re.compile(combined, flags)
        re_hilite = re.compile("|".join(hilite_parts), flags)
        re_scan = scan
    elif or_parts:
        match_parts = []
        scan_parts = []
        for part in [opt_regex] + or_parts:
            match, scan = build_regex(part, opt)
            if match:
                match_parts.append(match.pattern)
            if scan:
                scan_parts.append(scan.pattern)

        re_match = re.compile("|".join(match_parts), flags)
        re_hilite = re_match
        if scan_parts:
            re_scan = re.compile("|".join(scan_parts), flags | re.MULTILINE)
    else:
        re_match, re_scan = build_regex(opt_regex, opt)
        re_hilite = re_match

    if not_parts:
        not_compiled = []
        for part in not_parts:
            compiled, _ = build_regex(part, opt)
            if compiled:
                not_compiled.append(compiled.pattern)
        if not_compiled:
            re_not = re.compile("|".join(not_compiled), flags)

    return (re_match, re_not, re_hilite, re_scan)


def get_version_statement() -> str:
    return (
        f"ack {VERSION} (Python port)\n"
        f"Running under Python {sys.version}\n\n"
        f"{COPYRIGHT}\n\n"
        "This program is free software.  You may modify or distribute it\n"
        "under the terms of the Artistic License v2.0.\n"
    )


def show_help() -> None:
    print_line(
        f"""Usage: ack [OPTION]... PATTERN [FILES OR DIRECTORIES]

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
                                Ignored if -i or -I are specified.
  -I, --no-ignore-case          Turns on case-sensitivity in PATTERN.
                                Negates -i and --smart-case.
  -v, --invert-match            Invert match: select non-matching lines
  -w, --word-regexp             Force PATTERN to match only whole words
  -Q, --literal                 Quote all metacharacters; PATTERN is literal
  --range-start PATTERN         Specify PATTERN as the start of a match range.
  --range-end PATTERN           Specify PATTERN as the end of a match range.
  --match PATTERN               Specify PATTERN explicitly. Typically omitted.
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
                                output is redirected, or on Windows)
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
  --help-types                  Display all known types, and how they're defined.
  --thpppt                      Bill the Cat
  --bar                         The warning admiral
  --cathy                       Chocolate! Chocolate! Chocolate!

Filter specifications:
    If FILTER is "ext", ARGS is a list of extensions checked against the
        file's extension.
    If FILTER is "is", ARGS is matched against the file's name exactly.
    If FILTER is "match", ARGS is matched as a case-insensitive regex
        against the filename.
    If FILTER is "firstlinematch", ARGS is matched as a regex the first
        line of the file's contents.

Exit status is 0 if match, 1 if no match.

ack's home page is at https://beyondgrep.com/

The full ack manual is available by running "ack --man".

This is version {VERSION} of ack (Python port).
"""
    )


def show_help_types() -> None:
    say("Usage: ack [OPTION]... PATTERN [FILES OR DIRECTORIES]")
    say("")
    say("The following is the list of filetypes supported by ack.  You can specify a")
    say("filetype to include with -t TYPE or --type=TYPE.  You can exclude a")
    say("filetype with -T TYPE or --type=noTYPE.")
    say("")

    types_list = sorted(mappings.keys())
    maxlen = max((len(t) for t in types_list), default=0)
    for type_name in types_list:
        if type_name.startswith("-"):
            continue
        ext_list = mappings[type_name]
        ext_str = "; ".join(str(f) for f in ext_list)
        say(f"    {type_name:<{maxlen}} {ext_str}")
