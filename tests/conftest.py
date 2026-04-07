import pytest
from scenarios.registry import SCENARIOS

@pytest.fixture
def missing_dependency_scenario():
    return SCENARIOS["missing_dependency"]

