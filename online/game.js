/* Pure game logic for Maths Category Clash — JS port of game/logic.py and
   game/questions.py. Runs in the host tab (the authority); no Firebase or DOM
   imports here so it stays unit-testable. */

"use strict";

const MIN_TEAMS = 2;
const MAX_TEAMS = 8;
const DEFAULT_FINALE_SECONDS = 300;

const BOARD_CATEGORIES = 4, BOARD_CLUES = 4;
const BONUS_CATEGORIES = 2, BONUS_CLUES = 2;
const BOARD_TIMERS = [30, 45, 60, 120];   // seconds per row, top to bottom
const BONUS_TIMERS = [120, 300];

class GameError extends Error {}

function rankPercent(position) {
  if (position < 0) throw new GameError("position must be >= 0");
  return Math.max(100 - 10 * position, 10);
}

function rankPoints(value, position) {
  return Math.round(value * rankPercent(position) / 100);
}

function allInWagerCap(score, tileMax) {
  return Math.max(score, tileMax);
}

function finaleWagerCap(score) {
  return Math.max(0, score);
}

/* ---------------- markdown parser (port of questions.py) ---------------- */

const Q_KEYS = new Set(
  ["category", "points", "question", "answer", "all in", "seconds"]);
const Q_ALIASES = { "point amount": "points", "pts": "points",
                    "daily double": "all in", "all-in": "all in" };
const Q_KEY_RE = /^([A-Za-z][A-Za-z -]*):\s*(.*)$/;
const Q_TRUTHY = new Set(["yes", "true", "1", "y"]);
const Q_ALL_IN_MARK = /\*?\*?\s*(daily double|all[ -]?in)\s*\*?\*?/i;

function parseBlocks(text) {
  const blocks = [], errors = [];
  let cur = null, curKey = null;
  text.split(/\r?\n/).forEach((raw, i) => {
    const line = raw.replace(/\s+$/, "");
    const lineno = i + 1;
    if (!line.trim()) {
      if (cur !== null) { blocks.push(cur); cur = null; curKey = null; }
      return;
    }
    const m = line.match(Q_KEY_RE);
    const canon = m
      ? (Q_ALIASES[m[1].trim().toLowerCase()] || m[1].trim().toLowerCase())
      : null;
    if (m && Q_KEYS.has(canon)) {
      if (cur === null) cur = {};
      curKey = canon;
      cur[curKey] = m[2].trim();
    } else if (cur === null) {
      errors.push(`line ${lineno}: text outside any block`);
    } else {
      cur[curKey] += "\n" + line;   // continuation of current field
    }
  });
  if (cur !== null) blocks.push(cur);
  return [blocks, errors];
}

function buildBoard(blocks, nCats, nClues, timers, name) {
  const errors = [];
  const cats = {}, order = [];
  blocks.forEach((b, bi) => {
    const where = `block ${bi + 1}`;
    const missing = ["category", "points", "question", "answer"]
      .filter((k) => !(b[k] || "").trim());
    if (missing.length) {
      errors.push(`${where}: missing ${missing.join(", ")}`);
      return;
    }
    let rawPts = b.points.trim();
    const inlineAllIn = Q_ALL_IN_MARK.test(rawPts);
    rawPts = rawPts.replace(Q_ALL_IN_MARK, "").trim();
    const pts = parseInt(rawPts, 10);
    if (Number.isNaN(pts) || String(pts) !== rawPts && !/^\d+$/.test(rawPts)) {
      errors.push(`${where}: points must be an integer`);
      return;
    }
    if (pts <= 0) {
      errors.push(`${where}: points must be positive`);
      return;
    }
    const cat = b.category.trim();
    if (!(cat in cats)) { cats[cat] = []; order.push(cat); }
    cats[cat].push({
      value: pts,
      question: b.question.trim(),
      answer: b.answer.trim(),
      all_in: inlineAllIn || Q_TRUTHY.has((b["all in"] || "").trim().toLowerCase()),
    });
  });

  if (order.length !== nCats) {
    errors.push(`needs exactly ${nCats} categories, found ${order.length}` +
      (order.length ? ` (${order.join(", ")})` : ""));
  }
  for (const c of order) {
    if (cats[c].length !== nClues) {
      errors.push(`category '${c}': needs exactly ${nClues} clues, ` +
        `found ${cats[c].length}`);
    }
  }
  if (errors.length) return [null, errors];

  return [{
    name,
    categories: order.map((c) => ({
      name: c,
      clues: cats[c].slice().sort((a, b) => a.value - b.value),
    })),
    timers: timers.slice(),
  }, []];
}

