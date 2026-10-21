# DocWeave: hosted deployment (e.g. Render, Railway, Fly.io, any Docker host; see DEPLOY.md).
# Uses a hosted model API (Groq/Claude) because cloud hosts have no GPU for Ollama.
# Measured memory: about 220 MB while a run is in progress, so a 512 MB free instance is enough.

# ---- 1. build the React frontend --------------------------------------------------------
FROM node:20-slim AS web
WORKDIR /web
COPY frontend/package*.json ./
# Reproducible install when a lockfile is committed; plain install otherwise.
RUN if [ -f package-lock.json ]; then npm ci --no-audit --no-fund; else npm install --no-audit --no-fund; fi
COPY frontend/ ./
RUN npm run build

# ---- 2. Python runtime ------------------------------------------------------------------
FROM python:3.12-slim

# git is needed at run time to clone the repositories users paste in.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

# Run as an unprivileged user.
RUN useradd -m -u 1000 user
USER user
ENV PATH="/home/user/.local/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    PORT=10000 \
    PYTHONPATH=/home/user/app:/home/user/app/src \
    DOCWEAVE_PUBLIC=1 \
    DOCWEAVE_HOSTED_ONLY=1
WORKDIR /home/user/app

COPY --chown=user requirements-deploy.txt .
RUN pip install --no-cache-dir -r requirements-deploy.txt

COPY --chown=user . .
COPY --from=web --chown=user /web/dist ./frontend/dist
RUN mkdir -p workspace output/dependency_graphs

EXPOSE 10000
# GROQ_API_KEY (and optionally ANTHROPIC_API_KEY) are provided as environment variables by the host.
# The host's PORT variable, when set, overrides the default above.
CMD ["sh", "-c", "python run_web_ui.py --host 0.0.0.0 --port ${PORT}"]
