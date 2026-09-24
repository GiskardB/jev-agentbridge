"""Start `kev.serve` listening on KEV_HOST instead of 127.0.0.1.

kev.serve hard-codes host="127.0.0.1", which no other container can reach. This wrapper
overrides the host passed to uvicorn, then runs Kev's own entry point unchanged.
"""

import os
import sys

import uvicorn

_uvicorn_run = uvicorn.run


def _run(app, **kwargs):
    kwargs["host"] = os.environ.get("KEV_HOST", "0.0.0.0")
    return _uvicorn_run(app, **kwargs)


uvicorn.run = _run
sys.argv = [
    "kev.serve",
    "--run", os.environ.get("KEV_RUN", "jaredpalmer/kev-0.8b"),
    "--port", os.environ.get("KEV_PORT", "8009"),
]

from kev.serve import main  # noqa: E402  (after the patch on purpose)

main()
