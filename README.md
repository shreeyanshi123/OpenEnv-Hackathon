---
title: CICD Pipeline Diagnosis Env
emoji: 🔥
colorFrom: blue
colorTo: indigo
sdk: docker
pinned: false
---

# CI/CD Pipeline Diagnosis Environment 🔧

[![OpenEnv](https://img.shields.io/badge/OpenEnv-compatible-blue)](https://github.com/meta-pytorch/OpenEnv)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](https://www.docker.com/)

An **OpenEnv-compliant** environment that simulates failing CI/CD pipelines for AI agent training and evaluation. The agent must diagnose pipeline failures from logs, propose fixes, and verify that fixes work — a real-world DevOps task where AI+DevOps skills are extremely in-demand.

## Motivation

DevOps engineers spend **20-40% of their time** debugging CI/CD pipeline failures. Common issues include missing dependencies, YAML syntax errors, Docker misconfigurations, and version conflicts. This environment lets AI agents practice these diagnostic skills in a safe, reproducible simulation with **no existing benchmark** for this domain.

---

## Quick Start

### Install

```bash
pip install openenv-core
pip install -e .
```

### Run the Server

```bash
uvicorn server.app:app --host 0.0.0.0 --port 8000
```

### Run the Baseline Agent

```bash
export HF_TOKEN=your_token_here
python inference.py
```

### Docker

```bash
docker build -t cicd-diagnosis-env:latest .
docker run -p 8000:8000 cicd-diagnosis-env:latest
```

---

## Tasks

The environment includes **3 tasks** with increasing difficulty:

### Task 1: `log_diagnosis` (Easy)
**Goal:** Read pipeline logs and identify the failure root cause.

- Agent receives a failed pipeline with visible errors
- Must submit a diagnosis matching the known root cause
- **Scoring:** 20% for reading logs + 80% for diagnosis quality
- **Example:** Python build fails with `ModuleNotFoundError: No module named 'pandas'` → agent must identify "missing dependency: pandas in requirements.txt"

### Task 2: `suggest_fix` (Medium)
**Goal:** Read logs, diagnose the issue, AND suggest a specific fix.

- Agent must identify the issue AND propose valid corrected file content
- Fix is validated against the expected solution
- **Scoring:** 10% logs + 20% diagnosis + 70% fix quality
- **Example:** Docker build fails because `python:3.11-slm-bookworm` tag doesn't exist → agent must fix typo to `slim`

### Task 3: `auto_remediate` (Hard)
**Goal:** Full end-to-end: read → diagnose → fix → re-run pipeline.

- Agent must apply a fix AND re-run the pipeline to verify it passes
- May involve multiple cascading failures to fix simultaneously
- **Scoring:** 10% logs + 15% diagnosis + 35% fix + 40% pipeline passes
- **Example:** Node.js CI has wrong version (14 vs >=18), wrong env var name, AND low test timeout — agent must fix all three

---

## Action Space

```python
@dataclass
class CICDAction(Action):
    action_type: str  # "read_logs" | "diagnose" | "fix" | "run_pipeline"
    target: str       # Stage name or filename
    content: str      # Diagnosis text or fix content
```

| Action | Description | Target | Content |
|--------|-------------|--------|---------|
| `read_logs` | Get log output from a pipeline stage | `"build"`, `"test"`, `"deploy"`, `"config"` | (empty) |
| `diagnose` | Submit root cause analysis | (empty) | Description of the root cause |
| `fix` | Submit corrected file content | Filename (e.g. `"requirements.txt"`) | Complete corrected file |
| `run_pipeline` | Re-run pipeline after applying fix | (empty) | (empty) |

---

## Observation Space

```python
@dataclass
class CICDObservation(Observation):
    pipeline_status: str       # "failed" | "running" | "passed" | "pending"
    current_stage: str         # "build" | "test" | "deploy" | "complete"
    log_output: str            # Log text from the requested stage
    error_summary: str         # One-line error message
    available_actions: list    # Valid action types for current state
    config_snapshot: str       # Pipeline config (YAML)
    diagnosis_feedback: str    # Feedback on diagnosis attempt
    fix_feedback: str          # Feedback on fix attempt
    task_name: str             # Current task identifier
    step_number: int           # Current step in episode
```

---

## Reward Function

The environment provides **dense rewards** at every step (not just binary pass/fail):

| Signal | Reward | Description |
|--------|--------|-------------|
| Read relevant logs | +0.05 | First read of the failing stage |
| Read other logs | +0.01 | First read of non-failing stages |
| Good diagnosis (≥60% match) | +0.10 to +0.40 | Based on keyword match quality |
| Partial diagnosis (30-60%) | +0.05 to +0.15 | On the right track |
| Bad diagnosis (<30%) | -0.05 | Wrong root cause |
| Good fix (≥70% match) | +0.20 to +0.50 | Fix addresses root cause |
| Partial fix (40-70%) | +0.10 to +0.20 | Fix partially correct |
| Pipeline passes after fix | +0.30 | Pipeline re-run succeeds |
| Step penalty | -0.02 | Per step (encourages efficiency) |
| Empty/invalid action | -0.02 to -0.05 | Discourages waste |

**Episode length:** Maximum 15 steps.

---

## Scenarios

12+ realistic CI/CD failure scenarios across categories:

| Category | Scenario | Difficulty | Root Cause |
|----------|----------|:----------:|------------|
| Dependency | Missing pip package | Easy | `requirements.txt` missing entry |
| Dependency | Version conflict | Medium | numpy/pandas version incompatibility |
| Build | Dockerfile command typo | Easy | `pyhton` instead of `python` |
| Build | Wrong base image tag | Medium | `slm` instead of `slim` |
| Build | Python version too old | Medium | Python 3.8 vs match/case (3.10+) |
| Test | Test assertion failure | Easy | Float precision comparison |
| Test | Missing test fixture | Medium | `.gitignore` excludes fixture files |
| Deploy | Misspelled env var | Easy | `DATABSE_URL` vs `DATABASE_URL` |
| Deploy | OOM memory limit | Medium | 64MB too low for ML app |
| Deploy | Permission + secrets | Hard | Empty permissions + wrong secret name |
| Deploy | Circular dependencies | Hard | Docker Compose cycle + wrong port |
| Config | YAML indentation | Easy | Bad indentation on `env:` key |
| Multi | Cascading Node.js | Hard | Wrong Node version + env var + timeout |
| Multi | Docker multi-stage | Hard | Stage name mismatch + wrong EXPOSE |

---

## State

```python
@dataclass
class CICDState(State):
    scenario_id: str           # Active scenario
    task_name: str             # Current task
    diagnosed_correctly: bool  # Agent found root cause?
    diagnosis_score: float     # Quality of diagnosis (0-1)
    fix_applied: bool          # Agent submitted a fix?
    fix_score: float           # Quality of fix (0-1)
    pipeline_rerun: bool       # Agent re-ran pipeline?
    pipeline_passed: bool      # Pipeline passed after fix?
    accumulated_reward: float  # Total reward this episode
    logs_read: list            # Stages whose logs were read
```

---

## Project Structure

```
cicd_diagnosis_env/
├── __init__.py              # Exports CICDAction, CICDObservation, CICDEnv
├── models.py                # Typed Action, Observation, State models
├── client.py                # CICDEnv(EnvClient) client
├── openenv.yaml             # OpenEnv manifest
├── pyproject.toml           # Dependencies
├── inference.py             # Baseline inference script
├── README.md                # This file
├── scenarios/
│   ├── __init__.py
│   └── registry.py          # 12+ failure scenario definitions
├── core/
│   ├── __init__.py
│   ├── cicd_environment.py   # Core Environment implementation
│   ├── pipeline_simulator.py # Pipeline simulation engine
│   └── graders.py            # Task graders (0.0-1.0 scores)
└── server/
    ├── __init__.py
    ├── app.py                # FastAPI application
    ├── requirements.txt      # Server dependencies
    └── Dockerfile            # Container image
```

---

## OpenEnv Manifest (`openenv.yaml`)

The file `openenv.yaml` is the **OpenEnv configuration manifest** that declares this environment to the OpenEnv framework. It specifies:

| Field | Value | Purpose |
|-------|-------|---------|
| `spec_version` | `1` | OpenEnv spec version |
| `name` | `cicd_diagnosis_env` | Unique environment identifier |
| `type` | `space` | Deployment mode (Hugging Face Space) |
| `runtime` | `fastapi` | Server framework |
| `app` | `server.app:app` | ASGI application entrypoint |
| `port` | `8000` | Default listening port |

It also declares the three tasks (`log_diagnosis`, `suggest_fix`, `auto_remediate`) and the full observation/action JSON schemas so that OpenEnv clients and evaluators can auto-discover the environment's interface without reading source code.

---

## Baseline Scores

Running with `meta-llama/Meta-Llama-3-70B-Instruct`:

| Task | Score | Steps |
|------|:-----:|:-----:|
| `log_diagnosis` (Easy) | ~0.60–0.70 | 3-5 |
| `suggest_fix` (Medium) | ~0.40–0.50 | 4-7 |
| `auto_remediate` (Hard) | ~0.20–0.30 | 6-12 |

*Scores vary slightly between runs due to LLM stochasticity. Models that struggle to output raw JSON will score lower.*

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|:--------:|---------|-------------|
| `HF_TOKEN` | Yes | — | HuggingFace API key |
| `API_BASE_URL` | No | `https://router.huggingface.co/v1` | LLM API endpoint |
| `MODEL_NAME` | No | `meta-llama/Meta-Llama-3-70B-Instruct` | Model identifier |
| `IMAGE_NAME` | No | — | Docker image name |
| `CICD_TASK` | No | `log_diagnosis` | Default task for reset |
| `CICD_SCENARIO` | No | (auto) | Specific scenario ID |

---

## API Usage

### Python (Async)

```python
from cicd_diagnosis_env import CICDAction, CICDEnv

async with CICDEnv(base_url="http://localhost:8000") as client:
    result = await client.reset(task="log_diagnosis")
    
    # Read logs
    result = await client.step(CICDAction(
        action_type="read_logs",
        target="build"
    ))
    print(result.observation.log_output)
    
    # Submit diagnosis
    result = await client.step(CICDAction(
        action_type="diagnose",
        content="Missing pandas dependency in requirements.txt"
    ))
    print(result.observation.diagnosis_feedback)
```

### HTTP (curl)

```bash
# Reset
curl -X POST http://localhost:8000/reset \
  -H "Content-Type: application/json" \
  -d '{"task": "log_diagnosis"}'

# Step
curl -X POST http://localhost:8000/step \
  -H "Content-Type: application/json" \
  -d '{"action_type": "read_logs", "target": "build", "content": ""}'
```

---

## License

MIT
