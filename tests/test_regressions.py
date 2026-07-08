"""Regression tests for bugs found during real-world Sallyport smoke testing."""

import unittest
from types import SimpleNamespace
from typing import Any, cast

from sallyport.engine import SallyportEngine
from sallyport.server import ActionResponse


class FakePage:
    def __init__(self):
        self.calls = []
        self.scroll_x = 0
        self.scroll_y = 0
        self.elements = {}

    def evaluate(self, expr):
        self.calls.append(("evaluate", expr))
        if expr.startswith("window.scrollBy("):
            dx, dy = expr.removeprefix("window.scrollBy(").removesuffix(")").split(", ")
            self.scroll_x += int(dx)
            self.scroll_y += int(dy)
        if expr == "window.scrollX":
            return self.scroll_x
        if expr == "window.scrollY":
            return self.scroll_y
        return None

    def query_selector(self, selector):
        return self.elements.get(selector)

    def get_by_text(self, text, exact=True):
        return FakeLocator(self.elements.get(text))


class FakeElement:
    def __init__(self):
        self.clicked_with = None

    def click(self, **kwargs):
        self.clicked_with = kwargs


class FakeLocator:
    def __init__(self, element):
        self.first = element


class EngineRegressionTests(unittest.TestCase):
    def make_engine_with_page(self, page):
        engine = SallyportEngine()
        engine.tabs["t1"] = cast(Any, SimpleNamespace(tab_id="t1", page=page, cdp=None, url="https://example.com"))
        return engine

    def test_scroll_uses_window_scroll_by_and_returns_real_position(self):
        page = FakePage()
        engine = self.make_engine_with_page(page)

        result = engine.scroll_tab("t1", direction="down", amount=600)
        self.assertIsNotNone(result)
        result = cast(dict, result)

        self.assertTrue(result["success"])
        self.assertEqual(result["scrollX"], 0)
        self.assertEqual(result["scrollY"], 600)
        self.assertIn(("evaluate", "window.scrollBy(0, 600)"), page.calls)
        self.assertNotIn(("evaluate", "window.scrollTop"), page.calls)

    def test_click_passes_timeout_and_does_not_wait_after_navigation(self):
        page = FakePage()
        button = FakeElement()
        page.elements["button[type=submit]"] = button
        engine = self.make_engine_with_page(page)

        result = engine.click_element("t1", "button[type=submit]", timeout_ms=1234)

        self.assertTrue(result["success"])
        self.assertEqual(result["method"], "css")
        self.assertEqual(button.clicked_with, {"timeout": 1234, "no_wait_after": True})


class ServerModelRegressionTests(unittest.TestCase):
    def test_action_response_preserves_endpoint_specific_fields(self):
        payload = ActionResponse(
            success=True,
            url="https://example.com/",
            selector="button",
            method="css",
            scrollX=0,
            scrollY=600,
        ).model_dump()

        self.assertEqual(payload["url"], "https://example.com/")
        self.assertEqual(payload["selector"], "button")
        self.assertEqual(payload["method"], "css")
        self.assertEqual(payload["scrollX"], 0)
        self.assertEqual(payload["scrollY"], 600)


if __name__ == "__main__":
    unittest.main()
