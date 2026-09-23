/* Host window renderer — control panel. Receives full snapshots (answers,
   wagers, ranking) that the display never sees early. */

const app = document.getElementById("app");
const topbar = document.getElementById("topbar");
let S = null;
let wagerTeam = null;   // selected All In team (local UI state)

const LABEL_FIELDS = [
  ["title", "Game title"],
  ["all_in", "Wager tile"],
  ["finale", "Final round"],
  ["bonus", "Bonus board"],
  ["round1", "Round 1 name"],
  ["round2", "Round 2 name"],
];

function render(state) {
  const prevFocus = document.activeElement && document.activeElement.id;
  S = state;
  renderTopbar(state);
  app.innerHTML = "";
  const phase = state.phase;
  if (phase === "setup") viewSetup(state);
  else if (phase === "rules") viewSimple(state, "Rules are on the display.",
    "Next →", () => controller.advance());
  else if (phase === "board") viewBoard(state);
  else if (phase === "wager") viewWager(state);
  else if (phase === "question" || phase === "answer") viewQuestion(state);
  else if (phase === "finale_category") viewSimple(state,
    "Display shows the " + state.labels.finale + " category.",
    "Collect wagers →", () => controller.advance());
  else if (phase === "finale_wagers") viewFinaleWagers(state);
  else if (phase === "finale_question") viewFinaleQuestion(state);
  else if (phase === "finale_results") viewFinaleResults(state);
  else if (phase === "standings") viewStandings(state);
  if (prevFocus) {
    const f = document.getElementById(prevFocus);
    if (f) f.focus();
  }
}

function renderTopbar(s) {
  topbar.innerHTML = "";
  topbar.appendChild(el("span", "tb-title", s.labels.title));
  topbar.appendChild(el("span", "tb-phase", s.phase.replace(/_/g, " ")));
  const t = el("span", "tb-timer", fmtTime(s.timer_remaining || 0));
  t.id = "tnum";
  topbar.appendChild(t);
}

function paintTimer(secs) {
  const num = document.getElementById("tnum");
  if (num) {
    num.textContent = fmtTime(secs);
    num.classList.toggle("low", secs <= 10);
  }
}

function panel() {
  const p = el("div", "panel");
  app.appendChild(p);
  if (S.message) {
    p.appendChild(el("div",
      "msg" + (S.message.startsWith("Loaded") ? " info" : ""), S.message));
  }
  return p;
}

/* ---------------- setup ---------------- */
function viewSetup(s) {
  const p = panel();
  p.appendChild(el("h2", null, "Game setup"));

  // teams
  p.appendChild(el("h3", null, "Teams"));
  const countRow = el("div", "row");
  const countField = el("div", "field");
  countField.appendChild(el("label", null, "Number of teams"));
  const sel = document.createElement("select");
  sel.id = "team-count";
  for (let n = 2; n <= 8; n++) {
    const o = document.createElement("option");
    o.value = n; o.textContent = n;
    sel.appendChild(o);
  }
  sel.value = (s.teams.length || s.config_teams.length || 5);
  sel.onchange = () => buildTeamInputs(p, s);
  countField.appendChild(sel);
  countRow.appendChild(countField);
  p.appendChild(countRow);
  const namesWrap = el("div", "grid2");
  namesWrap.id = "team-names";
  p.appendChild(namesWrap);
  buildTeamInputs(p, s);
  const saveTeams = el("button", null, "Save teams");
  saveTeams.onclick = () => {
    const names = [...document.querySelectorAll(".team-name")]
      .map((i) => i.value);
    controller.setTeams(JSON.stringify(names));
  };
  const stRow = el("div", "btn-row");
  stRow.appendChild(saveTeams);
  p.appendChild(stRow);

  // question files — three separate uploads, each persisted
  p.appendChild(el("h3", null, "Question files"));
  [["board", "Regular board (4×4)", "openBoard", s.board_loaded],
   ["bonus", "Bonus board (2×2)", "openBonus", s.bonus_loaded],
   ["finale", s.labels.finale + " clue", "openFinale", s.finale_loaded]]
    .forEach(([key, pretty, slot, loaded]) => {
      const row = el("div", "row");
      const btn = el("button", null, "Load " + pretty.toLowerCase() + "…");
      btn.onclick = () => controller[slot]();
      row.appendChild(btn);
      row.appendChild(el("span", "label",
        loaded ? "✓ " + (s[key + "_name"] || "loaded") : "not loaded"));
      p.appendChild(row);
    });

  // logo
  p.appendChild(el("h3", null, "Logo"));
  const lRow = el("div", "row");
  const logoBtn = el("button", null, "Upload logo…");
  logoBtn.onclick = () => controller.openLogo();
  lRow.appendChild(logoBtn);
  const img = document.createElement("img");
  img.className = "logo-preview";
  img.src = s.logo || "../shared/placeholder-logo.svg";
  lRow.appendChild(img);
  lRow.appendChild(el("span", "label", s.logo_name || "default placeholder"));
  p.appendChild(lRow);

  // labels
  p.appendChild(el("h3", null, "Labels (rename anything)"));
  const grid = el("div", "grid2");
  LABEL_FIELDS.forEach(([key, pretty]) => {
    const f = el("div", "field");
    f.appendChild(el("label", null, pretty));
    const inp = document.createElement("input");
    inp.type = "text";
    inp.id = "label-" + key;
    inp.value = s.labels[key] || "";
    inp.onchange = () => controller.setLabel(key, inp.value);
    f.appendChild(inp);
    grid.appendChild(f);
  });
  p.appendChild(grid);

  // start
  const startRow = el("div", "btn-row");
  const start = el("button", "primary", "Start game →");
  start.disabled = !(s.board_loaded && s.teams.length >= 2);
  start.onclick = () => controller.startGame();
  startRow.appendChild(start);
  p.appendChild(startRow);
}

