"""
tests/test_parser.py
---------------------
Tests for docs/parser.py Python AST parsing.
"""
import pytest
from docs.parser import parse_python_file, parse_repo

SAMPLE_SOURCE = '''
"""Module docstring."""
import os
import sys
from pathlib import Path

class MyService:
    """A sample service class."""

    def __init__(self, name: str):
        """Init the service."""
        self.name = name

    def process(self, data: list) -> dict:
        """Process the data."""
        return {"result": data}

    def _private_method(self):
        pass

def helper(x: int, y: int) -> int:
    """Add two numbers."""
    return x + y

def undocumented():
    pass
'''


def test_module_docstring():
    result = parse_python_file(SAMPLE_SOURCE, "test.py")
    assert "Module docstring" in result["module_docstring"]


def test_imports_found():
    result = parse_python_file(SAMPLE_SOURCE, "test.py")
    assert "os" in result["imports"]
    assert "sys" in result["imports"]


def test_class_detected():
    result = parse_python_file(SAMPLE_SOURCE, "test.py")
    assert len(result["classes"]) == 1
    assert result["classes"][0]["name"] == "MyService"


def test_class_docstring():
    result = parse_python_file(SAMPLE_SOURCE, "test.py")
    assert "sample service" in result["classes"][0]["docstring"]


def test_class_methods():
    result = parse_python_file(SAMPLE_SOURCE, "test.py")
    cls = result["classes"][0]
    method_names = [m["name"] for m in cls["methods"]]
    assert "__init__" in method_names
    assert "process" in method_names
    assert "_private_method" in method_names


def test_top_level_functions():
    result = parse_python_file(SAMPLE_SOURCE, "test.py")
    fn_names = [f["name"] for f in result["functions"]]
    assert "helper" in fn_names
    assert "undocumented" in fn_names


def test_function_args():
    result = parse_python_file(SAMPLE_SOURCE, "test.py")
    helper = next(f for f in result["functions"] if f["name"] == "helper")
    assert "x" in helper["args"]
    assert "y" in helper["args"]


def test_function_return_type():
    result = parse_python_file(SAMPLE_SOURCE, "test.py")
    helper = next(f for f in result["functions"] if f["name"] == "helper")
    assert helper["returns"] == "int"


def test_syntax_error_handled():
    result = parse_python_file("def broken(:", "broken.py")
    assert "error" in result


def test_parse_repo():
    file_dict = {
        "module.py": SAMPLE_SOURCE,
        "other.txt": "not python",
    }
    result = parse_repo(file_dict)
    assert len(result) == 1
    assert result[0]["file"] == "module.py"