function loadBoardText(text) {
  const [blocks, errors] = parseBlocks(text);
  if (!blocks.length) errors.push("no clue blocks found");
  if (errors.length) return [null, errors];
  return buildBoard(blocks, BOARD_CATEGORIES, BOARD_CLUES, BOARD_TIMERS,
                    "board");
}

function loadBonusText(text) {
  const [blocks, errors] = parseBlocks(text);
  if (!blocks.length) errors.push("no clue blocks found");
  if (errors.length) return [null, errors];
  return buildBoard(blocks, BONUS_CATEGORIES, BONUS_CLUES, BONUS_TIMERS,
                    "bonus");
}

function loadFinaleText(text) {
  const [blocks, errors] = parseBlocks(text);
  if (blocks.length !== 1) {
    errors.push(
      `finale file must contain exactly one block, found ${blocks.length}`);
    return [null, errors];
  }
  const b = blocks[0];
  const missing = ["category", "question", "answer"]
    .filter((k) => !(b[k] || "").trim());
  if (missing.length) errors.push("finale: missing " + missing.join(", "));
  let secs = DEFAULT_FINALE_SECONDS;
  if ((b.seconds || "").trim()) {
    secs = parseInt(b.seconds.trim(), 10);
    if (Number.isNaN(secs) || secs <= 0)
      errors.push("finale: seconds must be a positive integer");
  }
  if (errors.length) return [null, errors];
  return [{
    category: b.category.trim(),
    question: b.question.trim(),
    answer: b.answer.trim(),
    seconds: secs,
  }, []];
}

/* ------------------------------ GameState ------------------------------- */

class GameState {
  constructor() { this.reset(); }

  reset() {
    this.phase = "setup";
    this.teams = [];              // [{name, score}]
    this.board = null;
    this.bonus = null;
    this.finale = null;
    this.round_index = 0;
    this.used = new Set();        // "r,c,i" strings
    this.active = null;
    this.wager = null;
    this.all_in_result = null;
    this.ranking = [];
    this.answer_revealed = false;
    this.time_up = false;
    this.finale_wagers = {};      // {teamId: int}
    this.finale_results = {};     // {teamId: bool}
    this.message = "";
  }

  _rounds() {
    return [this.board, this.bonus].filter((r) => r != null);
  }

  _round() {
    const rounds = this._rounds();
    if (!rounds.length) throw new GameError("No board loaded");
    if (this.round_index < 0 || this.round_index >= rounds.length)
      throw new GameError("Bad round");
    return rounds[this.round_index];
  }

  loadBoard(board) {
    if (!board || !board.categories) throw new GameError("Invalid board data");
    this.board = board;
    this.used = new Set([...this.used].filter((u) => !u.startsWith("0,")));
    this.round_index = 0;
  }

  loadBonus(bonus) {
    if (!bonus || !bonus.categories) throw new GameError("Invalid board data");
    this.bonus = bonus;
    this.used = new Set([...this.used].filter((u) => !u.startsWith("1,")));
  }

  loadFinale(finale) {
    if (!finale || !finale.question) throw new GameError("Invalid finale data");
    this.finale = finale;
  }

  setTeams(names) {
    names = (names || []).map((n) => (n || "").trim()).filter(Boolean);
    if (names.length < MIN_TEAMS || names.length > MAX_TEAMS)
      throw new GameError(`Enter ${MIN_TEAMS}–${MAX_TEAMS} team names`);
    this.teams = names.map((n) => ({ name: n, score: 0 }));
  }

  startGame() {
    if (!this._rounds().length) throw new GameError("Load a board file first");
    if (this.teams.length < MIN_TEAMS) throw new GameError("Set up teams first");
    this.phase = "rules";
  }

  advance() {
    if (this.phase === "rules") this.phase = "board";
    else if (this.phase === "finale_category") this.phase = "finale_wagers";
    else throw new GameError(`Nothing to advance from phase '${this.phase}'`);
  }

  /* --------------------------------- board ------------------------------- */

  _clue(cat, idx) {
    const cats = this._round().categories;
    if (cat < 0 || cat >= cats.length) throw new GameError("Bad category");
    const clues = cats[cat].clues;
    if (idx < 0 || idx >= clues.length) throw new GameError("Bad clue");
    return clues[idx];
  }

