"""Tests for output utilities."""

from ack_py.output import colored, get_color


class TestColored:
    def test_bold_green(self):
        result = colored("hello", "bold green")
        assert "\033[" in result
        assert "hello" in result

    def test_empty_spec(self):
        assert colored("hello", "") == "hello"

    def test_single_color(self):
        result = colored("x", "red")
        assert "\033[31m" in result

    def test_background(self):
        result = colored("x", "on_yellow")
        assert "\033[43m" in result


class TestGetColor:
    def test_default_colors(self):
        assert get_color("ACK_COLOR_MATCH") == "black on_yellow"
        assert get_color("ACK_COLOR_FILENAME") == "bold green"
        assert get_color("ACK_COLOR_LINENO") == "bold yellow"
