"""
CI/CD Pipeline Failure Scenario Registry.

Each scenario defines a realistic CI/CD pipeline failure with:
  - pipeline_config:    The YAML config (GitHub Actions / generic CI)
  - stage:              Which stage fails ("build", "test", "deploy")
  - logs:               Dict of stage → log output strings
  - error_summary:      One-line error visible to agent on reset
  - root_cause:         Ground-truth description of the failure
  - diagnosis_keywords: Keywords that a correct diagnosis MUST contain
  - expected_fix_file:  Which file needs to be fixed
  - expected_fix:       A reference fix string
  - fix_validator:      Function(submitted_fix) → float (0.0-1.0 quality)
  - difficulty:         "easy", "medium", "hard"
  - tasks:              Which tasks this scenario can be used for
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional


@dataclass
class Scenario:
    """A single CI/CD failure scenario."""

    id: str
    name: str
    description: str
    difficulty: str  # "easy", "medium", "hard"
    tasks: List[str]  # Which tasks this can be used for
    stage: str  # "build", "test", "deploy"
    pipeline_config: str  # YAML config
    logs: Dict[str, str]  # stage -> log output
    error_summary: str
    root_cause: str
    diagnosis_keywords: List[str]  # Must-have keywords in diagnosis
    expected_fix_file: str
    expected_fix: str
    fix_keywords: List[str]  # Keywords the fix should contain
    secondary_issues: Optional[List[Dict]] = None  # For cascading failures (hard)


def _keyword_match_score(text: str, keywords: List[str]) -> float:
    """Score 0.0-1.0 based on fraction of keywords found in text."""
    if not keywords:
        return 0.0
    text_lower = text.lower()
    matches = sum(1 for kw in keywords if kw.lower() in text_lower)
    return matches / len(keywords)


def _fix_validator_keywords(fix_text: str, keywords: List[str], expected: str) -> float:
    """Validate a fix based on keyword presence and similarity to expected fix."""
    if not fix_text.strip():
        return 0.0

    # Keyword matching (60% weight)
    kw_score = _keyword_match_score(fix_text, keywords)

    # Check if key structural elements are present (40% weight)
    expected_lines = [l.strip() for l in expected.strip().splitlines() if l.strip()]
    fix_lines = [l.strip() for l in fix_text.strip().splitlines() if l.strip()]

    if not expected_lines:
        return kw_score

    line_matches = 0
    for exp_line in expected_lines:
        for fix_line in fix_lines:
            # Fuzzy line match — check if core content overlaps
            exp_tokens = set(re.findall(r'\w+', exp_line.lower()))
            fix_tokens = set(re.findall(r'\w+', fix_line.lower()))
            if exp_tokens and fix_tokens:
                overlap = len(exp_tokens & fix_tokens) / len(exp_tokens)
                if overlap >= 0.6:
                    line_matches += 1
                    break

    structure_score = line_matches / len(expected_lines)

    return 0.6 * kw_score + 0.4 * structure_score


# ---------------------------------------------------------------------------
# SCENARIO DEFINITIONS
# ---------------------------------------------------------------------------

SCENARIOS: Dict[str, Scenario] = {}


def _register(s: Scenario) -> None:
    SCENARIOS[s.id] = s


# ── Easy Scenarios ──────────────────────────────────────────────────────────

_register(Scenario(
    id="missing_dependency",
    name="Missing pip dependency",
    description="Python build fails because a required package is not listed in requirements.txt",
    difficulty="easy",
    tasks=["log_diagnosis", "suggest_fix", "auto_remediate"],
    stage="build",
    pipeline_config="""\
name: CI Pipeline
on: [push]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: python -m pytest tests/
""",
    logs={
        "build": """\
Step 1/4: actions/checkout@v4 ✓
Step 2/4: actions/setup-python@v5 ✓
  Python 3.11.7 installed
Step 3/4: pip install -r requirements.txt
  Collecting flask==3.0.0
  Collecting requests==2.31.0
  Successfully installed flask-3.0.0 requests-2.31.0
Step 4/4: python -m pytest tests/
  FAILED — ModuleNotFoundError: No module named 'pandas'

  Traceback (most recent call last):
    File "app/data_loader.py", line 2, in <module>
      import pandas as pd
  ModuleNotFoundError: No module named 'pandas'

