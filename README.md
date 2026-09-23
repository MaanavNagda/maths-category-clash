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

1. **Setup (host)** — set team count/names, load a questions JSON, upload a
   logo (optional), rename any labels (optional). Press **Start game**.
2. **Logo → Rules** — shown on the display; press **Next**.
3. **Board** — 4 categories × 4 tiles (100–400 pts). Click a tile on either
   window.
4. **Question** — countdown auto-starts (30/60/90/120s by value). Click the
   display again (with confirmation) to reveal the answer.
5. **Scoring (host)** — tap teams in finishing order (tap again to undo);
   1st = 100% of points, each later team −10%. **End question & score**.
6. **All In tile** — the choosing team wagers (up to their score, min. tile
   max 400) and answers alone: +wager if right, −wager if wrong.
7. **Bonus Board** — `Ctrl+Shift+R` switches to the hidden second round
   (if the JSON has one).
8. **Grand Finale** — host enters each team's wager privately → question +
   5:00 timer → mark each team right/wrong → final standings.

## Questions JSON format

See `questions.example.json`. Structure:

```jsonc
{
  "rounds": [
    { "name": "Round 1",
      "categories": [
        { "name": "Algebra",
          "clues": [
            { "value": 100, "question": "Solve $x^2=9$.", "answer": "$x=\\pm 3$",
              "all_in": false }   // all_in optional; exactly 4 clues per
          ] }                     // category, values 100/200/300/400
      ] },                        // exactly 4 categories per round
    { "name": "Bonus Board", "categories": [ … ] }   // optional round 2
  ],
  "finale": { "category": "…", "question": "…", "answer": "…",
              "seconds": 300 }                        // optional
}
```

- LaTeX: `$…$` inline, `$$…$$` display, `\(…\)`, `\[…\]` (KaTeX, vendored —
  works offline).
- Keep your real questions **out of the public repo** — copy the example to
  `questions.local.json` (gitignored) and load that.

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
  --add-data "questions.example.json:." -n maths-category-clash main.py
```

## Legal

Not affiliated with Jeopardy!. All branding is neutral and renameable;
game mechanics are not copyrightable, but the names/visual identity are —
which is why this app ships with its own.
