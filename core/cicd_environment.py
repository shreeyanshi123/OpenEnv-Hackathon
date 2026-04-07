"""
CI/CD Pipeline Diagnosis Environment — Core Implementation.

This is the heart of the environment. It manages scenario state, processes
agent actions, computes rewards, and determines episode completion.
"""

from __future__ import annotations

import os
from typing import Any, Optional
from uuid import uuid4

from openenv.core.env_server.types import Action, Observation, State

try:
    from openenv.core.env_server import Environment
except ImportError:
    from openenv.core.env_server.environment import Environment

from models import CICDAction, CICDObservation, CICDState
from scenarios.registry import (
    TASK_DEFAULT_SCENARIO,
    Scenario,
    _keyword_match_score,
    get_scenario,
    get_scenarios_for_task,
)
from core.graders import grade_task
from core.pipeline_simulator import PipelineSimulator

MAX_STEPS = 15
STEP_PENALTY = 0.02


class CICDEnvironment(Environment):
    """
    Environment that simulates failing CI/CD pipelines for agent diagnosis.

    Tasks:
        - log_diagnosis (Easy):   Read logs → identify failure root cause
        - suggest_fix (Medium):   Read → diagnose → suggest a fix
        - auto_remediate (Hard):  Read → diagnose → fix → verify pipeline passes
    """

    def __init__(self):
        super().__init__()
        # Auto-initialize with default scenario so env is always valid
        task_name = os.environ.get("CICD_TASK", "log_diagnosis")
        scenario_id = TASK_DEFAULT_SCENARIO.get(task_name, "missing_dependency")
        self._scenario: Optional[Scenario] = get_scenario(scenario_id)
        self._simulator: Optional[PipelineSimulator] = PipelineSimulator(self._scenario)
        self._state = CICDState(
            episode_id=str(uuid4()),
            step_count=0,
            scenario_id=self._scenario.id,
            task_name=task_name,
        )
        self._done = False
        self._last_reward = 0.0

    def reset(
        self,
        seed: Optional[int] = None,
        episode_id: Optional[str] = None,
        **kwargs: Any,
    ) -> Observation:
        """
        Reset the environment for a new episode.

        Kwargs (passed via reset options):
            task: str — "log_diagnosis", "suggest_fix", or "auto_remediate"
            scenario_id: str — specific scenario to use (optional)
        """
        task_name = kwargs.get("task", os.environ.get("CICD_TASK", "log_diagnosis"))
        scenario_id = kwargs.get("scenario_id", os.environ.get("CICD_SCENARIO", ""))

        # Pick scenario
        if scenario_id and scenario_id in TASK_DEFAULT_SCENARIO.values():
            try:
                self._scenario = get_scenario(scenario_id)
            except KeyError:
                self._scenario = get_scenario(TASK_DEFAULT_SCENARIO.get(task_name, "missing_dependency"))
        elif scenario_id:
            try:
                self._scenario = get_scenario(scenario_id)
            except KeyError:
                self._scenario = get_scenario(TASK_DEFAULT_SCENARIO.get(task_name, "missing_dependency"))
        else:
            self._scenario = get_scenario(TASK_DEFAULT_SCENARIO.get(task_name, "missing_dependency"))

        self._simulator = PipelineSimulator(self._scenario)
        self._done = False
        self._last_reward = 0.0

        self._state = CICDState(
            episode_id=episode_id or str(uuid4()),
            step_count=0,
            scenario_id=self._scenario.id,
            task_name=task_name,
            diagnosed_correctly=False,
            diagnosis_score=0.0,
            fix_applied=False,
            fix_score=0.0,
            pipeline_rerun=False,
            pipeline_passed=False,
            accumulated_reward=0.0,
            logs_read=[],
        )

        # Build the initial observation
        obs = CICDObservation(
            pipeline_status="failed",
            current_stage=self._scenario.stage,
            log_output="",
            error_summary=self._scenario.error_summary,
            available_actions=self._get_available_actions(),
            config_snapshot=self._scenario.pipeline_config,
            diagnosis_feedback="",
            fix_feedback="",
            task_name=task_name,
            step_number=0,
        )

        return obs

    def step(
        self,
        action: Action,
        timeout_s: Optional[float] = None,
        **kwargs: Any,
    ) -> Observation:
        """
        Execute one step in the environment.

        Returns an Observation with updated state, reward, and done flag.
        The observation is also a StepResult-compatible dict when serialized.
        """
        if self._done:
            return self._make_done_observation("Episode already ended.", 0.0)

        if not isinstance(action, CICDAction):
            # Try to parse from dict
            if isinstance(action, dict):
                action = CICDAction(**action)
            else:
                return self._make_observation(
                    log_output="Invalid action format.",
                    reward=0.0,
                )

        self._state.step_count += 1
        reward = 0.0

        # Step penalty
        reward -= STEP_PENALTY

        # Dispatch by action type
        action_type = action.action_type.lower().strip()

        if action_type == "read_logs":
            obs, r = self._handle_read_logs(action)
            reward += r
        elif action_type == "diagnose":
            obs, r = self._handle_diagnose(action)
            reward += r
        elif action_type == "fix":
            obs, r = self._handle_fix(action)
            reward += r
        elif action_type == "run_pipeline":
            obs, r = self._handle_run_pipeline(action)
            reward += r
        else:
            obs = self._make_observation(
                log_output=f"Unknown action_type: '{action_type}'. "
                           f"Valid actions: {self._get_available_actions()}",
                reward=0.0,
            )
            reward = -0.05

        # Update accumulated reward
        self._state.accumulated_reward += reward
        self._last_reward = reward

        # Check if episode should end
        if self._state.step_count >= MAX_STEPS:
            self._done = True

        # Check task-specific completion
        if self._check_task_complete():
            self._done = True

        # Update observation fields
        obs.step_number = self._state.step_count
        obs.task_name = self._state.task_name
        obs.available_actions = self._get_available_actions()

        # For serialization via OpenEnv framework
        obs.done = self._done
        obs.reward = reward

        return obs

    @property
    def state(self) -> State:
        """Get the current environment state."""
        return self._state

    # ── Action Handlers ────────────────────────────────────────────────────

    def _handle_read_logs(self, action: CICDAction) -> tuple:
        """Handle read_logs action."""
        target = action.target.lower().strip() if action.target else ""

        if not target:
            target = self._scenario.stage  # Default to failing stage

        available_stages = list(self._scenario.logs.keys())

        if target not in self._scenario.logs:
            obs = self._make_observation(
                log_output=f"No logs available for stage '{target}'. "
                           f"Available stages: {available_stages}",
            )
            return obs, 0.0

        log_text = self._scenario.logs[target]

        # Reward for reading logs
        reward = 0.0
        if target not in self._state.logs_read:
            self._state.logs_read.append(target)
            if target == self._scenario.stage:
                reward = 0.05  # More reward for reading the relevant stage
            else:
                reward = 0.01
        else:
            reward = 0.0  # Already read

        obs = self._make_observation(
            log_output=log_text,
            pipeline_status="failed",
            current_stage=target,
        )
        return obs, reward

    def _handle_diagnose(self, action: CICDAction) -> tuple:
        """Handle diagnose action."""
        diagnosis = action.content.strip()

        if not diagnosis:
            obs = self._make_observation(
                diagnosis_feedback="Empty diagnosis submitted. Please describe the root cause.",
            )
            return obs, -0.02

        # Score diagnosis using keyword matching
        score = _keyword_match_score(diagnosis, self._scenario.diagnosis_keywords)
        self._state.diagnosis_score = max(self._state.diagnosis_score, score)

        if score >= 0.6:
            self._state.diagnosed_correctly = True
            feedback = "Good diagnosis — you've identified the key issue."
            reward = 0.1 + 0.3 * score  # 0.1 to 0.4
        elif score >= 0.3:
            feedback = "Partial diagnosis — you're on the right track but missing some details."
            reward = 0.05 + 0.1 * score
        else:
            feedback = "Incorrect diagnosis — the root cause hasn't been identified."
            reward = -0.05

        obs = self._make_observation(
            diagnosis_feedback=feedback,
            pipeline_status="failed",
        )
        return obs, reward

    def _handle_fix(self, action: CICDAction) -> tuple:
        """Handle fix action."""
        fix_content = action.content.strip()
        target_file = action.target.strip() if action.target else ""

        if not fix_content:
            obs = self._make_observation(
                fix_feedback="Empty fix submitted. Please provide the corrected content.",
            )
            return obs, -0.02

        # Apply fix to simulator and get feedback
        feedback = self._simulator.apply_fix(target_file, fix_content)
        score = self._simulator.evaluate_fix(fix_content)

        self._state.fix_applied = True
        self._state.fix_score = max(self._state.fix_score, score)

        if score >= 0.7:
            reward = 0.2 + 0.3 * score
        elif score >= 0.4:
            reward = 0.1 + 0.1 * score
        else:
            reward = -0.05

        obs = self._make_observation(
            fix_feedback=feedback,
            pipeline_status="failed",  # Haven't re-run yet
        )
        return obs, reward

    def _handle_run_pipeline(self, action: CICDAction) -> tuple:
        """Handle run_pipeline action."""
        self._state.pipeline_rerun = True

        if not self._state.fix_applied:
            obs = self._make_observation(
                log_output="Pipeline re-run without any fix applied.\n"
                          "The same failure occurred.\n\n"
                          + self._scenario.error_summary,
                pipeline_status="failed",
            )
            return obs, -0.05

        passed, log_output, quality = self._simulator.run_pipeline()
        self._state.pipeline_passed = passed

        if passed:
            reward = 0.3
            pipeline_status = "passed"
        elif quality >= 0.3:
            reward = 0.05
            pipeline_status = "failed"
        else:
            reward = -0.05
            pipeline_status = "failed"

        obs = self._make_observation(
            log_output=log_output,
            pipeline_status=pipeline_status,
        )
        return obs, reward

    # ── Helpers ───────────────────────────────────────────────────────────

    def _check_task_complete(self) -> bool:
        """Check if the current task's objective has been met."""
        task = self._state.task_name

        if task == "log_diagnosis":
            return self._state.diagnosed_correctly

        elif task == "suggest_fix":
            return self._state.diagnosed_correctly and self._state.fix_applied

        elif task == "auto_remediate":
            return self._state.pipeline_rerun

        return False

    def _get_available_actions(self) -> list:
        """Get list of currently valid action types."""
        if self._done:
            return []

        actions = ["read_logs", "diagnose"]
        task = self._state.task_name

        if task in ("suggest_fix", "auto_remediate"):
            actions.append("fix")

        if task == "auto_remediate":
            actions.append("run_pipeline")

        return actions

    def _make_observation(self, **overrides) -> CICDObservation:
        """Create observation with defaults from current scenario."""
        defaults = {
            "pipeline_status": "failed",
            "current_stage": self._scenario.stage if self._scenario else "",
            "log_output": "",
            "error_summary": self._scenario.error_summary if self._scenario else "",
            "available_actions": self._get_available_actions(),
            "config_snapshot": "",
            "diagnosis_feedback": "",
            "fix_feedback": "",
            "task_name": self._state.task_name,
            "step_number": self._state.step_count,
        }
        defaults.update(overrides)
        return CICDObservation(**defaults)

    def _make_done_observation(self, message: str, reward: float) -> CICDObservation:
        """Create a terminal observation."""
        obs = self._make_observation(
            log_output=message,
            pipeline_status="passed" if self._state.pipeline_passed else "failed",
        )
        obs.done = True
        obs.reward = reward
        return obs

    def get_final_score(self) -> float:
        """Get the final graded score for the episode."""
        if self._scenario is None:
            return 0.0
        return grade_task(self._state.task_name, self._state, self._scenario)
