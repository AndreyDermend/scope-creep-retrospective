"""Tests for the code-extraction utility."""

from scope_creep.utils.code_extract import extract_python_code, strip_code_fences


class TestExtractPythonCode:
    def test_python_fence(self):
        text = "Here you go:\n```python\nimport pandas as pd\nprint('hi')\n```"
        assert extract_python_code(text) == "import pandas as pd\nprint('hi')"

    def test_generic_fence(self):
        text = "Here:\n```\nx = 1\n```"
        assert extract_python_code(text) == "x = 1"

    def test_no_fence(self):
        text = "import os\nprint(os.getcwd())"
        assert extract_python_code(text) == "import os\nprint(os.getcwd())"

    def test_prefers_python_fence_over_generic(self):
        text = "Explanation\n```\nthis is prose\n```\n```python\nx = 1\n```"
        # Our implementation matches python fences first
        assert "x = 1" in extract_python_code(text)

    def test_multiple_python_fences_concatenated(self):
        text = "```python\na = 1\n```\n```python\nb = 2\n```"
        result = extract_python_code(text)
        assert "a = 1" in result
        assert "b = 2" in result

    def test_case_insensitive_python_tag(self):
        text = "```Python\nx = 1\n```"
        assert extract_python_code(text) == "x = 1"

    def test_whitespace_tolerance(self):
        text = "```python  \n  \n  x = 1  \n  \n```"
        assert "x = 1" in extract_python_code(text)


class TestStripCodeFences:
    def test_removes_fenced_block(self):
        text = "Before\n```python\nx = 1\n```\nAfter"
        result = strip_code_fences(text)
        assert "Before" in result
        assert "After" in result
        assert "x = 1" not in result

    def test_no_fences(self):
        text = "Just some prose here."
        assert strip_code_fences(text) == text

    def test_only_fences(self):
        text = "```\nx = 1\n```"
        assert strip_code_fences(text) == ""
