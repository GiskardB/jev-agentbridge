# Performance

Benchmark with `python -m benchmarks.run`. The benchmark measures:

- cold start
- warm direct decision
- warm shared decision
- input token count
- p50, p95, min, max latency

CPU inference latency is input-length and hardware dependent. Do not claim sub-100ms without benchmarking on stated hardware.

## Cold start vs warm inference

The first execution downloads/loads the model. Subsequent executions use a persistent Hugging Face cache.

## Running benchmarks

```bash
python -m benchmarks.run
```

Output includes machine-readable JSON and a human-readable summary.