Error: Process completed with exit code 1.""",
        "test": "Tests could not run — build step failed.",
        "deploy": "Deploy skipped — previous steps failed.",
        "config": "requirements.txt:\nflask==3.0.0\nrequests==2.31.0\n",
    },
    error_summary="Build failed: ModuleNotFoundError: No module named 'pandas'",
    root_cause="The package 'pandas' is imported in app/data_loader.py but not listed in requirements.txt",
    diagnosis_keywords=["pandas", "missing", "requirements", "dependency"],
    expected_fix_file="requirements.txt",
    expected_fix="flask==3.0.0\nrequests==2.31.0\npandas>=2.0.0\n",
    fix_keywords=["pandas", "requirements"],
))

_register(Scenario(
    id="yaml_syntax_error",
    name="YAML indentation error in CI config",
    description="Pipeline config has a YAML indentation error causing parse failure",
    difficulty="easy",
    tasks=["log_diagnosis", "suggest_fix", "auto_remediate"],
    stage="build",
    pipeline_config="""\
name: CI Pipeline
on: [push]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: echo "Building..."
       env:
        BUILD_MODE: production
""",
    logs={
        "build": """\
Error: Invalid workflow file: .github/workflows/ci.yml
  yaml: line 9: mapping values are not allowed in this context
  
The workflow file has a YAML syntax error at line 9.
Check indentation and formatting of the YAML file.

Error: Process completed with exit code 1.""",
        "test": "Pipeline parsing failed — no stages executed.",
        "deploy": "Pipeline parsing failed — no stages executed.",
        "config": """\
name: CI Pipeline
on: [push]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: echo "Building..."
       env:
        BUILD_MODE: production""",
    },
    error_summary="YAML syntax error at line 9: mapping values are not allowed in this context",
    root_cause="The 'env' key on line 9 has incorrect indentation — it should be aligned under the step (2 more spaces)",
    diagnosis_keywords=["yaml", "indentation", "syntax", "env"],
    expected_fix_file=".github/workflows/ci.yml",
    expected_fix="""\
name: CI Pipeline
on: [push]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: echo "Building..."
        env:
          BUILD_MODE: production""",
    fix_keywords=["env", "indentation", "BUILD_MODE"],
))

_register(Scenario(
    id="wrong_env_var",
    name="Misspelled environment variable",
    description="Deploy stage fails because an environment variable name is misspelled",
    difficulty="easy",
    tasks=["log_diagnosis", "suggest_fix", "auto_remediate"],
    stage="deploy",
    pipeline_config="""\
name: Deploy Pipeline
on:
  push:
    branches: [main]
jobs:
  deploy:
    runs-on: ubuntu-latest
    env:
      DATABSE_URL: ${{ secrets.DATABASE_URL }}
    steps:
      - uses: actions/checkout@v4
      - run: ./deploy.sh
""",
    logs={
        "build": "Build completed successfully ✓",
        "test": "All 42 tests passed ✓",
        "deploy": """\
Step 1/2: actions/checkout@v4 ✓
Step 2/2: ./deploy.sh
  Connecting to database...
  Error: Environment variable DATABASE_URL is not set.
  Expected DATABASE_URL to contain the PostgreSQL connection string.
  
  Available environment variables:
    DATABSE_URL=postgresql://...
    HOME=/home/runner
    
  Error: deploy.sh exited with code 1
  
Hint: Check that the environment variable name matches what the application expects.""",
        "config": """\
env:
  DATABSE_URL: ${{ secrets.DATABASE_URL }}""",
    },
    error_summary="Deploy failed: Environment variable DATABASE_URL is not set",
    root_cause="The environment variable is misspelled as 'DATABSE_URL' (missing 'A') — should be 'DATABASE_URL'",
    diagnosis_keywords=["typo", "misspell", "DATABSE_URL", "DATABASE_URL"],
    expected_fix_file=".github/workflows/deploy.yml",
    expected_fix="""\
    env:
      DATABASE_URL: ${{ secrets.DATABASE_URL }}""",
    fix_keywords=["DATABASE_URL"],
))

_register(Scenario(
    id="test_assertion_failure",
    name="Test assertion failure",
    description="Unit test fails due to an expected value mismatch after a code change",
    difficulty="easy",
    tasks=["log_diagnosis", "suggest_fix"],
    stage="test",
    pipeline_config="""\
