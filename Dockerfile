FROM python:3.11-slim-bookworm

WORKDIR /app

# Install system dependencies for healthy healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy the entire project into the container
COPY . /app/

# Install the environment and its dependencies
# Using -e . ensures meta_hackathon is in the path
# Install the environment and its dependencies
RUN pip install --no-cache-dir -e .

# Set PYTHONPATH so imports from root work reliably
ENV PYTHONPATH="/app:${PYTHONPATH:-}"

# Set a default PORT if not provided (HF Spaces provides this automatically)
ENV PORT=7860
EXPOSE 7860

# Run the FastAPI server.
# exec form is used so uvicorn is PID 1 and receives SIGTERM directly.
# The shell wrapper is only needed to expand the $PORT variable.
CMD ["sh", "-c", "exec uvicorn server.app:app --host 0.0.0.0 --port ${PORT:-7860}"]
