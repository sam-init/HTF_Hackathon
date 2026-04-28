"""
tests/test_orchestrator.py
---------------------------
Tests for agents/orchestrator.py deduplication and prioritisation logic.
Mocks agent LLM calls so no real API key is needed.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from agents.orchestrator import _deduplicate, _prioritise, _validate_finding, run_all_agents

# --- Unit tests for pure functions ---

def test_validate_finding_valid():
    f = {"file": "app.py", "line": 10, "issue": "Bug here", "severity": "high"}
    assert _validate_finding(f) is True


def test_validate_finding_missing_file():
    f = {"file": "", "line": 10, "issue": "Bug here"}
    assert _validate_finding(f) is False


def test_validate_finding_zero_line():
    f = {"file": "app.py", "line": 0, "issue": "Bug here"}
    assert _validate_finding(f) is False


def test_deduplicate_removes_same_file_line():
    findings = [
        {"file": "a.py", "line": 5, "issue": "Bug A", "severity": "medium"},
        {"file": "a.py", "line": 5, "issue": "Bug B", "severity": "high"},
        {"file": "a.py", "line": 6, "issue": "Bug C", "severity": "low"},
    ]
    result = _deduplicate(findings)
    # Two unique file+line combos
    assert len(result) == 2
    # For a.py:5, keep the high severity one
    line5 = next(r for r in result if r["line"] == 5)
    assert line5["severity"] == "high"


def test_prioritise_orders_by_severity():
    findings = [
        {"severity": "low"},
        {"severity": "critical"},
        {"severity": "medium"},
        {"severity": "high"},
    ]
    result = _prioritise(findings)
    severities = [r["severity"] for r in result]
    assert severities == ["critical", "high", "medium", "low"]


# --- Integration test with mocked agents ---

@pytest.mark.asyncio
async def test_run_all_agents_with_mocks():
    """All agents return mocked findings; orchestrator should aggregate them."""
    fake_findings = [
        {"file": "main.py", "line": 10, "issue": "SQL injection", "severity": "critical",
         "fix_suggestion": "Use parameterised queries", "agent": "SecurityAgent"},
        {"file": "main.py", "line": 20, "issue": "Missing docstring", "severity": "info",
         "fix_suggestion": "Add docstring", "agent": "ReadabilityDocsAgent"},
    ]

    diff_files = [{"file": "main.py", "patch": "", "added_lines": [(10, "x = db.query(q)")]}]
    meta = {"repo_full": "test/repo", "pr_number": 1, "pr_title": "Test PR", "author": "dev"}

    # Patch all agent classes to return our fake findings
    with patch("agents.orchestrator.BugAndSafetyAgent") as MockBug, \
         patch("agents.orchestrator.SecurityAgent") as MockSec, \
         patch("agents.orchestrator.PerformanceAgent") as MockPerf, \
         patch("agents.orchestrator.ReadabilityDocsAgent") as MockRead, \
         patch("agents.orchestrator.ArchitectureAgent") as MockArch, \
         patch("agents.orchestrator.AccessibilityAgent") as MockA11y:

        for MockClass in [MockBug, MockSec, MockPerf, MockRead, MockArch, MockA11y]:
            instance = MockClass.return_value
            instance.name = MockClass.__name__
            instance.run = AsyncMock(return_value=fake_findings)

        result = await run_all_agents(diff_files, meta)

    # After deduplication, file=main.py line=10 and line=20 are different → 2 unique
    assert len(result) >= 1
    # Critical findings should come first
    assert result[0]["severity"] == "critical"
