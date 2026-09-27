/* Beyond UP RocketPy - shared motion utilities (2026-09-27 UI redesign,
 * Step 2). Vendored locally (no CDN), tiny and dependency-free.
 *
 * BUP.countUp(root): finds every `[data-bup-countup]` element under
 * `root` (defaults to document) that hasn't already been animated,
 * and counts its text from 0 up to `data-bup-target` over
 * `data-bup-duration` ms (default 600), formatting with
 * `data-bup-decimals` (default 0) and appending `data-bup-suffix`
 * (default ""). Respects prefers-reduced-motion by jumping straight
 * to the final value with no animation. Safe to call repeatedly (each
 * element is marked done after its first run) - callers just invoke
 * it again after inserting new KPI cards into the DOM.
 */
window.BUP = window.BUP || {};

BUP.countUp = function (root) {
  root = root || document;
  const reduced = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const els = root.querySelectorAll("[data-bup-countup]:not([data-bup-done])");
  els.forEach((el) => {
    el.setAttribute("data-bup-done", "1");
    const target = parseFloat(el.getAttribute("data-bup-target"));
    const decimals = parseInt(el.getAttribute("data-bup-decimals") || "0", 10);
    const suffix = el.getAttribute("data-bup-suffix") || "";
    if (isNaN(target)) return;
    if (reduced) {
      el.textContent = target.toFixed(decimals) + suffix;
      return;
    }
    const duration = parseInt(el.getAttribute("data-bup-duration") || "600", 10);
    const start = performance.now();
    function easeOutCubic(t) {
      return 1 - Math.pow(1 - t, 3);
    }
    function frame(now) {
      const t = Math.min(1, (now - start) / duration);
      const value = target * easeOutCubic(t);
      el.textContent = value.toFixed(decimals) + suffix;
      if (t < 1) requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
  });
};

/* Applies a stagger index (--bup-i custom property) to every element
 * matching `selector` under `root`, so theme.py's .bup-stagger CSS
 * animation-delay spreads them out - called once per card GRID after
 * it's built (server-rendered index order = visual order). */
BUP.stagger = function (selector, root) {
  root = root || document;
  root.querySelectorAll(selector).forEach((el, i) => {
    el.style.setProperty("--bup-i", i);
  });
};

document.addEventListener("DOMContentLoaded", function () {
  BUP.countUp(document);
  BUP.stagger(".bup-stagger", document);
});
