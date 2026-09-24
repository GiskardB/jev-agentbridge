"""Accuracy evaluation against a running Bridge, for any engine.

Latency benchmarks say how fast an engine is; this says how often it is right, and which
threshold to use when JEV sits in front of an LLM as a gate (accepted -> use JEV's answer,
not accepted -> fall back to the LLM).

Dataset: JSONL, one labelled decision per line:
    {"state": "...", "question": "...", "options": [{"id": ..., "description": ...}],
     "expected": "<option id>"}

Usage:
    jev-eval --dataset examples/eval/sample.jsonl --url http://localhost:8000
    python -m jev_agentbridge.evaluation --dataset data.jsonl --target-accuracy 0.97

For each threshold it reports coverage (share of decisions JEV would answer on its own)
and accuracy on those accepted decisions. The recommended threshold is the lowest one
whose accepted accuracy reaches --target-accuracy, i.e. the one with the most coverage.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from typing import Any, Iterable

DEFAULT_THRESHOLDS = tuple(round(0.5 + 0.05 * i, 2) for i in range(10))  # 0.50 .. 0.95


@dataclass(frozen=True)
class Prediction:
    expected: str
    predicted: str
    probability: float
    latency_ms: float | None = None

    @property
    def correct(self) -> bool:
        return self.expected == self.predicted


@dataclass(frozen=True)
class ThresholdRow:
    threshold: float
    coverage: float
    accepted: int
    accuracy_accepted: float | None


def load_dataset(path: str) -> list[dict[str, Any]]:
    rows = []
    with open(path, encoding="utf-8") as handle:
        for number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            missing = {"state", "question", "options", "expected"} - row.keys()
            if missing:
                raise ValueError(f"{path}:{number}: missing fields {sorted(missing)}")
            if row["expected"] not in {option["id"] for option in row["options"]}:
                raise ValueError(f"{path}:{number}: expected {row['expected']!r} is not an option")
            rows.append(row)
    return rows


def _post(url: str, body: dict[str, Any], timeout: float) -> dict[str, Any]:
    request = urllib.request.Request(
        f"{url.rstrip('/')}/v1/decide",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"{error.code}: {error.read().decode(errors='replace')}") from error


def predict(rows: Iterable[dict[str, Any]], *, url: str, timeout: float) -> list[Prediction]:
    predictions = []
    for row in rows:
        body = {"state": row["state"], "question": row["question"], "options": row["options"]}
        result = _post(url, body, timeout)
        predictions.append(
            Prediction(
                expected=row["expected"],
                predicted=result["decision"]["id"],
                probability=float(result["selected_probability"]),
                latency_ms=result.get("metadata", {}).get("latency_ms"),
            )
        )
    return predictions


def summarize(
    predictions: list[Prediction],
    *,
    thresholds: Iterable[float] = DEFAULT_THRESHOLDS,
    target_accuracy: float = 0.97,
) -> dict[str, Any]:
    total = len(predictions)
    if total == 0:
        raise ValueError("No predictions to summarize")
    rows = []
    for threshold in sorted(thresholds):
        accepted = [p for p in predictions if p.probability >= threshold]
        rows.append(
            ThresholdRow(
                threshold=threshold,
                coverage=round(len(accepted) / total, 4),
                accepted=len(accepted),
                accuracy_accepted=(
                    round(sum(p.correct for p in accepted) / len(accepted), 4)
                    if accepted
                    else None
                ),
            )
        )
    recommended = next(
        (
            row
            for row in rows
            if row.accuracy_accepted is not None and row.accuracy_accepted >= target_accuracy
        ),
        None,
    )
    latencies = sorted(p.latency_ms for p in predictions if p.latency_ms is not None)
    return {
        "samples": total,
        "accuracy_overall": round(sum(p.correct for p in predictions) / total, 4),
        "target_accuracy": target_accuracy,
        "recommended_threshold": recommended.threshold if recommended else None,
        "recommended_coverage": recommended.coverage if recommended else None,
        "latency_p50_ms": latencies[len(latencies) // 2] if latencies else None,
        "thresholds": [asdict(row) for row in rows],
    }


def _print_table(summary: dict[str, Any]) -> None:
    print(f"\nSamples: {summary['samples']}  overall accuracy: {summary['accuracy_overall']:.1%}")
    print(f"{'threshold':>9}  {'coverage':>8}  {'accepted':>8}  {'acc. accepted':>13}")
    for row in summary["thresholds"]:
        accuracy = row["accuracy_accepted"]
        print(
            f"{row['threshold']:>9.2f}  {row['coverage']:>8.1%}  {row['accepted']:>8}  "
            f"{'-' if accuracy is None else f'{accuracy:.1%}':>13}"
        )
    if summary["recommended_threshold"] is None:
        print(
            f"\nNo threshold reaches {summary['target_accuracy']:.0%} accuracy on accepted "
            "decisions: keep the LLM for this decision type."
        )
    else:
        print(
            f"\nRecommended threshold: {summary['recommended_threshold']:.2f} -> JEV answers "
            f"{summary['recommended_coverage']:.1%} of decisions on its own at "
            f">= {summary['target_accuracy']:.0%} accuracy."
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--dataset", required=True, help="Labelled JSONL file")
    parser.add_argument("--url", default="http://localhost:8000", help="Bridge base URL")
    parser.add_argument("--target-accuracy", type=float, default=0.97)
    parser.add_argument("--timeout", type=float, default=60.0, help="Per-request seconds")
    parser.add_argument("--json", action="store_true", help="Print only the JSON summary")
    args = parser.parse_args(argv)

    predictions = predict(load_dataset(args.dataset), url=args.url, timeout=args.timeout)
    summary = summarize(predictions, target_accuracy=args.target_accuracy)
    print(json.dumps(summary, indent=2))
    if not args.json:
        _print_table(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
