FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir opencode-cli httpx python-dotenv

COPY sdk/python/src/jev_agent_bridge.py ./sdk/jev_agent_bridge.py
COPY examples/opencode-docker/test_integration.py .

CMD ["python", "-m", "opencode", "--help"]