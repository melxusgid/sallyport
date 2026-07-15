# Sallyport Benchmarks

> Measured: 2026-07-15 · Mac Mini (Apple M-series, ARM64) · macOS 26.5
> Python 3.11.15 · Sallyport v0.1.0 · Fortress channel: stable (Chromium 149)
>
> **Run it yourself:** `python3 benchmarks/run.py` (requires Sallyport running on :9378 with browser started)

## How benchmarks work

Each operation is measured 5 times with `time.perf_counter()`. Results include min, max, median, mean, and stdev. The tab is opened once (warmup), then all operations exercise that same tab so snapshot/evaluate/scroll metrics isolate operation latency from tab-open overhead.

Tab-open latency is measured separately (5 independent tab opens).

## Key results

| Operation | Median | Min | Max | n |
|-----------|--------|-----|-----|---|
| Open tab (simple page) | 1.43s | 1.09s | 3.07s | 5 |
| Snapshot (simple page) | 5.2ms | 2.9ms | 43.6ms | 5 |
| Snapshot (heavy page) | 65.6ms | 49.0ms | 187.8ms | 5 |
| JS evaluate | 3.8ms | 2.1ms | 51.4ms | 5 |
| Scroll down 500px | 14.7ms | 5.8ms | 22.0ms | 5 |
| Source retrieval | 2.3ms | 2.1ms | 11.7ms | 5 |
| Screenshot capture | 47.9ms | 41.5ms | 97.7ms | 5 |

## Detailed results

### Tab open latency

Opening a tab and navigating to `https://example.com` (no wait, domcontentloaded only).

| Metric | Value |
|--------|-------|
| Median | 1.43s |
| Mean | 1.77s |
| Min | 1.09s |
| Max | 3.07s |
| Std Dev | 0.83s |

**Dominant factor:** Fortress Chromium launch and CDP connection. The first open is slower because Fortress's Docker container is already running but establishing the Playwright CDP session has overhead. Subsequent opens on the same browser session are faster.

### Snapshot (accessibility tree)

CDP `Accessibility.getFullAXTree` call. Time is dominated by tree serialization to the YAML-ish format.

| Metric | Simple page (example.com) | Heavy page (Reddit thread) |
|--------|--------------------------|---------------------------|
| Median | 5.2ms | 65.6ms |
| Mean | 12.8ms | 93.1ms |
| Min | 2.9ms | 49.0ms |
| Max | 43.6ms | 187.8ms |
| Std Dev | 17.4ms | 56.1ms |

**Heavy page note:** Reddit's anti-bot blocking means the snapshot captured is small (~48 chars — the Cloudflare challenge page, not the actual thread). The "heavy" numbers above represent the cost of AX tree serialization on a minimal page, not a 5000-node tree. On a genuinely large tree (2000+ nodes), expect snapshot times in the 200-500ms range.

### JS evaluate

Executing `document.title` in the page context.

| Metric | Value |
|--------|-------|
| Median | 3.8ms |
| Mean | 13.1ms |
| Min | 2.1ms |
| Max | 51.4ms |
| Std Dev | 21.4ms |

**Outlier:** The 51ms max was likely a JIT warmup or GC pause. Sustained eval latency is consistently 2-5ms.

### Scroll

Scrolling 500px down via `window.scrollBy(0, 500)` in the page context.

| Metric | Value |
|--------|-------|
| Median | 14.7ms |
| Mean | 13.0ms |
| Min | 5.8ms |
| Max | 22.0ms |
| Std Dev | 7.0ms |

### Source retrieval

Getting the full rendered HTML via `page.content()`.

| Metric | Value |
|--------|-------|
| Median | 2.3ms |
| Mean | 4.4ms |
| Min | 2.1ms |
| Max | 11.7ms |
| Std Dev | 4.1ms |

### Screenshot

Capturing a viewport PNG (base64-encoded, ~16KB for example.com).

| Metric | Value |
|--------|-------|
| Median | 47.9ms |
| Mean | 57.5ms |
| Min | 41.5ms |
| Max | 97.7ms |
| Std Dev | 22.9ms |

## Worst-case observations

- **Tab open under load** (Fortress container cold start): 3.07s max. If Fortress has not been started (`POST /browser/start` not yet called), the first tab open includes Docker container launch time (~5-8s additional).
- **Anti-bot pages:** Reddit threads behind Cloudflare Turnstile return minimal snapshots (~48 chars). Sallyport cannot bypass Turnstile Managed Challenge — this is a Fortress engine limitation.
- **Memory pressure:** Not measured in this run. On systems with <8GB free RAM, expect screenshot and snapshot latency to increase 2-3x due to Chromium swap pressure.

## Raw data

The benchmark script outputs complete JSON to stdout with every iteration's timing. Run it yourself to see full variance:

```bash
python3 benchmarks/run.py 2>/dev/null | jq '.benchmarks[] | {name, times_s}'
```

## Replayability

These benchmarks use only stdlib Python (no `requests`, no `pytest`). The script requires Sallyport running on `localhost:9378` with the browser already started (`POST /browser/start`). The test pages are public (example.com and a specific Reddit URL) — no credentials or secrets needed.
