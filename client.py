"""
CI/CD Pipeline Diagnosis Environment — Client.

Provides the CICDEnv client for connecting to a running CICDEnvironment server.
Extends EnvClient with proper serialization/deserialization for our typed models.
"""

from openenv.core.env_client import EnvClient, StepResult

try:
    from .models import CICDAction, CICDObservation, CICDState
except ImportError:
    from models import CICDAction, CICDObservation, CICDState


class CICDEnv(EnvClient):
    """
    Client for the CI/CD Pipeline Diagnosis Environment.

    Usage (async):
        >>> async with CICDEnv(base_url="http://localhost:8000") as client:
        ...     result = await client.reset(task="log_diagnosis")
        ...     result = await client.step(CICDAction(
        ...         action_type="read_logs",
        ...         target="build"
        ...     ))
        ...     print(result.observation.log_output)

    Usage (sync):
        >>> with CICDEnv(base_url="http://localhost:8000").sync() as client:
        ...     result = client.reset(task="log_diagnosis")
        ...     result = client.step(CICDAction(
        ...         action_type="read_logs",
        ...         target="build"
        ...     ))

    Usage (Docker):
        >>> env = await CICDEnv.from_docker_image("cicd-diagnosis-env:latest")
        >>> result = await env.reset(task="suggest_fix")
    """

    def _step_payload(self, action: CICDAction) -> dict:
        """Serialize action for the HTTP request."""
        return {
            "action_type": action.action_type,
            "target": action.target,
            "content": action.content,
        }

    def _parse_result(self, payload: dict) -> StepResult:
        """Parse the step response into a StepResult."""
        obs_data = payload.get("observation", payload)
        obs = CICDObservation(
            pipeline_status=obs_data.get("pipeline_status", "pending"),
            current_stage=obs_data.get("current_stage", ""),
            log_output=obs_data.get("log_output", ""),
            error_summary=obs_data.get("error_summary", ""),
            available_actions=obs_data.get("available_actions", []),
            config_snapshot=obs_data.get("config_snapshot", ""),
            diagnosis_feedback=obs_data.get("diagnosis_feedback", ""),
            fix_feedback=obs_data.get("fix_feedback", ""),
            task_name=obs_data.get("task_name", ""),
            step_number=obs_data.get("step_number", 0),
        )
        return StepResult(
            observation=obs,
            reward=payload.get("reward", 0.0),
            done=payload.get("done", False),
        )

    def _parse_state(self, payload: dict) -> CICDState:
        """Parse the state response."""
        return CICDState(
            episode_id=payload.get("episode_id", ""),
            step_count=payload.get("step_count", 0),
            scenario_id=payload.get("scenario_id", ""),
            task_name=payload.get("task_name", ""),
            diagnosed_correctly=payload.get("diagnosed_correctly", False),
            diagnosis_score=payload.get("diagnosis_score", 0.0),
            fix_applied=payload.get("fix_applied", False),
            fix_score=payload.get("fix_score", 0.0),
            pipeline_rerun=payload.get("pipeline_rerun", False),
            pipeline_passed=payload.get("pipeline_passed", False),
            accumulated_reward=payload.get("accumulated_reward", 0.0),
            logs_read=payload.get("logs_read", []),
        )
