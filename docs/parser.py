from __future__ import annotations

import ast
import logging
import re
from pathlib import Path
from typing import Any

from docs.repo_loader import read_text_safe

logger = logging.getLogger(__name__)

IMPORT_PATTERNS = {
    ".py": re.compile(r"^(?:from\s+([\w\.]+)\s+import|import\s+([\w\.]+))", re.MULTILINE),
    ".js": re.compile(r"(?:import\s+.*?from\s+['\"]([^'\"]+)['\"]|require\(['\"]([^'\"]+)['\"])"),
    ".ts": re.compile(r"(?:import\s+.*?from\s+['\"]([^'\"]+)['\"]|require\(['\"]([^'\"]+)['\"])"),
    ".tsx": re.compile(r"(?:import\s+.*?from\s+['\"]([^'\"]+)['\"]|require\(['\"]([^'\"]+)['\"])"),
    ".jsx": re.compile(r"(?:import\s+.*?from\s+['\"]([^'\"]+)['\"]|require\(['\"]([^'\"]+)['\"])"),
}


def _parse_python_symbols(code: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    functions: list[dict[str, Any]] = []
    classes: list[dict[str, Any]] = []
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return functions, classes
    except Exception:
        return functions, classes

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            functions.append(
                {
                    "name": node.name,
                    "line": node.lineno,
                    "end_line": getattr(node, "end_lineno", node.lineno),
                    "args": [arg.arg for arg in node.args.args],
                }
            )
        elif isinstance(node, ast.AsyncFunctionDef):
            functions.append(
                {
                    "name": node.name,
                    "line": node.lineno,
                    "end_line": getattr(node, "end_lineno", node.lineno),
                    "args": [arg.arg for arg in node.args.args],
                }
            )
        elif isinstance(node, ast.ClassDef):
            classes.append(
                {
                    "name": node.name,
                    "line": node.lineno,
                    "end_line": getattr(node, "end_lineno", node.lineno),
                    "methods": [n.name for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))],
                }
            )
    return functions, classes


def _parse_generic_symbols(code: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    fn_pattern = re.compile(r"(?:function\s+(\w+)\s*\(|const\s+(\w+)\s*=\s*\(|def\s+(\w+)\s*\()")
    cls_pattern = re.compile(r"(?:class\s+(\w+))")

    functions: list[dict[str, Any]] = []
    classes: list[dict[str, Any]] = []
    for i, line in enumerate(code.splitlines(), start=1):
        f_match = fn_pattern.search(line)
        if f_match:
            name = next((g for g in f_match.groups() if g), "anonymous")
            functions.append({"name": name, "line": i, "end_line": i, "args": []})
        c_match = cls_pattern.search(line)
        if c_match:
            classes.append({"name": c_match.group(1), "line": i, "end_line": i, "methods": []})
    return functions, classes


def parse_file(path: Path, root: Path) -> dict[str, Any] | None:
    try:
        code = read_text_safe(path)
    except FileNotFoundError:
        logger.debug("File not found (skipped): %s", path)
        return None
    except OSError as exc:
        logger.debug("OS error reading %s (skipped): %s", path, exc)
        return None
    except Exception as exc:
        logger.warning("Unexpected error reading %s (skipped): %s", path, exc)
        return None

    if not code.strip():
        return None

    ext = path.suffix.lower()
    try:
        if ext == ".py":
            functions, classes = _parse_python_symbols(code)
        else:
            functions, classes = _parse_generic_symbols(code)
    except Exception as exc:
        logger.warning("Symbol parse failed for %s: %s", path, exc)
        functions, classes = [], []

    pattern = IMPORT_PATTERNS.get(ext)
    imports: list[str] = []
    if pattern:
        try:
            for match in pattern.findall(code):
                if isinstance(match, tuple):
                    imports.extend([x for x in match if x])
                elif match:
                    imports.append(match)
        except Exception:
            pass

    try:
        rel_path = str(path.relative_to(root))
    except ValueError:
        rel_path = str(path)

    return {
        "path": rel_path,
        "language": ext.lstrip("."),
        "imports": sorted(set(imports)),
        "functions": functions,
        "classes": classes,
        "line_count": len(code.splitlines()),
        "content": code,
    }


def parse_repository(files: list[Path], root: Path) -> list[dict[str, Any]]:
    parsed: list[dict[str, Any]] = []
    for path in files:
        try:
            item = parse_file(path, root)
            if item is not None:
                parsed.append(item)
        except Exception as exc:
            logger.warning("parse_file raised unexpectedly for %s: %s", path, exc)
    return parsed
