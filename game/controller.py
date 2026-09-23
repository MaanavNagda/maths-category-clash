"""Qt-facing controller: wraps GameState, owns the countdown timer, and
broadcasts JSON snapshots to the two web views over QWebChannel.

JS calls the @Slot methods; both views re-render on their dedicated signal
(displayChanged / hostChanged) so the projector never receives answers early.
"""

import json
import os
import shutil
import time

from PySide6.QtCore import QObject, QTimer, Signal, Slot
from PySide6.QtWidgets import QFileDialog

from game import config as cfg_mod
from game import questions
from game.logic import DEFAULT_FINALE_SECONDS, GameError, GameState

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
USERDATA_DIR = os.path.join(PROJECT_ROOT, "userdata")


class Controller(QObject):
    displayChanged = Signal(str)
    hostChanged = Signal(str)
    tick = Signal(int)          # seconds remaining (for smooth countdown)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.state = GameState()
        self.config = cfg_mod.load()
        self.host_window = None   # set by main.py for dialog parenting
        self._deadline = None
        self._timer_total = 0
        self._timer = QTimer(self)
        self._timer.setInterval(200)
        self._timer.timeout.connect(self._on_tick)
        # Pre-fill teams from last session so setup is one click.
        if self.config["teams"]:
            try:
                self.state.set_teams(self.config["teams"])
            except GameError:
                pass
        # Auto-load last session's files, if they still exist.
        loaded, missing = [], []
        for key, loader, setter in (
                ("board", questions.load_board, self.state.load_board),
                ("bonus", questions.load_bonus, self.state.load_bonus),
                ("finale", questions.load_finale, self.state.load_finale)):
            path = self.config.get(key)
            if not path:
                continue
            if not os.path.isfile(path):
                missing.append(os.path.basename(path))
                continue
            data, errors = loader(path)
            if errors:
                self.state.message += (
                    f"{os.path.basename(path)} failed validation: "
                    + "; ".join(errors[:6]) + "\n")
                continue
            try:
                setter(data)
                loaded.append(os.path.basename(path))
            except GameError as exc:
                self.state.message += str(exc) + "\n"
        if loaded:
            self.state.message += "Loaded " + ", ".join(loaded)
        if missing:
            self.state.message += (
                "\nNot found: " + ", ".join(missing) + " — load again.")
        self.state.message = self.state.message.strip()

    # ------------------------------------------------------------ internals

    def _logo_url(self):
        logo = self.config.get("logo")
        if not logo:
            return None
        path = os.path.join(PROJECT_ROOT, logo)
        return "file://" + path if os.path.isfile(path) else None

    def _snapshot(self, role):
        snap = self.state.snapshot(role)
        snap["labels"] = self.config["labels"]
        snap["logo"] = self._logo_url()
        snap["timer_remaining"] = self._remaining()
        snap["timer_total"] = self._timer_total
        if role == "host":
            snap["config_teams"] = self.config["teams"]
            snap["logo_name"] = (os.path.basename(self.config["logo"])
                                 if self.config.get("logo") else None)
            for key in ("board", "bonus", "finale"):
                snap[key + "_name"] = (
                    os.path.basename(self.config[key])
                    if self.config.get(key) else None)
        if self.state._rounds():
            snap["round_name"] = snap["labels"][
                "round1" if self.state.round_index == 0 else "round2"]
        return snap

    def _push(self):
        self.displayChanged.emit(json.dumps(self._snapshot("display")))
        self.hostChanged.emit(json.dumps(self._snapshot("host")))

    def _run(self, fn, *args):
        """Execute a GameState method, surfacing GameError to the host."""
        try:
            fn(*args)
            self.state.message = ""
        except GameError as exc:
            self.state.message = str(exc)
        self._push()

    # ----------------------------------------------------------------- timer

    def _remaining(self):
        if self._deadline is None:
            return 0
        return max(0, int(round(self._deadline - time.monotonic())))

    def _start_timer(self, seconds):
        self._timer_total = seconds
        self._deadline = time.monotonic() + seconds
        self._timer.start()
        self.tick.emit(seconds)

    def _stop_timer(self):
        self._timer.stop()
        self._deadline = None
        self._timer_total = 0

    def _on_tick(self):
        remaining = self._remaining()
        self.tick.emit(remaining)
        if remaining <= 0:
            self._stop_timer()
            self.state.time_up = True
            self._push()

    # ------------------------------------------------------------- file I/O

    def _load_file(self, title, loader, setter, config_key):
        """Shared upload flow: pick file -> parse -> load -> persist path."""
        path, _ = QFileDialog.getOpenFileName(
            self.host_window, title, PROJECT_ROOT,
            "Markdown files (*.md *.markdown *.txt)")
        if not path:
            return
        data, errors = loader(path)
        if errors:
            self.state.message = f"{os.path.basename(path)} rejected:\n" + \
                "\n".join(f"• {e}" for e in errors[:12])
            self._push()
            return
        self._run(setter, data)
        self.config[config_key] = path
        cfg_mod.save(self.config)
        self.state.message = f"Loaded {os.path.basename(path)}"
        self._push()

    @Slot()
    def openBoard(self):
        self._load_file("Load regular board", questions.load_board,
                        self.state.load_board, "board")

    @Slot()
    def openBonus(self):
        self._load_file("Load bonus board", questions.load_bonus,
                        self.state.load_bonus, "bonus")

    @Slot()
    def openFinale(self):
        self._load_file("Load Grand Finale clue", questions.load_finale,
                        self.state.load_finale, "finale")

    @Slot()
    def openLogo(self):
        path, _ = QFileDialog.getOpenFileName(
            self.host_window, "Choose logo image", PROJECT_ROOT,
            "Images (*.png *.jpg *.jpeg *.svg *.webp)")
        if not path:
            return
        os.makedirs(USERDATA_DIR, exist_ok=True)
        dest = os.path.join(USERDATA_DIR, "logo" + os.path.splitext(path)[1])
        try:
            shutil.copyfile(path, dest)
        except OSError as exc:
            self.state.message = f"Could not copy logo: {exc}"
            self._push()
            return
        self.config["logo"] = os.path.relpath(dest, PROJECT_ROOT)
        cfg_mod.save(self.config)
        self._push()

    # -------------------------------------------------------- slots: setup

    @Slot()
    def requestState(self):
        """Views call this once the channel is up to get the first snapshot."""
        self._push()

    @Slot(str)
    def setTeams(self, names_json):
        try:
            names = json.loads(names_json)
        except json.JSONDecodeError:
            names = []
        self._run(self.state.set_teams, names)
        if not self.state.message:
            self.config["teams"] = [t["name"] for t in self.state.teams]
            cfg_mod.save(self.config)

    @Slot(str, str)
    def setLabel(self, key, value):
        if key in self.config["labels"] and value.strip():
            self.config["labels"][key] = value.strip()
            cfg_mod.save(self.config)
            self._push()

    @Slot()
    def startGame(self):
        self._run(self.state.start_game)

    @Slot()
    def resetGame(self):
        """New game: zero scores, clear used tiles, keep teams + questions."""
        for t in self.state.teams:
            t["score"] = 0
        self.state.used = set()
        self.state.round_index = 0
        self.state._clear_active()
        self.state.phase = "board" if self.state._rounds() else "setup"
        self._stop_timer()
        self._push()

    # -------------------------------------------------------- slots: board

    @Slot()
    def advance(self):
        self._run(self.state.advance)

    @Slot(int, int)
    def selectTile(self, cat, idx):
        self._run(self.state.select_tile, cat, idx)
        if self.state.phase == "question" and self.state.active:
            self._start_timer(self.state.active["timer"])

    @Slot(int, int)
    def setWager(self, team_id, amount):
        self._run(self.state.set_wager, team_id, amount)
        if self.state.phase == "question" and self.state.active:
            self._start_timer(self.state.active["timer"])

    @Slot()
    def revealAnswer(self):
        self._run(self.state.reveal_answer)
        if self.state.phase == "answer":
            self._stop_timer()

    @Slot(int)
    def toggleRank(self, team_id):
        self._run(self.state.toggle_rank, team_id)

    @Slot(bool)
    def setAllInResult(self, correct):
        self._run(self.state.set_all_in_result, correct)

    @Slot()
    def endQuestion(self):
        self._run(self.state.end_question)
        if self.state.phase == "board":
            self._stop_timer()

    @Slot()
    def abortQuestion(self):
        self._run(self.state.abort_question)
        self._stop_timer()

    @Slot()
    def activateBonus(self):
        self._run(self.state.activate_bonus)

    # ------------------------------------------------------- slots: finale

    @Slot()
    def startFinale(self):
        self._run(self.state.start_finale)

    @Slot(int, int)
    def setFinaleWager(self, team_id, amount):
        self._run(self.state.set_finale_wager, team_id, amount)

    @Slot()
    def startFinaleQuestion(self):
        self._run(self.state.start_finale_question)
        if self.state.phase == "finale_question":
            secs = DEFAULT_FINALE_SECONDS
            if self.state.finale:
                secs = self.state.finale.get("seconds", secs)
            self._start_timer(secs)

    @Slot()
    def revealFinaleAnswer(self):
        self._run(self.state.reveal_finale_answer)
        self._stop_timer()

    @Slot(int, bool)
    def setFinaleResult(self, team_id, correct):
        self._run(self.state.set_finale_result, team_id, correct)

    @Slot()
    def finishFinale(self):
        self._run(self.state.finish_finale)