  selectTile(cat, idx) {
    if (this.phase !== "board") throw new GameError("Not on the board");
    const key = `${this.round_index},${cat},${idx}`;
    if (this.used.has(key)) throw new GameError("Tile already used");
    const rnd = this._round();
    const clue = this._clue(cat, idx);
    this.active = {
      round: this.round_index, cat, idx,
      value: clue.value, question: clue.question, answer: clue.answer,
      all_in: !!clue.all_in,
      timer: rnd.timers[idx],
      category: rnd.categories[cat].name,
    };
    this.answer_revealed = false;
    this.time_up = false;
    this.ranking = [];
    this.wager = null;
    this.all_in_result = null;
    this.phase = this.active.all_in ? "wager" : "question";
  }

  setWager(teamId, amount) {
    if (this.phase !== "wager" || !this.active)
      throw new GameError("No wager pending");
    this._checkTeam(teamId);
    const rnd = this._round();
    const tileMax = Math.max(...rnd.categories.flatMap(
      (c) => c.clues.map((cl) => cl.value)));
    const cap = allInWagerCap(this.teams[teamId].score, tileMax);
    if (!(amount >= 1 && amount <= cap))
      throw new GameError(`Wager must be 1–${cap}`);
    this.wager = { team: teamId, amount };
    this.phase = "question";
  }

  /* -------------------------------- question ----------------------------- */

  _checkTeam(teamId) {
    if (teamId < 0 || teamId >= this.teams.length)
      throw new GameError("Bad team id");
  }

  revealAnswer() {
    if (this.phase !== "question" && this.phase !== "answer")
      throw new GameError("No question in play");
    this.answer_revealed = true;
    this.phase = "answer";
  }

  toggleRank(teamId) {
    if (this.phase !== "question" && this.phase !== "answer")
      throw new GameError("No question in play");
    if (this.active && this.active.all_in)
      throw new GameError("All In uses correct/incorrect, not ranking");
    this._checkTeam(teamId);
    const i = this.ranking.indexOf(teamId);
    if (i >= 0) this.ranking.splice(i, 1);
    else this.ranking.push(teamId);
  }

  setAllInResult(correct) {
    if ((this.phase !== "question" && this.phase !== "answer") || !this.active)
      throw new GameError("No question in play");
    if (!this.active.all_in) throw new GameError("Not an All In tile");
    this.all_in_result = !!correct;
  }

  endQuestion() {
    if ((this.phase !== "question" && this.phase !== "answer") || !this.active)
      throw new GameError("No question in play");
    if (this.active.all_in) {
      if (this.all_in_result === null || this.all_in_result === undefined)
        throw new GameError("Mark the All In result (correct/incorrect)");
      const delta = this.wager.amount * (this.all_in_result ? 1 : -1);
      this.teams[this.wager.team].score += delta;
    } else {
      this.ranking.forEach((tid, pos) => {
        this.teams[tid].score += rankPoints(this.active.value, pos);
      });
    }
    this.used.add(`${this.active.round},${this.active.cat},${this.active.idx}`);
    this._clearActive();
    this.phase = "board";
  }

  abortQuestion() {
    if (!["wager", "question", "answer"].includes(this.phase))
      throw new GameError("No question in play");
    this._clearActive();
    this.phase = "board";
  }

  _clearActive() {
    this.active = null;
    this.wager = null;
    this.all_in_result = null;
    this.ranking = [];
    this.answer_revealed = false;
    this.time_up = false;
  }

  boardComplete() {
    if (!this._rounds().length) return false;
    const cats = this._round().categories;
    return cats.every((c, ci) => c.clues.every(
      (_, ii) => this.used.has(`${this.round_index},${ci},${ii}`)));
  }

  activateBonus() {
    if (this.phase !== "board")
      throw new GameError("Only available on the board");
    if (this._rounds().length < 2)
      throw new GameError("No bonus board loaded");
    this.round_index = (this.round_index + 1) % this._rounds().length;
  }

  /* --------------------------------- finale ------------------------------ */

  startFinale() {
    if (this.phase !== "board")
      throw new GameError("Only available on the board");
    if (!this.finale) throw new GameError("No finale loaded");
    this.finale_wagers = {};
    this.finale_results = {};
    this.time_up = false;
    this.phase = "finale_category";
  }

  setFinaleWager(teamId, amount) {
    if (this.phase !== "finale_wagers")
      throw new GameError("Not taking wagers");
    this._checkTeam(teamId);
    const cap = finaleWagerCap(this.teams[teamId].score);
    if (!(amount >= 0 && amount <= cap))
      throw new GameError(
        `Wager for ${this.teams[teamId].name} must be 0–${cap}`);
    this.finale_wagers[teamId] = amount;
  }

