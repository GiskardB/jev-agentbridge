# Local question-types run — environment and notes

## Environment

- CPU: Intel(R) Core(TM) i7-6700HQ CPU @ 2.60GHz, 8 cores
- RAM: 7.7 GiB total
- OS: Debian GNU/Linux 12 (bookworm), kernel 6.18.33.2-microsoft-standard-WSL2 (Linux container,
  not the Windows/PowerShell host assumed by LOCAL_RUN.md — commands below are the bash
  equivalents, run from the repository root)
- Docker: 28.1.1, build 4eba377
- GPU: none used (default CPU images)
- Start time (UTC): 2026-09-26T10:31:58Z

## Environment-specific deviations from LOCAL_RUN.md (not a rule violation — no code/docs/dataset changed)

- Host port 8000 is occupied by another service in this environment. Laya was run with
  `-p 8010:8000` on the `docker run` command line (no file changes needed). For Kev,
  `docker-compose.kev.yml`'s `8000:8000` port mapping was temporarily changed to `8010:8000` with
  `sed` to run the stack, then restored byte-for-byte with `git checkout -- docker-compose.kev.yml`
  immediately after `docker compose down` — verified clean (`git status` shows no diff on that
  file in the final commit).
- This shell's network namespace cannot reach containers via published host ports or default
  bridge IPs. Containers are attached to the pre-existing `cave` Docker network (already used by
  this shell's own container) via `--network cave` (plain `docker run`) or a local, untracked
  compose override file (`networks: {kev: [cave], bridge: [cave]}`, never committed), and reached
  by container name (e.g. `http://jev-qt:8000`, `http://jev-kev-bridge-1:8000`) instead of
  `localhost`.

## Run times (wall time, sequential requests, sum of per-request `latency_ms`)

| Run | n | Wall time |
|---|---|---|
| laya-emulated | 200 | ~79.4 s |
| laya-native | 200 | ~76.6 s |
| kev-emulated | 200 | ~426.3 s |
| kev-native | 200 | ~433.1 s |

End time (UTC): 2026-09-26T11:33:43Z

## Failures, retries, anomalies

- None. All four full runs (`laya-emulated`, `laya-native`, `kev-emulated`, `kev-native`)
  completed with every one of the 200 requests answered — no HTTP errors, timeouts, or
  malformed-response exceptions from the runner. The console shows many `ERR` lines per run;
  those mean "predicted label != expected label" (see `run_eval.py` line ~79), i.e. the model got
  the question wrong — not a request or infrastructure failure. Confirmed by inspecting the
  underlying `.predictions.jsonl` rows: each has a valid `predicted`/`probability`, no `error`
  field.
- The Laya container took ~90s to become ready on both starts (model load, from the
  already-warm `jev-hf-cache` Docker volume). Kev's bridge became ready in ~15s once its
  `kev` server container was already healthy from a prior warm-up in this same session.

## Labels now suspected of being ambiguous

- None identified. Every "hard" row was designed to have exactly one defensible answer despite
  requiring an inference step (negation, implicit signal, or a plausible-looking distractor); on
  review after seeing the results, none of the four configurations' errors clustered on a
  specific row in a way that suggests a mislabelled item rather than a genuine engine mistake
  (errors are broadly spread across both `normal` and `hard` rows in both languages).

(No interpretation of which path — native vs emulated — is better is included here; that is for
whoever analyses `REPORT.md`.)

