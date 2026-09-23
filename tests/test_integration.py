"""Integration test: launches the real app offscreen (both web windows +
controller) and drives a complete game through the JS bridge.

Run: .venv/bin/python -m unittest tests.test_integration -v
"""

import json
import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS",
                      "--no-sandbox --disable-gpu")

import PySide6.QtWebEngineWidgets  # noqa: F401,E402  (before QApplication)
from PySide6.QtCore import QEventLoop, QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from game.controller import Controller  # noqa: E402
from main import ROOT, WebWindow  # noqa: E402


def wait_for(pred, timeout_ms=15000):
    loop = QEventLoop()
    timer = QTimer()
    timer.setInterval(50)
    timer.timeout.connect(lambda: pred() and loop.quit())
    timer.start()
    QTimer.singleShot(timeout_ms, loop.quit)
    loop.exec()
    return pred()


def js(page, expr, timeout_ms=8000):
    """Evaluate JS, waiting for the (possibly async) result."""
    box = {}
    page.runJavaScript(expr, lambda v: box.setdefault("v", v))
    wait_for(lambda: "v" in box, timeout_ms)
    return box.get("v")


def sample_data():
    def clues():
        return [{"value": v, "question": f"Q{v} $x^2$", "answer": f"A{v}"}
                for v in (100, 200, 300, 400)]
    r1 = {"name": "Round 1", "categories": [
        {"name": f"C{c}", "clues": clues()} for c in range(4)]}
    r2 = {"name": "Bonus", "categories": [
        {"name": f"B{c}", "clues": clues()} for c in range(4)]}
    r2["categories"][0]["clues"][0]["all_in"] = True
    return {"rounds": [r1, r2],
            "finale": {"category": "F", "question": "FQ", "answer": "FA",
                       "seconds": 300}}


