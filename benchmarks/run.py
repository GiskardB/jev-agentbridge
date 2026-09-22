"""Benchmark utility for JEV-CPU-AgentBridge.

Loads the configured decision engine (JEV_ENGINE, or --engine) and measures cold start
plus warm direct/shared decision latency on a fixed set of representative decisions, so
different engines can be compared on the same hardware. See docs/performance.md.

Usage:
    python -m benchmarks.run --engine semif
    python -m benchmarks.run --engine laya
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import time

from jev_cpu_agentbridge.engine.base import Option
from jev_cpu_agentbridge.engine.registry import create_engine
from jev_cpu_agentbridge.runtime.settings import Settings

SCENARIOS = [
    (
        "A deployment failed because the health check timed out.",
        "What should happen next?",
        [
            Option(id="retry", description="Retry the deployment"),
            Option(id="abort", description="Abort the deployment"),
            Option(id="escalate", description="Escalate to a human operator"),
        ],
    ),
    (
        "A customer email says: 'I was charged twice for the same order, please refund me.'",
        "Which department should handle this?",
        [
            Option(id="billing", description="Billing issues, invoices, refunds"),
            Option(id="technical", description="Bugs, outages, system errors"),
            Option(id="sales", description="Pricing and new contracts"),
        ],
    ),
    (
        "A pull request modifies authentication middleware and touches 40 files.",
        "Should this be auto-merged?",
        [
            Option(id="auto_merge", description="Safe to auto-merge"),
            Option(id="require_review", description="Requires human review"),
        ],
    ),
]


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, round(pct / 100 * (len(ordered) - 1)))
    return ordered[index]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", default=None, help="Override JEV_ENGINE (semif or laya)")
    parser.add_argument("--iterations", type=int, default=10, help="Warm iterations per scenario")
    args = parser.parse_args()

    settings = Settings.from_env()
    if args.engine:
        settings = dataclasses.replace(settings, engine=args.engine)

    print(f"Benchmarking JEV-CPU-AgentBridge — engine={settings.engine}")

    cold_started = time.perf_counter()
    engine = create_engine(settings)
    cold_start_seconds = time.perf_counter() - cold_started

    # Discard the first call: it pays one-time JIT/compilation warmup that isn't
    # representative of steady-state latency and would otherwise skew p95/max.
    warmup_state, warmup_question, warmup_options = SCENARIOS[0]
    engine.decide(
        state=warmup_state,
        question=warmup_question,
        options=warmup_options,
        min_selected_probability=None,
    )

    latencies_ms: list[float] = []
    for _ in range(args.iterations):
        for state, question, options in SCENARIOS:
            started = time.perf_counter()
            engine.decide(
                state=state,
                question=question,
                options=options,
                min_selected_probability=None,
            )
            latencies_ms.append((time.perf_counter() - started) * 1000)

    shared_started = time.perf_counter()
    engine.decide_batch(
        state="Shared benchmark state: system under evaluation.",
        decisions=[(question, options) for _, question, options in SCENARIOS],
        min_selected_probability=None,
    )
    warm_shared_seconds = time.perf_counter() - shared_started

    results = {
        "engine": settings.engine,
        "cold_start_seconds": round(cold_start_seconds, 3),
        "warm_direct_p50_ms": round(_percentile(latencies_ms, 50), 2),
        "warm_direct_p95_ms": round(_percentile(latencies_ms, 95), 2),
        "warm_direct_min_ms": round(min(latencies_ms), 2),
        "warm_direct_max_ms": round(max(latencies_ms), 2),
        "warm_shared_seconds": round(warm_shared_seconds, 3),
        "samples": len(latencies_ms),
    }

    print(json.dumps(results, indent=2))

    print("\n--- Summary ---")
    print(f"Engine: {results['engine']}")
    print(f"Cold start: {results['cold_start_seconds']:.3f}s")
    print(
        f"Warm direct p50: {results['warm_direct_p50_ms']:.1f}ms  "
        f"p95: {results['warm_direct_p95_ms']:.1f}ms"
    )
    print(f"Warm shared (batch of {len(SCENARIOS)}): {results['warm_shared_seconds']:.3f}s")


if __name__ == "__main__":
    main()
