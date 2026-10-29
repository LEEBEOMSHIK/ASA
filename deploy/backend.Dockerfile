FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:0.12.19 /uv /usr/local/bin/uv
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --uid 10001 --create-home appuser
WORKDIR /app
COPY services/backend/pyproject.toml services/backend/uv.lock ./
COPY services/backend/src ./src
RUN uv sync --frozen --no-dev && mkdir -p /data/assets && chown -R appuser:appuser /data
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 LANGSMITH_TRACING=false
ENV ASA_ENVIRONMENT=production ASA_DEV_LOGIN_ENABLED=false
USER appuser
EXPOSE 8000
CMD ["uvicorn", "asa.api:app", "--host", "0.0.0.0", "--port", "8000"]
