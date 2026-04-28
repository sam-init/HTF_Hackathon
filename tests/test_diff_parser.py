"""
tests/test_diff_parser.py
--------------------------
Tests for github/diff_fetcher.py parse_diff_to_files()
Run: python -m pytest tests/ -v
"""
import pytest
from github.diff_fetcher import parse_diff_to_files

SAMPLE_DIFF = """\
diff --git a/foo/bar.py b/foo/bar.py
index abc123..def456 100644
--- a/foo/bar.py
+++ b/foo/bar.py
@@ -10,6 +10,12 @@ def existing():
     pass
+def new_function(x, y):
+    # This is a new function
+    if x is None:
+        return None
+    return x + y
+
 def another():
     pass
diff --git a/utils/helper.js b/utils/helper.js
index 111111..222222 100644
--- a/utils/helper.js
+++ b/utils/helper.js
@@ -1,3 +1,7 @@
 const a = 1;
+function riskyFunc(userInput) {
+    eval(userInput);  // dangerous
+}
+
 module.exports = {};
"""


def test_parse_finds_two_files():
    result = parse_diff_to_files(SAMPLE_DIFF)
    assert len(result) == 2


def test_parse_python_file_path():
    result = parse_diff_to_files(SAMPLE_DIFF)
    files = [r["file"] for r in result]
    assert "foo/bar.py" in files


def test_parse_js_file_path():
    result = parse_diff_to_files(SAMPLE_DIFF)
    files = [r["file"] for r in result]
    assert "utils/helper.js" in files


def test_added_lines_python():
    result = parse_diff_to_files(SAMPLE_DIFF)
    py_file = next(r for r in result if r["file"] == "foo/bar.py")
    # Should have 6 added lines
    assert len(py_file["added_lines"]) == 6


def test_added_lines_js():
    result = parse_diff_to_files(SAMPLE_DIFF)
    js_file = next(r for r in result if r["file"] == "utils/helper.js")
    assert len(js_file["added_lines"]) == 4


def test_line_numbers_are_positive():
    result = parse_diff_to_files(SAMPLE_DIFF)
    for f in result:
        for line_no, _ in f["added_lines"]:
            assert line_no > 0


def test_empty_diff():
    result = parse_diff_to_files("")
    assert result == []
