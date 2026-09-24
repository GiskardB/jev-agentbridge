"""Maps an engine name (JEV_ENGINE) to the factory that builds its adapter.

Adding a backend = one adapter package implementing `core.ports.DecisionAdapter` with its
own config (read from its own env vars) + one entry in `_ADAPTERS`. The API, the service,
the SDKs and the response shape never change.
"""

from __future__ import annotations

from typing import Callable

from ..core.ports import DecisionAdapter


def _semif() -> DecisionAdapter:
    from .semif.adapter import SemIfAdapter, SemIfConfig

    return SemIfAdapter.from_config(SemIfConfig.from_env())


def _laya() -> DecisionAdapter:
    from .laya.adapter import LayaAdapter, LayaConfig

    return LayaAdapter.from_config(LayaConfig.from_env())


def _rizzoflow() -> DecisionAdapter:
    from .rizzoflow.adapter import RizzoFlowAdapter, RizzoFlowConfig

    return RizzoFlowAdapter.from_config(RizzoFlowConfig.from_env())


def _kev() -> DecisionAdapter:
    from .systemone.adapter import SystemOneAdapter, SystemOneConfig

    config = SystemOneConfig.from_env(
        "JEV_KEV", engine_name="kev", base_url="http://localhost:8009", model="kev-latest"
    )
    return SystemOneAdapter.from_config(config)


def _systemone() -> DecisionAdapter:
    from .systemone.adapter import SystemOneAdapter, SystemOneConfig

    return SystemOneAdapter.from_config(SystemOneConfig.from_env("JEV_SYSTEMONE"))


_ADAPTERS: dict[str, Callable[[], DecisionAdapter]] = {
    "semif": _semif,
    "laya": _laya,
    "rizzoflow": _rizzoflow,
    "kev": _kev,
    "systemone": _systemone,
}


def available_engines() -> list[str]:
    return sorted(_ADAPTERS)


def create_adapter(engine: str) -> DecisionAdapter:
    """Build the adapter registered under `engine` (lazy: only its imports are loaded)."""

    try:
        factory = _ADAPTERS[engine]
    except KeyError:
        raise ValueError(
            f"Unknown JEV_ENGINE={engine!r}. Available engines: {available_engines()}"
        ) from None
    return factory()
