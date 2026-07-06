"""Sallyport REST API server — FastAPI app exposing Fortress browser capabilities."""

from __future__ import annotations

import os
import time
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import uvicorn

from sallyport.engine import SallyportEngine

# --- Configuration ---
SALLYPORT_HOST = os.environ.get("SALLYPORT_HOST", "0.0.0.0")
SALLYPORT_PORT = int(os.environ.get("SALLYPORT_PORT", "9378"))
FORT_CHANNEL = os.environ.get("FORT_CHANNEL", "stable")
FORT_PORT = int(os.environ.get("FORT_PORT", "9222"))

# --- App ---
app = FastAPI(
    title="Sallyport",
    description="Lightweight REST API wrapper around Fortress stealth Chromium engine",
    version="0.1.0",
)

engine = SallyportEngine()


# --- Request/Response Models ---

class BrowserStartRequest(BaseModel):
    persona: Optional[dict] = None
    channel: str = Field(default=FORT_CHANNEL, pattern="^(stable|latest)$")
    port: int = Field(default=FORT_PORT, ge=1024, le=65535)


class BrowserStartResponse(BaseModel):
    status: str
    cdp_url: str
    session_id: str


class BrowserStopResponse(BaseModel):
    status: str


class TabOpenRequest(BaseModel):
    url: str
    wait_ms: int = Field(default=3000, ge=0, le=30000)
    wait_for: Optional[str] = Field(
        default=None,
        description="Wait condition: 'domcontentloaded', 'load', 'networkidle', or CSS selector string. Overrides wait_ms when set.",
    )
    timeout_ms: int = Field(default=15000, ge=1000, le=60000)


class TabOpenResponse(BaseModel):
    tab_id: str
    url: str
    snapshot: str
    refs_count: int


class TabSnapshotResponse(BaseModel):
    tab_id: str
    url: str
    snapshot: str
    refs_count: int


class ClickRequest(BaseModel):
    ref: str


class TypeRequest(BaseModel):
    ref: str
    text: str


class EvaluateRequest(BaseModel):
    expression: str


class ActionResponse(BaseModel):
    success: bool
    result: Optional[object] = None
    error: Optional[str] = None


class NavigateRequest(BaseModel):
    url: str


class ScreenshotRequest(BaseModel):
    full_page: bool = Field(default=False, description="Capture full scrollable page")


class HealthResponse(BaseModel):
    status: str
    version: str
    browser_running: bool
    tabs: int
    uptime: float


# --- State ---
_start_time = time.time()
_session_id = os.environ.get("SALLYPORT_SESSION_ID", os.urandom(8).hex())


# --- Routes ---

@app.get("/health", response_model=HealthResponse)
def health():
    """Health check — returns server status and tab count."""
    return HealthResponse(
        status="ok" if engine._running else "idle",
        version="0.1.0",
        browser_running=engine._running,
        tabs=len(engine.tabs),
        uptime=time.time() - _start_time,
    )


@app.post("/browser/start", response_model=BrowserStartResponse)
def browser_start(req: BrowserStartRequest):
    """Start Fortress and connect Playwright over CDP."""
    if engine._running:
        return BrowserStartResponse(
            status="already_running",
            cdp_url=engine.fortress.cdp_url if engine.fortress else "",
            session_id=_session_id,
        )

    cdp_url = engine.start(channel=req.channel, port=req.port, persona=req.persona)
    return BrowserStartResponse(
        status="ok",
        cdp_url=cdp_url,
        session_id=_session_id,
    )


@app.post("/browser/stop", response_model=BrowserStopResponse)
def browser_stop():
    """Stop Fortress and clean up all tabs."""
    engine.stop()
    return BrowserStopResponse(status="stopped")


@app.post("/tabs", response_model=TabOpenResponse)
def tab_open(req: TabOpenRequest):
    """Open a new tab and navigate to a URL."""
    if not engine._running:
        raise HTTPException(status_code=400, detail="Browser not started. POST /browser/start first.")

    tab = engine.open_tab(url=req.url, wait_ms=req.wait_ms, wait_for=req.wait_for, timeout_ms=req.timeout_ms)
    snapshot = engine.snapshot_tab(tab.tab_id)

    return TabOpenResponse(
        tab_id=tab.tab_id,
        url=tab.url,
        snapshot=snapshot["snapshot"] if snapshot else "",
        refs_count=snapshot["refs_count"] if snapshot else 0,
    )


