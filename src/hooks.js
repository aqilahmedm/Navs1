import { useEffect, useRef, useState, useCallback } from "react";
const reduce = () => typeof matchMedia !== "undefined" && matchMedia("(prefers-reduced-motion: reduce)").matches;

export function useInView(opts = { threshold: 0.2 }) {
  const ref = useRef(null); const [seen, setSeen] = useState(false);
  useEffect(() => {
    const el = ref.current; if (!el || seen) return;
    if (typeof IntersectionObserver === "undefined") { setSeen(true); return; }
    const io = new IntersectionObserver(([e]) => { if (e.isIntersecting) { setSeen(true); io.disconnect(); } }, opts);
    io.observe(el); return () => io.disconnect();
  }, [seen]);
  return [ref, seen];
}
export function useCountUp(target, run = true, ms = 1100) {
  const [v, setV] = useState(0);
  useEffect(() => {
    if (!run) return; if (reduce()) { setV(target); return; }
    let raf, t0; const step = t => { t0 ??= t; const p = Math.min(1, (t - t0) / ms); setV(Math.round(target * (1 - Math.pow(1 - p, 3)))); if (p < 1) raf = requestAnimationFrame(step); };
    raf = requestAnimationFrame(step); return () => cancelAnimationFrame(raf);
  }, [target, run]);
  return v;
}
export function useFocusTrap(active) {
  const ref = useRef(null);
  useEffect(() => {
    if (!active) return; const el = ref.current; if (!el) return; const prev = document.activeElement;
    const sel = 'a[href],button:not([disabled]),input:not([disabled]),select,textarea,[tabindex]:not([tabindex="-1"])';
    (el.querySelector("[data-autofocus]") || el.querySelector(sel) || el).focus?.();
    const onKey = e => {
      if (e.key !== "Tab") return; const f = [...el.querySelectorAll(sel)].filter(x => x.offsetParent !== null); if (!f.length) return;
      const a = f[0], b = f[f.length - 1];
      if (e.shiftKey && document.activeElement === a) { e.preventDefault(); b.focus(); } else if (!e.shiftKey && document.activeElement === b) { e.preventDefault(); a.focus(); }
    };
    el.addEventListener("keydown", onKey); return () => { el.removeEventListener("keydown", onKey); prev?.focus?.(); };
  }, [active]);
  return ref;
}
export function useHashRoute() {
  const parse = () => { const h = location.hash.replace(/^#/, "") || "/"; const [path, qs] = h.split("?"); return { path, q: new URLSearchParams(qs || "") }; };
  const [r, setR] = useState(parse);
  useEffect(() => { const f = () => setR(parse()); addEventListener("hashchange", f); return () => removeEventListener("hashchange", f); }, []);
  const go = useCallback((p, replace) => { if (replace) location.replace("#" + p); else location.hash = p; }, []);
  return [r, go];
}
export function useTheme() {
  const [t, setT] = useState(document.documentElement.dataset.theme === "dark" ? "dark" : "light");
  const toggle = () => { const n = t === "dark" ? "light" : "dark"; setT(n); if (n === "dark") document.documentElement.dataset.theme = "dark"; else delete document.documentElement.dataset.theme; try { localStorage.setItem("navs-theme", n); } catch {} };
  return [t, toggle];
}
export const fmtAgo = s => s < 60 ? "just now" : s < 3600 ? `${Math.floor(s / 60)} min ago` : s < 86400 ? `${Math.floor(s / 3600)} h ago` : `${Math.floor(s / 86400)} d ago`;
export const mmss = s => `${Math.floor(Math.max(0, s) / 60)}:${String(Math.max(0, s) % 60).padStart(2, "0")}`;
export function useAsync(fn, deps = []) {
  const [s, setS] = useState({ loading: true, data: null, error: null });
  const run = useCallback(() => { setS(x => ({ ...x, loading: true, error: null })); return fn().then(d => setS({ loading: false, data: d, error: null })).catch(e => { if (!e.silent) setS({ loading: false, data: null, error: e.message }); }); }, deps);
  useEffect(() => { run(); }, [run]);
  return { ...s, reload: run };
}
