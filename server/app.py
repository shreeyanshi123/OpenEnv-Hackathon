"""
FastAPI application for the CI/CD Diagnosis Environment.

Exposes the CICDEnvironment over HTTP endpoints compatible with OpenEnv clients.

Usage:
    uvicorn server.app:app --host 0.0.0.0 --port 8000
"""

import json
import os
import sys

# Ensure parent directory is in path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from openenv.core.env_server.http_server import create_app

from models import CICDAction, CICDObservation
from core.cicd_environment import CICDEnvironment

# Create the app — pass the class for per-session instances
app = create_app(
    CICDEnvironment,
    CICDAction,
    CICDObservation,
    env_name="cicd_diagnosis_env",
)


@app.get("/")
async def root():
    """Welcome page for the CI/CD Diagnosis Environment."""
    return {
        "name": "CI/CD Pipeline Diagnosis Environment",
        "description": "An OpenEnv-compliant environment for AI agent evaluation.",
        "status": "active",
        "version": "1.0.0",
        "endpoints": ["/reset", "/step", "/state", "/health"]
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


def main():
    """Entry point for direct execution."""
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