name: Test Pipeline
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install -r requirements.txt
      - run: python -m pytest tests/ -v
""",
    logs={
        "build": "Dependencies installed successfully ✓",
        "test": """\
============================= test session starts ==============================
collected 15 items

tests/test_calculator.py::test_add PASSED
tests/test_calculator.py::test_subtract PASSED
tests/test_calculator.py::test_multiply PASSED
tests/test_calculator.py::test_divide FAILED
tests/test_calculator.py::test_modulo PASSED

================================= FAILURES =====================================
________________________________ test_divide ___________________________________

    def test_divide():
        calc = Calculator()
>       assert calc.divide(10, 3) == 3.33
E       AssertionError: assert 3.3333333333333335 == 3.33

tests/test_calculator.py:24: AssertionError
========================= 1 failed, 4 passed =======================================
Error: Process completed with exit code 1.""",
        "deploy": "Deploy skipped — tests failed.",
        "config": """\
# test_calculator.py (line 22-24)
def test_divide():
    calc = Calculator()
    assert calc.divide(10, 3) == 3.33""",
    },
    error_summary="Test failed: test_divide — AssertionError: 3.3333... != 3.33",
    root_cause="The test_divide assertion compares a float directly without rounding. calc.divide(10,3) returns 3.333... but test expects exactly 3.33",
    diagnosis_keywords=["float", "precision", "rounding", "divide", "3.33"],
    expected_fix_file="tests/test_calculator.py",
    expected_fix="""\
def test_divide():
    calc = Calculator()
    assert round(calc.divide(10, 3), 2) == 3.33""",
    fix_keywords=["round", "3.33", "divide"],
))

# ── Medium Scenarios ────────────────────────────────────────────────────────

_register(Scenario(
    id="version_conflict",
    name="Python package version conflict",
    description="Build fails due to incompatible package version requirements",
    difficulty="medium",
    tasks=["suggest_fix", "auto_remediate"],
    stage="build",
    pipeline_config="""\
name: CI Pipeline
on: [push]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: python -m pytest
""",
    logs={
        "build": """\
Step 3/4: pip install -r requirements.txt
  Collecting numpy==1.21.0
  Collecting pandas==2.1.0
  ERROR: Cannot install pandas==2.1.0 and numpy==1.21.0 because these package
  versions have conflicting dependencies.
  
  The conflict is caused by:
    pandas 2.1.0 depends on numpy>=1.23.2
    The user requested numpy==1.21.0
    
  To fix this you could try to:
    1. loosen the range of package versions you've specified
    2. remove the constraint on numpy
    
  ERROR: ResolutionImpossible: requirements conflict

Error: Process completed with exit code 1.""",
        "test": "Tests could not run — dependency installation failed.",
        "deploy": "Deploy skipped.",
        "config": """\
requirements.txt:
flask==3.0.0
numpy==1.21.0
pandas==2.1.0
scikit-learn==1.3.0""",
    },
    error_summary="Build failed: ResolutionImpossible — numpy==1.21.0 conflicts with pandas==2.1.0 (requires numpy>=1.23.2)",
    root_cause="numpy is pinned to 1.21.0 but pandas 2.1.0 requires numpy>=1.23.2. The numpy version must be upgraded to at least 1.23.2",
    diagnosis_keywords=["numpy", "version", "conflict", "pandas", "1.21", "1.23"],
    expected_fix_file="requirements.txt",
    expected_fix="""\
flask==3.0.0
numpy>=1.23.2
pandas==2.1.0
scikit-learn==1.3.0""",
    fix_keywords=["numpy", "1.23", "pandas"],
))

_register(Scenario(
    id="wrong_base_image",
    name="Dockerfile references non-existent base image",
    description="Docker build fails because the specified base image tag doesn't exist",
    difficulty="medium",
    tasks=["suggest_fix", "auto_remediate"],
    stage="build",
    pipeline_config="""\
name: Docker Build
on: [push]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: docker build -t myapp:latest .
""",
    logs={
        "build": """\
