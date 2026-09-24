# Maths Category Clash

A Jeopardy-style quiz game for maths society sessions. Native Linux desktop app
with **two windows** — a projector **display** and a laptop **host panel** —
running **100% locally** (no network needed at runtime).

## Run

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python main.py
```

Drag the **Display** window to the projector (F11 = fullscreen). Keep the
**Host** window on your laptop.

## Session flow

1. **Setup (host)** — set team count/names, load the three markdown files
   (board / bonus / finale), upload a logo (optional), rename any labels
   (optional). Press **Start game**.
2. **Logo → Rules** — shown on the display; press **Next**.
3. **Board** — 4 categories × 4 tiles. Click a tile on either window.
4. **Question** — countdown auto-starts (30/60/90/120s by value). Click the
   display again (with confirmation) to reveal the answer.
5. **Scoring (host)** — tap teams in finishing order (tap again to undo);
   1st = 100% of points, each later team −10%. **End question & score**.
6. **All In tile** — the choosing team wagers (up to their score, min. tile
   max 400) and answers alone: +wager if right, −wager if wrong.
7. **Bonus Board** — `Ctrl+Shift+R` switches to the hidden 2×2 second board
   (if a bonus file was loaded).
8. **Grand Finale** — host enters each team's wager privately → question +
   5:00 timer → mark each team right/wrong → final standings.

## Question files — markdown format

Three separate uploads in the host view (each persists across restarts):

- **Regular board** — `board.example.md`: 4 categories × 4 clues.
- **Bonus board** — `bonus.example.md`: 2 categories × 2 clues.
- **Grand Finale** — `finale.example.md`: one block, no `Points:`.

Format — one clue per block, blocks separated by a blank line:

```
Category: Algebra
Points: 100
Question: Solve $x^2 = 9$.
Answer: $x = \pm 3$
All In: yes          <- optional; marks the tile as an All In wager
```

- Keys (case-insensitive): `Category`, `Points`, `Question`, `Answer`,
  `All In`, `Seconds` (finale only, default 300).
- Clues are grouped by `Category` (first-seen order = column order) and
  sorted by `Points` (row order). Any positive point values work.
- Timers are per row: regular board 30s / 45s / 60s / 2min, bonus 2min / 5min.
- LaTeX: `$…$` inline, `$$…$$` display (KaTeX, vendored — works offline).
- Keep real questions **out of the repo** — name files `*.local.md`
  (gitignored) and load those.

## Online version (Firebase)

A browser-based edition lives in `online/` and is deployed at
**https://maths-category-clash.web.app** — no install needed.

- Open the URL → **Create room** for the host tab. Setup shows a display
  link — open it on the projector/second tab (or another machine).
- The host tab runs the game and syncs via Firebase Realtime Database;
  the display tab is read-only (tile/reveal clicks are forwarded).
- Answers never reach the display early — they live under a secret path
  that can't be enumerated (see `database.rules.json`).
- Host reloads recover the full session (state dump in the private node).
- Redeploy after edits: `firebase deploy --only hosting`
  (`online/firebase-config.js` is gitignored — copy the example file).

## Tests

```bash
.venv/bin/python -m unittest discover -s tests -v
```

Unit tests cover scoring, wager caps, JSON validation, and the full state
machine; the integration test launches both windows offscreen and drives a
complete game through the controller.

## Manual test checklist

- [ ] Both windows open; display shows logo splash
- [ ] Host: set teams, load `questions.example.json`, upload a logo
- [ ] Rename a label → display updates; survives app restart (config.json)
- [ ] Rules → board; tile click → question + correct countdown
- [ ] Second click → confirm → answer on display
- [ ] Host ranking → end question → scores on display scorebar
- [ ] All In tile → wager flow → ±wager applied
- [ ] Ctrl+Shift+R → Bonus Board appears
- [ ] Grand Finale → wagers → 5:00 question → results → standings
- [ ] Disconnect wifi → everything still works

## Packaging (optional)

```bash
.venv/bin/pip install pyinstaller
.venv/bin/pyinstaller --noconfirm --add-data "web:web" \
  --add-data "board.example.md:." --add-data "bonus.example.md:." \
  --add-data "finale.example.md:." -n maths-category-clash main.py
```

## Legal

Not affiliated with Jeopardy!. All branding is neutral and renameable;
game mechanics are not copyrightable, but the names/visual identity are —
which is why this app ships with its own.
