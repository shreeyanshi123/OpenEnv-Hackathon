"""
Inference Script — CI/CD Pipeline Diagnosis Environment
========================================================

Baseline inference script that uses the OpenAI API client to run an LLM
agent against all 3 tasks in the CI/CD diagnosis environment.

MANDATORY Environment Variables:
    API_BASE_URL   The API endpoint for the LLM (default: HuggingFace router)
    MODEL_NAME     The model identifier to use (default: meta-llama/Meta-Llama-3-70B-Instruct)
    HF_TOKEN       Your Hugging Face / API key
    IMAGE_NAME     Docker image name (if using from_docker_image)

STDOUT FORMAT:
    [START] task=<task> env=cicd_diagnosis model=<model>
    [STEP]  step=<n> action=<action_str> reward=<0.00> done=<true|false> error=<msg|null>
    [END]   success=<true|false> steps=<n> score=<score> rewards=<r1,r2,...,rn>
"""

import asyncio
import json
import os
import sys
import textwrap
import traceback
from typing import Dict, List, Optional

from openai import OpenAI

# Ensure parent directory is in path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import CICDAction, CICDObservation
from core.cicd_environment import CICDEnvironment
from core.graders import grade_task
from scenarios.registry import get_scenario, TASK_DEFAULT_SCENARIO
import core.constants as constants

# ── Configuration ─────────────────────────────────────────────────────────

IMAGE_NAME = os.getenv("IMAGE_NAME")
# MANDATORY VARIABLES PER HACKATHON SPECS
HF_TOKEN = os.getenv("HF_TOKEN")
API_BASE_URL = os.getenv("API_BASE_URL") or "https://router.huggingface.co/v1"
MODEL_NAME = os.getenv("MODEL_NAME") or "meta-llama/Meta-Llama-3-70B-Instruct"

# GROQ FALLBACK (Allows free Llama testing if HF credits are out)
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if GROQ_API_KEY:
    API_BASE_URL = "https://api.groq.com/openai/v1"
    MODEL_NAME = "llama-3.1-8b-instant" # Fast, free Llama 3.1 on Groq
    HF_TOKEN = GROQ_API_KEY
BENCHMARK = "cicd_diagnosis"

MAX_STEPS = constants.MAX_STEPS
TEMPERATURE = 0.6
MAX_TOKENS = 500

# Task list — run all 3
TASKS = ["log_diagnosis", "suggest_fix", "auto_remediate"]

# ── Logging helpers ───────────────────────────────────────────────────────

def log_start(task: str, env: str, model: str) -> None:
    print(f"[START] task={task} env={env} model={model}", flush=True)


def log_step(step: int, action: str, reward: float, done: bool, error: Optional[str]) -> None:
    error_val = error if error else "null"
    done_val = str(done).lower()
    # Truncate action string for readability
    action_short = action.replace('\n', ' ')[:120]
    # Two spaces after [STEP] for vertical alignment
    print(
        f"[STEP]  step={step} action={action_short} reward={reward:.2f} done={done_val} error={error_val}",
        flush=True,
    )


def log_end(success: bool, steps: int, score: float, rewards: List[float]) -> None:
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    # Three spaces after [END] for vertical alignment
    print(
        f"[END]   success={str(success).lower()} steps={steps} score={score:.2f} rewards={rewards_str}",
        flush=True,
    )


# ── System prompt per task ────────────────────────────────────────────────

