"""Pure game logic for Maths Category Clash.

No Qt imports here — this module is fully unit-testable. The Qt-facing
controller (game/controller.py) wraps GameState and broadcasts snapshots.
"""

TIMER_BY_VALUE = {100: 30, 200: 60, 300: 90, 400: 120}
MAX_TILE_VALUE = 400
MIN_TEAMS = 2
MAX_TEAMS = 8
DEFAULT_FINALE_SECONDS = 300

PHASES = (
    "setup",            # host configuring; display shows logo splash
    "rules",            # rules page on display
    "board",            # tile grid on display
    "wager",            # All In: host picks team + wager (display: splash)
    "question",         # question + countdown on display
    "answer",           # answer revealed on display
    "finale_category",  # Grand Finale category splash
    "finale_wagers",    # host enters wagers privately
    "finale_question",  # finale clue + countdown
    "finale_results",   # answer shown; host marks teams right/wrong
    "standings",        # final results
)


class GameError(Exception):
    """Raised for invalid actions; controller surfaces message to host."""


def rank_percent(position):
    """Scoring curve: 1st place (position 0) = 100%, each next -10%, floor 10%."""
    if position < 0:
        raise ValueError("position must be >= 0")
    return max(100 - 10 * position, 10)


def rank_points(value, position):
    """Points awarded to the team finishing at `position` (0-indexed)."""
    return round(value * rank_percent(position) / 100)


def timer_seconds(value):
    """Countdown length for a tile value; defaults to 60s for odd values."""
    return TIMER_BY_VALUE.get(value, 60)


def all_in_wager_cap(score):
    """Authentic Daily Double cap: current score, or max tile value if less."""
    return max(score, MAX_TILE_VALUE)


def finale_wager_cap(score):
    """Grand Finale wager cap: up to current score (0 if score <= 0)."""
    return max(0, score)