Step 1/2: actions/checkout@v4 ✓
Step 2/2: docker build -t myapp:latest .
  Sending build context to Docker daemon  2.048kB
  Step 1/5 : FROM python:3.11-slim-bookworm
  pull access denied for python, repository does not exist or may require 
  'docker login': denied: requested access to the resource is denied
  
  Actually, trying alternate tags...
  Step 1/5 : FROM python:3.11-slm-bookworm
  manifest for python:3.11-slm-bookworm not found: manifest unknown: 
  manifest unknown

Error: docker build failed with exit code 1.
  
Hint: The image tag 'python:3.11-slm-bookworm' does not exist. 
Check https://hub.docker.com/_/python for valid tags.""",
        "test": "Build failed — cannot run tests.",
        "deploy": "Build failed — cannot deploy.",
        "config": """\
Dockerfile:
FROM python:3.11-slm-bookworm
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "app.py"]""",
    },
    error_summary="Docker build failed: manifest for python:3.11-slm-bookworm not found",
    root_cause="The Dockerfile base image tag has a typo: 'slm' should be 'slim'. Correct tag: python:3.11-slim-bookworm",
    diagnosis_keywords=["typo", "slm", "slim", "base image", "tag", "Dockerfile"],
    expected_fix_file="Dockerfile",
    expected_fix="""\
FROM python:3.11-slim-bookworm
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "app.py"]""",
    fix_keywords=["slim-bookworm", "FROM", "python:3.11"],
))

_register(Scenario(
    id="missing_test_fixture",
    name="Missing test fixture file",
    description="Tests fail because a fixture data file referenced by tests is not included in the repo",
    difficulty="medium",
    tasks=["suggest_fix", "auto_remediate"],
    stage="test",
    pipeline_config="""\
name: Test Pipeline
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install -r requirements.txt
      - run: python -m pytest tests/ -v
""",
    logs={
        "build": "Dependencies installed successfully ✓",
        "test": """\
============================= test session starts ==============================
collected 8 items

tests/test_data_processing.py::test_load_csv FAILED
tests/test_data_processing.py::test_transform PASSED
tests/test_data_processing.py::test_validate PASSED

================================= FAILURES =====================================
_________________________ test_load_csv ________________________________________

    def test_load_csv():
        fixture_path = os.path.join("tests", "fixtures", "sample_data.csv")
>       df = load_csv(fixture_path)

tests/test_data_processing.py:12:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def load_csv(path):
>       with open(path, 'r') as f:
E       FileNotFoundError: [Errno 2] No such file or directory: 
E         'tests/fixtures/sample_data.csv'

src/data_processing.py:8: FileNotFoundError
========================= 1 failed, 2 passed =======================================
Error: Process completed with exit code 1.""",
        "deploy": "Deploy skipped — tests failed.",
        "config": """\
.gitignore includes:
*.csv
*.dat
tests/fixtures/""",
    },
    error_summary="Test failed: FileNotFoundError — tests/fixtures/sample_data.csv not found",
    root_cause="The test fixture file tests/fixtures/sample_data.csv is missing because .gitignore excludes the tests/fixtures/ directory and *.csv files",
    diagnosis_keywords=["fixture", "gitignore", "sample_data.csv", "missing", "excluded"],
    expected_fix_file=".gitignore",
    expected_fix="""\
*.dat
# Keep test fixtures tracked
!tests/fixtures/
!tests/fixtures/*.csv""",
    fix_keywords=["gitignore", "fixtures", "csv"],
))

