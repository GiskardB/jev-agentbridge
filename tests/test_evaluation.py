"""Tests for the accuracy evaluation tool."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from jev_agentbridge.evaluation import Prediction, load_dataset, summarize

SAMPLE = Path(__file__).resolve().parents[1] / "examples" / "eval" / "sample.jsonl"


def test_sample_dataset_is_valid() -> None:
    assert len(load_dataset(str(SAMPLE))) >= 10


def test_load_rejects_expected_not_in_options(tmp_path: Path) -> None:
    bad = tmp_path / "bad.jsonl"
    bad.write_text(
        json.dumps(
            {"state": "s", "question": "q", "options": [{"id": "a", "description": "A"}],
             "expected": "z"}
        )
    )
    with pytest.raises(ValueError, match="not an option"):
        load_dataset(str(bad))


def test_summarize_coverage_accuracy_and_recommendation() -> None:
    predictions = [
        Prediction("a", "a", 0.95),
        Prediction("a", "a", 0.9),
        Prediction("a", "b", 0.7),  # confident-ish mistake
        Prediction("a", "a", 0.55),
    ]
    summary = summarize(predictions, thresholds=[0.5, 0.8], target_accuracy=0.97)
    rows = {row["threshold"]: row for row in summary["thresholds"]}
    assert summary["accuracy_overall"] == 0.75
    assert rows[0.5]["coverage"] == 1.0 and rows[0.5]["accuracy_accepted"] == 0.75
    assert rows[0.8]["coverage"] == 0.5 and rows[0.8]["accuracy_accepted"] == 1.0
    assert summary["recommended_threshold"] == 0.8
    assert summary["recommended_coverage"] == 0.5


def test_summarize_no_threshold_reaches_target() -> None:
    summary = summarize([Prediction("a", "b", 0.99)], thresholds=[0.5])
    assert summary["recommended_threshold"] is None


def test_italian_sample_dataset_is_valid() -> None:
    assert len(load_dataset(str(SAMPLE.with_name("sample_it.jsonl")))) == 12


def test_model_routing_dataset_is_valid_and_balanced() -> None:
    from collections import Counter

    path = SAMPLE.parent / "model_routing" / "model_routing.jsonl"
    rows = load_dataset(str(path))
    assert len(rows) == 240
    assert len({row["id"] for row in rows}) == 240
    assert len({row["state"] for row in rows}) == 240
    assert set(Counter((row["lang"], row["expected"]) for row in rows).values()) == {40}
