# Kev model server (https://github.com/jaredpalmer/kev) for JEV-AgentBridge's `kev` engine.
#
# Kev needs Python 3.12+ and torch < 2.9, so it runs in its own container; the bridge talks to it
# over the System One protocol (see docker-compose.kev.yml). CPU by default. For an NVIDIA GPU:
#   docker build --build-arg TORCH_INDEX_URL=https://download.pytorch.org/whl/cu128 docker/kev-server
FROM python:3.12-slim

# Kev commit to build: pinned for reproducible builds, bump deliberately.
ARG KEV_REF=62c91838b9a6adc5b386cbeae8ed73daa36ce220
ARG TORCH_INDEX_URL=https://download.pytorch.org/whl/cpu

RUN apt-get update \
 && apt-get install -y --no-install-recommends git \
 && rm -rf /var/lib/apt/lists/* \
 && pip install --no-cache-dir uv

RUN git clone https://github.com/jaredpalmer/kev.git /opt/kev \
 && git -C /opt/kev checkout ${KEV_REF}

WORKDIR /opt/kev
ENV VIRTUAL_ENV=/opt/venv PATH=/opt/venv/bin:$PATH
# torch first, from the chosen index, so Kev's install keeps it instead of pulling CUDA wheels.
RUN uv venv /opt/venv \
 && uv pip install --no-cache "torch>=2.6,<2.9" --index-url ${TORCH_INDEX_URL} \
 && uv pip install --no-cache -e ".[serve]"

COPY serve.py /opt/serve.py

# KEV_RUN: jaredpalmer/kev-0.8b (CPU), kev-4b or kev-9b (GPU), pinned to a revision for
# reproducible results (@<revision>; drop it, or bump it deliberately, for the latest weights).
ENV KEV_RUN=jaredpalmer/kev-0.8b@9a45d25eb2ab761841196625383fa1dff0e56c1e \
    KEV_HOST=0.0.0.0 \
    KEV_PORT=8009

EXPOSE 8009

# The first start downloads the weights (about 2 GB for kev-0.8b), hence the long start period.
HEALTHCHECK --interval=15s --timeout=5s --start-period=900s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8009/v1/models')" || exit 1

CMD ["python", "/opt/serve.py"]
