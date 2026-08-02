# syntax=docker/dockerfile:1.7

ARG PYTHON_VERSION=3.11
ARG UAI_FORGE_WORKSPACE_TOOLS=0
FROM python:${PYTHON_VERSION}-slim AS runtime

ARG UAI_FORGE_WORKSPACE_TOOLS=0

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    UAI_FORGE_HOST=0.0.0.0 \
    UAI_FORGE_PORT=8000 \
    UAI_FORGE_DATABASE_PATH=/data/forge.db

WORKDIR /app

RUN addgroup --system --gid 10001 uai && \
    adduser --system --uid 10001 --ingroup uai --home /nonexistent --no-create-home uai

COPY pyproject.toml README.md ./
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install .

# The local development Compose profile can opt into the fixed Git/pytest
# commands exposed by tool.workspace.  The production/default image does not
# need these tools and keeps the smaller runtime surface.
RUN if [ "$UAI_FORGE_WORKSPACE_TOOLS" = "1" ]; then \
      apt-get update && \
      apt-get install -y --no-install-recommends git && \
      rm -rf /var/lib/apt/lists/* && \
      python -m pip install --no-cache-dir pytest==8.3.5 pytest-asyncio==0.25.3; \
    fi

# The marker makes Docker initialize a new named volume with the correct owner.
RUN mkdir -p /data && touch /data/.uai-forge-volume && chown -R uai:uai /data

USER uai
VOLUME ["/data"]
EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 CMD ["python", "-c", "import os, urllib.request; port = os.environ.get('UAI_FORGE_PORT', '8000'); urllib.request.urlopen(f'http://127.0.0.1:{port}/health', timeout=2).read()"]

CMD ["uai-forge", "serve"]
