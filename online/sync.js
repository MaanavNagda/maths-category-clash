/* Firebase sync layer for the online version.

   Model: the HOST tab is the authority — it runs GameState locally and pushes
   snapshots. The DISPLAY tab subscribes read-only and sends interactions
   (tile clicks, reveal clicks) through a requests queue the host drains.

   RTDB layout:
     rooms/{room}/public/state        display-safe snapshot (no early answers)
     rooms/{room}/public/requests/{id}  display -> host action requests
     rooms/{room}/private/{key}/dump  full state + config (host reload recovery)

   `key` is a random secret in the host URL only; the private parent is
   unreadable so the key can't be enumerated (see database.rules.json). */

import { initializeApp } from
  "https://www.gstatic.com/firebasejs/10.12.2/firebase-app.js";
import { getDatabase, ref, onValue, set, push, remove, get,
         onChildAdded, serverTimestamp } from
  "https://www.gstatic.com/firebasejs/10.12.2/firebase-database.js";
import { firebaseConfig } from "./firebase-config.js";

const DEFAULT_LABELS = {
  title: "Maths Category Clash",
  all_in: "All In",
  finale: "Grand Finale",
  bonus: "Bonus Board",
  round1: "Round 1",
  round2: "Bonus Board",
};

const ROOM_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789";

export function randomCode(len) {
  const bytes = new Uint8Array(len);
  crypto.getRandomValues(bytes);
  return [...bytes].map((b) => ROOM_ALPHABET[b % ROOM_ALPHABET.length]).join("");
}

const app = initializeApp(firebaseConfig);
const db = getDatabase(app);

function params() {
  return new URLSearchParams(location.search);
}

export function displayUrl(room) {
  const u = new URL(location.href);
  u.search = `?room=${room}&role=display`;
  return u.toString();
}

export function hostUrl(room, key) {
  const u = new URL(location.href);
  u.search = `?room=${room}&role=host&key=${key}`;
  return u.toString();
}

/* ------------------------------ landing -------------------------------- */

export function initLanding() {
  const app_ = document.getElementById("app");
  const box = el("div", "panel");
  box.style.maxWidth = "520px";
  box.style.margin = "12vh auto";
  box.appendChild(el("h2", null, "Maths Category Clash — online"));

  box.appendChild(el("h3", null, "Host a game"));
  const hostBtn = el("button", "primary", "Create room →");
  hostBtn.onclick = () => {
    const room = randomCode(6), key = randomCode(20);
    location.href = hostUrl(room, key);
  };
  const hr = el("div", "btn-row");
  hr.appendChild(hostBtn);
  box.appendChild(hr);

  box.appendChild(el("h3", null, "Join as display"));
  const row = el("div", "row");
  const inp = document.createElement("input");
  inp.type = "text";
  inp.placeholder = "Room code";
  inp.style.textTransform = "uppercase";
  inp.maxLength = 8;
  row.appendChild(inp);
  const join = el("button", null, "Join →");
  const msg = el("div", "msg", "");
  msg.style.display = "none";
  join.onclick = async () => {
    const room = inp.value.trim().toUpperCase();
    if (!room) return;
    const snap = await get(ref(db, `rooms/${room}/public/state`));
    if (!snap.exists()) {
      msg.textContent = "No room with that code — ask the host to create one.";
      msg.style.display = "";
      return;
    }
    location.href = `?room=${room}&role=display`;
  };
  row.appendChild(join);
  box.appendChild(row);
  box.appendChild(msg);
  app_.appendChild(box);
}

/* ------------------------------ host ----------------------------------- */