class GameState:
    def __init__(self):
        self.reset()

    def reset(self):
        self.phase = "setup"
        self.teams = []              # [{"name": str, "score": int}]
        self.data = None             # validated questions dict
        self.round_index = 0
        self.used = set()            # {(round, cat, idx)}
        self.active = None           # current clue dict + location
        self.wager = None            # All In: {"team": int, "amount": int}
        self.all_in_result = None    # bool once host marks it
        self.ranking = []            # team ids in finishing order
        self.answer_revealed = False
        self.time_up = False
        self.finale_wagers = {}      # {team_id: int}
        self.finale_results = {}     # {team_id: bool}
        self.message = ""

    # ------------------------------------------------------------------ setup

    def load_data(self, data):
        """Attach a validated questions dict (see game/questions.py)."""
        if not isinstance(data, dict) or "rounds" not in data:
            raise GameError("Invalid question data")
        self.data = data
        self.round_index = 0
        self.used = set()

    def set_teams(self, names):
        names = [n.strip() for n in names if n and n.strip()]
        if not (MIN_TEAMS <= len(names) <= MAX_TEAMS):
            raise GameError(f"Enter {MIN_TEAMS}–{MAX_TEAMS} team names")
        self.teams = [{"name": n, "score": 0} for n in names]

    def start_game(self):
        if self.data is None:
            raise GameError("Load a questions file first")
        if len(self.teams) < MIN_TEAMS:
            raise GameError("Set up teams first")
        self.phase = "rules"

    def advance(self):
        """Generic 'next' button: rules -> board, logo handled by start_game."""
        if self.phase == "rules":
            self.phase = "board"
        elif self.phase == "finale_category":
            self.phase = "finale_wagers"
        else:
            raise GameError(f"Nothing to advance from phase '{self.phase}'")

    # ------------------------------------------------------------------ board

    def _clue(self, cat, idx):
        if self.data is None:
            raise GameError("No questions loaded")
        rounds = self.data["rounds"]
        if not (0 <= self.round_index < len(rounds)):
            raise GameError("Bad round")
        cats = rounds[self.round_index]["categories"]
        if not (0 <= cat < len(cats)):
            raise GameError("Bad category")
        clues = cats[cat]["clues"]
        if not (0 <= idx < len(clues)):
            raise GameError("Bad clue")
        return clues[idx]

    def select_tile(self, cat, idx):
        if self.phase != "board":
            raise GameError("Not on the board")
        if (self.round_index, cat, idx) in self.used:
            raise GameError("Tile already used")
        clue = self._clue(cat, idx)
        self.active = {
            "round": self.round_index, "cat": cat, "idx": idx,
            "value": clue["value"], "question": clue["question"],
            "answer": clue["answer"], "all_in": bool(clue.get("all_in")),
            "category": self.data["rounds"][self.round_index]
            ["categories"][cat]["name"],
        }
        self.answer_revealed = False
        self.time_up = False
        self.ranking = []
        self.wager = None
        self.all_in_result = None
        self.phase = "wager" if self.active["all_in"] else "question"

    def set_wager(self, team_id, amount):
        if self.phase != "wager" or not self.active:
            raise GameError("No wager pending")
        self._check_team(team_id)
        cap = all_in_wager_cap(self.teams[team_id]["score"])
        if not (1 <= amount <= cap):
            raise GameError(f"Wager must be 1–{cap}")
        self.wager = {"team": team_id, "amount": amount}
        self.phase = "question"

    # --------------------------------------------------------------- question

    def _check_team(self, team_id):
        if not (0 <= team_id < len(self.teams)):
            raise GameError("Bad team id")

    def reveal_answer(self):
        if self.phase not in ("question", "answer"):
            raise GameError("No question in play")
        self.answer_revealed = True
        self.phase = "answer"

    def toggle_rank(self, team_id):
        if self.phase not in ("question", "answer"):
            raise GameError("No question in play")
        if self.active and self.active["all_in"]:
            raise GameError("All In uses correct/incorrect, not ranking")
        self._check_team(team_id)
        if team_id in self.ranking:
            self.ranking.remove(team_id)
        else:
            self.ranking.append(team_id)

    def set_all_in_result(self, correct):
        if self.phase not in ("question", "answer") or not self.active:
            raise GameError("No question in play")
        if not self.active["all_in"]:
            raise GameError("Not an All In tile")
        self.all_in_result = bool(correct)

    def end_question(self):
        if self.phase not in ("question", "answer") or not self.active:
            raise GameError("No question in play")
        if self.active["all_in"]:
            if self.all_in_result is None:
                raise GameError("Mark the All In result (correct/incorrect)")
            delta = self.wager["amount"] * (1 if self.all_in_result else -1)
            self.teams[self.wager["team"]]["score"] += delta
        else:
            for pos, tid in enumerate(self.ranking):
                self.teams[tid]["score"] += rank_points(self.active["value"], pos)
        self.used.add((self.active["round"], self.active["cat"],
                       self.active["idx"]))
        self._clear_active()
        self.phase = "board"

    def abort_question(self):
        """Back out of a tile without scoring or consuming it."""
        if self.phase not in ("wager", "question", "answer"):
            raise GameError("No question in play")
        self._clear_active()
        self.phase = "board"

    def _clear_active(self):
        self.active = None
        self.wager = None
        self.all_in_result = None
        self.ranking = []
        self.answer_revealed = False
        self.time_up = False

    def board_complete(self):
        if self.data is None:
            return False
        cats = self.data["rounds"][self.round_index]["categories"]
        return all(
            (self.round_index, c, i) in self.used
            for c in range(len(cats)) for i in range(len(cats[c]["clues"]))
        )

    def activate_bonus(self):
        """Ctrl+Shift+R: cycle to the next available round's board."""
        if self.phase != "board":
            raise GameError("Only available on the board")
        if self.data is None or len(self.data["rounds"]) < 2:
            raise GameError("No bonus round in this questions file")
        self.round_index = (self.round_index + 1) % len(self.data["rounds"])

    # ----------------------------------------------------------------- finale

    def start_finale(self):
        if self.phase != "board":
            raise GameError("Only available on the board")
        if not self.data or "finale" not in self.data:
            raise GameError("No finale in this questions file")
        self.finale_wagers = {}
        self.finale_results = {}
        self.time_up = False
        self.phase = "finale_category"

    def set_finale_wager(self, team_id, amount):
        if self.phase != "finale_wagers":
            raise GameError("Not taking wagers")
        self._check_team(team_id)
        cap = finale_wager_cap(self.teams[team_id]["score"])
        if not (0 <= amount <= cap):
            raise GameError(
                f"Wager for {self.teams[team_id]['name']} must be 0–{cap}")
        self.finale_wagers[team_id] = amount

    def start_finale_question(self):
        if self.phase != "finale_wagers":
            raise GameError("Not taking wagers")
        for tid in range(len(self.teams)):
            self.finale_wagers.setdefault(tid, 0)  # unmarked teams wager 0
        self.time_up = False
        self.phase = "finale_question"

    def reveal_finale_answer(self):
        if self.phase != "finale_question":
            raise GameError("No finale question in play")
        self.phase = "finale_results"

    def set_finale_result(self, team_id, correct):
        if self.phase != "finale_results":
            raise GameError("Not marking results")
        self._check_team(team_id)
        self.finale_results[team_id] = bool(correct)

    def finish_finale(self):
        if self.phase != "finale_results":
            raise GameError("Not marking results")
        unmarked = [t["name"] for i, t in enumerate(self.teams)
                    if i not in self.finale_results]
        if unmarked:
            raise GameError("Mark every team correct or incorrect: "
                            + ", ".join(unmarked))
        for tid, correct in self.finale_results.items():
            wager = self.finale_wagers.get(tid, 0)
            self.teams[tid]["score"] += wager if correct else -wager
        self.phase = "standings"

    # --------------------------------------------------------------- snapshot

    def standings(self):
        order = sorted(range(len(self.teams)),
                       key=lambda i: (-self.teams[i]["score"], i))
        return [{"id": i, "name": self.teams[i]["name"],
                 "score": self.teams[i]["score"], "place": p + 1}
                for p, i in enumerate(order)]

    def snapshot(self, role):
        """Serialisable state for a view. role: 'display' or 'host'.

        The display never receives answers/wagers before reveal time.
        """
        host = role == "host"
        s = {
            "phase": self.phase,
            "teams": [{"id": i, "name": t["name"], "score": t["score"]}
                      for i, t in enumerate(self.teams)],
            "round_index": self.round_index,
            "rounds_total": len(self.data["rounds"]) if self.data else 0,
            "round_name": (self.data["rounds"][self.round_index].get("name")
                           if self.data else ""),
            "questions_loaded": self.data is not None,
            "board_complete": self.board_complete(),
            "time_up": self.time_up,
            "answer_revealed": self.answer_revealed,
        }

        if self.data:
            s["board"] = {"categories": [
                {"name": c["name"], "clues": [
                    {"value": cl["value"],
                     "used": (self.round_index, ci, ii) in self.used}
                    for ii, cl in enumerate(c["clues"])]}
                for ci, c in enumerate(
                    self.data["rounds"][self.round_index]["categories"])]}
            if "finale" in self.data:
                f = self.data["finale"]
                fin = {"category": f["category"],
                       "seconds": f.get("seconds", DEFAULT_FINALE_SECONDS)}
                if self.phase in ("finale_question", "finale_results",
                                  "standings") or host:
                    fin["question"] = f["question"]
                if self.phase in ("finale_results", "standings") or host:
                    fin["answer"] = f["answer"]
                s["finale"] = fin

        if self.active:
            a = {"category": self.active["category"],
                 "value": self.active["value"],
                 "all_in": self.active["all_in"],
                 "question": self.active["question"],
                 "timer": timer_seconds(self.active["value"])}
            if self.answer_revealed or host:
                a["answer"] = self.active["answer"]
            if self.wager:
                a["wager_team"] = self.wager["team"]
                if self.answer_revealed or host:
                    a["wager"] = self.wager["amount"]
            s["active"] = a

        if host:
            s["ranking"] = list(self.ranking)
            s["all_in_result"] = self.all_in_result
            s["finale_wagers"] = dict(self.finale_wagers)
            s["finale_results"] = dict(self.finale_results)
            s["message"] = self.message

        if self.phase == "standings":
            s["standings"] = self.standings()
            s["finale_wagers_public"] = dict(self.finale_wagers)

        return s
