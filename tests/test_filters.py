"""Tests for the filter classes."""

import os
import tempfile

import ack_py.filters.extension  # noqa: F401
import ack_py.filters.firstlinematch  # noqa: F401
import ack_py.filters.is_filter  # noqa: F401
import ack_py.filters.is_path  # noqa: F401
import ack_py.filters.match  # noqa: F401
from ack_py.ack_file import AckFile
from ack_py.filters.base import Filter
from ack_py.filters.collection import CollectionFilter
from ack_py.filters.default import DefaultFilter


def _make_file(name: str) -> AckFile:
    return AckFile(name)


class TestExtensionFilter:
    def test_matches_extension(self):
        f = Filter.create_filter("ext", "py", "js")
        assert f.filter(_make_file("foo.py"))
        assert f.filter(_make_file("bar.js"))
        assert not f.filter(_make_file("baz.rb"))

    def test_case_insensitive(self):
        f = Filter.create_filter("ext", "py")
        assert f.filter(_make_file("FOO.PY"))
        assert f.filter(_make_file("bar.Py"))

    def test_to_string(self):
        f = Filter.create_filter("ext", "py", "js")
        assert f.to_string() == ".py .js"


class TestIsFilter:
    def test_matches_basename(self):
        f = Filter.create_filter("is", "Makefile")
        assert f.filter(_make_file("Makefile"))
        assert f.filter(_make_file("/some/path/Makefile"))
        assert not f.filter(_make_file("makefile"))
        assert not f.filter(_make_file("Makefile.bak"))


class TestMatchFilter:
    def test_matches_regex(self):
        f = Filter.create_filter("match", r"test_.*\.py$")
        assert f.filter(_make_file("test_foo.py"))
        assert not f.filter(_make_file("foo.py"))

    def test_strips_slashes(self):
        f = Filter.create_filter("match", r"/~$/")
        assert f.filter(_make_file("backup~"))


class TestFirstLineMatchFilter:
    def test_matches_first_line(self):
        f = Filter.create_filter("firstlinematch", r"^#!.*\bpython")
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as tmp:
            tmp.write("#!/usr/bin/env python3\nprint('hi')\n")
            tmp.flush()
            name = tmp.name

        try:
            file = AckFile(name)
            assert f.filter(file)
        finally:
            os.unlink(name)

    def test_no_match(self):
        f = Filter.create_filter("firstlinematch", r"^#!.*\bperl")
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as tmp:
            tmp.write("#!/usr/bin/env python3\nprint('hi')\n")
            tmp.flush()
            name = tmp.name

        try:
            file = AckFile(name)
            assert not f.filter(file)
        finally:
            os.unlink(name)


class TestCollectionFilter:
    def test_groups_filters(self):
        coll = CollectionFilter()
        coll.add(Filter.create_filter("ext", "py"))
        coll.add(Filter.create_filter("ext", "js"))
        coll.add(Filter.create_filter("is", "Makefile"))

        assert coll.filter(_make_file("foo.py"))
        assert coll.filter(_make_file("bar.js"))
        assert coll.filter(_make_file("Makefile"))
        assert not coll.filter(_make_file("baz.rb"))


class TestInverseFilter:
    def test_inverts(self):
        f = Filter.create_filter("ext", "py")
        inv = f.invert()
        assert not inv.filter(_make_file("foo.py"))
        assert inv.filter(_make_file("foo.rb"))
        assert inv.is_inverted()

    def test_double_invert(self):
        f = Filter.create_filter("ext", "py")
        assert f.invert().invert() is f


class TestDefaultFilter:
    def test_accepts_all(self):
        f = DefaultFilter()
        assert f.filter(_make_file("anything.txt"))
        assert f.filter(_make_file("foo.bin"))
