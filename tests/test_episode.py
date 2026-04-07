import pytest
from core.cicd_environment import CICDEnvironment
from models import CICDAction

def test_full_episode_log_diagnosis():
    env = CICDEnvironment()
    obs = env.reset(task="log_diagnosis")
    
    assert obs.task_name == "log_diagnosis"
    assert "read_logs" in obs.available_actions
    
    # Read the logs
    obs = env.step(CICDAction(action_type="read_logs", target="build"))
    assert obs.log_output != ""
    
    # Diagnose correctly
    obs = env.step(CICDAction(action_type="diagnose", content="pandas missing in requirements dependency"))
    assert obs.done is True
    
    score = env.get_final_score()
    # Read logs (0.2) + perfect diagnosis (0.8) should be 1.0
    assert score > 0.8

def test_auto_remediate_requires_pipeline_pass():
    """Verify bug #6 is fixed: agent cannot complete auto_remediate with a failed pipeline rerun."""
    env = CICDEnvironment()
    env.reset(task="auto_remediate")
    
    # Apply a bad fix
    env.step(CICDAction(action_type="fix", target="requirements.txt", content="pandas==1.0.0"))
    
    # Rerun the pipeline (it will fail because fix is bad)
    obs = env.step(CICDAction(action_type="run_pipeline"))
    
    # The episode should NOT be done just because they ran the pipeline.
    # It only succeeds if the pipeline passes.
    assert obs.done is False
    assert env._state.pipeline_passed is False

def test_auto_remediate_success():
    """Verify a perfect run completes the episode."""
    env = CICDEnvironment()
    env.reset(task="auto_remediate", scenario_id="missing_dependency")
    
    # Read relevant logs first (10% of score)
    env.step(CICDAction(action_type="read_logs", target="build"))
    
    # Diagnose correctly (15% of score)
    env.step(CICDAction(action_type="diagnose", content="Missing dependency: pandas is not listed in requirements.txt"))
    
    # Apply perfect fix (35% of score)
    perfect_fix = "flask==3.0.0\nrequests==2.31.0\npandas>=2.0.0\n"
    env.step(CICDAction(action_type="fix", target="requirements.txt", content=perfect_fix))
    
    # Rerun the pipeline (40% of score — it should pass)
    obs = env.step(CICDAction(action_type="run_pipeline"))
    
    assert obs.done is True
    assert env._state.pipeline_passed is True
    assert env.get_final_score() > 0.9

