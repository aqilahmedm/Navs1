let csrf = "", stepUp = null, lost = null;
export let lastActivity = Date.now();               // last time the SERVER saw us (a successful request)
let userActive = Date.now();                         // last time the PERSON did something (click, key, scroll, touch)
if (typeof addEventListener !== "undefined") for (const ev of ["pointerdown", "keydown", "scroll", "touchstart"]) addEventListener(ev, () => { userActive = Date.now(); }, { passive: true, capture: true });
export const userIdleFor = () => Date.now() - userActive;
export const setCsrf = v => { csrf = v || ""; };
export const onStepUp = f => { stepUp = f; };
export const onAuthLost = f => { lost = f; };
export async function api(url, opts = {}, retried = false) {
  opts = { ...opts, headers: { ...(opts.headers || {}) }, credentials: "same-origin" };
  if (opts.method && opts.method !== "GET") opts.headers["X-CSRF-Token"] = csrf;
  let res;
  try { res = await fetch(url, opts); } catch { throw new Error("We couldn't reach the server. Check your internet connection and try again."); }
  const j = await res.json().catch(() => ({}));
  if (res.ok) lastActivity = Date.now();
  if (res.status === 428 && j.step_up && stepUp && !retried) { await stepUp(j.step_up); return api(url, opts, true); }
  if (res.status === 401 && j.expired && lost) { lost(j.error); const e = new Error(j.error || "Signed out"); e.silent = true; throw e; }
  if (!res.ok) { const e = new Error(j.error || `Request failed (${res.status})`); e.status = res.status; e.data = j; throw e; }
  return j;
}
export const post = (u, b) => api(u, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(b || {}) });
export async function loadCsrf() { const j = await api("/api/csrf"); setCsrf(j.csrf); }
