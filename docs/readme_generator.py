"""
docs/readme_generator.py
------------------------
Generates a comprehensive README.md for a repository using:
  - Parsed AST data (modules, classes, functions)
  - NIM LLM for natural language sections
  - RAG pipeline for context-aware summaries
  - Mermaid diagrams from graph_builder

Persona modes control the tone and detail level:
  - intern:    simple language, lots of explanation, step-by-step
  - student:   educational tone, explains patterns and why
  - frontend:  focuses on UI components, props, events
  - backend:   focuses on API endpoints, data flow, services
"""
import logging
from typing import List, Dict, Any, Literal
from openai import AsyncOpenAI
from docs.graph_builder import generate_mermaid_flowchart
from config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

PersonaMode = Literal["intern", "student", "frontend", "backend"]

PERSONA_INSTRUCTIONS = {
    "intern": (
        "Write for a junior developer who just joined the team. "
        "Use simple language. Explain all acronyms. "
        "Include step-by-step setup instructions with exact commands. "
        "Add 'What this does' explanations for each module."
    ),
    "student": (
        "Write for a CS student learning from this codebase. "
        "Explain design patterns used and why they were chosen. "
        "Include a 'Learning Points' section. Be educational."
    ),
    "frontend": (
        "Focus on UI components, props, state management, and event flow. "
        "Skip backend/infrastructure details. "
        "Include component hierarchy and data flow diagrams."
    ),
    "backend": (
        "Focus on API endpoints, request/response shapes, database schema, "
        "service layer design, and system architecture. "
        "Include API reference table with all endpoints."
    ),
}


def _build_api_reference(parsed_files: List[Dict[str, Any]]) -> str:
    """Build a markdown API reference table from parsed classes and functions."""
    lines = ["## 📚 API Reference\n"]

    for pf in parsed_files:
        if not (pf.get("classes") or pf.get("functions")):
            continue
        lines.append(f"### `{pf['file']}`\n")

        for cls in pf.get("classes", []):
            lines.append(f"#### Class: `{cls['name']}`")
            if cls["docstring"]:
                lines.append(f"> {cls['docstring'].splitlines()[0]}\n")
            if cls["bases"]:
                lines.append(f"**Inherits:** {', '.join(cls['bases'])}\n")

            public_methods = [m for m in cls["methods"] if not m["name"].startswith("_")]
            if public_methods:
                lines.append("| Method | Args | Returns | Description |")
                lines.append("|--------|------|---------|-------------|")
                for m in public_methods:
                    args = ", ".join(m["args"])
                    desc = m["docstring"].splitlines()[0] if m["docstring"] else "*undocumented*"
                    lines.append(f"| `{m['name']}` | `{args}` | `{m['returns'] or 'None'}` | {desc} |")
            lines.append("")

        for fn in pf.get("functions", []):
            if fn["name"].startswith("_"):
                continue
            args = ", ".join(fn["args"])
            desc = fn["docstring"].splitlines()[0] if fn["docstring"] else "*undocumented*"
            lines.append(f"#### `{fn['name']}({args})` → `{fn['returns'] or 'None'}`")
            lines.append(f"> {desc}\n")

    return "\n".join(lines)


def _detect_doc_rot(parsed_files: List[Dict[str, Any]]) -> str:
    """
    Doc rot detection: find functions/classes with missing or trivial docstrings.
    Returns a markdown warning section.
    """
    issues = []
    for pf in parsed_files:
        for fn in pf.get("functions", []):
            if not fn["docstring"] or len(fn["docstring"]) < 10:
                issues.append(f"- `{pf['file']}` → `{fn['name']}()` — missing docstring")
        for cls in pf.get("classes", []):
            if not cls["docstring"]:
                issues.append(f"- `{pf['file']}` → class `{cls['name']}` — missing docstring")
            for m in cls["methods"]:
                if not m["name"].startswith("_") and not m["docstring"]:
                    issues.append(f"- `{pf['file']}` → `{cls['name']}.{m['name']}()` — missing docstring")

    if not issues:
        return ""

    lines = ["\n## ⚠️ Doc Rot Detected\n"]
    lines.append(f"The following {len(issues)} public symbols are missing documentation:\n")
    lines.extend(issues[:20])  # Cap at 20 items
    if len(issues) > 20:
        lines.append(f"\n*...and {len(issues) - 20} more*")
    return "\n".join(lines)


async def generate_readme(
    parsed_files: List[Dict[str, Any]],
    repo_name: str,
    persona: PersonaMode = "backend",
    extra_context: str = "",
) -> str:
    """
    Generate a full README.md string.

    Args:
        parsed_files: output of docs.parser.parse_repo()
        repo_name: e.g., "owner/repo-name"
        persona: controls tone and focus
        extra_context: any additional context (e.g., from RAG retrieval)

    Returns:
        Complete README.md content as a string
    """
    client = AsyncOpenAI(
        base_url=settings.nvidia_base_url,
        api_key=settings.nvidia_api_key,
    )

    persona_instr = PERSONA_INSTRUCTIONS.get(persona, PERSONA_INSTRUCTIONS["backend"])

    # Build a summary of the repo structure for the LLM
    structure_summary = []
    for pf in parsed_files[:15]:  # limit to avoid token overflow
        classes_str = ", ".join(cls["name"] for cls in pf.get("classes", []))
        funcs_str = ", ".join(fn["name"] for fn in pf.get("functions", []))
        line = f"- `{pf['file']}`: classes=[{classes_str}], functions=[{funcs_str}]"
        if pf.get("module_docstring"):
            line += f"\n  Module doc: {pf['module_docstring'][:100]}"
        structure_summary.append(line)

    structure_text = "\n".join(structure_summary)

    llm_prompt = f"""You are generating a professional README.md for the GitHub repository: {repo_name}

Persona mode: {persona}
Instructions: {persona_instr}

Repository structure:
{structure_text}

{f"Additional context: {extra_context}" if extra_context else ""}

Generate ONLY the following sections (in order):
1. # {repo_name.split("/")[-1]} (H1 title with one-line description)
2. ## Overview (2-3 paragraphs explaining what the project does and why)
3. ## Features (bullet list of 5-8 key features)
4. ## Tech Stack (technologies used)
5. ## Getting Started (prerequisites, installation steps, environment setup)
6. ## Usage (code examples, common use cases)
7. ## Configuration (environment variables table: Variable | Description | Default)
8. ## Contributing (how to contribute, PR process)

Write in clean markdown. Be specific to the actual codebase shown, not generic."""

    try:
        resp = await client.chat.completions.create(
            model=settings.nim_docs_model,
            messages=[{"role": "user", "content": llm_prompt}],
            temperature=0.4,
            max_tokens=3000,
        )
        llm_sections = resp.choices[0].message.content or ""
    except Exception as e:
        logger.error(f"[ReadmeGen] LLM call failed: {e}")
        llm_sections = f"# {repo_name}\n\n*Documentation generation failed: {e}*"

    # Append auto-generated sections
    mermaid_chart = generate_mermaid_flowchart(parsed_files)
    api_ref = _build_api_reference(parsed_files)
    doc_rot = _detect_doc_rot(parsed_files)

    readme = f"""{llm_sections}

---

## 🗺️ Module Structure

{mermaid_chart}

---

{api_ref}
{doc_rot}

---

*📖 Documentation auto-generated by [DevIQ](https://github.com/deviq) · NVIDIA NIM · Persona: `{persona}`*
"""
    return readme
