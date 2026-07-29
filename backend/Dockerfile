# syntax=docker/dockerfile:1.7

ARG PYTHON_VERSION=3.11
FROM python:${PYTHON_VERSION}-slim AS runtime

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

# The marker makes Docker initialize a new named volume with the correct owner.
RUN mkdir -p /data && touch /data/.uai-forge-volume && chown -R uai:uai /data

USER uai
VOLUME ["/data"]
EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2).read()"]

CMD ["uai-forge", "serve"]
