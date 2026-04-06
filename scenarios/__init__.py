"""Scenario engine for CI/CD pipeline failure scenarios."""

from .registry import SCENARIOS, get_scenario, get_scenarios_for_task

__all__ = ["SCENARIOS", "get_scenario", "get_scenarios_for_task"]
