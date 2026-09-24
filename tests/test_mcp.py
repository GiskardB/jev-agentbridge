"""MCP layer tests: the tools call the same DecisionService as the REST API."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from jev_agentbridge.main import create_app
from jev_agentbridge.runtime.settings import Settings
from tests.conftest import FakeAdapter

HEADERS = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
OPTIONS = [{"id": "retry", "description": "Retry"}, {"id": "abort", "description": "Abort"}]


def _rpc(client: TestClient, method: str, params: dict | None = None, id_: int = 1) -> dict:
    body = {"jsonrpc": "2.0", "id": id_, "method": method, "params": params or {}}
    response = client.post("/mcp", headers=HEADERS, json=body)
    assert response.status_code == 200, response.text
    return response.json()


def _call(client: TestClient, name: str, arguments: dict) -> dict:
    return _rpc(client, "tools/call", {"name": name, "arguments": arguments})["result"]


def _client(adapter: FakeAdapter | None = None) -> TestClient:
    app = create_app(Settings(min_selected_probability=0.6), adapter or FakeAdapter())
    return TestClient(app, base_url="http://localhost:8000")  # MCP checks the Host header


def test_initialize_and_list_tools() -> None:
    with _client() as client:
        init = _rpc(client, "initialize", {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "0"},
        })["result"]
        assert init["serverInfo"]["name"] == "jev-agentbridge"
        assert "accepted" in init["instructions"]
        tools = {t["name"]: t for t in _rpc(client, "tools/list", id_=2)["result"]["tools"]}
        assert set(tools) == {"jev_decide", "jev_decide_batch", "jev_info"}
        assert tools["jev_decide"]["annotations"]["readOnlyHint"] is True
        assert "options" in tools["jev_decide"]["inputSchema"]["properties"]


def test_decide_matches_the_rest_contract() -> None:
    with _client(FakeAdapter(top=0.7)) as client:
        result = _call(client, "jev_decide", {
            "state": {"deploy": "failed"},
            "question": "Next?",
            "options": OPTIONS,
            "min_selected_probability": 0.9,
        })
        assert result.get("isError") is not True
        payload = result.get("structuredContent") or json.loads(result["content"][0]["text"])
        assert payload["decision"]["id"] == "retry"
        assert payload["accepted"] is False and payload["threshold"] == 0.9
        assert payload["metadata"]["engine"] == "fake"
        body = {"state": {"deploy": "failed"}, "question": "Next?", "options": OPTIONS,
                "min_selected_probability": 0.9}
        rest = client.post("/v1/decide", json=body)
        assert rest.json()["probabilities"] == payload["probabilities"]


def test_batch_and_info() -> None:
    with _client() as client:
        batch = _call(client, "jev_decide_batch", {
            "state": "s",
            "decisions": [{"question": "a?", "options": OPTIONS},
                          {"question": "b?", "options": OPTIONS, "min_selected_probability": 0.95}],
        })
        payload = batch.get("structuredContent") or json.loads(batch["content"][0]["text"])
        assert [d["accepted"] for d in payload["decisions"]] == [True, False]
        info = _call(client, "jev_info", {})
        info = info.get("structuredContent") or json.loads(info["content"][0]["text"])
        assert info["engine"]["name"] == "fake" and info["api_version"] == "v1"


def test_engine_errors_become_tool_errors() -> None:
    adapter = FakeAdapter()
    adapter.error = RuntimeError("boom")
    with _client(adapter) as client:
        result = _call(client, "jev_decide", {"state": "s", "question": "q", "options": OPTIONS})
        assert result["isError"] is True
        assert "ENGINE_ERROR" in result["content"][0]["text"]


def test_mcp_can_be_disabled() -> None:
    app = create_app(Settings(mcp_enabled=False), FakeAdapter())
    with TestClient(app, base_url="http://localhost:8000") as client:
        assert client.post("/mcp", headers=HEADERS, json={}).status_code == 404


def test_foreign_host_rejected_when_bound_to_localhost() -> None:
    with TestClient(create_app(Settings(host="127.0.0.1"), FakeAdapter())) as client:
        response = client.post("/mcp", headers=HEADERS, json={})
        assert response.status_code == 421  # Host "testserver" is not localhost
