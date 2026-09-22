FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY src/ ./src/
COPY benchmarks/ ./benchmarks/

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=90s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uv", "run", "python", "-m", "uvicorn", "jev_cpu_agentbridge.main:app", "--host", "0.0.0.0", "--port", "8000"]
