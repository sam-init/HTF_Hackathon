from __future__ import annotations

from collections import Counter
from typing import Any


PERSONA_HINTS = {
    "Intern": "Use simple language, explain why each step matters, and include learning tips.",
    "Student": "Balance conceptual clarity with practical usage examples.",
    "Frontend Developer": "Highlight UI architecture, component structure, and API integration details.",
    "Backend Developer": "Focus on service boundaries, data flow, performance, and deployment details.",
}


def build_repo_facts(parsed_files: list[dict[str, Any]]) -> dict[str, Any]:
    langs = Counter(item["language"] for item in parsed_files)
    total_functions = sum(len(item["functions"]) for item in parsed_files)
    total_classes = sum(len(item["classes"]) for item in parsed_files)
    return {
        "languages": dict(langs),
        "file_count": len(parsed_files),
        "function_count": total_functions,
        "class_count": total_classes,
    }


def _module_role(item: dict[str, Any]) -> str:
    path = item["path"].lower()
    imports = " ".join(item.get("imports", [])).lower()
    fn_count = len(item.get("functions", []))
    cls_count = len(item.get("classes", []))

    if any(key in path for key in ("main", "app.py", "server", "index.ts", "index.js")):
        return "Likely entrypoint or application bootstrap."
    if any(key in path for key in ("route", "controller", "api")):
        return "API routing or request/response boundary."
    if any(key in path for key in ("component", ".tsx", ".jsx", "ui/")):
        return "UI/component layer."
    if "fastapi" in imports or "flask" in imports:
        return "Backend service layer."
    if cls_count > fn_count:
        return "Class-oriented domain logic."
    if fn_count > 0:
        return "Function-oriented utility/business logic."
    return "Support/configuration module."


def _module_map(parsed_files: list[dict[str, Any]], max_items: int = 10) -> str:
    ranked = sorted(parsed_files, key=lambda x: (x.get("line_count", 0), len(x.get("functions", []))), reverse=True)
    lines: list[str] = []
    for item in ranked[:max_items]:
        imports = ", ".join(item.get("imports", [])[:4]) or "none"
        lines.append(
            f"- `{item['path']}` ({item.get('line_count', 0)} lines) "
            f"-> {len(item.get('functions', []))} functions, {len(item.get('classes', []))} classes. "
            f"Role: {_module_role(item)} Imports: {imports}."
        )
    return "\n".join(lines) or "- No modules detected."


def _entrypoint_candidates(parsed_files: list[dict[str, Any]], max_items: int = 6) -> str:
    candidates = []
    for item in parsed_files:
        path = item["path"].lower()
        if any(name in path for name in ("main.py", "app.py", "server.py", "index.ts", "index.js")):
            candidates.append(item["path"])
    if not candidates:
        candidates = [item["path"] for item in parsed_files[:max_items]]
    return "\n".join(f"- `{path}`" for path in candidates[:max_items])


def _change_map(parsed_files: list[dict[str, Any]]) -> str:
    hints = []
    for item in parsed_files[:24]:
        path = item["path"].lower()
        original = item["path"]
        if any(k in path for k in ("readme", "docs", "guide")):
            hints.append(f"- Documentation updates: `{original}`")
        elif any(k in path for k in ("api", "route", "controller")):
            hints.append(f"- API behavior changes: `{original}`")
        elif any(k in path for k in ("component", ".tsx", ".jsx", "ui/")):
            hints.append(f"- UI/UX updates: `{original}`")
        elif any(k in path for k in ("agent", "service", "logic", "core")):
            hints.append(f"- Core logic changes: `{original}`")
    deduped = []
    seen = set()
    for line in hints:
        if line in seen:
            continue
        seen.add(line)
        deduped.append(line)
    return "\n".join(deduped[:12]) or "- Core changes: inspect entrypoint and largest modules."


def create_readme_template(parsed_files: list[dict[str, Any]], persona: str) -> str:
    facts = build_repo_facts(parsed_files)
    lang_block = "\n".join(f"- {k}: {v} files" for k, v in facts["languages"].items())

    return f"""# Project Documentation

## Overview
This repository contains **{facts['file_count']}** code files with **{facts['function_count']}** functions and **{facts['class_count']}** classes.

## Tech Snapshot
{lang_block or '- No supported source files detected'}

## Repository Map (Specific)
{_module_map(parsed_files)}

## Likely Entrypoints
{_entrypoint_candidates(parsed_files)}

## Setup
1. Install dependencies for each service.
2. Configure environment variables.
3. Start backend and frontend services.

## Usage
1. Run the application locally.
2. Use the dashboard to generate code reviews and documentation.
3. Export generated docs into your repository.

## API (High-Level)
- `POST /api/review/repo`
- `POST /api/review/upload`
- `POST /api/docs/repo`
- `POST /api/docs/upload`
- `POST /api/github/webhook`

## Change Guide (What To Edit)
{_change_map(parsed_files)}

## Persona Notes
{PERSONA_HINTS.get(persona, PERSONA_HINTS['Student'])}
"""


def create_onboarding_guide(parsed_files: list[dict[str, Any]], persona: str) -> str:
    first_files = "\n".join(
        f"- `{item['path']}` -> {_module_role(item)}" for item in sorted(parsed_files, key=lambda x: x.get("line_count", 0), reverse=True)[:8]
    )
    change_map = _change_map(parsed_files)
    return f"""# Onboarding Guide ({persona})

## First 30 Minutes
{first_files or '- Explore repository root files'}

## What to Learn First
- Understand entrypoints and request flow.
- Identify core modules and utility layers.
- Run the project locally and verify health endpoints.

## Where To Change What
{change_map}

## Contribution Checklist
- Add tests for behavior changes.
- Keep docs in sync with code.
- Run static checks before opening a PR.
"""
