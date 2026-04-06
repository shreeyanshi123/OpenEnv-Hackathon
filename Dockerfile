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

# Run the FastAPI server
# We use the shell form to ensure $PORT is expanded correctly
CMD uvicorn server.app:app --host 0.0.0.0 --port $PORT