class TestApp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)
        cls.ctl = Controller()
        cls.display = WebWindow("d", os.path.join(
            ROOT, "web", "display", "index.html"), cls.ctl)
        cls.host = WebWindow("h", os.path.join(
            ROOT, "web", "host", "index.html"), cls.ctl)
        cls.ctl.host_window = cls.host
        cls.display.show()
        cls.host.show()

        # Wait for both pages to finish loading (poll readyState — avoids
        # racing the loadFinished signal).
        for page in (cls.display.view.page(), cls.host.view.page()):
            ok = wait_for(lambda p=page: js(
                p, "document.readyState") == "complete", 20000)
            assert ok, "page load"

        # Wait for the JS bridge on both pages.
        for page in (cls.display.view.page(), cls.host.view.page()):
            ok = wait_for(lambda p=page: js(
                p, "typeof controller !== 'undefined' && controller !== null"),
                15000)
            assert ok, "webchannel bridge connected"

        cls.last = {"display": None, "host": None}
        cls.ctl.displayChanged.connect(
            lambda s: cls.last.update(display=json.loads(s)))
        cls.ctl.hostChanged.connect(
            lambda s: cls.last.update(host=json.loads(s)))

    @classmethod
    def tearDownClass(cls):
        cls.display.close()
        cls.host.close()

    # ------------------------------------------------------------- helpers

    def dstate(self):
        wait_for(lambda: self.last["display"] is not None, 3000)
        return self.last["display"]

    def hstate(self):
        wait_for(lambda: self.last["host"] is not None, 3000)
        return self.last["host"]

    # ---------------------------------------------------------------- test

    def test_full_game(self):
        ctl = self.ctl

        # --- setup ---
        ctl.setTeams(json.dumps(["Alpha", "Beta", "Gamma"]))
        ctl._run(ctl.state.load_data, sample_data())
        ctl.setLabel("title", "Test Clash")
        ctl.startGame()
        self.assertEqual(self.dstate()["phase"], "rules")
        self.assertEqual(self.dstate()["labels"]["title"], "Test Clash")

        # display rendered the rules screen
        ok = wait_for(lambda: js(self.display.view.page(),
                                 "document.querySelectorAll('.rules-list li')"
                                 ".length") == 8)
        self.assertTrue(ok, "rules rendered on display")

        # --- board ---
        ctl.advance()
        self.assertEqual(self.dstate()["phase"], "board")
        ok = wait_for(lambda: js(self.display.view.page(),
                                 "document.querySelectorAll('.tile').length")
                      == 16)
        self.assertTrue(ok, "16 tiles rendered")

        # --- question ---
        ctl.selectTile(0, 0)
        d = self.dstate()
        self.assertEqual(d["phase"], "question")
        self.assertNotIn("answer", d["active"])          # hidden from display
        self.assertEqual(self.hstate()["active"]["answer"], "A100")
        self.assertTrue(ctl._deadline is not None)       # timer running

        # --- ranked scoring ---
        for tid in (2, 0, 1):
            ctl.toggleRank(tid)
        self.assertEqual(self.hstate()["ranking"], [2, 0, 1])
        ctl.revealAnswer()
        self.assertIn("answer", self.dstate()["active"])   # now visible
        ctl.endQuestion()
        d = self.dstate()
        self.assertEqual(d["phase"], "board")
        scores = {t["name"]: t["score"] for t in d["teams"]}
        self.assertEqual(scores, {"Alpha": 90, "Beta": 80, "Gamma": 100})

        # --- bonus board via shortcut path ---
        ctl.activateBonus()
        self.assertEqual(self.dstate()["round_index"], 1)

        # --- All In ---
        ctl.selectTile(0, 0)
        self.assertEqual(self.dstate()["phase"], "wager")
        ctl.setWager(0, 200)
        self.assertEqual(self.dstate()["phase"], "question")
        self.assertNotIn("wager", self.dstate()["active"])  # hidden til reveal
        ctl.setAllInResult(True)
        ctl.revealAnswer()
        self.assertEqual(self.dstate()["active"]["wager"], 200)
        ctl.endQuestion()
        scores = {t["name"]: t["score"] for t in self.dstate()["teams"]}
        self.assertEqual(scores["Alpha"], 290)            # 90 + 200 wager

        # --- Grand Finale ---
        ctl.startFinale()
        self.assertEqual(self.dstate()["phase"], "finale_category")
        self.assertNotIn("question", self.dstate()["finale"])
        ctl.advance()
        self.assertEqual(self.dstate()["phase"], "finale_wagers")
        ctl.setFinaleWager(0, 100)
        ctl.setFinaleWager(1, 50)
        ctl.setFinaleWager(2, 0)
        ctl.startFinaleQuestion()
        self.assertIn("question", self.dstate()["finale"])
        ctl.revealFinaleAnswer()
        for tid, ok_ in ((0, True), (1, False), (2, True)):
            ctl.setFinaleResult(tid, ok_)
        ctl.finishFinale()
        d = self.dstate()
        self.assertEqual(d["phase"], "standings")
        scores = {t["name"]: t["score"] for t in d["teams"]}
        self.assertEqual(scores, {"Alpha": 390, "Beta": 30, "Gamma": 100})
        self.assertEqual(d["standings"][0]["name"], "Alpha")

    def test_katex_and_offline(self):
        page = self.display.view.page()
        self.assertTrue(js(page, "typeof katex === 'object'"), "KaTeX loaded")
        self.assertTrue(js(page, "typeof renderMathInElement === 'function'"))
        # external requests must be blocked by the interceptor
        js(page, "window.__fb = null;"
                 "fetch('https://example.com')"
                 ".then(() => window.__fb = false)"
                 ".catch(() => window.__fb = true);")
        ok = wait_for(lambda: js(page, "window.__fb") is not None, 8000)
        self.assertTrue(ok and js(page, "window.__fb"),
                        "external fetch blocked")


if __name__ == "__main__":
    unittest.main()
