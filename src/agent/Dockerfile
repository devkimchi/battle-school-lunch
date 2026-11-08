# syntax=docker/dockerfile:1.7

ARG PYTHON_VERSION=3.12
FROM python:${PYTHON_VERSION}-slim-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    COPILOT_CLI_EXTRACT_DIR=/opt/copilot-sdk-runtime

RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates \
 && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.11.32 /uv /usr/local/bin/uv

WORKDIR /app

COPY agent/pyproject.toml agent/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY agent/app ./app
COPY agent/instructions ./instructions
COPY agent/.generated/EVALUATION-RUBRIC.md ./EVALUATION-RUBRIC.md
RUN uv sync --frozen --no-dev
RUN /app/.venv/bin/python -m copilot download-runtime \
 && /app/.venv/bin/python -c "from pathlib import Path; from copilot._cli_download import ensure_runtime_wrapper; p=Path(ensure_runtime_wrapper()); assert p.is_file() and p.stat().st_size > 0; assert (p.parent / 'runtime.node').is_file() and (p.parent / '.hostless-runtime-assets-v2').is_file()"

FROM python:${PYTHON_VERSION}-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:${PATH}" \
    HOME=/home/appuser \
    COPILOT_CLI_EXTRACT_DIR=/opt/copilot-sdk-runtime \
    COPILOT_SKIP_CLI_DOWNLOAD=1 \
    PORT=8000

RUN groupadd --system --gid 10001 appuser \
 && useradd --system --uid 10001 --gid appuser \
      --home-dir /home/appuser --shell /usr/sbin/nologin appuser \
 && install -d -o appuser -g appuser /home/appuser /home/appuser/.copilot /app/.copilot-runtime

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/app /app/app
COPY --from=builder /app/instructions /app/instructions
COPY --from=builder /app/EVALUATION-RUBRIC.md /app/EVALUATION-RUBRIC.md
COPY --from=builder /opt/copilot-sdk-runtime /opt/copilot-sdk-runtime
RUN chmod -R a+rX /opt/copilot-sdk-runtime

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import os,urllib.request,sys; \
        url=f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8000\")}/health'; \
        sys.exit(0 if urllib.request.urlopen(url, timeout=3).status==200 else 1)"

CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
