"""Sallyport benchmark suite — replayable, no secrets, no external dependencies.

Run:  python3 benchmarks/run.py
Requires: Sallyport running on localhost:9378 with browser started
Output: JSON to stdout, human-readable summary to stderr
"""

import json
import sys
import time
import urllib.request
import urllib.error
import statistics
import platform
import os

BASE = "http://localhost:9378"

def api(method, path, body=None):
    """Thin HTTP client — stdlib only, no requests dependency."""
    url = f"{BASE}{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return {"error": e.code, "detail": e.read().decode()[:200]}
    except Exception as e:
        return {"error": str(e)}


class Timer:
    def __enter__(self):
        self.start = time.perf_counter()
        return self
    def __exit__(self, *args):
        self.elapsed = time.perf_counter() - self.start


def run_benchmark(name, fn, iterations=5):
    """Run fn() `iterations` times, return stats."""
    times = []
    results = []
    for i in range(iterations):
        t = Timer()
        with t:
            r = fn()
        times.append(t.elapsed)
        results.append(r)
    return {
        "name": name,
        "iterations": iterations,
        "times_s": {
            "min": round(min(times), 4),
            "max": round(max(times), 4),
            "median": round(statistics.median(times), 4),
            "mean": round(statistics.mean(times), 4),
            "stdev": round(statistics.stdev(times), 4) if len(times) > 1 else 0,
            "p95": round(sorted(times)[int(len(times)*0.95)], 4) if len(times) >= 20 else round(max(times), 4),
        },
        "last_result_summary": str(results[-1])[:200] if results else "",
    }


def bench_tab_open():
    """Open a tab to a simple page."""
    r = api("POST", "/tabs", {"url": "https://example.com", "wait_ms": 0, "timeout_ms": 10000})
    tab_id = r.get("tab_id", "")
    return {"tab_id": tab_id, **r}

def bench_tab_open_heavy():
    """Open a tab to a heavy page (Reddit thread)."""
    r = api("POST", "/tabs", {
        "url": "https://www.reddit.com/r/vibecoding/comments/1uxe923/update_2_my_vibecoded_government_saas_finally_got/",
        "wait_ms": 0, "timeout_ms": 20000
    })
    tab_id = r.get("tab_id", "")
    return {"tab_id": tab_id, "snapshot_len": len(r.get("snapshot", "")), **r}

def bench_snapshot(tab_id):
    """Snapshot an existing tab."""
    def fn():
        return api("GET", f"/tabs/{tab_id}/snapshot")
    return fn

def bench_evaluate(tab_id):
    """Run JS in page context."""
    def fn():
        return api("POST", f"/tabs/{tab_id}/evaluate", {"expression": "document.title"})
    return fn

def bench_scroll(tab_id):
    """Scroll the page."""
    def fn():
        return api("POST", f"/tabs/{tab_id}/scroll", {"direction": "down", "amount": 500})
    return fn

def bench_source(tab_id):
    """Get rendered HTML source."""
    def fn():
        return api("GET", f"/tabs/{tab_id}/source")
    return fn

def bench_screenshot(tab_id):
    """Take a screenshot (capture timing only, don't log base64)."""
    def fn():
        r = api("POST", f"/tabs/{tab_id}/screenshot", {"full_page": False})
        if r.get("success"):
            r["result"]["image_base64"] = f"<{len(r['result'].get('image_base64',''))} chars>"
        return r
    return fn