function buildTeamInputs(p, s) {
  const wrap = p.querySelector("#team-names");
  if (!wrap) return;
  const count = parseInt(p.querySelector("#team-count").value, 10);
  const current = [...wrap.querySelectorAll(".team-name")].map((i) => i.value);
  const saved = s.teams.length ? s.teams.map((t) => t.name) : s.config_teams;
  wrap.innerHTML = "";
  for (let i = 0; i < count; i++) {
    const f = el("div", "field");
    f.appendChild(el("label", null, "Team " + (i + 1)));
    const inp = document.createElement("input");
    inp.type = "text";
    inp.className = "team-name";
    inp.id = "team-name-" + i;
    inp.value = current[i] || saved[i] || "";
    f.appendChild(inp);
    wrap.appendChild(f);
  }
}

/* ---------------- simple phases ---------------- */
function viewSimple(s, text, btnLabel, fn) {
  const p = panel();
  p.appendChild(el("h2", null, text));
  const row = el("div", "btn-row");
  const b = el("button", "primary", btnLabel);
  b.onclick = fn;
  row.appendChild(b);
  p.appendChild(row);
}

/* ---------------- board ---------------- */
function viewBoard(s) {
  const p = panel();
  p.appendChild(el("h2", null,
    (s.round_name || "Board") + (s.board_complete ? " — complete" : "")));

  const grid = el("div", "mini-grid");
  const nCats = s.board.categories.length;
  const nRows = s.board.categories[0].clues.length;
  grid.style.gridTemplateColumns = `repeat(${nCats}, 1fr)`;
  s.board.categories.forEach((cat) =>
    grid.appendChild(el("div", "mini-cat", cat.name)));
  for (let row = 0; row < nRows; row++) {
    s.board.categories.forEach((cat, ci) => {
      const clue = cat.clues[row];
      const t = el("div", "mini-tile" + (clue.used ? " used" : ""), clue.value);
      if (!clue.used) t.onclick = () => controller.selectTile(ci, row);
      grid.appendChild(t);
    });
  }
  p.appendChild(grid);
  p.appendChild(scoresStrip(s));

  const row = el("div", "btn-row");
  if (s.finale_loaded) {
    const fin = el("button", "primary", s.labels.finale + " →");
    fin.onclick = () => confirmModal(
      "Start " + s.labels.finale + "?",
      "The board will close and the final round begins.", "Start",
      () => controller.startFinale());
    row.appendChild(fin);
  }
  const reset = el("button", "ghost", "New game");
  reset.onclick = () => confirmModal("Reset game?",
    "Scores reset to zero and the board is restored.", "Reset",
    () => controller.resetGame());
  row.appendChild(reset);
  p.appendChild(row);
}

