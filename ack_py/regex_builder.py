"""Regex building utilities for ack.

Ported from the build_regex / build_all_regexes functions in lib/App/Ack.pm.
"""

from __future__ import annotations

import re


def is_lowercase(pat: str) -> bool:
    """Check if a regex pattern is all lowercase (for smart-case)."""
    if pat.lower() == pat:
        return True

    # Strip out metacharacters that might contain uppercase letters.
    cleaned = pat
    cleaned = cleaned.replace("\\\\", "")

    metachar = re.compile(
        r"\\A|\\B|\\c[a-zA-Z]|\\D|\\G|\\H|\\K|\\N(?:\{.+?\})?|"
        r"\\[pP]\{.+?\}|\\[pP][A-Z]|\\R|\\S|\\V|\\W|\\X|"
        r"\\x[0-9A-Fa-f]{2}|\\Z"
    )
    cleaned = metachar.sub("", cleaned)

    # Remove named captures.
    name_re = r"[_A-Za-z][_A-Za-z0-9]*?"
    cleaned = re.sub(rf"\(\?'{name_re}'", "", cleaned)
    cleaned = re.sub(rf"\(\?<{name_re}>", "", cleaned)
    cleaned = re.sub(rf"\\k'{name_re}'", "", cleaned)
    cleaned = re.sub(rf"\\k<{name_re}>", "", cleaned)
    cleaned = re.sub(rf"\\k\{{{name_re}\}}", "", cleaned)

    return cleaned.lower() == cleaned


def build_regex(
    pattern: str,
    ignore_case: bool = False,
    smart_case: bool = False,
    literal: bool = False,
    word_regexp: bool = False,
) -> tuple[re.Pattern[str], re.Pattern[str] | None]:
    """Build a compiled regex from a pattern string.

    Returns (match_regex, scan_regex). scan_regex may be None if the pattern
    contains '$' anchors.
    """
    regex_is_lc = is_lowercase(pattern)

    if literal:
        pattern = re.escape(pattern)
    else:
        try:
            re.compile(pattern)
        except re.error as e:
            raise SystemExit(f"ack: Invalid regex '{pattern}'\n  {e}") from None

    scan_str = pattern

    if word_regexp:
        ok = True
        if pattern.startswith(("\\w", "\\d")):
            pass  # Explicit \w or \d is fine
        elif not re.match(r"^[\w\(\[\.]", pattern):
            ok = False

        if not re.search(r"[\w\}\)\]\+\*\?\.]$", pattern):
            ok = False
        elif re.search(r"\\[\}\)\]\+\*\?\.]$", pattern):
            ok = False

        if not ok:
            raise SystemExit(
                "ack: -w will not do the right thing if your regex does not "
                "begin and end with a word character."
            )

        if re.match(r"^\w+$", pattern):
            pattern = rf"\b(?:{pattern})\b"
        else:
            pattern = rf"(?:^|\b|\s)(?:{pattern})(?=\s|\b|$)"

    if ignore_case or (smart_case and regex_is_lc):
        flags = re.IGNORECASE
    else:
        flags = re.RegexFlag(0)

    try:
        match_regex = re.compile(pattern, flags)
    except re.error as e:
        raise SystemExit(f"ack: Invalid regex '{pattern}':\n  {e}") from None

    scan_regex: re.Pattern[str] | None = None
    if "$" not in scan_str:
        try:
            scan_regex = re.compile(scan_str, flags | re.MULTILINE)
        except re.error:
            scan_regex = None

    return match_regex, scan_regex


def build_all_regexes(
    opt_regex: str,
    and_patterns: list[str] | None = None,
    or_patterns: list[str] | None = None,
    not_patterns: list[str] | None = None,
    ignore_case: bool = False,
    smart_case: bool = False,
    literal: bool = False,
    word_regexp: bool = False,
) -> tuple[re.Pattern[str], re.Pattern[str] | None, re.Pattern[str], re.Pattern[str] | None]:
    """Build all regexes needed for matching, highlighting, and scanning.

    Returns (re_match, re_not, re_hilite, re_scan).
    """
    kwargs = dict(ignore_case=ignore_case, smart_case=smart_case, literal=literal, word_regexp=word_regexp)

    re_match: re.Pattern[str]
    re_not: re.Pattern[str] | None = None
    re_hilite: re.Pattern[str]
    re_scan: re.Pattern[str] | None

    if and_patterns:
        match_parts = []
        hilite_parts = []
        for part in and_patterns:
            m, _ = build_regex(part, **kwargs)
            match_parts.append(f"(?=.*{m.pattern})")
            hilite_parts.append(m.pattern)
        m_main, scan_main = build_regex(opt_regex, **kwargs)
        match_parts.append(f".*{m_main.pattern}")
        hilite_parts.append(m_main.pattern)

        flags = m_main.flags
        combined_match = "".join(match_parts)
        re_match = re.compile(combined_match, flags)
        re_hilite = re.compile("|".join(hilite_parts), flags)
        re_scan = scan_main

    elif or_patterns:
        match_parts = []
        scan_parts = []
        for part in [opt_regex, *or_patterns]:
            m, s = build_regex(part, **kwargs)
            match_parts.append(m.pattern)
            if s is not None:
                scan_parts.append(s.pattern)
        flags = m.flags
        re_match = re.compile("|".join(match_parts), flags)
        re_hilite = re_match
        re_scan = re.compile("|".join(scan_parts), flags) if scan_parts else None

    else:
        re_match, re_scan = build_regex(opt_regex, **kwargs)
        re_hilite = re_match

    if not_patterns:
        not_parts = []
        for part in not_patterns:
            m, _ = build_regex(part, **kwargs)
            not_parts.append(m.pattern)
        re_not = re.compile("|".join(not_parts), re_match.flags)

    return re_match, re_not, re_hilite, re_scan
