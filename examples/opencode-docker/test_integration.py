#!/usr/bin/env python3
"""Test script demonstrating JEV-AgentBridge with and without OpenRouter."""

import json
import os
import sys
import time
from typing import Any

import httpx

for _sdk_path in (os.path.join(os.path.dirname(__file__), "sdk"), "/home/dev/workspace/Jev-plugin/sdk/python/src"):
    if os.path.isdir(_sdk_path):
        sys.path.insert(0, _sdk_path)
        break
from jev_agent_bridge import AgentBridgeClient


def get_env(var: str, default: str = "") -> str:
    """Get environment variable."""
    return os.getenv(var, default)


def test_hardware_capabilities() -> dict[str, Any]:
    """Report what hardware is available."""
    result = {
        "python_version": sys.version,
        "cpu_cores": os.cpu_count() or 1,
        "available": False,
    }

    try:
        import torch

        result["torch_version"] = torch.__version__
        result["cuda_available"] = torch.cuda.is_available()
        result["cpu_only"] = True
    except ImportError:
        result["torch_version"] = "not installed"

    result["available"] = True
    return result


def test_jev_local_decision() -> dict[str, Any]:
    """Test JEV-AgentBridge for discrete decision (local CPU)."""
    start = time.time()
    client = AgentBridgeClient(get_env("JEV_URL", "http://localhost:8000"))

    request = {
        "state": "Deployment of api-v2 failed due to health check timeout.",
        "question": "What should the agent do next?",
        "options": [
            {"id": "retry", "description": "Retry the deployment once"},
            {"id": "abort", "description": "Abort and notify team"},
            {"id": "escalate", "description": "Escalate to human operator"},
        ],
    }

    try:
        result = client.decide(**request)
        elapsed_ms = (time.time() - start) * 1000
        return {
            "status": "success",
            "decision_id": result["decision"]["id"],
            "selected_probability": result["selected_probability"],
            "accepted": result["accepted"],
            "latency_ms": elapsed_ms,
            "mode": result["metadata"]["mode"],
            "model": result["metadata"]["model"],
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}
    finally:
        client.close()


def test_oprouter_if_available() -> dict[str, Any]:
    """Test OpenRouter API if key is available (for comparison)."""
    api_key = get_env("OPENROUTER_API_KEY", "")
    model = get_env("OPENROUTER_MODEL", "qwen/qwen3-32b")

    if not api_key:
        return {"status": "skipped", "reason": "OPENROUTER_API_KEY not set in environment"}

    start = time.time()
    headers = {
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "http://localhost:8000",
        "X-Title": "JEV-AgentBridge Test",
    }
    data = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": "Deployment failed, what next? Options: A=retry, B=abort, C=escalate. Respond with single letter.",
            }
        ],
        "max_tokens": 10,
        "temperature": 0.0,
    }

    try:
        response = httpx.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=30.0,
        )
        response.raise_for_status()
        elapsed_ms = (time.time() - start) * 1000
        result = response.json()
        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        choice = content.strip() if content else ""

        return {
            "status": "success",
            "response": choice,
            "latency_ms": elapsed_ms,
            "model": model,
            "cost": result.get("usage", {}).get("total_tokens", 0),
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


def compare_decision_making() -> dict[str, Any]:
    """Compare JEV local decision vs OpenRouter (if available)."""
    results = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "hardware": test_hardware_capabilities(),
        "jev_local": test_jev_local_decision(),
        "openrouter": test_oprouter_if_available(),
    }

    if results["jev_local"]["status"] == "success":
        latency_jev = results["jev_local"]["latency_ms"]
        if results["openrouter"].get("status") == "success":
            latency_openrouter = results["openrouter"]["latency_ms"]
            results["comparison"] = {
                "jev_ms": latency_jev,
                "openrouter_ms": latency_openrouter,
                "speedup": f"{latency_openrouter/latency_jev:.2f}x faster" if latency_jev > 0 else "N/A",
                "cost": results["openrouter"].get("cost", 0),
                "note": "JEV uses local CPU, no API cost. OpenRouter uses remote inference with cost.",
            }
        else:
            results["comparison"] = {
                "jev_ms": latency_jev,
                "openrouter_status": results["openrouter"].get("status", "unknown"),
                "note": "OpenRouter not available (no API key or error). JEV runs locally with no external dependencies.",
            }

    return results


def main() -> int:
    """Run all tests and print results."""
    print("=" * 60)
    print("JEV-AgentBridge vs OpenRouter Comparison Test")
    print("=" * 60)

    results = compare_decision_making()
    print(json.dumps(results, indent=2, default=str))

    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"JEV Local: {results['jev_local'].get('status', 'unknown')}")
    if results['jev_local'].get('status') == 'success':
        print(f"  Decision: {results['jev_local']['decision_id']}")
        print(f"  Probability: {results['jev_local']['selected_probability']:.4f}")
        print(f"  Latency: {results['jev_local']['latency_ms']:.1f}ms")

    openrouter = results.get('openrouter', {})
    print(f"OpenRouter: {openrouter.get('status', 'unknown')}")
    if openrouter.get('status') == 'success':
        print(f"  Response: {openrouter.get('response')}")
        print(f"  Latency: {openrouter.get('latency_ms'):.1f}ms")
        print(f"  Cost (tokens): {openrouter.get('cost', 0)}")

    if 'comparison' in results:
        comp = results['comparison']
        print(f"\nJEV: {comp.get('jev_ms', 0):.1f}ms")
        if 'openrouter_ms' in comp:
            print(f"OpenRouter: {comp['openrouter_ms']:.1f}ms")
            print(f"Speedup: {comp['speedup']}")
        print(f"Note: {comp['note']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())