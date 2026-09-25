"""JEV-AgentBridge: a standard decision REST API over pluggable local engines."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("jev-agentbridge")
except PackageNotFoundError:
    __version__ = "0.0.0+unknown"

API_VERSION = "v1"
