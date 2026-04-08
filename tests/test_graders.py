import pytest
from core.graders import grade_task, grade_log_diagnosis, grade_suggest_fix, grade_auto_remediate
from models import CICDState
from scenarios.registry import SCENARIOS

def test_grade_log_diagnosis_perfect(missing_dependency_scenario):
    state = CICDState(
        scenario_id="missing_dependency",
        task_name="log_diagnosis",
        logs_read=["build"],
        diagnosis_score=1.0
    )
    score = grade_log_diagnosis(state, missing_dependency_scenario)
    assert score == pytest.approx(0.99)

def test_grade_log_diagnosis_partial(missing_dependency_scenario):
    state = CICDState(
        scenario_id="missing_dependency",
        task_name="log_diagnosis",
        logs_read=["test"], # Wrong stage
        diagnosis_score=0.5
    )
    score = grade_log_diagnosis(state, missing_dependency_scenario)
    # 0.1 for reading wrong logs + 0.8 * 0.5 = 0.5
    assert score == pytest.approx(0.5)

def test_grade_log_diagnosis_bad(missing_dependency_scenario):
    state = CICDState(
        scenario_id="missing_dependency",
        task_name="log_diagnosis",
        logs_read=[],
        diagnosis_score=0.0
    )
    score = grade_log_diagnosis(state, missing_dependency_scenario)
    assert score == pytest.approx(0.01)

def test_grade_suggest_fix_perfect(missing_dependency_scenario):
    state = CICDState(
        scenario_id="missing_dependency",
        task_name="suggest_fix",
        logs_read=["build"],
        diagnosis_score=1.0,
        fix_score=1.0
    )
    score = grade_suggest_fix(state, missing_dependency_scenario)
    assert score == pytest.approx(0.99)

def test_grade_auto_remediate_perfect(missing_dependency_scenario):
    state = CICDState(
        scenario_id="missing_dependency",
        task_name="auto_remediate",
        logs_read=["build"],
        diagnosis_score=1.0,
        fix_score=1.0,
        pipeline_rerun=True,
        pipeline_passed=True
    )
    score = grade_auto_remediate(state, missing_dependency_scenario)
    assert score == pytest.approx(0.99)

def test_grade_auto_remediate_rerun_failed(missing_dependency_scenario):
    state = CICDState(
        scenario_id="missing_dependency",
        task_name="auto_remediate",
        logs_read=["build"],
        diagnosis_score=1.0,
        fix_score=1.0,
        pipeline_rerun=True,
        pipeline_passed=False
    )
    score = grade_auto_remediate(state, missing_dependency_scenario)
    # 0.1 (logs) + 0.15 (diag) + 0.35 (fix) + 0.05 (attempted rerun) = 0.65
    assert score == pytest.approx(0.65)

def test_grade_task_invalid():
    state = CICDState()
    with pytest.raises(ValueError, match="Unknown task"):
        grade_task("invalid_task", state, None)
