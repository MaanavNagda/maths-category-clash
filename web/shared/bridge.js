/* Shared bridge helpers: QWebChannel wiring, KaTeX rendering, modal. */

let controller = null;

/* signalName: 'displayChanged' or 'hostChanged'.
   onState(stateObj) called on every pushed snapshot.
   onTick(secondsLeft) called on every timer tick. */
function initBridge(signalName, onState, onTick) {
  new QWebChannel(qt.webChannelTransport, function (channel) {
    controller = channel.objects.controller;
    controller[signalName].connect(function (json) {
      onState(JSON.parse(json));
    });
    controller.tick.connect(function (s) { onTick(s); });
  });
}

/* Render $...$ / $$...$$ / \(...\) / \[...\] inside an element. */
function tex(el) {
  if (typeof renderMathInElement !== "function" || !el) return;
  renderMathInElement(el, {
    delimiters: [
      { left: "$$", right: "$$", display: true },
      { left: "\\[", right: "\\]", display: true },
      { left: "$", right: "$", display: false },
      { left: "\\(", right: "\\)", display: false },
    ],
    throwOnError: false,
  });
}

function el(tag, className, text) {
  const e = document.createElement(tag);
  if (className) e.className = className;
  if (text !== undefined) e.textContent = text;
  return e;
}

function fmtTime(totalSecs) {
  const m = Math.floor(totalSecs / 60);
  const s = totalSecs % 60;
  return m + ":" + String(s).padStart(2, "0");
}

/* Minimal confirm modal. Returns nothing; calls onYes(). */
function confirmModal(title, body, yesLabel, onYes) {
  const backdrop = el("div", "modal-backdrop");
  const modal = el("div", "modal");
  modal.appendChild(el("h3", null, title));
  modal.appendChild(el("p", null, body));
  const actions = el("div", "modal-actions");
  const no = el("button", "ghost", "Cancel");
  const yes = el("button", "primary", yesLabel || "Confirm");
  no.onclick = () => backdrop.remove();
  yes.onclick = () => { backdrop.remove(); onYes(); };
  actions.appendChild(no);
  actions.appendChild(yes);
  modal.appendChild(actions);
  backdrop.appendChild(modal);
  backdrop.onclick = (e) => { if (e.target === backdrop) backdrop.remove(); };
  document.body.appendChild(backdrop);
}