_register(Scenario(
    id="resource_limit",
    name="Container memory limit too low",
    description="Deploy fails because the container's memory limit is set too low for the application",
    difficulty="medium",
    tasks=["suggest_fix", "auto_remediate"],
    stage="deploy",
    pipeline_config="""\
name: Deploy
on:
  push:
    branches: [main]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: docker-compose up -d
      - run: docker-compose ps
      - run: curl -f http://localhost:8080/health
""",
    logs={
        "build": "Docker image built successfully ✓",
        "test": "All tests passed ✓",
        "deploy": """\
Step 3/4: docker-compose up -d
  Creating network "app_default"
  Creating app_web_1 ...
  Creating app_web_1 ... done

Step 4/4: docker-compose ps
  Name          Command          State
  app_web_1     python app.py    Restarting (137)

  Container app_web_1 is restarting with exit code 137 (OOMKilled).
  
  Docker inspect shows:
    "OOMKilled": true
    "Memory": 67108864  (64MB limit)
    
  The application requires approximately 256MB of memory for ML model loading.

Step 5/5: curl -f http://localhost:8080/health
  curl: (7) Failed to connect to localhost port 8080: Connection refused

Error: Health check failed. Container is OOM-killed.""",
        "config": """\
docker-compose.yml:
services:
  web:
    build: .
    ports:
      - "8080:8080"
    deploy:
      resources:
        limits:
          memory: 64M""",
    },
    error_summary="Deploy failed: Container OOMKilled (exit code 137) — memory limit 64MB too low",
    root_cause="The docker-compose memory limit is set to 64MB but the application needs ~256MB for ML model loading. The limit should be increased to at least 256M",
    diagnosis_keywords=["OOM", "memory", "64M", "limit", "137"],
    expected_fix_file="docker-compose.yml",
    expected_fix="""\
services:
  web:
    build: .
    ports:
      - "8080:8080"
    deploy:
      resources:
        limits:
          memory: 512M""",
    fix_keywords=["memory", "256", "512", "limit"],
))

# ── Hard Scenarios ──────────────────────────────────────────────────────────

_register(Scenario(
    id="cascading_node_env",
    name="Cascading Node.js failures",
    description="GitHub Actions has wrong Node version, missing env var AND a test config issue — must fix all three",
    difficulty="hard",
    tasks=["auto_remediate"],
    stage="build",
    pipeline_config="""\
name: Full CI/CD
on: [push]
jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '14'
      - run: npm ci
      - run: npm test
      - run: npm run build
      - run: ./deploy.sh
        env:
          API_ENDPOINT: ${{ secrets.API_URL }}
""",
    logs={
        "build": """\
Step 2/6: actions/setup-node@v4 ✓
  Node.js 14.21.3 installed
Step 3/6: npm ci
  npm warn engine package@1.0.0: wanted node>=18 but got 14.21.3
  npm ERR! engine Unsupported engine
  npm ERR! notsup Required: {"node":">=18"}
  npm ERR! notsup Actual:  {"node":"14.21.3"}

Error: npm ci failed with exit code 1.""",
        "test": "Build failed — tests could not run.",
        "deploy": "Build failed — deploy skipped.",
        "config": """\
.github/workflows/ci.yml:
  node-version: '14'
  
deploy.sh expects: DEPLOY_API_ENDPOINT
workflow sets: API_ENDPOINT

jest.config.js:
  testTimeout: 1000  (integration tests need >=10000)""",
    },
    error_summary="Build failed: Node.js 14 unsupported (requires >=18). Additional issues: wrong env var name, low test timeout.",
    root_cause="Three issues: (1) Node.js version 14 but package requires >=18, (2) env var API_ENDPOINT should be DEPLOY_API_ENDPOINT, (3) jest testTimeout 1000ms too low for integration tests",
    diagnosis_keywords=["node", "18", "14", "version", "API_ENDPOINT", "DEPLOY_API_ENDPOINT", "timeout"],
    expected_fix_file=".github/workflows/ci.yml",
    expected_fix="""\
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
      - run: npm ci
      - run: npm test
      - run: npm run build
      - run: ./deploy.sh
        env:
          DEPLOY_API_ENDPOINT: ${{ secrets.API_URL }}""",
    fix_keywords=["node", "18", "20", "DEPLOY_API_ENDPOINT", "timeout", "10000"],
    secondary_issues=[
        {
            "file": "jest.config.js",
            "issue": "testTimeout too low",
            "fix": "testTimeout: 10000",
            "keywords": ["timeout", "10000"],
        }
    ],
))