  startFinaleQuestion() {
    if (this.phase !== "finale_wagers")
      throw new GameError("Not taking wagers");
    for (let tid = 0; tid < this.teams.length; tid++) {
      if (!(tid in this.finale_wagers)) this.finale_wagers[tid] = 0;
    }
    this.time_up = false;
    this.phase = "finale_question";
  }

  revealFinaleAnswer() {
    if (this.phase !== "finale_question")
      throw new GameError("No finale question in play");
    this.phase = "finale_results";
  }

  setFinaleResult(teamId, correct) {
    if (this.phase !== "finale_results")
      throw new GameError("Not marking results");
    this._checkTeam(teamId);
    this.finale_results[teamId] = !!correct;
  }

  finishFinale() {
    if (this.phase !== "finale_results")
      throw new GameError("Not marking results");
    const unmarked = this.teams
      .filter((_, i) => !(i in this.finale_results))
      .map((t) => t.name);
    if (unmarked.length)
      throw new GameError(
        "Mark every team correct or incorrect: " + unmarked.join(", "));
    Object.entries(this.finale_results).forEach(([tid, correct]) => {
      const wager = this.finale_wagers[tid] || 0;
      this.teams[tid].score += correct ? wager : -wager;
    });
    this.phase = "standings";
  }

  /* -------------------------------- snapshot ----------------------------- */

  standings() {
    const order = this.teams.map((_, i) => i)
      .sort((a, b) => this.teams[b].score - this.teams[a].score || a - b);
    return order.map((i, p) => ({
      id: i, name: this.teams[i].name,
      score: this.teams[i].score, place: p + 1,
    }));
  }

  snapshot(role) {
    const host = role === "host";
    const s = {
      phase: this.phase,
      teams: this.teams.map((t, i) => ({ id: i, name: t.name, score: t.score })),
      round_index: this.round_index,
      rounds_total: this._rounds().length,
      board_loaded: this.board != null,
      bonus_loaded: this.bonus != null,
      finale_loaded: this.finale != null,
      board_complete: this.boardComplete(),
      time_up: this.time_up,
      answer_revealed: this.answer_revealed,
    };

    if (this._rounds().length) {
      s.board = {
        categories: this._round().categories.map((c, ci) => ({
          name: c.name,
          clues: c.clues.map((cl, ii) => ({
            value: cl.value,
            used: this.used.has(`${this.round_index},${ci},${ii}`),
          })),
        })),
      };
    }
    if (this.finale) {
      const f = this.finale;
      const fin = { category: f.category,
                    seconds: f.seconds || DEFAULT_FINALE_SECONDS };
      if (["finale_question", "finale_results", "standings"].includes(this.phase)
          || host) fin.question = f.question;
      if (["finale_results", "standings"].includes(this.phase) || host)
        fin.answer = f.answer;
      s.finale = fin;
    }
    if (this.active) {
      const a = {
        category: this.active.category,
        value: this.active.value,
        all_in: this.active.all_in,
        question: this.active.question,
        timer: this.active.timer,
      };
      if (this.answer_revealed || host) a.answer = this.active.answer;
      if (this.wager) {
        a.wager_team = this.wager.team;
        if (this.answer_revealed || host) a.wager = this.wager.amount;
      }
      s.active = a;
    }
    if (host) {
      s.ranking = [...this.ranking];
      s.all_in_result = this.all_in_result;
      s.finale_wagers = { ...this.finale_wagers };
      s.finale_results = { ...this.finale_results };
      s.message = this.message;
    }
    if (this.phase === "standings") {
      s.standings = this.standings();
      s.finale_wagers_public = { ...this.finale_wagers };
    }
    return s;
  }

  /* Full internal dump for host-reload recovery (private node only). */
  dump() {
    return {
      phase: this.phase,
      teams: this.teams,
      board: this.board,
      bonus: this.bonus,
      finale: this.finale,
      round_index: this.round_index,
      used: [...this.used],
      active: this.active,
      wager: this.wager,
      all_in_result: this.all_in_result,
      ranking: this.ranking,
      answer_revealed: this.answer_revealed,
      time_up: this.time_up,
      finale_wagers: this.finale_wagers,
      finale_results: this.finale_results,
      message: this.message,
    };
  }

  restore(d) {
    if (!d || typeof d !== "object") return;
    Object.assign(this, d);
    this.used = new Set(d.used || []);
    // JSON object keys come back as strings — normalise to int keys.
    const intKeyed = (o) => Object.fromEntries(
      Object.entries(o || {}).map(([k, v]) => [parseInt(k, 10), v]));
    this.finale_wagers = intKeyed(d.finale_wagers);
    this.finale_results = intKeyed(d.finale_results);
  }
}