SYSTEM_PROMPTS = {
    "log_diagnosis": textwrap.dedent("""\
        You are a DevOps AI agent diagnosing a failing CI/CD pipeline.

        Your goal: Read the pipeline logs and identify the ROOT CAUSE of the failure.

        Available actions (respond with JSON):
        1. {"action_type": "read_logs", "target": "<stage>", "content": ""}
           — Read logs from a pipeline stage (build, test, deploy, config)
        2. {"action_type": "diagnose", "target": "", "content": "<your diagnosis>"}
           — Submit your diagnosis of what's causing the failure

        Strategy:
        - First read the logs from the failing stage
        - Look at the config if needed
        - Then submit a clear, specific diagnosis mentioning:
          * What specifically is failing
          * Why it's failing (the root cause)
          * Key error messages or identifiers

        Respond with STRICT raw JSON only, no markdown formatting, no code blocks, and no other conversational text.
    """),

    "suggest_fix": textwrap.dedent("""\
        You are a DevOps AI agent diagnosing and fixing a failing CI/CD pipeline.

        Your goal: Read logs, identify the root cause, AND suggest a specific fix.

        Available actions (respond with JSON):
        1. {"action_type": "read_logs", "target": "<stage>", "content": ""}
        2. {"action_type": "diagnose", "target": "", "content": "<your diagnosis>"}
        3. {"action_type": "fix", "target": "<filename>", "content": "<fixed file content>"}

        Strategy:
        - Read logs from the failing stage
        - Diagnose the root cause
        - Submit a fix with the corrected file content
        - The fix should be the COMPLETE corrected file, not a diff

        Respond with STRICT raw JSON only, no markdown formatting, no code blocks, and no other conversational text.
    """),

    "auto_remediate": textwrap.dedent("""\
        You are a DevOps AI agent that must fully remediate a failing CI/CD pipeline.

        Your goal: Read logs → diagnose → apply fix → re-run pipeline to verify.

        Available actions (respond with JSON):
        1. {"action_type": "read_logs", "target": "<stage>", "content": ""}
        2. {"action_type": "diagnose", "target": "", "content": "<your diagnosis>"}
        3. {"action_type": "fix", "target": "<filename>", "content": "<fixed file content>"}
        4. {"action_type": "run_pipeline", "target": "", "content": ""}

        Strategy:
        - Read logs to understand the failure
        - Read config for additional context
        - Diagnose the root cause (may be multiple issues)
        - Apply fix(es) for ALL issues found
        - Re-run the pipeline to verify the fix works
        - The fix should be COMPLETE corrected file content

        Respond with STRICT raw JSON only, no markdown formatting, no code blocks, and no other conversational text.
    """),
}

# ── Agent logic ───────────────────────────────────────────────────────────

def build_user_prompt(
    task: str,
    step: int,
    obs: CICDObservation,
    history: List[str],
) -> str:
    """Build user prompt from current observation."""
    history_block = "\n".join(history[-6:]) if history else "None"

    parts = [f"Step: {step}/{MAX_STEPS}"]
    parts.append(f"Pipeline Status: {obs.pipeline_status}")
    parts.append(f"Failing Stage: {obs.current_stage}")
    parts.append(f"Error: {obs.error_summary}")

    if obs.log_output:
        parts.append(f"\n--- Log Output ---\n{obs.log_output}\n--- End Logs ---")

    if obs.config_snapshot:
        parts.append(f"\n--- Config ---\n{obs.config_snapshot}\n--- End Config ---")

    if obs.diagnosis_feedback:
        parts.append(f"\nDiagnosis Feedback: {obs.diagnosis_feedback}")

    if obs.fix_feedback:
        parts.append(f"\nFix Feedback: {obs.fix_feedback}")

    parts.append(f"\nAvailable actions: {obs.available_actions}")
    parts.append(f"\n--- Previous Steps ---\n{history_block}")
    parts.append("\nRespond with your next action as a JSON object.")

    return "\n".join(parts)




def get_model_action(
    client: OpenAI,
    task: str,
    step: int,
    obs: CICDObservation,
    history: List[str],
) -> Dict:
    """Query the LLM for the next action."""
    user_prompt = build_user_prompt(task, step, obs, history)
    system_prompt = SYSTEM_PROMPTS.get(task, SYSTEM_PROMPTS["log_diagnosis"])

    try:
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
            response_format={"type": "json_object"},
            stream=False,
        )
        text = (completion.choices[0].message.content or "").strip()
        data = json.loads(text)
        
        # Ensure fallback for missed keys
        return {
            "action_type": data.get("action_type", "read_logs"),
            "target": data.get("target", ""),
            "content": data.get("content", ""),
        }
    except Exception as exc:
        print(f"[DEBUG] Model request failed or parsing failed: {exc}", flush=True)
        # Fallback action
        return {"action_type": "read_logs", "target": "build", "content": ""}


