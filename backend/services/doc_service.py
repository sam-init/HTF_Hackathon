from __future__ import annotations

from typing import Any

from backend.services.nim_client import NIMClient
from backend.services.persona import persona_style
from backend.services.structure_service import StructureService
from backend.utils.settings import settings
from docs.graph_builder import build_dependency_graph, build_execution_flowchart, build_knowledge_graph
from docs.readme_generator import create_onboarding_guide, create_readme_template
from docs.rot_detector import detect_doc_rot
from rag.rag_pipeline import RAGPipeline


class DocumentationService:
    def __init__(self, rag: RAGPipeline) -> None:
        self.rag = rag
        self.nim = NIMClient()
        self.structure = StructureService()

    def generate(self, parsed_files: list[dict[str, Any]], persona: str) -> dict[str, Any]:
        index_stats = self.rag.index_repository(parsed_files)
        structure_context = self.structure.derive(parsed_files)

        docstrings = self._generate_docstrings(parsed_files, persona)
        readme = self._generate_readme(parsed_files, persona, structure_context)

        existing_docs = "\n\n".join(item["content"] for item in parsed_files if item["path"].endswith(".md"))
        doc_rot = detect_doc_rot(parsed_files, existing_docs)
        if doc_rot:
            readme = self._generate_readme(parsed_files, persona, structure_context, regenerate=True)

        modular_docs = self._build_modular_docs(parsed_files, persona)

        return {
            "docstrings": docstrings,
            "readme": readme,
            "modular_docs": modular_docs,
            "onboarding_guide": create_onboarding_guide(parsed_files, persona),
            "dependency_graph": build_dependency_graph(parsed_files),
            "execution_flowchart": build_execution_flowchart(parsed_files),
            "knowledge_graph": build_knowledge_graph(parsed_files),
            "doc_rot_detected": doc_rot,
            "metadata": {"rag": index_stats, "nim_enabled": self.nim.enabled, "structure": structure_context},
        }

    def _generate_docstrings(self, parsed_files: list[dict[str, Any]], persona: str) -> dict[str, str]:
        output: dict[str, str] = {}
        for item in parsed_files:
            blocks = []
            for fn in item.get("functions", [])[:25]:
                args = ", ".join(fn.get("args", [])) if fn.get("args") else "args"
                imports = ", ".join(item.get("imports", [])[:4]) or "none"
                blocks.append(
                    f"{fn['name']} (line {fn['line']}):\n"
                    f"\"\"\"{fn['name']} in `{item['path']}` (around line {fn['line']}) performs a targeted operation "
                    f"within the {item['language']} module context.\n\n"
                    f"Args:\n"
                    f"    {args}: Parameters consumed by this function.\n\n"
                    f"Context:\n"
                    f"    Imports used in this module include: {imports}.\n\n"
                    f"Returns:\n"
                    f"    Output produced by `{fn['name']}` for downstream callers.\n\"\"\""
                )
            if blocks:
                output[item["path"]] = "\n\n".join(blocks)

        if not output:
            output["project"] = "No functions detected in supported language parsers."

        return output

    def _generate_readme(
        self,
        parsed_files: list[dict[str, Any]],
        persona: str,
        structure_context: dict[str, Any],
        regenerate: bool = False,
    ) -> str:
        base = create_readme_template(parsed_files, persona)
        action = "Regenerated due to doc rot detection." if regenerate else "Generated from current repository state."

        prompt = f"""
Persona guidance: {persona_style(persona)}
Rewrite this README so it is practical and immediately useful for contributors.
Add sections for setup, architecture, API usage, and workflow.
Use specific file references from the input map; avoid generic statements.
Context note: {action}
Structure context: {structure_context}

{base}
""".strip()

        generated = self.nim.chat(
            model=settings.nim_model_qwen_docs,
            system_prompt="You are a technical writer focused on developer onboarding.",
            user_prompt=prompt,
            temperature=0.2,
        )
        return generated or base

    def _build_modular_docs(self, parsed_files: list[dict[str, Any]], persona: str) -> dict[str, str]:
        modules: dict[str, str] = {}
        for item in parsed_files:
            symbols = []
            for fn in item.get("functions", [])[:8]:
                symbols.append(f"- function `{fn['name']}` at line {fn['line']}")
            for cls in item.get("classes", [])[:6]:
                symbols.append(f"- class `{cls['name']}` at line {cls['line']}")
            symbol_block = "\n".join(symbols) or "- no parsed symbols"
            imports = ", ".join(item.get("imports", [])[:12]) or "None"
            modules[item["path"]] = (
                f"Module: {item['path']}\n"
                f"Language: {item['language']}\n"
                f"Size: {item.get('line_count', 0)} lines\n"
                f"Functions: {len(item.get('functions', []))}\n"
                f"Classes: {len(item.get('classes', []))}\n"
                f"Imports: {imports}\n"
                f"Key symbols:\n{symbol_block}\n"
                f"Persona note: {persona_style(persona)}\n"
                f"Suggested next read: start at line 1, then jump to the listed symbols."
            )
        return modules
