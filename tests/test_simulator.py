from scenarios.registry import SCENARIOS
from core.pipeline_simulator import PipelineSimulator

def test_pipeline_simulator_evaluate_fix():
    scenario = SCENARIOS.get("missing_dependency")
    assert scenario is not None, "Scenario 'missing_dependency' must exist"
    
    sim = PipelineSimulator(scenario)
    
    # Empty fix
    assert sim.evaluate_fix("") == 0.0
    
    # Perfect fix (approximate checking)
    perfect_fix = "flask==3.0.0\nrequests==2.31.0\npandas>=2.0.0\n"
    score = sim.evaluate_fix(perfect_fix)
    assert score > 0.8  # Should be very high since keywords and structure match
    
    # Partial fix (has 'pandas', but wrong structure)
    partial_fix = "pandas==1.0"
    partial_score = sim.evaluate_fix(partial_fix)
    assert 0.0 < partial_score < 0.8
    
    # Garbage fix
    garbage_fix = "just some nonsense"
    garbage_score = sim.evaluate_fix(garbage_fix)
    assert garbage_score < 0.2