_register(Scenario(
    id="docker_multistage_error",
    name="Docker multi-stage build broken",
    description="Multi-stage Dockerfile has a COPY --from referencing a non-existent stage, plus wrong EXPOSE port",
    difficulty="hard",
    tasks=["auto_remediate"],
    stage="build",
    pipeline_config="""\
name: Docker Build
on: [push]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: docker build -t myapp:latest .
      - run: docker run -p 3000:3000 myapp:latest
""",
    logs={
        "build": """\
Step 2/3: docker build -t myapp:latest .
  Sending build context to Docker daemon  45.2MB
  
  Step 1/8 : FROM node:20-alpine AS builder
   ---> a1b2c3d4e5f6
  Step 2/8 : WORKDIR /app
  Step 3/8 : COPY package*.json ./
  Step 4/8 : RUN npm ci --production
  
  Step 5/8 : FROM node:20-alpine AS runtime
  Step 6/8 : COPY --from=build /app/node_modules ./node_modules
  ERROR: invalid from flag value build: stage not found
  
  The COPY --from references stage 'build' but the build stage is named 'builder'.
  
  Additional issue: EXPOSE 8080 but docker run maps port 3000

Error: docker build failed with exit code 1.""",
        "test": "Build failed — cannot test.",
        "deploy": "Build failed — cannot deploy.",
        "config": """\
Dockerfile:
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci --production
COPY . .
RUN npm run build

FROM node:20-alpine AS runtime
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/dist ./dist
EXPOSE 8080
CMD ["node", "dist/index.js"]""",
    },
    error_summary="Docker build failed: COPY --from=build — stage 'build' not found (named 'builder')",
    root_cause="Two issues: (1) COPY --from=build should be COPY --from=builder (stage name mismatch), (2) EXPOSE 8080 should be EXPOSE 3000 to match the docker run port mapping",
    diagnosis_keywords=["builder", "build", "stage", "COPY", "from", "port", "EXPOSE"],
    expected_fix_file="Dockerfile",
    expected_fix="""\
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci --production
COPY . .
RUN npm run build

FROM node:20-alpine AS runtime
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/dist ./dist
EXPOSE 3000
CMD ["node", "dist/index.js"]""",
    fix_keywords=["builder", "COPY", "from", "3000", "EXPOSE"],
))

_register(Scenario(
    id="permissions_and_secrets",
    name="Deploy permission + secrets misconfiguration",
    description="Deploy fails due to missing GITHUB_TOKEN permissions AND a secret reference that doesn't exist",
    difficulty="hard",
    tasks=["auto_remediate"],
    stage="deploy",
    pipeline_config="""\
name: Deploy to GH Pages
on:
  push:
    branches: [main]
permissions: {}
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: npm ci && npm run build
      - uses: peaceiris/actions-gh-pages@v3
        with:
          github_token: ${{ secrets.GH_TOKEN }}
          publish_dir: ./dist
""",
    logs={
        "build": "Build completed successfully ✓",
        "test": "All tests passed ✓",
        "deploy": """\
Step 3/3: peaceiris/actions-gh-pages@v3
  Error: Input required and not supplied: github_token
  
  The secret GH_TOKEN is not found. Available secrets:
    - GITHUB_TOKEN (auto-provided)
    
  Error: actions-gh-pages requires push access. Check your workflow token and permissions scopes.

Error: Process completed with exit code 1.""",
        "config": """\
permissions: {}  # No permissions granted

github_token: ${{ secrets.GH_TOKEN }}  # Secret doesn't exist
# Should use: ${{ secrets.GITHUB_TOKEN }}""",
    },
    error_summary="Deploy failed: secret GH_TOKEN not found AND permissions are empty",
    root_cause="Two issues: (1) secrets.GH_TOKEN should be secrets.GITHUB_TOKEN (the auto-provided token), (2) permissions: {} grants no permissions, needs 'contents: write'",
    diagnosis_keywords=["GH_TOKEN", "GITHUB_TOKEN", "permissions", "contents", "write", "secret"],
    expected_fix_file=".github/workflows/deploy.yml",
    expected_fix="""\
permissions:
  contents: write
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: npm ci && npm run build
      - uses: peaceiris/actions-gh-pages@v3
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          publish_dir: ./dist""",
    fix_keywords=["GITHUB_TOKEN", "permissions", "contents", "write"],
))

