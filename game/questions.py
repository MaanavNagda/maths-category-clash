"""Loading and validation for markdown question files.

Block format — one clue per block, blocks separated by blank lines:

    Category: Algebra
    Points: 100
    Question: Solve $x^2 = 9$.
    Answer: $x = \\pm 3$
    All In: yes            <- optional; marks the tile as an All In wager

Recognised keys (case-insensitive): Category, Points, Question, Answer,
All In, Seconds. A "Key:" line with an unrecognised key is treated as a
continuation of the current field, so questions may contain colons.

Three loaders, one per upload slot in the host view:

  load_board(path)  -> regular board: exactly 4 categories x 4 clues
  load_bonus(path)  -> bonus board:   exactly 2 categories x 2 clues
  load_finale(path) -> single block:  Category / Question / Answer
                       (+ optional Seconds, default 300)

Each returns (data, errors); data is None when errors exist.
"""

import os
import re

BOARD_CATEGORIES = 4
BOARD_CLUES = 4
BONUS_CATEGORIES = 2
BONUS_CLUES = 2
BOARD_TIMERS = [30, 45, 60, 120]    # seconds per row, top to bottom
BONUS_TIMERS = [120, 300]
DEFAULT_FINALE_SECONDS = 300

KEYS = {"category", "points", "question", "answer", "all in", "seconds"}
_KEY_RE = re.compile(r"^([A-Za-z][A-Za-z ]*):\s*(.*)$")
_TRUTHY = {"yes", "true", "1", "y"}


def parse_blocks(text):
    """Split markdown text into field dicts. Returns (blocks, errors)."""
    blocks, errors = [], []
    cur, cur_key = None, None
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.rstrip()
        if not line.strip():
            if cur is not None:
                blocks.append(cur)
                cur, cur_key = None, None
            continue
        m = _KEY_RE.match(line)
        if m and m.group(1).strip().lower() in KEYS:
            if cur is None:
                cur = {}
            cur_key = m.group(1).strip().lower()
            cur[cur_key] = m.group(2).strip()
        elif cur is None:
            errors.append(f"line {lineno}: text outside any block")
        else:
            cur[cur_key] += "\n" + line   # continuation of current field
    if cur is not None:
        blocks.append(cur)
    return blocks, errors


def _build_board(blocks, n_cats, n_clues, timers, name):
    """Group clue blocks into categories; validate shape. -> (board, errors)"""
    errors = []
    cats, order = {}, []
    for bi, b in enumerate(blocks):
        where = f"block {bi + 1}"
        missing = [k for k in ("category", "points", "question", "answer")
                   if not b.get(k, "").strip()]
        if missing:
            errors.append(f"{where}: missing {', '.join(missing)}")
            continue
        try:
            pts = int(b["points"].strip())
        except ValueError:
            errors.append(f"{where}: points must be an integer")
            continue
        if pts <= 0:
            errors.append(f"{where}: points must be positive")
            continue
        cat = b["category"].strip()
        if cat not in cats:
            cats[cat] = []
            order.append(cat)
        cats[cat].append({
            "value": pts,
            "question": b["question"].strip(),
            "answer": b["answer"].strip(),
            "all_in": b.get("all in", "").strip().lower() in _TRUTHY,
        })

    if len(order) != n_cats:
        errors.append(
            f"needs exactly {n_cats} categories, found {len(order)}"
            + (f" ({', '.join(order)})" if order else ""))
    for c in order:
        if len(cats[c]) != n_clues:
            errors.append(
                f"category '{c}': needs exactly {n_clues} clues, "
                f"found {len(cats[c])}")
    if errors:
        return None, errors

    return {"name": name,
            "categories": [
                {"name": c,
                 "clues": sorted(cats[c], key=lambda cl: cl["value"])}
                for c in order],
            "timers": list(timers)}, []


def _read(path):
    if not os.path.isfile(path):
        return None, [f"File not found: {path}"]
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read(), []
    except OSError as exc:
        return None, [f"Could not read file: {exc}"]


def _load(path, n_cats, n_clues, timers, name):
    text, errors = _read(path)
    if errors:
        return None, errors
    blocks, errors = parse_blocks(text)
    if not blocks:
        errors.append("no clue blocks found")
    if errors:
        return None, errors
    return _build_board(blocks, n_cats, n_clues, timers, name)


def load_board(path):
    """Regular board file: 4 categories x 4 clues, rows 30/45/60/120s."""
    return _load(path, BOARD_CATEGORIES, BOARD_CLUES, BOARD_TIMERS, "board")


def load_bonus(path):
    """Bonus board file: 2 categories x 2 clues, rows 120/300s."""
    return _load(path, BONUS_CATEGORIES, BONUS_CLUES, BONUS_TIMERS, "bonus")


def load_finale(path):
    """Finale file: one block with Category/Question/Answer (+Seconds)."""
    text, errors = _read(path)
    if errors:
        return None, errors
    blocks, errors = parse_blocks(text)
    if len(blocks) != 1:
        errors.append(
            f"finale file must contain exactly one block, "
            f"found {len(blocks)}")
        return None, errors
    b = blocks[0]
    missing = [k for k in ("category", "question", "answer")
               if not b.get(k, "").strip()]
    if missing:
        errors.append("finale: missing " + ", ".join(missing))
    secs = DEFAULT_FINALE_SECONDS
    if b.get("seconds", "").strip():
        try:
            secs = int(b["seconds"].strip())
            if secs <= 0:
                raise ValueError
        except ValueError:
            errors.append("finale: seconds must be a positive integer")
    if errors:
        return None, errors
    return {"category": b["category"].strip(),
            "question": b["question"].strip(),
            "answer": b["answer"].strip(),
            "seconds": secs}, []
