"""Model-routing evaluation for JEV-AgentBridge. Standard library only (Python 3.9+).

Runs a labelled dataset through a running Bridge (any engine), or scores predictions made by
something else (e.g. an LLM baseline), and writes comparable results.

    python run_eval.py run    --url http://localhost:8000 --label laya-en
    python run_eval.py score  --predictions results/llm.predictions.jsonl --label llm-baseline
    python run_eval.py report

Outputs, under --out-dir (default: results/ next to this script):
    <label>.predictions.jsonl  one line per request: id, lang, expected, predicted, probability, ...
    <label>.summary.json       accuracy, per-language accuracy, confusion matrix, threshold table
    REPORT.md                  written by `report`, one comparison table over every summary

See INSTRUCTIONS.md for the full procedure.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_DATASET = HERE / "model_routing.jsonl"
DEFAULT_OUT = HERE / "results"
THRESHOLDS = [round(0.5 + 0.05 * i, 2) for i in range(10)]  # 0.50 .. 0.95
CONFIDENT = 0.8  # errors at or above this probability are listed as "confident errors"


def load_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def http_json(url: str, body: dict | None = None, timeout: float = 60.0) -> dict:
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="GET" if body is None else "POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read())


def wait_ready(url: str, wait_seconds: int) -> dict:
    deadline = time.monotonic() + wait_seconds
    last_error = ""
    while time.monotonic() < deadline:
        try:
            return http_json(f"{url}/ready", timeout=5)
        except (urllib.error.URLError, OSError, ValueError) as error:
            last_error = str(error)
            time.sleep(3)
    raise SystemExit(f"Bridge at {url} not ready after {wait_seconds}s: {last_error}")


def summarize(predictions: list[dict], target_accuracy: float) -> dict:
    ok = [p for p in predictions if p.get("predicted") is not None]
    total = len(ok)
    if total == 0:
        raise SystemExit("No successful predictions to summarize")

    def accuracy(rows: list[dict]) -> float | None:
        return (
            round(sum(r["predicted"] == r["expected"] for r in rows) / len(rows), 4)
            if rows
            else None
        )

    labels = sorted({p["expected"] for p in ok} | {p["predicted"] for p in ok})
    confusion = {e: {p: 0 for p in labels} for e in labels}
    for row in ok:
        confusion[row["expected"]][row["predicted"]] += 1

    table = []
    for threshold in THRESHOLDS:
        accepted = [p for p in ok if p["probability"] >= threshold]
        table.append(
            {
                "threshold": threshold,
                "coverage": round(len(accepted) / total, 4),
                "accepted": len(accepted),
                "accuracy_accepted": accuracy(accepted),
            }
        )
    recommended = next(
        (
            r
            for r in table
            if r["accuracy_accepted"] is not None and r["accuracy_accepted"] >= target_accuracy
        ),
        None,
    )
    latencies = sorted(p["latency_ms"] for p in ok if p.get("latency_ms") is not None)
    confident_errors = sorted(
        (
            {k: p.get(k) for k in ("id", "expected", "predicted", "probability", "state")}
            for p in ok
            if p["predicted"] != p["expected"] and p["probability"] >= CONFIDENT
        ),
        key=lambda e: -e["probability"],
    )
    return {
        "samples": total,
        "failed_requests": len(predictions) - total,
        "accuracy_overall": accuracy(ok),
        "accuracy_by_lang": {
            lang: accuracy([p for p in ok if p.get("lang") == lang])
            for lang in sorted({p.get("lang") for p in ok if p.get("lang")})
        },
        "accuracy_by_class": {
            label: accuracy([p for p in ok if p["expected"] == label]) for label in labels
        },
        "confusion_matrix": confusion,
        "target_accuracy": target_accuracy,
        "recommended_threshold": recommended["threshold"] if recommended else None,
        "recommended_coverage": recommended["coverage"] if recommended else None,
        "latency_p50_ms": latencies[len(latencies) // 2] if latencies else None,
        "latency_p95_ms": latencies[int(len(latencies) * 0.95)] if latencies else None,
        "thresholds": table,
        "confident_errors": confident_errors,
    }


def save(out_dir: Path, label: str, predictions: list[dict], summary: dict, meta: dict) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(out_dir / f"{label}.predictions.jsonl", predictions)
    summary = {"label": label, **meta, **summary}
    (out_dir / f"{label}.summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(
        json.dumps(
            {k: v for k, v in summary.items() if k not in ("thresholds", "confident_errors")},
            indent=2,
            ensure_ascii=False,
        )
    )
    print(f"\nWrote {out_dir / (label + '.summary.json')}")


def cmd_run(args: argparse.Namespace) -> None:
    url = args.url.rstrip("/")
    ready = wait_ready(url, args.wait_seconds)
    info = http_json(f"{url}/v1/info")
    print(f"Bridge ready: engine={info['engine']['name']} model={info['engine']['model']}")
    rows = load_jsonl(Path(args.dataset))
    if args.limit:
        rows = rows[: args.limit]

    predictions = []
    started = time.monotonic()
    for index, row in enumerate(rows, start=1):
        body = {"state": row["state"], "question": row["question"], "options": row["options"]}
        record = {
            "id": row.get("id"),
            "lang": row.get("lang"),
            "expected": row["expected"],
            "state": row["state"],
        }
        try:
            result = http_json(f"{url}/v1/decide", body, timeout=args.timeout)
            record.update(
                predicted=result["decision"]["id"],
                probability=float(result["selected_probability"]),
                probabilities=result["probabilities"],
                latency_ms=result["metadata"].get("latency_ms"),
            )
        except (urllib.error.URLError, OSError, KeyError, ValueError) as error:
            detail = (
                error.read().decode("utf-8", "replace")
                if isinstance(error, urllib.error.HTTPError)
                else str(error)
            )
            record.update(predicted=None, probability=None, error=detail[:500])
        predictions.append(record)
        if index % 20 == 0 or index == len(rows):
            print(f"  {index}/{len(rows)} done ({time.monotonic() - started:.0f}s)")

    meta = {
        "source": "bridge",
        "url": url,
        "engine": info["engine"],
        "bridge_version": info.get("version"),
        "ready": ready,
        "dataset": str(Path(args.dataset).name),
        "wall_seconds": round(time.monotonic() - started, 1),
    }
    save(
        Path(args.out_dir),
        args.label,
        predictions,
        summarize(predictions, args.target_accuracy),
        meta,
    )


def cmd_score(args: argparse.Namespace) -> None:
    predictions = load_jsonl(Path(args.predictions))
    dataset = {row["id"]: row for row in load_jsonl(Path(args.dataset))}
    for record in predictions:
        truth = dataset.get(record["id"])
        if truth is None:
            raise SystemExit(f"Prediction id {record['id']!r} is not in the dataset")
        record.setdefault("expected", truth["expected"])
        record.setdefault("lang", truth.get("lang"))
        record.setdefault("state", truth["state"])
        # Sources without a confidence (e.g. an LLM answering with a label) count as certain.
        if record.get("predicted") is not None and record.get("probability") is None:
            record["probability"] = 1.0
    missing = sorted(set(dataset) - {r["id"] for r in predictions})
    meta = {"source": "external", "dataset": Path(args.dataset).name, "missing_ids": missing}
    save(
        Path(args.out_dir),
        args.label,
        predictions,
        summarize(predictions, args.target_accuracy),
        meta,
    )


def cmd_report(args: argparse.Namespace) -> None:
    out_dir = Path(args.out_dir)
    summaries = [
        json.loads(p.read_text(encoding="utf-8")) for p in sorted(out_dir.glob("*.summary.json"))
    ]
    if not summaries:
        raise SystemExit(f"No *.summary.json in {out_dir}")

    def pct(value: float | None) -> str:
        return "-" if value is None else f"{value:.1%}"

    def dash(value: object) -> str:
        return "-" if value is None else str(value)

    langs = sorted({lang for s in summaries for lang in s["accuracy_by_lang"]})
    classes = sorted({c for s in summaries for c in s["accuracy_by_class"]})
    header = ["Run", "Samples", "Failed", "Accuracy"]
    header += [f"Acc. {lang}" for lang in langs] + [f"Acc. {c}" for c in classes]
    header += ["Rec. threshold", "Coverage at rec.", "p50 ms"]
    lines = [
        "# Model routing evaluation",
        "",
        f"Generated {time.strftime('%Y-%m-%d %H:%M')}. Dataset: `{summaries[0].get('dataset')}`.",
        "",
        "| " + " | ".join(header) + " |",
        "|" + "---|" * len(header),
    ]
    for s in summaries:
        cells = [s["label"], s["samples"], s["failed_requests"], pct(s["accuracy_overall"])]
        cells += [pct(s["accuracy_by_lang"].get(lang)) for lang in langs]
        cells += [pct(s["accuracy_by_class"].get(c)) for c in classes]
        cells += [
            dash(s["recommended_threshold"]),
            pct(s["recommended_coverage"]),
            dash(s["latency_p50_ms"]),
        ]
        lines.append("| " + " | ".join(str(cell) for cell in cells) + " |")
    target = summaries[0]["target_accuracy"]
    lines += [
        "",
        f"Recommended threshold = lowest threshold whose accuracy on accepted decisions is "
        f">= {target:.0%}; coverage = share of requests JEV would route on its own.",
        "",
    ]
    for s in summaries:
        lines += [
            f"## {s['label']}",
            "",
            "Confusion matrix (rows = expected, columns = predicted):",
            "",
        ]
        cols = list(s["confusion_matrix"])
        lines += [
            "| expected \\ predicted | " + " | ".join(cols) + " |",
            "|" + "---|" * (len(cols) + 1),
        ]
        for expected, row in s["confusion_matrix"].items():
            lines.append(f"| {expected} | " + " | ".join(str(row[c]) for c in cols) + " |")
        errors = s.get("confident_errors", [])
        lines += ["", f"Confident errors (p >= {CONFIDENT}): {len(errors)}", ""]
        for error in errors[:15]:
            lines.append(
                f"- `{error['id']}` expected **{error['expected']}**, got **{error['predicted']}** "
                f"(p={error['probability']:.2f}): {error['state']}"
            )
        lines.append("")
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {out_dir / 'REPORT.md'}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT))
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET))
    parser.add_argument("--target-accuracy", type=float, default=0.95)
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Evaluate a running Bridge")
    run.add_argument("--url", default="http://localhost:8000")
    run.add_argument("--label", required=True, help="Name of this run, e.g. laya-en")
    run.add_argument("--timeout", type=float, default=60.0, help="Per-request seconds")
    run.add_argument("--wait-seconds", type=int, default=300, help="Max wait for /ready")
    run.add_argument("--limit", type=int, default=0, help="Only the first N rows (smoke test)")
    run.set_defaults(func=cmd_run)

    score = sub.add_parser("score", help="Score an external predictions JSONL (e.g. LLM baseline)")
    score.add_argument("--predictions", required=True)
    score.add_argument("--label", required=True)
    score.set_defaults(func=cmd_score)

    report = sub.add_parser("report", help="Write REPORT.md comparing every summary in --out-dir")
    report.set_defaults(func=cmd_report)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    sys.exit(main())
