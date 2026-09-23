"""Maths Category Clash — entry point.

Launches two windows sharing one game controller over QWebChannel:
  • Display window — projector-facing view (logo/rules/board/questions/scores)
  • Host window    — laptop-facing control panel

Everything runs locally: pages load over file:// and a request interceptor
blocks any non-local URL, so the app works with no network at all.
"""

import os
import sys

import PySide6.QtWebEngineWidgets  # noqa: F401  (must precede QApplication)
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import (QWebEngineProfile,
                                     QWebEngineUrlRequestInterceptor,
                                     QWebEngineUrlRequestInfo)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QApplication, QMainWindow

from game.controller import Controller

ROOT = os.path.dirname(os.path.abspath(__file__))
ALLOWED_SCHEMES = {"file", "qrc", "data", "blob", "about"}


class LocalOnlyInterceptor(QWebEngineUrlRequestInterceptor):
    """Hard guarantee: nothing leaves the machine."""

    def interceptRequest(self, info: QWebEngineUrlRequestInfo):
        if info.requestUrl().scheme() not in ALLOWED_SCHEMES:
            info.block(True)


class WebWindow(QMainWindow):
    def __init__(self, title, html_path, controller):
        super().__init__()
        self.setWindowTitle(title)
        self.view = QWebEngineView(self)
        self.channel = QWebChannel(self.view.page())
        self.channel.registerObject("controller", controller)
        self.view.page().setWebChannel(self.channel)
        self.view.setUrl(QUrl.fromLocalFile(html_path))
        self.setCentralWidget(self.view)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Maths Category Clash")

    profile = QWebEngineProfile.defaultProfile()
    interceptor = LocalOnlyInterceptor(profile)
    profile.setUrlRequestInterceptor(interceptor)

    controller = Controller()

    display = WebWindow(
        "Maths Category Clash — Display",
        os.path.join(ROOT, "web", "display", "index.html"), controller)
    host = WebWindow(
        "Maths Category Clash — Host",
        os.path.join(ROOT, "web", "host", "index.html"), controller)
    controller.host_window = host

    display.resize(1366, 860)
    host.resize(1120, 780)
    display.show()
    host.show()

    # Ctrl+Shift+R — cycle to the Bonus Board (works from either window).
    for win in (display, host):
        sc = QShortcut(QKeySequence("Ctrl+Shift+R"), win)
        sc.setContext(Qt.ApplicationShortcut)
        sc.activated.connect(controller.activateBonus)

    # F11 — toggle fullscreen on the display window.
    fs = QShortcut(QKeySequence("F11"), display)
    fs.setContext(Qt.ApplicationShortcut)
    fs.activated.connect(
        lambda: display.showNormal()
        if display.isFullScreen() else display.showFullScreen())

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
