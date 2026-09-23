"""Loading and validation for questions JSON files.

Format:
{
  "rounds": [
    {"name": "Round 1", "categories": [
      {"name": "Algebra", "clues": [
        {"value": 100, "question": "Solve $x^2=9$.", "answer": "$x=\\\\pm 3$",
         "all_in": false},
        ... exactly 4 clues, values 100/200/300/400 ...
      ]},
      ... exactly 4 categories ...
    ]},
    ... optional second round (Bonus Board) ...
  ],
  "finale": {"category": "Number Theory", "question": "...", "answer": "...",
             "seconds": 300}          // optional; seconds defaults to 300
}
"""

import json
import os

VALID_VALUES = (100, 200, 300, 400)
CATEGORIES_PER_ROUND = 4
CLUES_PER_CATEGORY = 4
MAX_ROUNDS = 2


def _err(errors, where, msg):
    errors.append(f"{where}: {msg}")


def validate(data):
    """Return a list of human-readable problems; empty list means valid."""
    errors = []
    if not isinstance(data, dict):
        return ["Root must be a JSON object"]

    rounds = data.get("rounds")
    if not isinstance(rounds, list) or not rounds:
        _err(errors, "rounds", "must be a non-empty list")
        return errors
    if len(rounds) > MAX_ROUNDS:
        _err(errors, "rounds", f"at most {MAX_ROUNDS} rounds supported")

    for ri, rnd in enumerate(rounds):
        where = f"rounds[{ri}]"
        if not isinstance(rnd, dict):
            _err(errors, where, "must be an object")
            continue
        cats = rnd.get("categories")
        if not isinstance(cats, list) or len(cats) != CATEGORIES_PER_ROUND:
            _err(errors, where,
                 f"needs exactly {CATEGORIES_PER_ROUND} categories")
            continue
        for ci, cat in enumerate(cats):
            cwhere = f"{where}.categories[{ci}]"
            if not isinstance(cat, dict):
                _err(errors, cwhere, "must be an object")
                continue
            if not cat.get("name") or not isinstance(cat["name"], str):
                _err(errors, cwhere, "missing category 'name'")
            clues = cat.get("clues")
            if not isinstance(clues, list) or len(clues) != CLUES_PER_CATEGORY:
                _err(errors, cwhere,
                     f"needs exactly {CLUES_PER_CATEGORY} clues")
                continue
            values = sorted(c.get("value") for c in clues
                            if isinstance(c, dict))
            if values != sorted(VALID_VALUES):
                _err(errors, cwhere,
                     f"clue values must be {VALID_VALUES}")
            for ii, clue in enumerate(clues):
                iwhere = f"{cwhere}.clues[{ii}]"
                if not isinstance(clue, dict):
                    _err(errors, iwhere, "must be an object")
                    continue
                if not clue.get("question"):
                    _err(errors, iwhere, "missing 'question'")
                if not clue.get("answer"):
                    _err(errors, iwhere, "missing 'answer'")
                if "all_in" in clue and not isinstance(clue["all_in"], bool):
                    _err(errors, iwhere, "'all_in' must be true/false")

    finale = data.get("finale")
    if finale is not None:
        if not isinstance(finale, dict):
            _err(errors, "finale", "must be an object")
        else:
            for field in ("category", "question", "answer"):
                if not finale.get(field):
                    _err(errors, "finale", f"missing '{field}'")
            secs = finale.get("seconds")
            if secs is not None and (not isinstance(secs, int) or secs <= 0):
                _err(errors, "finale", "'seconds' must be a positive int")

    return errors


def normalise(data):
    """Sort each category's clues by value so board rows line up."""
    for rnd in data["rounds"]:
        for cat in rnd["categories"]:
            cat["clues"].sort(key=lambda c: c["value"])
    return data


def load(path):
    """Load + validate a questions file.

    Returns (data, errors). data is None when errors exist.
    """
    if not os.path.isfile(path):
        return None, [f"File not found: {path}"]
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except json.JSONDecodeError as exc:
        return None, [f"Invalid JSON: {exc}"]
    except OSError as exc:
        return None, [f"Could not read file: {exc}"]

    errors = validate(data)
    if errors:
        return None, errors
    return normalise(data), []
