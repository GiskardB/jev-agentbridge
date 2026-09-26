# Score acceptance window (bridge 0.7.0)

The 112 score questions of the two suites (`../../question_types.jsonl` and
`../../datasets/local-20260926.jsonl`), run on 2026-09-26 against bridge 0.7.0 with the default
emulated types: Kev-0.8B (`kev.serve`, pinned `jaredpalmer/kev-0.8b@9a45d25e...`) and Laya
multilingual, CPU. Compares the 0.6 acceptance (probability of the exact level) with the 0.7
one (probability of the chosen level ± 1, `score_window_probability`).

| Engine | Threshold | 0.6: answered (exact acc.) | 0.7: answered (exact acc., within ±1) |
|---|---|---|---|
| Kev-0.8B | 0.6 | 41.1% (87.0%) | 99.1% (72.1%, 99.1%) |
| Kev-0.8B | 0.7 | 20.5% (82.6%) | 92.9% (72.1%, 100%) |
| Kev-0.8B | 0.8 | 8.0% (100%) | 83.9% (72.3%, 100%) |
| Laya multilingual | 0.7 | 40.2% (64.4%) | 82.1% (50.0%, 85.9%) |
| Laya multilingual | 0.8 | 27.7% (67.7%) | 71.4% (53.8%, 90.0%) |

`REPORT.md` is the runner's table; raw predictions and summaries are next to it.
