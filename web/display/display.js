/* Display window renderer. Receives filtered snapshots (no early answers). */

const app = document.getElementById("app");
let S = null;               // last state
let lastTimerTotal = 0;

const RULES = [
  "<b>Teams.</b> Play in teams — solve together at your table on whiteboards.",
  "<b>Speed flash.</b> When a question appears, every team solves at once. Raise your board as soon as you have an answer.",
  "<b>Ranked points.</b> First correct team earns full points; each later correct team earns 10% less.",
  "<b>Three attempts.</b> Wrong? Erase, re-work, and try again — up to 3 tries within the time limit.",
  "<b>No penalties.</b> Incorrect guesses cost nothing. Only correct answers score.",
  "<b>Plain answers.</b> Just write the final answer clearly — no 'what is…' needed.",
  "<b>Time limits.</b> Rows: 30s · 45s · 60s · 2min (bonus board: 2min · 5min). Time up = nobody scores.",
  "<b>All In.</b> One hidden tile: the choosing team wagers points and answers alone.",
];

function render(state) {
  S = state;
  if (state.timer_total) lastTimerTotal = state.timer_total;
  else if (state.active) lastTimerTotal = state.active.timer;
  else if (state.finale) lastTimerTotal = state.finale.seconds;
  app.innerHTML = "";
  const phase = state.phase;
  if (phase === "setup") return viewLogo(state);
  if (phase === "rules") return viewRules(state);
  if (phase === "board") return viewBoard(state);
  if (phase === "wager") return viewWager(state);
  if (phase === "question" || phase === "answer") return viewQuestion(state);
  if (phase === "finale_category") return viewFinaleCategory(state);
  if (phase === "finale_wagers") return viewFinaleWagers(state);
  if (phase === "finale_question") return viewFinaleQuestion(state);
  if (phase === "finale_results") return viewFinaleResults(state);
  if (phase === "standings") return viewStandings(state);
}

/* ---------------- logo / setup ---------------- */
function viewLogo(s) {
  const scr = el("section", "screen center");
  const img = document.createElement("img");
  img.className = "logo-img" + (s.logo ? "" : " placeholder");
  img.src = s.logo || "../shared/placeholder-logo.svg";
  img.alt = "";
  scr.appendChild(img);
  scr.appendChild(el("h1", "game-title", s.labels.title));
  scr.appendChild(el("hr", "rule-line splash-rule"));
  scr.appendChild(el("p", "splash-sub", "Maths Society Quiz"));
  app.appendChild(scr);
}

/* ---------------- rules ---------------- */
function viewRules(s) {
  const scr = el("section", "screen center");
  const box = el("div", "rules-box");
  box.appendChild(el("h2", "rules-title", "How it works"));
  const ol = el("ol", "rules-list");
  RULES.forEach((r) => {
    const li = document.createElement("li");
    const span = document.createElement("span");
    span.innerHTML = r;
    li.appendChild(span);
    ol.appendChild(li);
  });
  box.appendChild(ol);
  scr.appendChild(box);
  const next = el("button", "primary next-btn", "Next →");
  next.onclick = () => controller.advance();
  scr.appendChild(next);
  app.appendChild(scr);
}

/* ---------------- board ---------------- */
function viewBoard(s) {
  const scr = el("section", "screen");
  const head = el("div", "board-head");
  head.appendChild(el("div", "board-round",
    s.round_name || s.labels["round" + (s.round_index + 1)] || ""));
  head.appendChild(el("div", "label", s.labels.title));
  scr.appendChild(head);

  const grid = el("div", "board-grid");
  const nCats = s.board.categories.length;
  const nRows = s.board.categories[0].clues.length;
  grid.style.gridTemplateColumns = `repeat(${nCats}, 1fr)`;
  grid.style.gridTemplateRows = `auto repeat(${nRows}, 1fr)`;
  s.board.categories.forEach((cat) => {
    grid.appendChild(el("div", "cat-cell", cat.name));
  });
  for (let row = 0; row < nRows; row++) {
    s.board.categories.forEach((cat, ci) => {
      const clue = cat.clues[row];
      const t = el("div", "tile" + (clue.used ? " used" : ""));
      t.appendChild(el("span", "tile-val", clue.value));
      if (!clue.used) t.onclick = () => controller.selectTile(ci, row);
      grid.appendChild(t);
    });
  }
  scr.appendChild(grid);
  scr.appendChild(scorebar(s));
  app.appendChild(scr);
}

function scorebar(s) {
  const bar = el("div", "scorebar");
  const top = Math.max(...s.teams.map((t) => t.score));
  s.teams.forEach((t) => {
    const d = el("div", "sb-team" + (t.score === top && top > 0 ? " leader" : ""));
    d.appendChild(el("div", "sb-name", t.name));
    d.appendChild(el("div", "sb-score", t.score));
    bar.appendChild(d);
  });
  return bar;
}

