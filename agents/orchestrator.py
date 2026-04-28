"""
agents/orchestrator.py
-----------------------
Runs all review agents concurrently, then:
  1. Aggregates all findings
  2. Deduplicates findings at the same file+line
  3. Prioritises by severity
  4. Caps output to avoid comment spam (max 25 inline comments)
"""
import asyncio
import logging
from typing import List, Dict, Any

from agents.bug_agent import BugAndSafetyAgent
from agents.security_agent import SecurityAgent
from agents.performance_agent import PerformanceAgent
from agents.readability_agent import ReadabilityDocsAgent
from agents.architecture_agent import ArchitectureAgent
from agents.accessibility_agent import AccessibilityAgent

logger = logging.getLogger(__name__)

# All agents to run on every PR
ALL_AGENTS = [
    BugAndSafetyAgent,
    SecurityAgent,
    PerformanceAgent,
    ReadabilityDocsAgent,
    ArchitectureAgent,
    AccessibilityAgent,
]

# Severity ordering for prioritisation (lower index = higher priority)
SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}

# Max inline comments to post (to avoid spamming the PR)
MAX_INLINE_COMMENTS = 25


def _deduplicate(findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Remove duplicate findings at the same file + line.
    Keeps the finding with the highest severity when duplicates exist.
    """
    seen: Dict[tuple, Dict[str, Any]] = {}
    for f in findings:
        key = (f.get("file", ""), f.get("line", 0))
        existing = seen.get(key)
        if existing is None:
            seen[key] = f
        else:
            # Keep higher-severity finding
            if SEVERITY_ORDER.get(f.get("severity", "info"), 99) < \
               SEVERITY_ORDER.get(existing.get("severity", "info"), 99):
                seen[key] = f
    return list(seen.values())


def _prioritise(findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Sort findings by severity (critical first)."""
    return sorted(
        findings,
        key=lambda f: SEVERITY_ORDER.get(f.get("severity", "info"), 99),
    )


def _validate_finding(f: Dict[str, Any]) -> bool:
    """
    Filter out malformed findings that would cause GitHub API errors.
    Requires: file (non-empty string), line (positive int), issue (non-empty).
    """
    return (
        isinstance(f.get("file"), str) and f["file"].strip()
        and isinstance(f.get("line"), int) and f["line"] > 0
        and isinstance(f.get("issue"), str) and f["issue"].strip()
    )


async def run_all_agents(
    diff_files: List[Dict[str, Any]],
    meta: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Instantiate and run all agents concurrently.
    Returns a deduplicated, prioritised list of findings capped at MAX_INLINE_COMMENTS.
    """
    agents = [AgentClass() for AgentClass in ALL_AGENTS]

    # Run all agents in parallel using asyncio.gather
    results = await asyncio.gather(
        *[agent.run(diff_files, meta) for agent in agents],
        return_exceptions=True,
    )

    all_findings: List[Dict[str, Any]] = []
    for agent, result in zip(agents, results):
        if isinstance(result, Exception):
            logger.error(f"[Orchestrator] Agent {agent.name} raised: {result}")
            continue
        valid = [f for f in result if _validate_finding(f)]
        logger.info(f"[Orchestrator] {agent.name}: {len(valid)} valid findings")
        all_findings.extend(valid)

    # Deduplicate → prioritise → cap
    deduplicated = _deduplicate(all_findings)
    prioritised = _prioritise(deduplicated)
    capped = prioritised[:MAX_INLINE_COMMENTS]

    logger.info(
        f"[Orchestrator] Total: {len(all_findings)} raw → "
        f"{len(deduplicated)} deduped → {len(capped)} posted"
    )
    return capped
