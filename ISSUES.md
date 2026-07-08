# Sallyport — Known Issues & Roadmap

> Logged 2026-07-08 after a full repo health audit.
> These are **tracked, not fixed** — transparent record of what needs work before v0.2.0.

---

## P0 — Broken / Blocked (blocks basic use)

### #1: Docker image never pushed to Docker Hub
`fromthescope/sallyport:latest` returns **404** on hub.docker.com. The README, llms.txt, and Hermes skill all reference `docker run fromthescope/sallyport:latest` as the primary launch method, but the image doesn't exist.

**Fix:** Build and push the Docker image to Docker Hub under the `fromthescope` org (or update docs if the org path changed).

---

### #2: Zero tests
- `engine.py` — 463 lines, 0 test coverage
- `server.py` — 329 lines, 0 test coverage
- No `tests/` directory, no pytest config, no test runner

**Risk:** Any change is a blind merge. The 5 commits on July 5 (screenshot, smart wait, source, tab list, scroll) were pushed without tests.

**Fix:** Write tests for:
- Engine lifecycle (start → open_tab → snapshot → evaluate → close_tab → stop)
- AX tree rendering (known page structures)
- Error paths (Fortress crash, bad URL, CDP disconnect)
- Concurrent tab management
- Then add CI to enforce them

---

### #3: No CI/CD pipeline
No `.github/workflows/` directory. The repo has no:
- Automated test runs
- Docker build + push
- Package publishing
- Linting

**Fix:** Add GitHub Actions for `pytest`, `docker buildx bake`, and `pip install` sanity check.

---

## P1 — Wrong / Misleading (hurts first impressions)

### #4: pyproject.toml has wrong homepage URL
```toml
Homepage = "https://github.com/fromthescope/sallyport"
```
Actual repo: `https://github.com/melxusgid/sallyport`

`fromthescope` org is a different org than `melxusgid`. Anyone following the package metadata ends up at a 404.

---

### #5: llms.txt is stale
`llms.txt` was written for v0.1.0 initial release and only lists **6 of 14 endpoints**. Missing:
- `GET /tabs` — list tabs
- `GET /tabs/{id}/source` — raw HTML
- `POST /tabs/{id}/scroll` — scroll page
- `POST /tabs/{id}/screenshot` — base64 screenshot
- `POST /tabs/{id}/navigate` — navigate existing tab
- `POST /tabs/{id}/click` — click element
- `POST /tabs/{id}/type` — type text
- `POST /tabs/{id}/evaluate` — run JS

Also missing: the `persona` parameter on `/browser/start`, the `wait_for` parameter on `/tabs`, the `timeout_ms` parameter.

---

### #6: examples/curl-demo.sh doesn't cover new endpoints
The demo script at `examples/curl-demo.sh` was written for the initial 6-endpoint release. It doesn't demonstrate:
- Scroll
- Source
- Screenshot
- Tab list
- Smart wait (`wait_for` instead of `wait_ms`)
- Navigating existing tabs

---

## P2 — Reliability & Robustness (will fail in production)

### #7: No error recovery if Fortress crashes
If the Fortress process dies mid-session, `engine._running` stays `True` but `engine.fortress` is `None`. All subsequent API calls hit:
```python
if not engine._running or not self.browser:
    raise RuntimeError("Engine not started. Call start() first.")
```
The only recovery path is calling `POST /browser/stop` (which tries to close a dead browser and might itself raise) then `POST /browser/start` again.

**Fix:** Add a health-check callback or CDP reconnect loop. Detect dead browser on the next API call and auto-restart or surface a clear error.

---

### #8: Single browser instance
Sallyport currently supports exactly **one** browser instance at a time. To switch personas:
1. `POST /browser/stop`
2. `POST /browser/start` with new persona

No isolated contexts, no multi-profile support. Switching between e.g. macOS and Windows personas means restarting the full browser.

**Fix:** Support multiple Fortress instances or Playwright browser contexts with isolated storage/personas.

---

### #9: No concurrent request handling
`engine.open_tab()` and `engine.stop()` share mutable state (`self.tabs`, `self.browser`, `self._running`) with no locks. If a stop request arrives while a tab is opening:
- `tab_creation`: `self.browser.new_page()` → stop fires → `self.browser.close()` → new_page call crashes
- `stop` iterates over `list(self.tabs.values())` while tabs are being added

For a single-user REST API this is unlikely to race in practice, but it's a correctness gap.

**Fix:** Add a threading lock around engine state mutations.

---

## P3 — Deferred Features (known gaps from July 5)

### #10: Snapshot ref mapping
AX tree nodes are rendered as YAML but there's no way to map a snapshot line back to a CSS selector for `click`/`type`. Currently `click` and `type` require the caller to know the CSS selector independently.

CDP has `DOM.getNodeForLocation` — given x/y coordinates you can get the backend node ID, then `DOM.describeNode` gives you selectors. This is the correct approach but it's complex enough for its own focused PR.

**Deferred since:** July 5, 2026 (commit 95c0180)

---

### #11: Cookie / session persistence
No way to persist cookies between requests. Each `POST /tabs` starts a fresh context. For sites that need login:
1. Open login page
2. Manually type credentials (or inject JS)
3. Complete auth flow
4. Snapshot content
5. Auth session is lost on tab close

**Fix:** A full `context` management layer — persistent storage directories per persona, cookie import/export endpoints, session replay.

---

### #12: Proxy support
No way to configure an egress proxy for Fortress. Blocked requests on datacenter IPs are the #1 reason Fortress clears the fingerprint check but the site still blocks. The skill's own documentation says: *"Blocked 90% of the time = IP issue (datacenter), not fingerprint. Use a residential proxy."* — but Sallyport provides no way to set one.

**Fix:** Add proxy config to `POST /browser/start`. Forward to Fortress's `--proxy-server` or Playwright's `browser.new_context(proxy=...)`.

---

## Minor / Quality of Life

### Docker image size
The multi-stage build copies the full Playwright/Chromium install from builder to runtime. Runtime image is ~850MB. Could be reduced with `playwright install --only-deps chromium` and careful layer ordering.

### No `__main__` guard in server.py's `main()`
`main()` is guarded by `if __name__ == "__main__"` — but the module-level `engine = SallyportEngine()` runs on every import, not just when `main()` is called. `uvicorn.run("sallyport.server:app")` triggers the engine creation. This is fine for the Docker CMD but wasteful for imports.

---

## Changelog

| Date | What |
|------|------|
| 2026-07-08 | Initial audit — 12 issues logged, file created |