/* ---------------- All In splash ---------------- */
function viewWager(s) {
  const scr = el("section", "screen center");
  scr.appendChild(el("div", "label", s.active.category));
  scr.appendChild(el("div", "big-word", s.labels.all_in));
  scr.appendChild(el("p", "splash-sub", "A wager is being placed…"));
  app.appendChild(scr);
}

/* ---------------- question / answer ---------------- */
function viewQuestion(s) {
  const scr = el("section", "screen");
  const meta = el("div", "q-meta");
  meta.appendChild(el("span", null, s.active.category));
  meta.appendChild(el("span", "pts", s.active.value + " pts"));
  if (s.active.all_in) {
    meta.appendChild(el("span", "badge", s.labels.all_in));
    if (s.active.wager !== undefined)
      meta.appendChild(el("span", "pts", "wager: " + s.active.wager));
  }
  scr.appendChild(meta);

  const body = el("div", "q-body");
  const q = el("div", "q-text tex");
  q.textContent = s.active.question;
  tex(q);
  body.appendChild(q);

  if (s.answer_revealed) {
    const ab = el("div", "a-block");
    ab.appendChild(el("div", "a-label", "Answer"));
    const at = el("div", "a-text tex");
    at.textContent = s.active.answer;
    tex(at);
    ab.appendChild(at);
    body.appendChild(ab);
  } else {
    body.appendChild(timerWrap(s));
  }
  scr.appendChild(body);
  scr.onclick = () => {
    if (!s.answer_revealed)
      confirmModal("Reveal answer?", "The answer will be shown to every team.",
        "Reveal", () => controller.revealAnswer());
  };
  app.appendChild(scr);
  paintTimer(S.timer_remaining || 0);
}

function timerWrap(s) {
  const initial = s.timer_remaining || lastTimerTotal || 0;
  const w = el("div", "timer-wrap");
  w.appendChild(el("div", "timer-num", fmtTime(initial))).id = "tnum";
  const track = el("div", "timer-track");
  track.appendChild(el("div", "timer-fill")).id = "tfill";
  w.appendChild(track);
  if (s.time_up) w.appendChild(el("div", "time-up", "Time"));
  return w;
}

function paintTimer(secs) {
  const num = document.getElementById("tnum");
  const fill = document.getElementById("tfill");
  if (num) {
    num.textContent = fmtTime(secs);
    num.classList.toggle("low", secs <= 10);
  }
  if (fill && lastTimerTotal) {
    fill.style.width = Math.max(0, (secs / lastTimerTotal) * 100) + "%";
    fill.classList.toggle("low", secs <= 10);
  }
}

/* ---------------- finale ---------------- */
function viewFinaleCategory(s) {
  const scr = el("section", "screen center");
  scr.appendChild(el("div", "big-word", s.labels.finale));
  scr.appendChild(el("hr", "rule-line splash-rule"));
  scr.appendChild(el("p", "splash-sub", "Category"));
  scr.appendChild(el("h1", "game-title", s.finale.category));
  app.appendChild(scr);
}

function viewFinaleWagers(s) {
  const scr = el("section", "screen center");
  scr.appendChild(el("div", "big-word", s.labels.finale));
  scr.appendChild(el("p", "splash-sub", "Teams are placing their wagers…"));
  app.appendChild(scr);
}

function viewFinaleQuestion(s) {
  const scr = el("section", "screen");
  const meta = el("div", "q-meta");
  meta.appendChild(el("span", "badge", s.labels.finale));
  meta.appendChild(el("span", null, s.finale.category));
  scr.appendChild(meta);
  const body = el("div", "q-body");
  const q = el("div", "q-text tex");
  q.textContent = s.finale.question;
  tex(q);
  body.appendChild(q);
  body.appendChild(timerWrap(s));
  scr.appendChild(body);
  app.appendChild(scr);
  paintTimer(S.timer_remaining || lastTimerTotal || 0);
}

function viewFinaleResults(s) {
  const scr = el("section", "screen center");
  scr.appendChild(el("div", "label", s.labels.finale + " — answer"));
  const at = el("div", "a-text tex");
  at.style.marginTop = "30px";
  at.textContent = s.finale.answer;
  tex(at);
  scr.appendChild(at);
  scr.appendChild(el("p", "splash-sub", "Results are being tallied…"))
    .style.marginTop = "40px";
  app.appendChild(scr);
}

/* ---------------- standings ---------------- */
function viewStandings(s) {
  const scr = el("section", "screen center");
  const box = el("div", "standings-box");
  box.appendChild(el("h2", "rules-title", "Final standings"));
  s.standings.forEach((t) => {
    const row = el("div", "standing-row" + (t.place === 1 ? " winner" : ""));
    row.appendChild(el("span", "place", String(t.place).padStart(2, "0")));
    row.appendChild(el("span", "name", t.name));
    const w = s.finale_wagers_public[t.id];
    if (w !== undefined) row.appendChild(el("span", "wager", "wagered " + w));
    row.appendChild(el("span", "score", t.score));
    box.appendChild(row);
  });
  scr.appendChild(box);
  app.appendChild(scr);
}

initBridge("displayChanged", render, paintTimer);

initBridge("displayChanged", render, paintTimer);