# ── Main loop ─────────────────────────────────────────────────────────────

def run_task(client: OpenAI, task_name: str) -> float:
    """
    Run a single task episode and return the final score.
    """
    env = CICDEnvironment()

    history: List[str] = []
    rewards: List[float] = []
    steps_taken = 0
    score = 0.0
    success = False

    log_start(task=task_name, env=BENCHMARK, model=MODEL_NAME)

    try:
        # Reset with task-specific settings
        scenario_id = TASK_DEFAULT_SCENARIO.get(task_name, "missing_dependency")
        obs = env.reset(task=task_name, scenario_id=scenario_id)

        # Convert Observation to our typed observation if needed
        if isinstance(obs, CICDObservation):
            current_obs = obs
        else:
            current_obs = CICDObservation(
                pipeline_status="failed",
                current_stage=getattr(obs, "current_stage", "build"),
                error_summary=getattr(obs, "error_summary", ""),
                config_snapshot=getattr(obs, "config_snapshot", ""),
                task_name=task_name,
            )

        done = False

        for step in range(1, MAX_STEPS + 1):
            if done:
                break

            # Get action from LLM
            action_dict = get_model_action(client, task_name, step, current_obs, history)

            # Execute step
            action = CICDAction(
                action_type=action_dict.get("action_type", "read_logs"),
                target=action_dict.get("target", ""),
                content=action_dict.get("content", ""),
            )

            result_obs = env.step(action)

            # Extract reward and done
            reward = getattr(result_obs, "reward", 0.0) or 0.0
            done = getattr(result_obs, "done", False) or False
            error = None

            rewards.append(reward)
            steps_taken = step

            # Update current observation
            if isinstance(result_obs, CICDObservation):
                current_obs = result_obs
            else:
                current_obs = CICDObservation(
                    pipeline_status=getattr(result_obs, "pipeline_status", "failed"),
                    current_stage=getattr(result_obs, "current_stage", ""),
                    log_output=getattr(result_obs, "log_output", ""),
                    error_summary=getattr(result_obs, "error_summary", ""),
                    diagnosis_feedback=getattr(result_obs, "diagnosis_feedback", ""),
                    fix_feedback=getattr(result_obs, "fix_feedback", ""),
                    task_name=task_name,
                    step_number=step,
                )

            # Log step
            action_str = f"{action.action_type}({action.target})"
            log_step(step=step, action=action_str, reward=reward, done=done, error=error)

            # Add to history
            history.append(
                f"Step {step}: {action.action_type}(target={action.target!r}) "
                f"→ reward={reward:+.2f}"
            )

            if done:
                break

        # Compute final graded score
        score = env.get_final_score()
        score = min(max(score, 0.0), 1.0)
        success = score >= constants.SUCCESS_SCORE_THRESHOLD

    except Exception as e:
        print(f"[DEBUG] Task {task_name} error: {e}", flush=True)
        traceback.print_exc()
        success = False

    finally:
        log_end(success=success, steps=steps_taken, score=score, rewards=rewards)

    return score


def main() -> None:
    """Run all tasks and report results."""
    if HF_TOKEN is None:
        raise ValueError("HF_TOKEN environment variable is required")


    client = OpenAI(base_url=API_BASE_URL, api_key=HF_TOKEN)

    all_scores = {}

    for task in TASKS:
        print(f"\n{'='*60}", flush=True)
        print(f"Running task: {task}", flush=True)
        print(f"{'='*60}", flush=True)

        score = run_task(client, task)
        all_scores[task] = score

    # Summary
    print(f"\n{'='*60}", flush=True)
    print("SUMMARY", flush=True)
    print(f"{'='*60}", flush=True)
    for task, score in all_scores.items():
        status = "✓ PASS" if score >= constants.SUCCESS_SCORE_THRESHOLD else "✗ FAIL"
        print(f"  {task:20s} → score={score:.2f}  {status}", flush=True)

    avg_score = sum(all_scores.values()) / len(all_scores) if all_scores else 0.0
    print(f"\n  Average score: {avg_score:.2f}", flush=True)


if __name__ == "__main__":
    main()
