FROM python:3.12.10-slim
WORKDIR /app/backend
RUN apt-get update && apt-get install --no-install-recommends -y libgomp1 && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir uv==0.12.10
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
COPY src src
COPY migrations migrations
COPY alembic.ini .
RUN uv sync --locked --no-dev
ENV PATH="/app/backend/.venv/bin:$PATH" PYTHONUNBUFFERED=1
CMD ["uvicorn", "stockpilot.main:app", "--host", "0.0.0.0", "--port", "8000"]
