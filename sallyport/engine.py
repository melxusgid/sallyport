"""Sallyport engine — manages Fortress (stealth Chromium) and Playwright tab sessions."""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

from tilion_fortress import Fortress as FortressEngine
from playwright.sync_api import (
    sync_playwright,
    Page,
    Browser as PW_Browser,
    Playwright,
    CDPSession,
)


@dataclass
class Tab:
    """A single browser tab with its CDP session."""

    tab_id: str
    page: Page
    cdp: CDPSession
    created_at: float = field(default_factory=time.time)
    url: str = ""


@dataclass
class SallyportEngine:
    """Manages one Fortress instance and its tabs."""

    fortress: Optional[FortressEngine] = None
    playwright: Optional[Playwright] = None
    browser: Optional[PW_Browser] = None
    tabs: dict[str, Tab] = field(default_factory=dict)
    _running: bool = False

    def start(
        self,
        channel: str = "stable",
        port: int = 9222,
        persona: Optional[dict] = None,
    ) -> str:
        """Launch Fortress and connect Playwright over CDP."""
        if self._running:
            return self.fortress.cdp_url

        self.fortress = FortressEngine(channel=channel, port=port, persona=persona)
        self.fortress.start()
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.connect_over_cdp(self.fortress.cdp_url)
        self._running = True
        return self.fortress.cdp_url

    def stop(self):
        """Close all tabs, browser, playwright, and Fortress."""
        self._running = False
        # Close tabs
        for tab in list(self.tabs.values()):
            try:
                tab.page.close()
            except Exception:
                pass
        self.tabs.clear()
        # Close browser
        if self.browser:
            try:
                self.browser.close()
            except Exception:
                pass
            self.browser = None
        # Stop Playwright
        if self.playwright:
            try:
                self.playwright.stop()
            except Exception:
                pass
            self.playwright = None
        # Stop Fortress
        if self.fortress:
            try:
                self.fortress.close()
            except Exception:
                pass
            self.fortress = None

    def open_tab(self, url: str, wait_ms: int = 3000) -> Tab:
        """Open a new tab and navigate to URL."""
        if not self._running or not self.browser:
            raise RuntimeError("Engine not started. Call start() first.")

        page = self.browser.new_page()
        page.goto(url, wait_until="domcontentloaded")
        time.sleep(wait_ms / 1000)

        # Create CDP session for this page
        contexts = self.browser.contexts
        ctx = contexts[0] if contexts else page.context
        cdp = ctx.new_cdp_session(page)

        tab_id = str(uuid.uuid4())
        tab = Tab(tab_id=tab_id, page=page, cdp=cdp, url=page.url)
        self.tabs[tab_id] = tab
        return tab

    def close_tab(self, tab_id: str) -> bool:
        """Close a tab by ID."""
        tab = self.tabs.pop(tab_id, None)
        if tab:
            try:
                tab.page.close()
            except Exception:
                pass
            return True
        return False

    def get_tab(self, tab_id: str) -> Optional[Tab]:
        """Get a tab by ID."""
        return self.tabs.get(tab_id)

    def snapshot_tab(self, tab_id: str, wait_ms: int = 0) -> Optional[dict]:
        """Get the accessibility tree snapshot for a tab."""
        tab = self.get_tab(tab_id)
        if not tab:
            return None

        if wait_ms > 0:
            time.sleep(wait_ms / 1000)

        tree = tab.cdp.send("Accessibility.getFullAXTree", {})
        nodes = tree.get("nodes", [])

        # Build node map and child lookup
        node_map = {}
        root_id = None
        for n in nodes:
            node_id = n["nodeId"]
            node_map[node_id] = n
            if not n.get("ignored", True) and n["role"]["value"] == "RootWebArea":
                root_id = node_id

        # Build child lookup: for ignored nodes, skip them and link children to parent
        def resolve_children(node_id: str) -> list[str]:
            """Walk through ignored nodes to find real children."""
            n = node_map.get(node_id)
            if not n:
                return []
            direct = list(n.get("childIds", []))
            # If this node is ignored, inherit grandchildren
            result = []
            for cid in direct:
                child = node_map.get(cid)
                if child and child.get("ignored", True):
                    result.extend(resolve_children(cid))
                else:
                    result.append(cid)
            return result

        snapshot = self._render_ax_tree(root_id, node_map, resolve_children) if root_id else ""
        refs_count = len([n for n in nodes if not n.get("ignored", True)])

        return {
            "url": tab.url,
            "snapshot": snapshot,
            "refs_count": refs_count,
            "total_nodes": len(nodes),
        }

    def _render_ax_tree(
        self,
        root_id: str,
        node_map: dict,
        resolve_children_fn,
    ) -> str:
        """Render AX tree into Camofox-compatible YAML-ish format."""
        lines = []

        def render_node(node_id: str, indent: int = 0):
            node = node_map.get(node_id)
            if not node or node.get("ignored", True):
                return

            prefix = "  " * indent
            role: str = node["role"]["value"]
            name: str = node.get("name", {}).get("value", "")

            # Escape quotes in names
            safe_name = name.replace('"', '\\"')

            if role == "RootWebArea":
                lines.append(f"{prefix}- document: \"{safe_name}\"")
            elif role == "StaticText":
                if safe_name.strip():
                    lines.append(f"{prefix}- text: \"{safe_name}\"")
                else:
                    return  # Skip empty text nodes
            elif role == "InlineTextBox":
                return  # Skip inline boxes (duplicate info)
            elif role == "heading":
                level = ""
                for prop in node.get("properties", []):
                    if prop["name"] == "level":
                        level = f" [level={prop['value']['value']}]"
                lines.append(f'{prefix}- heading "{safe_name}"{level}')
            elif role == "link":
                url = ""
                for prop in node.get("properties", []):
                    if prop["name"] == "url":
                        url = prop["value"]["value"]
                lines.append(f'{prefix}- link "{safe_name}"')
                if url:
                    lines.append(f"{prefix}  - /url: {url}")
            elif role == "paragraph":
                if safe_name:
                    lines.append(f"{prefix}- paragraph: {safe_name}")
                else:
                    lines.append(f"{prefix}- paragraph")
            elif role == "button":
                lines.append(f'{prefix}- button "{safe_name}"')
            elif role == "textbox":
                placeholder = ""
                for prop in node.get("properties", []):
                    if prop["name"] == "placeholder":
                        placeholder = prop["value"]["value"]
                lines.append(f'{prefix}- textbox "{safe_name}"')
                if placeholder:
                    lines.append(f'{prefix}  - /placeholder: "{placeholder}"')
            elif role == "list":
                lines.append(f"{prefix}- list:")
            elif role == "listitem":
                lines.append(f"{prefix}  - listitem:")
            elif role == "image":
                if safe_name:
                    lines.append(f'{prefix}- img "{safe_name}"')
                else:
                    lines.append(f"{prefix}- img")
            elif role in ("generic", "none", "document", "main"):
                # Container roles — render as section
                if safe_name:
                    lines.append(f'{prefix}- {role}: "{safe_name}"')
                else:
                    lines.append(f"{prefix}- {role}:")
            elif role == "navigation":
                lines.append(f"{prefix}- navigation:")
            elif role == "banner":
                lines.append(f"{prefix}- banner:")
            elif role == "complementary":
                lines.append(f"{prefix}- complementary:")
            elif role == "region":
                if safe_name:
                    lines.append(f'{prefix}- region "{safe_name}"')
                else:
                    lines.append(f"{prefix}- region:")
            elif role == "contentinfo":
                lines.append(f"{prefix}- contentinfo:")
            elif role == "search":
                lines.append(f"{prefix}- search:")
            elif role == "form":
                lines.append(f"{prefix}- form:")
            elif role == "table":
                lines.append(f"{prefix}- table:")
            elif role == "row":
                lines.append(f"{prefix}  - row:")
            elif role == "cell":
                lines.append(f'{prefix}    - cell: "{safe_name}"')
            elif role in ("combobox", "listbox"):
                lines.append(f'{prefix}- {role} "{safe_name}"')
            elif role == "option":
                lines.append(f'{prefix}  - option: "{safe_name}"')
            elif role == "checkbox":
                checked = ""
                for prop in node.get("properties", []):
                    if prop["name"] == "checked":
                        checked = " [checked]" if prop["value"]["value"] else " [unchecked]"
                lines.append(f'{prefix}- checkbox "{safe_name}"{checked}')
            elif role == "radio":
                lines.append(f'{prefix}- radio "{safe_name}"')
            elif role == "slider":
                value = ""
                for prop in node.get("properties", []):
                    if prop["name"] == "valuetext":
                        value = f" [{prop['value']['value']}]"
                lines.append(f'{prefix}- slider "{safe_name}"{value}')
            elif role == "progressbar":
                lines.append(f'{prefix}- progressbar "{safe_name}"')
            elif role == "math":
                lines.append(f"{prefix}- math:")
            elif role == "note":
                lines.append(f'{prefix}- note: "{safe_name}"')
            elif role in ("alert", "dialog", "status", "timer", "tooltip"):
                lines.append(f'{prefix}- {role}: "{safe_name}"')
            else:
                # Fallback for unknown roles
                if safe_name:
                    lines.append(f"{prefix}- {role}: \"{safe_name}\"")
                else:
                    lines.append(f"{prefix}- {role}")

            # Recurse into children
            for cid in resolve_children_fn(node_id):
                render_node(cid, indent + 1)

        render_node(root_id)
        return "\n".join(lines)

    def click_element(self, tab_id: str, selector: str) -> Optional[dict]:
        """Click an element identified by CSS selector or text-based approach."""
        tab = self.get_tab(tab_id)
        if not tab:
            return None

        try:
            # Try as a CSS selector first
            element = tab.page.query_selector(selector)
            if element:
                element.click()
                return {"success": True, "method": "css", "selector": selector}

            # Try as text content match
            element = tab.page.get_by_text(selector, exact=True).first
            if element:
                element.click()
                return {"success": True, "method": "text", "selector": selector}

            return {"success": False, "error": f"Element not found: {selector}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def type_text(self, tab_id: str, selector: str, text: str) -> Optional[dict]:
        """Type text into an element."""
        tab = self.get_tab(tab_id)
        if not tab:
            return None

        try:
            element = tab.page.query_selector(selector)
            if element:
                element.fill(text)
                return {"success": True, "selector": selector}
            return {"success": False, "error": f"Element not found: {selector}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def evaluate_js(self, tab_id: str, expression: str) -> Optional[dict]:
        """Run JavaScript in the page context and return the result."""
        tab = self.get_tab(tab_id)
        if not tab:
            return None

        try:
            result = tab.page.evaluate(expression)
            return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def navigate(self, tab_id: str, url: str) -> Optional[dict]:
        """Navigate an existing tab to a new URL."""
        tab = self.get_tab(tab_id)
        if not tab:
            return None

        try:
            tab.page.goto(url, wait_until="domcontentloaded")
            tab.url = tab.page.url
            return {"success": True, "url": tab.url}
        except Exception as e:
            return {"success": False, "error": str(e)}
