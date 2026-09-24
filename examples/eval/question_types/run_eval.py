"""Question-type evaluation for JEV-AgentBridge: native noul/score against emulated ones.

Standard library only (Python 3.9+). Runs a labelled dataset of yes/no (noul) and ordinal
(score) questions through a running Bridge. Run it twice against the same engine, once with
native types (default) and once with `JEV_NATIVE_TYPES=false` (the Bridge then asks every
question as a plain choice), to see whether the engine's native heads help.

    python run_eval.py run --url http://localhost:8000 --label kev-native
    python run_eval.py run --url http://localhost:8001 --label kev-emulated
    python run_eval.py report

Outputs, under --out-dir (default: results/ next to this script):
    <label>.predictions.jsonl  one line per question
    <label>.summary.json       accuracy per type and language, coverage table, score error
    REPORT.md                  written by `report`, one table over every summary
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
DEFAULT_DATASET = HERE / "question_types.jsonl"
DEFAULT_OUT = HERE / "results"
THRESHOLDS = [0.6, 0.7, 0.8, 0.9]


def load_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def post(url: str, body: dict, timeout: float) -> dict:
    request = urllib.request.Request(
        f"{url.rstrip('/')}/v1/decide",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read())


def run(args: argparse.Namespace) -> None:
    rows = load_jsonl(args.dataset)[: args.limit or None]
    predictions = []
    for index, row in enumerate(rows, 1):
        body = {"type": row["type"], "state": row["state"], "question": row["question"]}
        if row["type"] != "noul":
            body["options"] = row["options"]
        started = time.perf_counter()
        try:
            result = post(args.url, body, args.timeout)
        except urllib.error.URLError as error:
            sys.exit(f"{row['id']}: request failed: {error}")
        prediction = {
            "id": row["id"],
            "type": row["type"],
            "lang": row["lang"],
            "expected": row["expected"],
            "predicted": result["decision"]["id"],
            "probability": result["selected_probability"],
            "noul": result.get("noul"),
            "score": result.get("score"),
            "native_type": result["metadata"].get("native_type"),
            "latency_ms": round((time.perf_counter() - started) * 1000, 1),
        }
        if row["type"] == "score":
            ids = [option["id"] for option in row["options"]]
            prediction["expected_level"] = ids.index(row["expected"])
            prediction["predicted_level"] = ids.index(prediction["predicted"])
        predictions.append(prediction)
        mark = "ok " if prediction["predicted"] == row["expected"] else "ERR"
        print(f"[{index}/{len(rows)}] {mark} {row['id']} -> {prediction['predicted']}"
              f" p={prediction['probability']:.3f}")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    with (args.out_dir / f"{args.label}.predictions.jsonl").open("w", encoding="utf-8") as f:
        for prediction in predictions:
            f.write(json.dumps(prediction, ensure_ascii=False) + "\n")
    summary = summarize(args.label, predictions)
    (args.out_dir / f"{args.label}.summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))


def _accuracy(rows: list[dict]) -> float | None:
    if not rows:
        return None
    return round(sum(r["predicted"] == r["expected"] for r in rows) / len(rows), 4)


def summarize(label: str, predictions: list[dict]) -> dict:
    summary: dict = {"label": label, "native_type": None, "types": {}}
    natives = {p["native_type"] for p in predictions if p["type"] != "choice"}
    summary["native_type"] = natives.pop() if len(natives) == 1 else "mixed"
    for type_ in ("noul", "score"):
        rows = [p for p in predictions if p["type"] == type_]
        if not rows:
            continue
        stats: dict = {
            "n": len(rows),
            "accuracy": _accuracy(rows),
            "by_lang": {
                lang: _accuracy([r for r in rows if r["lang"] == lang])
                for lang in sorted({r["lang"] for r in rows})
            },
            "coverage": {},
        }
        for threshold in THRESHOLDS:
            kept = [r for r in rows if r["probability"] >= threshold]
            stats["coverage"][str(threshold)] = {
                "coverage": round(len(kept) / len(rows), 4),
                "accuracy": _accuracy(kept),
            }
        if type_ == "score":
            stats["within_one_level"] = round(
                sum(abs(r["predicted_level"] - r["expected_level"]) <= 1 for r in rows)
                / len(rows),
                4,
            )
            stats["score_mae"] = round(
                sum(abs(r["score"] - r["expected_level"]) for r in rows) / len(rows), 4
            )
        summary["types"][type_] = stats
    return summary


def report(args: argparse.Namespace) -> None:
    summaries = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(args.out_dir.glob("*.summary.json"))
    ]
    lines = [
        "# Question types: native vs emulated",
        "",
        "| Run | Native | noul acc. | noul IT | noul EN | noul cov. @0.8 (acc.) "
        "| score exact | score ±1 | score MAE | score cov. @0.8 (acc.) |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]

    def pct(value: float | None) -> str:
        return "—" if value is None else f"{value * 100:.1f}%"

    for s in summaries:
        noul, score = s["types"].get("noul", {}), s["types"].get("score", {})
        n08, s08 = noul.get("coverage", {}).get("0.8", {}), score.get("coverage", {}).get("0.8", {})
        by_lang = noul.get("by_lang", {})
        lines.append(
            f"| {s['label']} | {s['native_type']} | {pct(noul.get('accuracy'))} "
            f"| {pct(by_lang.get('it'))} | {pct(by_lang.get('en'))} "
            f"| {pct(n08.get('coverage'))} ({pct(n08.get('accuracy'))}) "
            f"| {pct(score.get('accuracy'))} | {pct(score.get('within_one_level'))} "
            f"| {score.get('score_mae', '—')} "
            f"| {pct(s08.get('coverage'))} ({pct(s08.get('accuracy'))}) |"
        )
    (args.out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    sub = parser.add_subparsers(dest="command", required=True)
    run_parser = sub.add_parser("run", help="run the dataset through a Bridge")
    run_parser.add_argument("--url", default="http://localhost:8000")
    run_parser.add_argument("--label", required=True)
    run_parser.add_argument("--limit", type=int, default=0)
    run_parser.add_argument("--timeout", type=float, default=120.0)
    run_parser.set_defaults(func=run)
    report_parser = sub.add_parser("report", help="write REPORT.md from every summary")
    report_parser.set_defaults(func=report)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