function scoresStrip(s) {
  const strip = el("div", "scores-strip");
  s.teams.forEach((t) => {
    const d = el("span", "sc");
    d.appendChild(document.createTextNode(t.name));
    const b = el("b", null, t.score);
    d.appendChild(b);
    strip.appendChild(d);
  });
  return strip;
}

/* ---------------- All In wager ---------------- */
function viewWager(s) {
  wagerTeam = null;
  const p = panel();
  p.appendChild(el("h2", null,
    s.labels.all_in + " — " + s.active.category + " (" + s.active.value + ")"));
  p.appendChild(el("h3", null, "Which team is answering?"));
  const grid = el("div", "team-grid");
  s.teams.forEach((t) => {
    const b = el("button", "team-btn", t.name);
    b.onclick = () => {
      wagerTeam = t.id;
      grid.querySelectorAll(".team-btn").forEach((x) =>
        x.classList.remove("ranked"));
      b.classList.add("ranked");
      updateCap();
    };
    grid.appendChild(b);
  });
  p.appendChild(grid);

  p.appendChild(el("h3", null, "Wager"));
  const row = el("div", "row");
  const inp = document.createElement("input");
  inp.type = "number"; inp.min = 1; inp.id = "wager-input";
  row.appendChild(inp);
  const cap = el("span", "label", "pick a team first");
  cap.id = "wager-cap";
  row.appendChild(cap);
  p.appendChild(row);

  const tileMax = Math.max(...s.board.categories.flatMap(
    (c) => c.clues.map((cl) => cl.value)));
  function updateCap() {
    if (wagerTeam === null) return;
    const score = s.teams[wagerTeam].score;
    cap.textContent = "max " + Math.max(score, tileMax);
    inp.max = Math.max(score, tileMax);
  }

  const btns = el("div", "btn-row");
  const ok = el("button", "primary", "Lock wager & show question");
  ok.onclick = () => {
    const amt = parseInt(inp.value, 10);
    if (wagerTeam === null || !(amt >= 1)) return;
    controller.setWager(wagerTeam, amt);
  };
  const abort = el("button", "ghost", "Abort tile");
  abort.onclick = () => controller.abortQuestion();
  btns.appendChild(ok); btns.appendChild(abort);
  p.appendChild(btns);
}

/* ---------------- question / answer ---------------- */
function viewQuestion(s) {
  const p = panel();
  p.appendChild(el("h2", null,
    s.active.category + " — " + s.active.value + " pts" +
    (s.active.all_in ? " — " + s.labels.all_in : "")));

  const q = el("div", "q-card");
  q.appendChild(el("div", "qc-label", "Question"));
  const qt = el("div", "qc-text tex");
  qt.textContent = s.active.question;
  tex(qt);
  q.appendChild(qt);
  p.appendChild(q);

  const a = el("div", "q-card answer");
  a.appendChild(el("div", "qc-label", "Answer (host only)"));
  const at = el("div", "qc-text tex");
  at.textContent = s.active.answer;
  tex(at);
  a.appendChild(at);
  p.appendChild(a);

  if (s.active.all_in) allInControls(p, s);
  else rankControls(p, s);

  const row = el("div", "btn-row");
  if (!s.answer_revealed) {
    const rev = el("button", null, "Reveal answer");
    rev.onclick = () => confirmModal("Reveal answer?",
      "Shown on the display to every team.", "Reveal",
      () => controller.revealAnswer());
    row.appendChild(rev);
  }
  const end = el("button", "primary", "End question & score");
  end.onclick = () => controller.endQuestion();
  const abort = el("button", "ghost", "Abort");
  abort.onclick = () => confirmModal("Abort tile?",
    "Returns to the board; tile stays unused.", "Abort",
    () => controller.abortQuestion());
  row.appendChild(end); row.appendChild(abort);
  p.appendChild(row);
}

function rankControls(p, s) {
  p.appendChild(el("h3", null,
    "Tap teams in finishing order (tap again to undo)"));
  const grid = el("div", "team-grid");
  s.teams.forEach((t) => {
    const pos = s.ranking.indexOf(t.id);
    const b = el("button", "team-btn" + (pos >= 0 ? " ranked" : ""), t.name);
    if (pos >= 0) {
      const pts = Math.round(s.active.value * Math.max(100 - 10 * pos, 10) / 100);
      b.appendChild(el("span", "rank-badge", "#" + (pos + 1) + " +" + pts));
    }
    b.onclick = () => controller.toggleRank(t.id);
    grid.appendChild(b);
  });
  p.appendChild(grid);
}

