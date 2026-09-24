"""The three JEV question types (choice, noul, score): API, service emulation and adapters."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from jev_agentbridge.adapters.laya.adapter import LayaAdapter
from jev_agentbridge.adapters.rizzoflow.adapter import RizzoFlowAdapter
from jev_agentbridge.adapters.systemone.adapter import SystemOneAdapter, SystemOneConfig
from jev_agentbridge.core.errors import InvalidDecisionError
from jev_agentbridge.core.models import Decision, Option
from jev_agentbridge.core.service import DecisionService
from jev_agentbridge.main import create_app
from jev_agentbridge.runtime.settings import Settings
from tests.conftest import FakeAdapter

ALL_TYPES = frozenset({"choice", "noul", "score"})
LEVELS = (Option("calm", "Calm"), Option("annoyed", "Annoyed"), Option("angry", "Angry"))
LEVELS_IN = [{"id": o.id, "description": o.description} for o in LEVELS]
OPTIONS_IN = [{"id": "retry", "description": "Retry"}, {"id": "abort", "description": "Abort"}]


def _client(adapter: FakeAdapter, native_types: bool = True) -> TestClient:
    return TestClient(create_app(Settings(native_types=native_types), adapter))


# --- service -----------------------------------------------------------------------------


def test_noul_is_yes_no_with_the_yes_probability() -> None:
    service = DecisionService(FakeAdapter(top=0.8), default_threshold=0.6)
    result = service.decide(state="s", decision=Decision.noul("Refund?"))
    assert result.type == "noul"
    assert result.decision.id == "yes" and result.noul == 0.8
    assert result.probabilities == {"yes": 0.8, "no": pytest.approx(0.2)}
    assert result.score is None


def test_score_expected_level_is_computed_by_the_service() -> None:
    service = DecisionService(FakeAdapter(top=0.6), default_threshold=0.6)
    result = service.decide(state="s", decision=Decision("Mood?", LEVELS, type="score"))
    assert result.decision.id == "calm"
    assert result.score == pytest.approx(0 * 0.6 + 1 * 0.2 + 2 * 0.2)
    assert result.noul is None


def test_types_the_engine_lacks_are_emulated_as_choice() -> None:
    adapter = FakeAdapter()  # choice only
    service = DecisionService(adapter, default_threshold=0.6)
    noul = service.decide(state="s", decision=Decision.noul("q"))
    score = service.decide(state="s", decision=Decision("q", LEVELS, type="score"))
    assert adapter.seen_types == ["choice", "choice"]
    assert noul.type == "noul" and noul.metadata["native_type"] is False
    assert score.type == "score" and score.metadata["native_type"] is False


def test_native_types_reach_the_adapter_unless_disabled() -> None:
    adapter = FakeAdapter(native_types=ALL_TYPES)
    DecisionService(adapter, default_threshold=0.6).decide_batch(
        state="s", decisions=[Decision.noul("a"), Decision("b", LEVELS, type="score")]
    )
    assert adapter.seen_types == ["noul", "score"]
    adapter.seen_types.clear()
    DecisionService(adapter, default_threshold=0.6, native_types=False).decide(
        state="s", decision=Decision.noul("a")
    )
    assert adapter.seen_types == ["choice"]


def test_invalid_types() -> None:
    service = DecisionService(FakeAdapter(), default_threshold=0.6)
    with pytest.raises(InvalidDecisionError):
        service.decide(state="s", decision=Decision("q", LEVELS, type="numeric"))  # type: ignore[arg-type]
    with pytest.raises(InvalidDecisionError):
        service.decide(state="s", decision=Decision("q", LEVELS[:2], type="noul"))


# --- REST API ----------------------------------------------------------------------------


def test_rest_noul_score_and_choice() -> None:
    client = _client(FakeAdapter(top=0.7))
    noul = client.post("/v1/decide", json={"type": "noul", "state": "s", "question": "Refund?"})
    assert noul.status_code == 200, noul.text
    body = noul.json()
    assert body["type"] == "noul" and body["decision"] == {"id": "yes", "description": "Yes"}
    assert body["noul"] == 0.7 and body["score"] is None
    body = {"type": "score", "state": "s", "question": "Mood?", "options": LEVELS_IN}
    score = client.post("/v1/decide", json=body).json()
    assert score["type"] == "score" and score["score"] == pytest.approx(0.45)
    choice = client.post("/v1/decide", json={"state": "s", "question": "q", "options": OPTIONS_IN})
    assert choice.json()["type"] == "choice"  # default: 0.5 clients keep working


def test_rest_noul_descriptions_become_the_options() -> None:
    body = {"type": "noul", "state": "s", "question": "Eligible?",
            "yes_description": "Meets every rule", "no_description": "Breaks one rule"}
    result = _client(FakeAdapter()).post("/v1/decide", json=body).json()
    assert result["decision"] == {"id": "yes", "description": "Meets every rule"}


@pytest.mark.parametrize(
    "body",
    [
        {"type": "noul", "state": "s", "question": "q", "options": OPTIONS_IN},
        {"type": "score", "state": "s", "question": "q"},
        {"type": "choice", "state": "s", "question": "q"},
        {"state": "s", "question": "q", "options": OPTIONS_IN, "yes_description": "y"},
        {"type": "numeric", "state": "s", "question": "q", "options": OPTIONS_IN},
    ],
)
def test_rest_type_field_mismatches_are_422(body: dict) -> None:
    r = _client(FakeAdapter()).post("/v1/decide", json=body)
    assert r.status_code == 422 and r.json()["error"]["code"] == "INVALID_REQUEST"


def test_rest_mixed_batch_and_info() -> None:
    adapter = FakeAdapter(native_types=frozenset({"choice", "noul"}))
    client = _client(adapter)
    r = client.post("/v1/decide/batch", json={
        "state": "s",
        "decisions": [
            {"type": "noul", "question": "a?"},
            {"type": "score", "question": "b?", "options": LEVELS_IN},
            {"question": "c?", "options": OPTIONS_IN},
        ],
    })
    results = r.json()["decisions"]
    assert [d["type"] for d in results] == ["noul", "score", "choice"]
    assert [d["metadata"]["native_type"] for d in results] == [True, False, True]
    assert adapter.batch_calls == 1
    info = client.get("/v1/info").json()
    assert info["supported_types"] == ["choice", "noul", "score"]
    assert info["engine"]["native_types"] == ["choice", "noul"]
    emulated = _client(adapter, native_types=False).get("/v1/info").json()
    assert emulated["engine"]["native_types"] == ["choice"]


# --- adapters: native mapping ------------------------------------------------------------


class _LayaAgent:
    def __init__(self) -> None:
        self.questions: dict = {}

    def predict(self, state, questions):
        self.questions = questions
        answers = {}
        for key, q in questions.items():
            if q["type"] == "noul":
                answers[key] = {"type": "noul", "noul": 0.9, "confidence": 0.9}
            elif q["type"] == "score":
                answers[key] = {"type": "score", "score": 1.2, "confidence": 0.5,
                                "probabilities": {"0": 0.1, "1": 0.6, "2": 0.3}}
        return {"answers": answers}


def test_laya_native_noul_and_score() -> None:
    agent = _LayaAgent()
    service = DecisionService(LayaAdapter(agent=agent, model_name="laya", subfolder=None),
                              default_threshold=0.6)
    noul, score = service.decide_batch(
        state="s", decisions=[Decision.noul("Refund?"), Decision("Mood?", LEVELS, type="score")]
    )
    assert agent.questions["0"] == {"type": "noul", "instructions": "Refund?"}
    assert agent.questions["1"]["criteria"] == ["Calm", "Annoyed", "Angry"]
    assert noul.decision.id == "yes" and noul.noul == 0.9
    assert noul.metadata["native_type"] is True
    assert score.decision.id == "annoyed" and score.score == pytest.approx(1.2)


class _Response:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload).encode()

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None


def _mock_http(monkeypatch: pytest.MonkeyPatch, module: str, payload: dict) -> list:
    sent: list = []

    def fake(request, timeout=None):
        sent.append(json.loads(request.data))
        return _Response(payload)

    monkeypatch.setattr(f"jev_agentbridge.adapters.{module}.adapter.urllib.request.urlopen", fake)
    return sent


def test_systemone_native_noul_and_score(monkeypatch: pytest.MonkeyPatch) -> None:
    sent = _mock_http(monkeypatch, "systemone", {"answers": {
        "q0": {"type": "noul", "noul": 0.3},
        "q1": {"type": "score", "score": 1.8, "confidence": 0.7,
               "probabilities": {"0": 0.05, "1": 0.1, "2": 0.85}},
    }})
    service = DecisionService(SystemOneAdapter(SystemOneConfig(engine_name="kev")),
                              default_threshold=0.6)
    noul, score = service.decide_batch(state="s", decisions=[
        Decision.noul("Eligible?", yes_description="Meets the rules"),
        Decision("Mood?", LEVELS, type="score"),
    ])
    questions = sent[0]["questions"]
    assert questions["q0"] == {"type": "noul", "instructions": "Eligible?",
                               "criteria": {"true": "Meets the rules", "false": "No"}}
    assert questions["q1"] == {"type": "score", "instructions": "Mood?",
                               "criteria": ["Calm", "Annoyed", "Angry"]}
    assert noul.decision.id == "no" and noul.noul == 0.3
    assert score.decision.id == "angry" and score.score == pytest.approx(1.8)


def test_systemone_plain_noul_sends_no_criteria(monkeypatch: pytest.MonkeyPatch) -> None:
    sent = _mock_http(monkeypatch, "systemone", {"answers": {
        "decision": {"type": "noul", "noul": 0.9}}})
    SystemOneAdapter(SystemOneConfig()).score(state="s", decision=Decision.noul("Refund?"))
    assert sent[0]["questions"]["decision"] == {"type": "noul", "instructions": "Refund?"}


def test_rizzoflow_native_boolean_and_score(monkeypatch: pytest.MonkeyPatch) -> None:
    sent = _mock_http(monkeypatch, "rizzoflow", {"answers": {
        "0": {"status": "ok", "probabilities": {"false": 0.2, "true": 0.8, "__insufficient__": 0}},
        "1": {"status": "ok", "probabilities": {"0": 0.7, "1": 0.2, "2": 0.1}},
    }})
    service = DecisionService(RizzoFlowAdapter(base_url="http://r"), default_threshold=0.6)
    noul, score = service.decide_batch(state="s", decisions=[
        Decision.noul("Refund?"), Decision("Mood?", LEVELS, type="score")])
    questions = sent[0]["questions"]
    assert questions["0"]["type"] == "boolean" and "true_description" not in questions["0"]
    assert questions["1"]["levels"] == ["Calm", "Annoyed", "Angry"]
    assert noul.decision.id == "yes" and noul.noul == 0.8
    assert score.decision.id == "calm" and score.score == pytest.approx(0.4)


def test_native_types_can_be_enabled_per_type(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = FakeAdapter(native_types=ALL_TYPES)
    service = DecisionService(adapter, default_threshold=0.6, native_types={"noul"})
    decisions = [Decision.noul("a"), Decision("b", LEVELS, type="score")]
    service.decide_batch(state="s", decisions=decisions)
    assert adapter.seen_types == ["noul", "choice"]
    for value, expected in [("", False), ("false", False), ("all", True), ("true", True),
                            ("noul", frozenset({"noul"})),
                            ("noul, score", frozenset({"noul", "score"}))]:
        monkeypatch.setenv("JEV_NATIVE_TYPES", value)
        assert Settings.from_env().native_types == expected
    monkeypatch.delenv("JEV_NATIVE_TYPES")
    assert Settings.from_env().native_types is False  # emulated by default
