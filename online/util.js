/* Shared helpers for the online version: DOM builder, KaTeX render, modal.
   (Same as web/shared/bridge.js minus the QWebChannel wiring.) */

"use strict";

function el(tag, className, text) {
  const e = document.createElement(tag);
  if (className) e.className = className;
  if (text !== undefined) e.textContent = text;
  return e;
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