function allInControls(p, s) {
  const team = s.teams[s.active.wager_team];
  p.appendChild(el("h3", null,
    team.name + " wagered " + s.active.wager + " — mark the result"));
  const grid = el("div", "team-grid");
  const ok = el("button", "team-btn" +
    (s.all_in_result === true ? " correct" : ""), "Correct");
  const bad = el("button", "team-btn" +
    (s.all_in_result === false ? " incorrect" : ""), "Incorrect");
  ok.onclick = () => controller.setAllInResult(true);
  bad.onclick = () => controller.setAllInResult(false);
  grid.appendChild(ok); grid.appendChild(bad);
  p.appendChild(grid);
}

/* ---------------- finale ---------------- */
function viewFinaleWagers(s) {
  const p = panel();
  p.appendChild(el("h2", null, s.labels.finale + " — wagers"));
  p.appendChild(el("h3", null, "Category: " + s.finale.category));
  s.teams.forEach((t) => {
    const row = el("div", "row");
    row.appendChild(el("span", "label", t.name + " (" + t.score + ")"));
    const inp = document.createElement("input");
    inp.type = "number"; inp.min = 0;
    inp.max = Math.max(0, t.score);
    inp.id = "fw-" + t.id;
    inp.value = s.finale_wagers[t.id] || 0;
    inp.onchange = () =>
      controller.setFinaleWager(t.id, parseInt(inp.value || "0", 10));
    row.appendChild(inp);
    row.appendChild(el("span", "label", "max " + Math.max(0, t.score)));
    p.appendChild(row);
  });
  const btns = el("div", "btn-row");
  const go = el("button", "primary", "Reveal question (5:00)");
  go.onclick = () => confirmModal("Reveal the question?",
    "The " + s.labels.finale + " question and timer start on the display.",
    "Reveal", () => controller.startFinaleQuestion());
  btns.appendChild(go);
  p.appendChild(btns);
}

function viewFinaleQuestion(s) {
  const p = panel();
  p.appendChild(el("h2", null, s.labels.finale));
  const q = el("div", "q-card");
  q.appendChild(el("div", "qc-label", "Question"));
  const qt = el("div", "qc-text tex");
  qt.textContent = s.finale.question;
  tex(qt);
  q.appendChild(qt);
  p.appendChild(q);
  const a = el("div", "q-card answer");
  a.appendChild(el("div", "qc-label", "Answer (host only)"));
  const at = el("div", "qc-text tex");
  at.textContent = s.finale.answer;
  tex(at);
  a.appendChild(at);
  p.appendChild(a);
  const row = el("div", "btn-row");
  const rev = el("button", "primary", "Reveal answer & mark results");
  rev.onclick = () => controller.revealFinaleAnswer();
  row.appendChild(rev);
  p.appendChild(row);
}

function viewFinaleResults(s) {
  const p = panel();
  p.appendChild(el("h2", null, s.labels.finale + " — results"));
  p.appendChild(el("h3", null, "Mark each team (wager shown)"));
  const grid = el("div", "team-grid");
  s.teams.forEach((t) => {
    const res = s.finale_results[t.id];
    const b = el("button",
      "team-btn" + (res === true ? " correct" : res === false ? " incorrect" : ""),
      t.name + " — wager " + (s.finale_wagers[t.id] || 0));
    b.onclick = () => controller.setFinaleResult(t.id, res !== true);
    grid.appendChild(b);
  });
  p.appendChild(grid);
  const row = el("div", "btn-row");
  const fin = el("button", "primary", "Finish — final standings");
  fin.onclick = () => controller.finishFinale();
  row.appendChild(fin);
  p.appendChild(row);
}

function viewStandings(s) {
  const p = panel();
  p.appendChild(el("h2", null, "Final standings"));
  s.standings.forEach((t) => {
    p.appendChild(el("div", "sc",
      "#" + t.place + "  " + t.name + " — " + t.score));
  });
  const row = el("div", "btn-row");
  const again = el("button", null, "New game");
  again.onclick = () => controller.resetGame();
  row.appendChild(again);
  p.appendChild(row);
}

initBridge("hostChanged", render, paintTimer);