function initHost(room, key, onState, onTick) {
  const state = new GameState();
  const pubRef = ref(db, `rooms/${room}/public/state`);
  const privRef = ref(db, `rooms/${room}/private/${key}/dump`);
  const reqRef = ref(db, `rooms/${room}/public/requests`);

  /* Host-side config (labels, logo, file names, team prefill) — persisted
     inside the private dump so a host reload restores everything. */
  const cfg = {
    labels: { ...DEFAULT_LABELS },
    logo: null,            // data URL
    logo_name: null,
    teams: [],             // prefill names
    file_names: {},        // {board, bonus, finale}
  };

  let deadline = null;        // ms epoch (local clock)
  let timerTotal = 0;
  let timerIv = null;

  function remaining() {
    if (deadline === null) return 0;
    return Math.max(0, Math.round((deadline - Date.now()) / 1000));
  }

  function startTimer(secs) {
    timerTotal = secs;
    deadline = Date.now() + secs * 1000;
    clearInterval(timerIv);
    timerIv = setInterval(onTick_, 200);
    onTick_(secs);
  }

  function stopTimer() {
    clearInterval(timerIv);
    timerIv = null;
    deadline = null;
    timerTotal = 0;
  }

  function onTick_() {
    const rem = remaining();
    onTick(rem);
    if (rem <= 0 && deadline !== null) {
      stopTimer();
      state.time_up = true;
      pushState();
    }
  }

  function hostSnap() {
    const s = state.snapshot("host");
    decorate(s);
    s.config_teams = cfg.teams;
    s.logo_name = cfg.logo_name;
    for (const k of ["board", "bonus", "finale"])
      s[k + "_name"] = cfg.file_names[k] || null;
    return s;
  }

  function decorate(s) {
    s.labels = cfg.labels;
    s.logo = cfg.logo;
    s.timer_remaining = remaining();
    s.timer_total = timerTotal;
    if (state._rounds().length) {
      s.round_name = cfg.labels[
        state.round_index === 0 ? "round1" : "round2"];
    }
    return s;
  }

  function pushState() {
    const pub = decorate(state.snapshot("display"));
    pub.timer_running = deadline !== null;
    if (deadline !== null) {
      // server timestamp so displays sync despite clock skew
      pub.timer_start = serverTimestamp();
      pub.timer_start_local = deadline - timerTotal * 1000;
    }
    set(pubRef, pub);
    set(privRef, { dump: state.dump(), cfg });
    onState(hostSnap());
  }

  function run(fn, ...args) {
    try {
      fn(...args);
      state.message = "";
    } catch (e) {
      state.message = (e instanceof GameError) ? e.message : String(e);
    }
    pushState();
  }

  /* file picking — browser replacement for QFileDialog */
  function pickFile(accept, cb) {
    const inp = document.createElement("input");
    inp.type = "file";
    inp.accept = accept;
    inp.onchange = () => inp.files[0] && cb(inp.files[0]);
    inp.click();
  }

  function loadMd(file, loader, setter, key) {
    const rd = new FileReader();
    rd.onload = () => {
      const [data, errors] = loader(String(rd.result));
      if (errors.length) {
        state.message = `${file.name} rejected:\n` +
          errors.slice(0, 12).map((e) => "• " + e).join("\n");
        pushState();
        return;
      }
      run(setter, data);
      cfg.file_names[key] = file.name;
      state.message = `Loaded ${file.name}`;
      pushState();
    };
    rd.readAsText(file);
  }

  /* The controller object the host UI drives — same API as the Qt bridge. */
  window.controller = {
    requestState: () => onState(hostSnap()),
    setTeams: (json) => {
      let names = [];
      try { names = JSON.parse(json); } catch (e) { /* keep [] */ }
      run(state.setTeams.bind(state), names);
      if (!state.message) {
        cfg.teams = state.teams.map((t) => t.name);
        pushState();
      }
    },
    setLabel: (k, v) => {
      if (k in cfg.labels && v.trim()) {
        cfg.labels[k] = v.trim();
        pushState();
      }
    },
    openBoard: () => pickFile(".md,.markdown,.txt", (f) =>
      loadMd(f, loadBoardText, state.loadBoard.bind(state), "board")),
    openBonus: () => pickFile(".md,.markdown,.txt", (f) =>
      loadMd(f, loadBonusText, state.loadBonus.bind(state), "bonus")),
    openFinale: () => pickFile(".md,.markdown,.txt", (f) =>
      loadMd(f, loadFinaleText, state.loadFinale.bind(state), "finale")),
    openLogo: () => pickFile("image/*", (f) => {
      const rd = new FileReader();
      rd.onload = () => {
        cfg.logo = String(rd.result);
        cfg.logo_name = f.name;
        pushState();
      };
      rd.readAsDataURL(f);
    }),
    startGame: () => run(state.startGame.bind(state)),
    resetGame: () => {
      state.teams.forEach((t) => { t.score = 0; });
      state.used = new Set();
      state.round_index = 0;
      state._clearActive();
      state.phase = state._rounds().length ? "board" : "setup";
      stopTimer();
      pushState();
    },
    advance: () => run(state.advance.bind(state)),
    selectTile: (c, i) => {
      run(state.selectTile.bind(state), c, i);
      if (state.phase === "question" && state.active)
        startTimer(state.active.timer);
    },
    setWager: (t, a) => {
      run(state.setWager.bind(state), t, a);
      if (state.phase === "question" && state.active)
        startTimer(state.active.timer);
    },
    revealAnswer: () => {
      run(state.revealAnswer.bind(state));
      if (state.phase === "answer") stopTimer();
    },
    toggleRank: (t) => run(state.toggleRank.bind(state), t),
    setAllInResult: (ok) => run(state.setAllInResult.bind(state), ok),
    endQuestion: () => {
      run(state.endQuestion.bind(state));
      if (state.phase === "board") stopTimer();
    },
    abortQuestion: () => {
      run(state.abortQuestion.bind(state));
      stopTimer();
    },
    activateBonus: () => run(state.activateBonus.bind(state)),
    startFinale: () => run(state.startFinale.bind(state)),
    setFinaleWager: (t, a) => run(state.setFinaleWager.bind(state), t, a),
    startFinaleQuestion: () => {
      run(state.startFinaleQuestion.bind(state));
      if (state.phase === "finale_question") {
        const secs = state.finale
          ? (state.finale.seconds || DEFAULT_FINALE_SECONDS)
          : DEFAULT_FINALE_SECONDS;
        startTimer(secs);
      }
    },
    revealFinaleAnswer: () => {
      run(state.revealFinaleAnswer.bind(state));
      stopTimer();
    },
    setFinaleResult: (t, ok) => run(state.setFinaleResult.bind(state), t, ok),
    finishFinale: () => run(state.finishFinale.bind(state)),
    displayUrl: () => displayUrl(room),
  };

  /* Drain display -> host action requests. */
  onChildAdded(reqRef, (snap) => {
    const r = snap.val();
    remove(snap.ref);
    if (!r || !r.action) return;
    const c = window.controller;
    if (r.action === "selectTile") c.selectTile(r.cat, r.idx);
    else if (r.action === "revealAnswer") c.revealAnswer();
    else if (r.action === "advance") c.advance();
  });

  /* Recover a previous session on reload (same room + key). */
  get(privRef).then((snap) => {
    if (snap.exists()) {
      const d = snap.val();
      if (d.cfg) Object.assign(cfg, d.cfg);
      if (d.dump) state.restore(d.dump);
      state.message = (state.message ? state.message + "\n" : "") +
        "Session restored after reload.";
    }
    onState(hostSnap());
  });
}

