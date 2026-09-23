"""Tests for the adapter registry (JEV_ENGINE switch)."""

from __future__ import annotations

import pytest

from jev_cpu_agentbridge.adapters import registry
from jev_cpu_agentbridge.core.ports import DecisionAdapter
from tests.conftest import FakeAdapter


def test_unknown_engine_raises() -> None:
    with pytest.raises(ValueError, match="Unknown JEV_ENGINE"):
        registry.create_adapter("does-not-exist")


def test_create_adapter_dispatches(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeAdapter()
    monkeypatch.setitem(registry._ADAPTERS, "fake", lambda: fake)
    assert registry.create_adapter("fake") is fake


def test_known_engines_are_registered() -> None:
    assert {"semif", "laya", "rizzoflow"} <= set(registry.available_engines())


def test_adapters_satisfy_the_port() -> None:
    from jev_cpu_agentbridge.adapters.laya.adapter import LayaAdapter
    from jev_cpu_agentbridge.adapters.rizzoflow.adapter import RizzoFlowAdapter
    from tests.conftest import make_adapter

    assert isinstance(make_adapter(), DecisionAdapter)
    assert isinstance(RizzoFlowAdapter(base_url="http://x"), DecisionAdapter)
    assert isinstance(LayaAdapter(agent=object(), model_name="m", subfolder=None), DecisionAdapter)
    assert isinstance(FakeAdapter(), DecisionAdapter)


def test_laya_is_the_default_engine() -> None:
    from jev_cpu_agentbridge.runtime.settings import Settings

    assert Settings().engine == "laya"