_register(Scenario(
    id="circular_service_deps",
    name="Circular Docker Compose service dependencies",
    description="docker-compose services have circular depends_on + a healthcheck that references wrong port",
    difficulty="hard",
    tasks=["auto_remediate"],
    stage="deploy",
    pipeline_config="""\
name: Integration Test
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: docker-compose up -d
      - run: docker-compose ps
      - run: curl http://localhost:8080/api/health
""",
    logs={
        "build": "All images built successfully ✓",
        "test": "Integration tests skipped — services failed to start.",
        "deploy": """\
Step 2/4: docker-compose up -d
  ERROR: Circular dependency detected:
    service 'api' depends on 'worker'
    service 'worker' depends on 'redis'
    service 'redis' depends on 'api'
    
  This creates a cycle: api -> worker -> redis -> api
  
  Additionally, the api service healthcheck pings port 3000 but the 
  app listens on port 8080.

docker-compose up failed with exit code 1.""",
        "config": """\
docker-compose.yml:
services:
  api:
    build: ./api
    ports:
      - "8080:8080"
    depends_on:
      - worker
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3000/health"]
      
  worker:
    build: ./worker
    depends_on:
      - redis
      
  redis:
    image: redis:7-alpine
    depends_on:
      - api""",
    },
    error_summary="Deploy failed: Circular dependency detected — api → worker → redis → api",
    root_cause="Two issues: (1) Redis should not depend on api — remove depends_on from redis service to break the cycle. (2) API healthcheck pings port 3000 but app runs on 8080",
    diagnosis_keywords=["circular", "dependency", "redis", "depends_on", "port", "3000", "8080", "healthcheck"],
    expected_fix_file="docker-compose.yml",
    expected_fix="""\
services:
  api:
    build: ./api
    ports:
      - "8080:8080"
    depends_on:
      - worker
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      
  worker:
    build: ./worker
    depends_on:
      - redis
      
  redis:
    image: redis:7-alpine""",
    fix_keywords=["redis", "depends_on", "8080", "healthcheck"],
))

_register(Scenario(
    id="dns_resolution_failure",
    name="Network DNS resolution failure",
    description="Test suite fails because it attempts to connect to the wrong database hostname in docker-compose network.",
    difficulty="hard",
    tasks=["auto_remediate"],
    stage="test",
    pipeline_config="""\
name: Integration Tests
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: docker-compose -f docker-compose.test.yml up -d
      - run: sleep 5
      - run: docker-compose -f docker-compose.test.yml exec -T app npm run test:integration
""",
    logs={
        "build": "Images built successfully ✓",
        "test": """\
Step 4/4: docker-compose ... exec -T app npm run test:integration
  Running integration tests...
  
  FAIL  tests/integration/db.test.js
  ● Database Connection › should connect and run migrations
  
    SequelizeConnectionError: getaddrinfo ENOTFOUND db-primary.internal
        at ...
        at originalError (node_modules/sequelize/lib/dialects/postgres/connection-manager.js:130:17)
  
  The app is configured to connect to POSTGRES_HOST=db-primary.internal,
  but that hostname cannot be resolved in the current Docker network.

Test Suites: 1 failed, 1 total
Tests:       1 failed, 1 total
Error: Process completed with exit code 1.""",
        "deploy": "Deploy skipped.",
        "config": """\
# docker-compose.test.yml
services:
  app:
    build: .
    environment:
      - POSTGRES_HOST=db-primary.internal
      - POSTGRES_USER=test
      - POSTGRES_PASSWORD=test
    depends_on:
      - db
  
  db:
    image: postgres:15-alpine
    environment:
      - POSTGRES_USER=test
      - POSTGRES_PASSWORD=test""",
    },
    error_summary="Test failed: SequelizeConnectionError: getaddrinfo ENOTFOUND db-primary.internal",
    root_cause="The application is trying to connect to 'db-primary.internal' but the actual database service in docker-compose is named 'db'. The environment variable POSTGRES_HOST needs to be updated.",
    diagnosis_keywords=["dns", "ENOTFOUND", "db-primary.internal", "db", "hostname", "network", "POSTGRES_HOST"],
    expected_fix_file="docker-compose.test.yml",
    expected_fix="""\
services:
  app:
    build: .
    environment:
      - POSTGRES_HOST=db
      - POSTGRES_USER=test
      - POSTGRES_PASSWORD=test
    depends_on:
      - db
  
  db:
    image: postgres:15-alpine
    environment:
      - POSTGRES_USER=test
      - POSTGRES_PASSWORD=test""",
    fix_keywords=["POSTGRES_HOST=db", "environment"],
))