/* ----------------------------- display --------------------------------- */

function initDisplay(room, onState, onTick) {
  const stateRef = ref(db, `rooms/${room}/public/state`);
  const reqRef = ref(db, `rooms/${room}/public/requests`);

  let offset = 0;
  onValue(ref(db, ".info/serverTimeOffset"), (s) => {
    offset = s.val() || 0;
  });

  let timerStart = null, timerTotal = 0, timerRunning = false;
  onValue(stateRef, (snap) => {
    const s = snap.val();
    if (!s) return;
    timerStart = s.timer_start || null;
    timerTotal = s.timer_total || 0;
    timerRunning = !!s.timer_running;
    onState(s);
  });

  setInterval(() => {
    if (!timerRunning || !timerStart) return;
    const rem = Math.max(
      0, Math.round(timerTotal - (Date.now() + offset - timerStart) / 1000));
    onTick(rem);
  }, 200);

  /* Display-side controller: read-only, sends requests to the host. */
  window.controller = {
    selectTile: (cat, idx) =>
      push(reqRef, { action: "selectTile", cat, idx }),
    revealAnswer: () => push(reqRef, { action: "revealAnswer" }),
    advance: () => push(reqRef, { action: "advance" }),
  };
}

/* ------------------------------- entry ---------------------------------- */

/* Called by host.js / display.js once the DOM is ready. */
export function initOnline(role, onState, onTick) {
  const p = params();
  const room = (p.get("room") || "").toUpperCase();
  const key = p.get("key") || "";
  if (!room) { initLanding(); return; }
  if (role === "host") {
    if (!key) { location.href = hostUrl(room, randomCode(20)); return; }
    initHost(room, key, onState, onTick);
  } else {
    initDisplay(room, onState, onTick);
  }
}
