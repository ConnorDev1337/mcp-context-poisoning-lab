# Harness image. Pin to a digest for production use; a tag is kept here so the
# lab builds offline from a local base image.
FROM python:3.12-slim-bookworm

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY lab ./lab
RUN pip install --no-cache-dir -e ".[services,agent,plot]"

ENV MCPLAB_SCENARIOS=/app/lab/scenarios
# Default command: the deterministic mock demo, so `docker compose up` produces a
# report with no model and no network. Override to run a real backend.
CMD ["mcplab", "demo", "--out-dir", "/runs"]
