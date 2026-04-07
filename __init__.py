"""
CI/CD Pipeline Diagnosis Environment — OpenEnv.

An environment where AI agents diagnose and fix failing CI/CD pipelines.
Simulates real-world DevOps scenarios with 3 tasks of increasing difficulty:
  1. log_diagnosis   (Easy)   — Read logs and identify the root cause
  2. suggest_fix     (Medium) — Diagnose AND propose a correct fix
  3. auto_remediate  (Hard)   — Full loop: diagnose → fix → verify pipeline passes

Usage:
    >>> from cicd_diagnosis_env import CICDAction, CICDEnv
    >>>
    >>> async with CICDEnv(base_url="http://localhost:8000") as client:
    ...     result = await client.reset()
    ...     result = await client.step(CICDAction(action_type="read_logs", target="build"))
"""

try:
    from .client import CICDEnv
    from .models import CICDAction, CICDObservation, CICDState
except ImportError:
    # When running from project root (e.g. pytest, uvicorn), use absolute imports
    from client import CICDEnv
    from models import CICDAction, CICDObservation, CICDState

__all__ = ["CICDAction", "CICDObservation", "CICDState", "CICDEnv"]
