"""
Task Graders — deterministic scoring functions for each task.

Each grader returns a float in [0.0, 1.0] based on the agent's performance
across the episode. Scores are deterministic given the same state.
"""

from __future__ import annotations

from models import CICDState
from scenarios.registry import Scenario, _keyword_match_score


def grade_log_diagnosis(state: CICDState, scenario: Scenario) -> float:
    """
    Grade the 'log_diagnosis' task (Easy).

    Scoring:
      - 20% for reading relevant logs
      - 80% for diagnosis quality (keyword match)

    Returns:
        Score in [0.0, 1.0]
    """
    score = 0.0

    # 20%: Did the agent read logs?
    if state.logs_read:
        # Bonus if they read the relevant stage
        if scenario.stage in state.logs_read:
            score += 0.20
        else:
            score += 0.10  # Read some logs, not the right one

    # 80%: Diagnosis quality
    score += 0.80 * state.diagnosis_score

    return min(max(score, 0.0), 1.0)


def grade_suggest_fix(state: CICDState, scenario: Scenario) -> float:
    """
    Grade the 'suggest_fix' task (Medium).

    Scoring:
      - 10% for reading logs
      - 20% for diagnosis quality
      - 70% for fix quality

    Returns:
        Score in [0.0, 1.0]
    """
    score = 0.0

    # 10%: logs
    if state.logs_read:
        if scenario.stage in state.logs_read:
            score += 0.10
        else:
            score += 0.05

    # 20%: diagnosis
    score += 0.20 * state.diagnosis_score

    # 70%: fix quality
    score += 0.70 * state.fix_score

    return min(max(score, 0.0), 1.0)


def grade_auto_remediate(state: CICDState, scenario: Scenario) -> float:
    """
    Grade the 'auto_remediate' task (Hard).

    Scoring:
      - 10% for reading logs
      - 15% for diagnosis quality
      - 35% for fix quality
      - 40% for pipeline passing after fix

    Returns:
        Score in [0.0, 1.0]
    """
    score = 0.0

    # 10%: logs
    if state.logs_read:
        if scenario.stage in state.logs_read:
            score += 0.10
        else:
            score += 0.05

    # 15%: diagnosis
    score += 0.15 * state.diagnosis_score

    # 35%: fix quality
    score += 0.35 * state.fix_score

    # 40%: pipeline outcome
    if state.pipeline_rerun:
        if state.pipeline_passed:
            score += 0.40
        else:
            # Partial credit for attempting rerun
            score += 0.05

    return min(max(score, 0.0), 1.0)


# Map task names to grader functions
GRADERS = {
    "log_diagnosis": grade_log_diagnosis,
    "suggest_fix": grade_suggest_fix,
    "auto_remediate": grade_auto_remediate,
}


def grade_task(task_name: str, state: CICDState, scenario: Scenario) -> float:
    """
    Grade a task by name.

    Args:
        task_name: One of 'log_diagnosis', 'suggest_fix', 'auto_remediate'
        state: The current environment state
        scenario: The active scenario

    Returns:
        Score in [0.0, 1.0]

    Raises:
        ValueError: If task_name is unknown
    """
    grader = GRADERS.get(task_name)
    if grader is None:
        raise ValueError(f"Unknown task: {task_name}. Valid tasks: {list(GRADERS.keys())}")
    return grader(state, scenario)
