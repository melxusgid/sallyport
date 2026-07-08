[![Sallyport](docs/assets/banner-sallyport.png)](https://github.com/melxusgid/sallyport)

### Stealth browser REST API — drive a bot-proof browser with `curl`

[![Python](https://img.shields.io/badge/python-3.9+-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![License](https://img.shields.io/badge/license-MIT-2ea44f)](LICENSE)
[![Docker](https://img.shields.io/badge/docker-fromthescope/sallyport-2496ED?logo=docker&logoColor=white)](https://hub.docker.com/r/fromthescope/sallyport)

[![CreepJS](https://img.shields.io/badge/CreepJS-0%25%20headless-2ea44f)](https://github.com/tiliondev/fortress)
[![Cloudflare](https://img.shields.io/badge/Cloudflare%20Turnstile-bypassed-2ea44f)](https://github.com/tiliondev/fortress)
[![Akamai](https://img.shields.io/badge/Akamai%20Bot%20Manager-cleared-2ea44f)](https://github.com/tiliondev/fortress)
[![Runtime.enable leak](https://img.shields.io/badge/Runtime.enable-no%20leak-2ea44f)](https://github.com/tiliondev/fortress)

[![Copy for agent](https://img.shields.io/badge/Copy%20for%20agent-24292f?logo=readme&logoColor=white)](#copy-for-agent)
[![llms.txt](https://img.shields.io/badge/llms.txt-24292f?logo=readme&logoColor=white)](llms.txt)

**Sallyport** wraps [Fortress](https://github.com/tiliondev/fortress) — a stealth Chromium engine with C++-level fingerprint spoofing — behind a REST API. Any agent, script, or human can browse the web through a bot-proof browser with simple HTTP calls.

No Playwright scripts. No CDP boilerplate. No anti-bot configuration.

> *A sallyport is a controlled passage through a fortress wall — the secure way in and out.*

## Why?

- **Bypasses anti-bot** — Fortress corrects canvas, WebGL, audio, fonts, navigator, and 30+ fingerprint surfaces inside Chromium's C++. CreepJS: 0%. Live Cloudflare Turnstile: cleared. Akamai Bot Manager: bypassed.
- **Agent-friendly** — REST API instead of Playwright. Any agent that speaks HTTP can browse.
- **Camofox-compatible** — Same endpoint pattern (`POST /tabs`, `GET /tabs/{id}/snapshot`).
- **Open source** — MIT license. Build on it, fork it, ship it.

## Quick start

### Docker

```bash
docker run -d --rm --platform linux/amd64 --shm-size=1g -p 9378:9378 fromthescope/sallyport:latest
```

### Local

```bash
pip install sallyport
python3 -m sallyport.server
```

Then:

```bash
# Start the stealth browser engine
curl -X POST http://localhost:9378/browser/start \
  -H "Content-Type: application/json" \
  -d '{"channel":"stable"}'

# Open a page — even Cloudflare/Akamai protected ones
curl -s -X POST http://localhost:9378/tabs \
  -H "Content-Type: application/json" \
  -d '{"url":"https://bot.sannysoft.com","wait_ms":4000}' \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['snapshot'][:500])"

# Close up
curl -X DELETE "http://localhost:9378/tabs/<tab_id>"
curl -X POST http://localhost:9378/browser/stop
```

## API

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Server status, tab count, uptime |
| `POST` | `/browser/start` | Launch Fortress with optional persona |
| `POST` | `/browser/stop` | Kill Fortress, clean up all tabs |
| `POST` | `/tabs` | Open URL → tab ID + snapshot |
| `GET` | `/tabs/{id}/snapshot` | Accessibility tree content |
| `GET` | `/tabs` | List all open tabs with URL, age |
| `GET` | `/tabs/{id}/source` | Raw rendered HTML (full DOM after JS) |
| `POST` | `/tabs/{id}/scroll` | Scroll up/down/left/right by px |
| `POST` | `/tabs/{id}/screenshot` | Base64 PNG screenshot (supports full_page) |
| `POST` | `/tabs/{id}/click` | Click element by ref |
| `POST` | `/tabs/{id}/type` | Type text into element |
| `POST` | `/tabs/{id}/evaluate` | Run JS, get result |
| `POST` | `/tabs/{id}/navigate` | Navigate existing tab |
| `DELETE` | `/tabs/{id}` | Close tab |

### Example: persona override

```bash
# Start with a specific browser persona
curl -X POST http://localhost:9378/browser/start \
  -H "Content-Type: application/json" \
  -d '{
    "channel":"stable",
    "persona": {
      "timezone":"America/New_York",
      "languages":"en-US,en",
      "hw_concurrency":16,
      "screen_width":1920,
      "screen_height":1080
    }
  }'
```

## Architecture

```
Agent/Hermes ──curl──> Sallyport (:9378) ──CDP──> Fortress (:9222)
                              │
                              └── Playwright drives CDP, FastAPI wraps it
```

| Layer | What | Who |
|---|---|---|
| Engine | Chromium C++ fingerprint patches (34 patches) | [tiliondev/fortress](https://github.com/tiliondev/fortress) |
| SDK | Python package to download & launch Fortress | tiliondev (upstream) |
| REST API | FastAPI + Playwright CDP session management | **Sallyport** (this project) |
| Agent skill | Hermes skill for curl-based browsing | **Sallyport** |

## How it compares

| | Stock Playwright | puppeteer-stealth | Camoufox | **Sallyport + Fortress** |
|---|---|---|---|---|
| Spoof layer | none | JS injection | C++ (Firefox) | **C++ (Chromium)** |
| `toString` yields `[native code]` | n/a | ❌ | ✅ | ✅ |
| Survives iframe/worker | ❌ | ❌ | ✅ | ✅ |
| Engine | Chromium | Chromium | Firefox | **Chromium** |
| TLS shape | Chromium | Chromium | Firefox (sticks out) | **Chromium** |
| Agent-friendly REST API | ❌ | ❌ | ❌ (Camofox adds it) | **✅ built in** |
| Open source | ✅ | ✅ | ✅ (MPL) | **✅ (MIT)** |

## Environment

| Variable | Default | Description |
|---|---|---|
| `SALLYPORT_HOST` | `0.0.0.0` | Server bind address |
| `SALLYPORT_PORT` | `9378` | Server port |
| `FORT_CHANNEL` | `stable` | `stable` (Chromium 149) or `latest` (151) |
| `FORT_PORT` | `9222` | Fortress CDP port |

## Copy for agent

```
Sallyport is a REST API wrapper around Fortress, an open-source stealth Chromium engine.
It exposes HTTP endpoints so any agent can browse anti-bot-protected sites with curl.

LAUNCH:
  docker run -d --rm --platform linux/amd64 --shm-size=1g -p 9378:9378 fromthescope/sallyport:latest
  curl -X POST http://localhost:9378/browser/start -H "Content-Type: application/json" -d '{}'
  curl -X POST http://localhost:9378/tabs -H "Content-Type: application/json" -d '{"url":"<URL>","wait_ms":3000}'

CONNECT:
  Use the returned tab_id to interact: snapshot, click, type, evaluate.
  curl http://localhost:9378/tabs/{tab_id}/snapshot

RULES:
  1) Do NOT add puppeteer-stealth or JS stealth plugins — Fortress does this in C++.
  2) Do NOT use chromedriver — connect over CDP.
  3) Blocked 90% of the time = IP issue (datacenter), not fingerprint. Use residential proxy.

Full guide: https://github.com/melxusgid/sallyport
```

## License

MIT. The upstream Fortress engine is BSD-3.
