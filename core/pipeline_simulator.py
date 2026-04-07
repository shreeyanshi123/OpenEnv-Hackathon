"""
Pipeline Simulator — validates agent-applied fixes against scenarios.

Given a scenario and the agent's submitted fix, simulates re-running the
pipeline and determines whether the fix resolves the original issue.
"""

from __future__ import annotations

import re
from typing import Dict, Tuple

from scenarios.registry import Scenario, _keyword_match_score
import core.constants as constants


class PipelineSimulator:
    """
    Simulates CI/CD pipeline execution with the agent's applied fix.

    IMPORTANT HACKATHON NOTE:
    This simulator does NOT run any actual Docker or shell commands, ensuring
    total safety, speed, and platform-independence. It evaluates fixes purely via
    rule-based string matching and structural overlap against expected patterns.
    """

    def __init__(self, scenario: Scenario):
        self.scenario = scenario
        self._fix_applied: str = ""
        self._secondary_fixes: Dict[str, str] = {}  # file -> fix content

    def apply_fix(self, target_file: str, fix_content: str) -> str:
        """
        Apply a fix from the agent.

        Returns feedback on the fix quality (but doesn't reveal the answer).
        """
        self._fix_applied = fix_content

        if not fix_content.strip():
            return "Empty fix submitted — no changes applied."

        # Check if the fix targets the right file
        expected_file = self.scenario.expected_fix_file
        if target_file and expected_file:
            target_base = target_file.rsplit("/", 1)[-1] if "/" in target_file else target_file
            expected_base = expected_file.rsplit("/", 1)[-1] if "/" in expected_file else expected_file
            if target_base.lower() != expected_base.lower():
                # Check if it might be a secondary issue fix (for hard scenarios)
                if self.scenario.secondary_issues:
                    for sec in self.scenario.secondary_issues:
                        sec_base = sec["file"].rsplit("/", 1)[-1]
                        if target_base.lower() == sec_base.lower():
                            self._secondary_fixes[sec["file"]] = fix_content
                            return f"Fix applied to {target_file}. This addresses a secondary issue."
                return f"Fix target '{target_file}' may not address the primary issue in '{expected_file}'."

        # Evaluate fix quality
        score = self.evaluate_fix(fix_content)
        if score >= 0.8:
            return "Fix looks correct — the changes address the root cause."
        elif score >= 0.5:
            return "Fix partially addresses the issue but may be incomplete."
        elif score >= 0.2:
            return "Fix has some relevant changes but doesn't fully resolve the issue."
        else:
            return "Fix doesn't appear to address the root cause."

    def evaluate_fix(self, fix_content: str) -> float:
        """
        Score a fix 0.0-1.0 based on keyword and structural match.
        """
        if not fix_content.strip():
            return 0.0

        s = self.scenario

        # Keyword matching (60%)
        kw_score = _keyword_match_score(fix_content, s.fix_keywords)

        # Structural matching (40%) — compare lines to expected fix
        expected_lines = [l.strip() for l in s.expected_fix.strip().splitlines() if l.strip()]
        fix_lines = [l.strip() for l in fix_content.strip().splitlines() if l.strip()]

        if not expected_lines:
            return kw_score

        line_matches = 0
        for exp_line in expected_lines:
            exp_tokens = set(re.findall(r'\w+', exp_line.lower()))
            if not exp_tokens:
                continue
            for fix_line in fix_lines:
                fix_tokens = set(re.findall(r'\w+', fix_line.lower()))
                if fix_tokens:
                    overlap = len(exp_tokens & fix_tokens) / len(exp_tokens)
                    if overlap >= constants.LINE_OVERLAP_THRESHOLD:
                        line_matches += 1
                        break

        structure_score = line_matches / len(expected_lines) if expected_lines else 0.0

        return constants.KEYWORD_WEIGHT * kw_score + constants.STRUCTURE_WEIGHT * structure_score

    def run_pipeline(self) -> Tuple[bool, str, float]:
        """
        Simulate re-running the pipeline after fixes.

        Returns:
            (passed, log_output, score)
            - passed: True if the pipeline would succeed with the fix
            - log_output: Simulated output of the re-run
            - score: 0.0-1.0 quality of the pipeline outcome
        """
        if not self._fix_applied:
            return False, "No fix was applied before re-running the pipeline.", 0.0

        primary_score = self.evaluate_fix(self._fix_applied)

        # For hard scenarios with secondary issues, check those too
        secondary_score = 1.0  # Default: no secondary issues
        if self.scenario.secondary_issues:
            sec_scores = []
            for sec in self.scenario.secondary_issues:
                if sec["file"] in self._secondary_fixes:
                    s = _keyword_match_score(
                        self._secondary_fixes[sec["file"]],
                        sec["keywords"],
                    )
                    sec_scores.append(s)
                else:
                    # Check if secondary fix keywords appear in primary fix
                    s = _keyword_match_score(self._fix_applied, sec["keywords"])
                    sec_scores.append(s * 0.5)  # Partial credit

            if sec_scores:
                secondary_score = sum(sec_scores) / len(sec_scores)

        overall = 0.7 * primary_score + 0.3 * secondary_score
        passed = overall >= 0.6

        if passed:
            log_output = (
                "Pipeline re-run results:\n"
                "  ✓ Build stage passed\n"
                "  ✓ Test stage passed\n"
                "  ✓ Deploy stage passed\n"
                f"\nPipeline completed successfully. Fix quality: {overall:.0%}"
            )
        elif overall >= 0.3:
            failing_stage = self.scenario.stage
            log_output = (
                "Pipeline re-run results:\n"
                f"  ⚠ {failing_stage.title()} stage: partial improvement\n"
                "  Some issues remain. The fix addressed part of the problem\n"
                "  but additional changes may be needed.\n"
                f"\nFix quality: {overall:.0%}"
            )
        else:
            failing_stage = self.scenario.stage
            log_output = (
                "Pipeline re-run results:\n"
                f"  ✗ {failing_stage.title()} stage failed\n"
                "  The submitted fix did not resolve the issue.\n"
                "  The same error persists.\n"
                f"\nFix quality: {overall:.0%}"
            )

        return passed, log_output, overall
