"""Tests for the regex builder."""


from ack_py.regex_builder import build_all_regexes, build_regex, is_lowercase


class TestIsLowercase:
    def test_simple_lowercase(self):
        assert is_lowercase("hello")

    def test_simple_uppercase(self):
        assert not is_lowercase("Hello")

    def test_with_metacharacters(self):
        assert is_lowercase(r"hello\Bworld")
        assert is_lowercase(r"\Dfoo")

    def test_empty(self):
        assert is_lowercase("")


class TestBuildRegex:
    def test_simple_pattern(self):
        regex, scan = build_regex("foo")
        assert regex.search("foobar")
        assert not regex.search("bar")
        assert scan is not None

    def test_literal(self):
        regex, _ = build_regex("foo.bar", literal=True)
        assert regex.search("foo.bar")
        assert not regex.search("fooXbar")

    def test_ignore_case(self):
        regex, _ = build_regex("foo", ignore_case=True)
        assert regex.search("FOO")

    def test_smart_case_lowercase(self):
        regex, _ = build_regex("foo", smart_case=True)
        assert regex.search("FOO")

    def test_smart_case_uppercase(self):
        regex, _ = build_regex("Foo", smart_case=True)
        assert not regex.search("FOO")
        assert regex.search("Foo")

    def test_word_regexp_simple(self):
        regex, _ = build_regex("foo", word_regexp=True)
        assert regex.search("foo")
        assert not regex.search("foobar")
        assert regex.search("hello foo world")

    def test_invalid_regex(self):
        try:
            build_regex("[invalid")
            assert False, "Should have raised"
        except SystemExit:
            pass

    def test_dollar_no_scan(self):
        _, scan = build_regex("foo$")
        assert scan is None


class TestBuildAllRegexes:
    def test_simple(self):
        re_match, re_not, re_hilite, re_scan = build_all_regexes("foo")
        assert re_match.search("foobar")
        assert re_not is None
        assert re_hilite is not None

    def test_and_patterns(self):
        re_match, _, re_hilite, _ = build_all_regexes("foo", and_patterns=["bar"])
        assert re_match.search("foo bar")
        assert not re_match.search("foo only")

    def test_or_patterns(self):
        re_match, _, _, _ = build_all_regexes("foo", or_patterns=["bar"])
        assert re_match.search("foo")
        assert re_match.search("bar")
        assert not re_match.search("baz")

    def test_not_patterns(self):
        _, re_not, _, _ = build_all_regexes("foo", not_patterns=["bar"])
        assert re_not is not None
        assert re_not.search("bar")
        assert not re_not.search("baz")
