"""
docs/parser.py
--------------
Parses Python source files into a structured AST-based representation:
  Module → Classes → Methods / Functions → Dependencies

Uses Python's built-in `ast` module (no external tools needed).
"""
import ast
import os
from typing import List, Dict, Any, Optional


def parse_python_file(source_code: str, file_path: str) -> Dict[str, Any]:
    """
    Parse a single Python file into a structured dict.

    Returns:
        {
          "file": "path/to/file.py",
          "module_docstring": "...",
          "imports": ["os", "sys", ...],
          "classes": [
            {
              "name": "MyClass",
              "docstring": "...",
              "bases": ["BaseClass"],
              "methods": [
                {
                  "name": "my_method",
                  "args": ["self", "x", "y"],
                  "returns": "str",
                  "docstring": "...",
                  "lineno": 42,
                  "source": "def my_method(...): ..."
                }
              ]
            }
          ],
          "functions": [
            {
              "name": "helper",
              "args": [...],
              "returns": "None",
              "docstring": "...",
              "lineno": 10,
              "source": "def helper(): ..."
            }
          ]
        }
    """
    try:
        tree = ast.parse(source_code)
    except SyntaxError as e:
        return {
            "file": file_path,
            "error": f"SyntaxError: {e}",
            "classes": [],
            "functions": [],
            "imports": [],
        }

    lines = source_code.splitlines()
    module_docstring = ast.get_docstring(tree) or ""

    # Collect top-level imports
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                imports.append(f"{module}.{alias.name}")

    # Collect top-level classes
    classes = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            classes.append(_parse_class(node, lines))

    # Collect top-level functions (not inside classes)
    functions = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append(_parse_function(node, lines))

    return {
        "file": file_path,
        "module_docstring": module_docstring,
        "imports": list(set(imports)),
        "classes": classes,
        "functions": functions,
    }


def _parse_function(node: ast.FunctionDef, lines: List[str]) -> Dict[str, Any]:
    """Extract metadata from a function/method AST node."""
    args = [arg.arg for arg in node.args.args]
    returns = ""
    if node.returns:
        try:
            returns = ast.unparse(node.returns)
        except Exception:
            returns = ""

    # Grab source lines for this function
    start = node.lineno - 1
    end = node.end_lineno if hasattr(node, "end_lineno") else start + 10
    source_snippet = "\n".join(lines[start:end])

    return {
        "name": node.name,
        "args": args,
        "returns": returns,
        "docstring": ast.get_docstring(node) or "",
        "lineno": node.lineno,
        "is_async": isinstance(node, ast.AsyncFunctionDef),
        "source": source_snippet,
    }


def _parse_class(node: ast.ClassDef, lines: List[str]) -> Dict[str, Any]:
    """Extract metadata from a class AST node including all its methods."""
    bases = []
    for base in node.bases:
        try:
            bases.append(ast.unparse(base))
        except Exception:
            pass

    methods = []
    for item in node.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            methods.append(_parse_function(item, lines))

    return {
        "name": node.name,
        "docstring": ast.get_docstring(node) or "",
        "bases": bases,
        "methods": methods,
        "lineno": node.lineno,
    }


def parse_repo(file_dict: Dict[str, str]) -> List[Dict[str, Any]]:
    """
    Parse all Python files in a repo.

    Args:
        file_dict: {relative_path: source_code}

    Returns:
        List of parsed file dicts (one per .py file)
    """
    parsed = []
    for file_path, source in file_dict.items():
        if file_path.endswith(".py"):
            parsed.append(parse_python_file(source, file_path))
    return parsed
