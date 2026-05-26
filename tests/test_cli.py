"""Integration tests for the ack CLI."""

import subprocess
import sys

import pytest


def _run_ack(*args: str, input_text: str | None = None, cwd: str | None = None) -> subprocess.CompletedProcess:
    """Run ack as a subprocess."""
    cmd = [sys.executable, "-m", "ack_py", *args]
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        input=input_text,
        cwd=cwd,
        timeout=30,
    )


@pytest.fixture
def sample_dir(tmp_path):
    """Create a sample directory with files for testing."""
    (tmp_path / "hello.py").write_text("def hello():\n    print('hello world')\n    return True\n")
    (tmp_path / "greet.py").write_text("def greet(name):\n    print(f'hello {name}')\n")
    (tmp_path / "data.txt").write_text("some data\nhello data\ngoodbye\n")
    (tmp_path / "readme.md").write_text("# Hello\n\nThis is a readme.\n")
    sub = tmp_path / "subdir"
    sub.mkdir()
    (sub / "nested.py").write_text("# nested file\nx = 'hello'\n")
    return tmp_path


class TestVersion:
    def test_version(self):
        result = _run_ack("--version")
        assert result.returncode == 0
        assert "ack" in result.stdout
        assert "Python" in result.stdout


class TestHelp:
    def test_help(self):
        result = _run_ack("--help")
        assert result.returncode == 0
        assert "PATTERN" in result.stdout

    def test_help_types(self):
        result = _run_ack("--help-types")
        assert result.returncode == 0
        assert "python" in result.stdout


class TestBasicSearch:
    def test_simple_search(self, sample_dir):
        result = _run_ack("hello", str(sample_dir), "--nocolor", "--noheading", "--nobreak")
        assert result.returncode == 0
        assert "hello" in result.stdout

    def test_no_match(self, sample_dir):
        result = _run_ack("zzzznotfound", str(sample_dir), "--nocolor")
        assert result.returncode == 1
        assert result.stdout.strip() == ""

    def test_case_insensitive(self, sample_dir):
        result = _run_ack("-i", "HELLO", str(sample_dir), "--nocolor", "--noheading", "--nobreak")
        assert result.returncode == 0
        assert "hello" in result.stdout.lower()

    def test_literal(self, sample_dir):
        (sample_dir / "special.txt").write_text("foo.bar baz\nfooXbar\n")
        result = _run_ack("-Q", "foo.bar", str(sample_dir), "--nocolor", "--noheading", "--nobreak")
        assert result.returncode == 0
        assert "foo.bar" in result.stdout
        assert "fooXbar" not in result.stdout

    def test_invert_match(self, sample_dir):
        result = _run_ack("-v", "hello", str(sample_dir / "data.txt"), "--nocolor", "--noheading")
        assert result.returncode == 0
        assert "some data" in result.stdout
        assert "goodbye" in result.stdout

    def test_word_regexp(self, sample_dir):
        (sample_dir / "words.txt").write_text("cat\ncatch\nthe cat sat\n")
        result = _run_ack("-w", "cat", str(sample_dir / "words.txt"), "--nocolor", "--noheading")
        assert result.returncode == 0
        assert "cat\n" in result.stdout or "cat" in result.stdout
        # "catch" should NOT match with -w
        lines = [line.strip() for line in result.stdout.strip().split("\n")]
        assert "catch" not in lines


class TestFileSelection:
    def test_list_files(self, sample_dir):
        result = _run_ack("-f", str(sample_dir), "--sort-files")
        assert result.returncode == 0
        assert "hello.py" in result.stdout

    def test_type_filter(self, sample_dir):
        result = _run_ack("-t", "python", "-f", str(sample_dir), "--sort-files")
        assert result.returncode == 0
        assert ".py" in result.stdout
        assert ".txt" not in result.stdout
        assert ".md" not in result.stdout


class TestCountMode:
    def test_count(self, sample_dir):
        result = _run_ack("-c", "hello", str(sample_dir), "--nocolor")
        assert result.returncode == 0
        # Should show filenames with counts
        assert ":" in result.stdout


class TestFileListing:
    def test_files_with_matches(self, sample_dir):
        result = _run_ack("-l", "hello", str(sample_dir))
        assert result.returncode == 0
        assert ".py" in result.stdout or "data.txt" in result.stdout

    def test_files_without_matches(self, sample_dir):
        result = _run_ack("-L", "hello", str(sample_dir))
        assert result.returncode == 0


class TestContext:
    def test_after_context(self, sample_dir):
        result = _run_ack("-A", "1", "hello", str(sample_dir / "hello.py"), "--nocolor", "--noheading")
        assert result.returncode == 0
        lines = result.stdout.strip().split("\n")
        assert len(lines) >= 2

    def test_before_context(self, sample_dir):
        result = _run_ack("-B", "1", "return", str(sample_dir / "hello.py"), "--nocolor", "--noheading")
        assert result.returncode == 0
        lines = result.stdout.strip().split("\n")
        assert len(lines) >= 2


class TestMaxCount:
    def test_max_count(self, sample_dir):
        result = _run_ack("-m", "1", "hello", str(sample_dir), "--nocolor", "--noheading", "--nobreak")
        assert result.returncode == 0
        # Should limit matches per file


class TestStdinSearch:
    def test_stdin_pipe(self):
        result = _run_ack("hello", input_text="hello world\ngoodbye\nhello again\n")
        assert result.returncode == 0
        assert "hello" in result.stdout
