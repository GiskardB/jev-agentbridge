"""Selects a DecisionEngine implementation from Settings.engine (JEV_ENGINE).

Adding a new backend means adding one entry to `_ENGINES` — the API layer never changes.
"""

from __future__ import annotations

from typing import Callable

from ..runtime.settings import Settings
from .base import DecisionEngine


def _load_semif(settings: Settings) -> DecisionEngine:
    from ..runtime.model_loader import ModelLoader
    from .semif import SemIfEngine

    loaded = ModelLoader(settings).load()
    return SemIfEngine(
        model=loaded.model,
        tokenizer=loaded.tokenizer,
        model_name=settings.model_name,
        model_revision=settings.model_revision,
        max_input_tokens=settings.max_input_tokens,
        min_selected_probability=settings.min_selected_probability,
    )


def _load_laya(settings: Settings) -> DecisionEngine:
    from .laya import LayaEngine

    return LayaEngine(
        model_name=settings.laya_model_name,
        subfolder=settings.laya_subfolder,
        device=settings.model_device,
        min_selected_probability=settings.min_selected_probability,
    )


def _load_rizzoflow(settings: Settings) -> DecisionEngine:
    from .rizzoflow import RizzoFlowEngine

    return RizzoFlowEngine(
        base_url=settings.rizzoflow_url,
        min_selected_probability=settings.min_selected_probability,
    )


_ENGINES: dict[str, Callable[[Settings], DecisionEngine]] = {
    "semif": _load_semif,
    "laya": _load_laya,
    "rizzoflow": _load_rizzoflow,
}


def create_engine(settings: Settings) -> DecisionEngine:
    """Instantiate the engine selected by `settings.engine` (env: JEV_ENGINE)."""

    try:
        loader = _ENGINES[settings.engine]
    except KeyError:
        raise ValueError(
            f"Unknown JEV_ENGINE={settings.engine!r}. Available engines: {sorted(_ENGINES)}"
        ) from None
    engine = loader(settings)
    engine._ready = True  # noqa: SLF001
    return engine