# ── Additional Easy/Medium Fillers ──────────────────────────────────────────

_register(Scenario(
    id="dockerfile_syntax",
    name="Dockerfile command typo",
    description="Dockerfile has a typo in the RUN command: 'pyhton' instead of 'python'",
    difficulty="easy",
    tasks=["log_diagnosis", "suggest_fix", "auto_remediate"],
    stage="build",
    pipeline_config="""\
name: Docker CI
on: [push]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: docker build -t app:test .
""",
    logs={
        "build": """\
Step 2/2: docker build -t app:test .
  Step 1/4 : FROM python:3.11-slim
   ---> abc123
  Step 2/4 : COPY . /app
   ---> def456
  Step 3/4 : RUN pyhton -m pip install -r /app/requirements.txt
   ---> Running in xyz789
  /bin/sh: 1: pyhton: not found
  The command '/bin/sh -c pyhton -m pip install -r /app/requirements.txt' 
  returned a non-zero code: 127

Error: docker build failed.""",
        "test": "Build failed.",
        "deploy": "Build failed.",
        "config": """\
Dockerfile:
FROM python:3.11-slim
COPY . /app
RUN pyhton -m pip install -r /app/requirements.txt
CMD ["python", "/app/main.py"]""",
    },
    error_summary="Docker build failed: pyhton: not found (command not found, exit code 127)",
    root_cause="Typo in Dockerfile RUN command: 'pyhton' should be 'python'",
    diagnosis_keywords=["typo", "pyhton", "python", "command not found"],
    expected_fix_file="Dockerfile",
    expected_fix="""\
FROM python:3.11-slim
COPY . /app
RUN python -m pip install -r /app/requirements.txt
CMD ["python", "/app/main.py"]""",
    fix_keywords=["python", "pip", "install"],
))

_register(Scenario(
    id="wrong_python_version",
    name="Python version incompatibility",
    description="Pipeline uses Python 3.8 but code uses match/case (Python 3.10+ feature)",
    difficulty="medium",
    tasks=["suggest_fix", "auto_remediate"],
    stage="build",
    pipeline_config="""\
name: CI Pipeline
on: [push]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.8'
      - run: pip install -r requirements.txt
      - run: python -c 'import app; print("OK")'
""",
    logs={
        "build": """\
Step 2/4: actions/setup-python@v5 ✓
  Python 3.8.18 installed
Step 3/4: pip install -r requirements.txt ✓
Step 4/4: python -c 'import app; print("OK")'
  File "app/__init__.py", line 15
    match command:
          ^
  SyntaxError: invalid syntax
  
  The match/case statement requires Python 3.10 or later.
  Current Python version: 3.8.18

Error: Process completed with exit code 1.""",
        "test": "Build failed — cannot import app.",
        "deploy": "Build failed.",
        "config": """\
python-version: '3.8'
# Code uses match/case (Python 3.10+ required)""",
    },
    error_summary="Build failed: SyntaxError at match/case statement — Python 3.8 does not support this (requires 3.10+)",
    root_cause="The CI pipeline uses Python 3.8 but the code uses match/case syntax which requires Python 3.10+. Update python-version to '3.11'",
    diagnosis_keywords=["python", "3.8", "3.10", "match", "case", "syntax", "version"],
    expected_fix_file=".github/workflows/ci.yml",
    expected_fix="""\
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'""",
    fix_keywords=["python-version", "3.10", "3.11"],
))


# ---------------------------------------------------------------------------
# Lookup helpers
# ---------------------------------------------------------------------------

def get_scenario(scenario_id: str) -> Scenario:
    """Get a scenario by its ID. Raises KeyError if not found."""
    return SCENARIOS[scenario_id]


def get_scenarios_for_task(task_name: str) -> List[Scenario]:
    """Get all scenarios valid for a given task name."""
    return [s for s in SCENARIOS.values() if task_name in s.tasks]


# Task → default scenario mapping (deterministic for reproducibility)
TASK_DEFAULT_SCENARIO = {
    "log_diagnosis": "missing_dependency",
    "suggest_fix": "version_conflict",
    "auto_remediate": "cascading_node_env",
}