@app.get("/tabs/{tab_id}/snapshot", response_model=TabSnapshotResponse)
def tab_snapshot(tab_id: str, wait_ms: int = 0):
    """Get the accessibility tree snapshot for a tab."""
    tab = engine.get_tab(tab_id)
    if not tab:
        raise HTTPException(status_code=404, detail=f"Tab {tab_id} not found")

    result = engine.snapshot_tab(tab_id, wait_ms=wait_ms)
    if not result:
        raise HTTPException(status_code=500, detail="Failed to get snapshot")

    return TabSnapshotResponse(
        tab_id=tab_id,
        url=tab.url,
        snapshot=result["snapshot"],
        refs_count=result["refs_count"],
    )


@app.post("/tabs/{tab_id}/click", response_model=ActionResponse)
def tab_click(tab_id: str, req: ClickRequest):
    """Click an element by CSS selector or text match."""
    tab = engine.get_tab(tab_id)
    if not tab:
        raise HTTPException(status_code=404, detail=f"Tab {tab_id} not found")

    # The 'ref' parameter is reused as a CSS selector or text content
    result = engine.click_element(tab_id, req.ref)
    if not result:
        raise HTTPException(status_code=500, detail="Click failed")

    return ActionResponse(**result)


@app.post("/tabs/{tab_id}/type", response_model=ActionResponse)
def tab_type(tab_id: str, req: TypeRequest):
    """Type text into an element identified by CSS selector."""
    tab = engine.get_tab(tab_id)
    if not tab:
        raise HTTPException(status_code=404, detail=f"Tab {tab_id} not found")

    result = engine.type_text(tab_id, req.ref, req.text)
    if not result:
        raise HTTPException(status_code=500, detail="Type failed")

    return ActionResponse(**result)


@app.post("/tabs/{tab_id}/evaluate", response_model=ActionResponse)
def tab_evaluate(tab_id: str, req: EvaluateRequest):
    """Execute JavaScript in the page context."""
    tab = engine.get_tab(tab_id)
    if not tab:
        raise HTTPException(status_code=404, detail=f"Tab {tab_id} not found")

    result = engine.evaluate_js(tab_id, req.expression)
    if not result:
        raise HTTPException(status_code=500, detail="Evaluate failed")

    return ActionResponse(**result)


@app.post("/tabs/{tab_id}/navigate", response_model=ActionResponse)
def tab_navigate(tab_id: str, req: NavigateRequest):
    """Navigate an existing tab to a new URL."""
    tab = engine.get_tab(tab_id)
    if not tab:
        raise HTTPException(status_code=404, detail=f"Tab {tab_id} not found")

    result = engine.navigate(tab_id, req.url)
    if not result:
        raise HTTPException(status_code=500, detail="Navigate failed")

    return ActionResponse(**result)


@app.get("/tabs/{tab_id}/source")
def tab_source(tab_id: str):
    """Get the rendered HTML source of a tab."""
    tab = engine.get_tab(tab_id)
    if not tab:
        raise HTTPException(status_code=404, detail=f"Tab {tab_id} not found")

    result = engine.source_tab(tab_id)
    if not result:
        raise HTTPException(status_code=500, detail="Failed to get page source")
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))

    return {"success": True, "html": result["html"], "url": result["url"], "tab_id": tab_id, "html_length": len(result["html"])}


@app.post("/tabs/{tab_id}/screenshot", response_model=ActionResponse)
def tab_screenshot(tab_id: str, req: ScreenshotRequest):
    """Take a screenshot of the tab — returns base64 PNG."""
    tab = engine.get_tab(tab_id)
    if not tab:
        raise HTTPException(status_code=404, detail=f"Tab {tab_id} not found")

    result = engine.screenshot_tab(tab_id, full_page=req.full_page)
    if not result:
        raise HTTPException(status_code=500, detail="Screenshot failed")
    if not result.get("success"):
        return ActionResponse(success=False, error=result.get("error"))

    return ActionResponse(
        success=True,
        result={
            "image_base64": result["image_base64"],
            "full_page": result["full_page"],
            "tab_id": tab_id,
        },
    )


@app.delete("/tabs/{tab_id}", response_model=ActionResponse)
def tab_close(tab_id: str):
    """Close a tab."""
    ok = engine.close_tab(tab_id)
    return ActionResponse(success=ok, error=None if ok else f"Tab {tab_id} not found")


# --- Main ---

def main():
    uvicorn.run(
        "sallyport.server:app",
        host=SALLYPORT_HOST,
        port=SALLYPORT_PORT,
        log_level="info",
    )


if __name__ == "__main__":
    main()
