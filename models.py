"""
CI/CD Pipeline Diagnosis Environment — Data Models.

Defines typed Action, Observation, and State Pydantic models used by the environment.
These models follow the OpenEnv spec by inheriting from the openenv.core base types
which are Pydantic BaseModel subclasses.
"""

from typing import List, Optional

from pydantic import Field

from openenv.core.env_server.types import Action, Observation, State


class CICDAction(Action):
    """
    An action the agent can take in the CI/CD diagnosis environment.

    Attributes:
        action_type: One of "read_logs", "diagnose", "fix", "run_pipeline".
        target: Which pipeline stage or file to target.
        content: The diagnosis text or the fix content.
    """

    action_type: str = Field(
        default="read_logs",
        description='One of "read_logs", "diagnose", "fix", "run_pipeline"',
    )
    target: str = Field(
        default="",
        description='Pipeline stage (build/test/deploy/config) or filename for fix',
    )
    content: str = Field(
        default="",
        description="Diagnosis text (for diagnose) or fix content (for fix)",
    )


class CICDObservation(Observation):
    """
    What the agent observes after each step.
    """

    pipeline_status: str = Field(default="pending", description="Overall pipeline status")
    current_stage: str = Field(default="", description="Currently relevant stage")
    log_output: str = Field(default="", description="Log text from requested stage")
    error_summary: str = Field(default="", description="One-line error summary")
    available_actions: List[str] = Field(
        default_factory=list,
        description="Valid action types for current state (set by environment on each step)",
    )
    config_snapshot: str = Field(default="", description="Current pipeline config YAML")
    diagnosis_feedback: str = Field(default="", description="Feedback on diagnosis")
    fix_feedback: str = Field(default="", description="Feedback on fix")
    task_name: str = Field(default="", description="Current task identifier")
    step_number: int = Field(default=0, description="Current step count")


class CICDState(State):
    """
    Internal episode state tracked by the environment.

    Extends the base State (which has episode_id, step_count).
    """

    scenario_id: str = Field(default="", description="Active failure scenario ID")
    task_name: str = Field(default="log_diagnosis", description="Current task")
    diagnosed_correctly: bool = Field(default=False, description="Agent found root cause")
    diagnosis_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Diagnosis quality")
    fix_applied: bool = Field(default=False, description="Agent submitted a fix")
    fix_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Fix quality")
    pipeline_rerun: bool = Field(default=False, description="Agent re-ran pipeline")
    pipeline_passed: bool = Field(default=False, description="Pipeline passed after fix")
    accumulated_reward: float = Field(default=0.0, description="Total reward this episode")
    logs_read: List[str] = Field(default_factory=list, description="Stages whose logs were read")