def main():
    print("=== Sallyport Benchmark Suite ===", file=sys.stderr)

    # System info
    info = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "hardware": platform.platform(),
        "processor": platform.processor(),
        "python": platform.python_version(),
        "sallyport_version": "0.1.0",
    }
    print(f"Hardware: {info['hardware']}", file=sys.stderr)
    print(f"Python: {info['python']}", file=sys.stderr)

    # Verify server is up
    health = api("GET", "/health")
    if "error" in health:
        print(f"FATAL: Server not reachable — {health}", file=sys.stderr)
        sys.exit(1)
    print(f"Server: {health}", file=sys.stderr)

    config = api("GET", "/config")
    print(f"Config: {config}", file=sys.stderr)

    results = {"system": info, "server_health": health, "server_config": config, "benchmarks": []}

    # --- Simple page benchmarks ---
    print("\n--- Opening simple page (example.com) ---", file=sys.stderr)

    # Get a tab first (single open for warm-up)
    warmup = bench_tab_open()
    simple_tab = warmup.get("tab_id", "")
    if not simple_tab:
        print(f"FAILED to open tab: {warmup}", file=sys.stderr)
        sys.exit(1)
    results["benchmarks"].append({
        "name": "tab_open_simple",
        "iterations": 1,
        "times_s": {"single": 0},
        "note": "Single open (warmup for subsequent ops)",
        "tab_id_prefix": simple_tab[:8],
    })

    results["benchmarks"].append(run_benchmark("snapshot_simple", bench_snapshot(simple_tab)))
    results["benchmarks"].append(run_benchmark("evaluate_js_simple", bench_evaluate(simple_tab)))
    results["benchmarks"].append(run_benchmark("scroll_down", bench_scroll(simple_tab)))
    results["benchmarks"].append(run_benchmark("source_retrieval", bench_source(simple_tab)))
    results["benchmarks"].append(run_benchmark("screenshot_capture", bench_screenshot(simple_tab)))

    # Cleanup simple tab
    api("DELETE", f"/tabs/{simple_tab}")

    # --- Heavy page benchmark ---
    print("\n--- Opening heavy page (Reddit thread) ---", file=sys.stderr)
    heavy = bench_tab_open_heavy()
    heavy_tab = heavy.get("tab_id", "")
    if heavy_tab:
        snap_len = len(api("GET", f"/tabs/{heavy_tab}/snapshot").get("snapshot", ""))
        results["benchmarks"].append({
            "name": "tab_open_heavy_reddit",
            "iterations": 1,
            "times_s": {"single": 0},
            "snapshot_size_chars": snap_len,
            "note": "Single open — snapshot size recorded for context",
        })
        results["benchmarks"].append(run_benchmark("snapshot_heavy", bench_snapshot(heavy_tab)))
        api("DELETE", f"/tabs/{heavy_tab}")

    # --- Tab open latency (5 iterations) ---
    print("\n--- Tab open latency (5x) ---", file=sys.stderr)
    open_times = []
    opened_tabs = []
    for i in range(5):
        t = Timer()
        with t:
            r = api("POST", "/tabs", {"url": "https://example.com", "wait_ms": 0, "timeout_ms": 10000})
        open_times.append(t.elapsed)
        tid = r.get("tab_id", "")
        if tid:
            opened_tabs.append(tid)

    results["benchmarks"].append({
        "name": "tab_open_latency_5x",
        "iterations": 5,
        "times_s": {
            "min": round(min(open_times), 4),
            "max": round(max(open_times), 4),
            "median": round(statistics.median(open_times), 4),
            "mean": round(statistics.mean(open_times), 4),
            "stdev": round(statistics.stdev(open_times), 4) if len(open_times) > 1 else 0,
        },
    })

    # Cleanup remaining tabs
    for tid in opened_tabs:
        api("DELETE", f"/tabs/{tid}")

    # --- Summary ---
    print("\n" + "=" * 60, file=sys.stderr)
    print("RESULTS SUMMARY", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    for b in results["benchmarks"]:
        name = b["name"]
        ts = b.get("times_s", {})
        if "median" in ts:
            print(f"  {name:35s}  median={ts['median']:>6.3f}s  min={ts['min']:>6.3f}s  max={ts['max']:>6.3f}s  (n={b['iterations']})", file=sys.stderr)
        elif "single" in ts:
            print(f"  {name:35s}  (single open)", file=sys.stderr)
        else:
            print(f"  {name:35s}  {json.dumps(ts)[:60]}", file=sys.stderr)

    # Output JSON on stdout
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
