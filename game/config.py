"""Persistence for user settings: renameable labels, logo path, team names.

Stored in config.json in the project root (gitignored — custom labels may
contain trademarked terms, so they must never reach the public repo).
"""

import json
import os

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "config.json")

DEFAULT_LABELS = {
    "title": "Maths Category Clash",
    "all_in": "All In",
    "finale": "Grand Finale",
    "bonus": "Bonus Board",
    "round1": "Round 1",
    "round2": "Bonus Board",
}

DEFAULTS = {
    "labels": DEFAULT_LABELS,
    "logo": None,          # path inside userdata/, e.g. "userdata/logo.png"
    "board": None,         # absolute path to last loaded board .md
    "bonus": None,         # absolute path to last loaded bonus .md
    "finale": None,        # absolute path to last loaded finale .md
    "teams": ["Team 1", "Team 2", "Team 3", "Team 4", "Team 5"],
}


def load():
    cfg = dict(DEFAULTS)
    cfg["labels"] = dict(DEFAULT_LABELS)
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
            saved = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return cfg
    if isinstance(saved.get("labels"), dict):
        cfg["labels"].update({k: str(v) for k, v in saved["labels"].items()})
    if saved.get("logo"):
        cfg["logo"] = saved["logo"]
    for key in ("board", "bonus", "finale"):
        if saved.get(key):
            cfg[key] = saved[key]
    if isinstance(saved.get("teams"), list) and saved["teams"]:
        cfg["teams"] = [str(t) for t in saved["teams"]]
    return cfg


def save(cfg):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, indent=2)
    except OSError:
        pass  # non-fatal: settings just won't persist
