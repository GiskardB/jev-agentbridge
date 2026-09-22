"""Tests for the engine registry (JEV_ENGINE switch)."""

from __future__ import annotations

import pytest

from jev_cpu_agentbridge.engine import registry
from jev_cpu_agentbridge.runtime.settings import Settings


class _FakeEngine:
    pass


def test_unknown_engine_raises() -> None:
    settings = Settings(engine="does-not-exist")
    with pytest.raises(ValueError, match="Unknown JEV_ENGINE"):
        registry.create_engine(settings)


def test_create_engine_dispatches_and_marks_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeEngine()
    monkeypatch.setitem(registry._ENGINES, "fake", lambda settings: fake)

    engine = registry.create_engine(Settings(engine="fake"))

    assert engine is fake
    assert engine._ready is True


def test_known_engines_are_registered() -> None:
    assert {"semif", "laya"} <= set(registry._ENGINES)
