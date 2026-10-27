import { useEffect, useRef, useState } from "react";
import { RefreshCw } from "lucide-react";
import { api } from "./api.js";
import { Skeleton } from "./ui.jsx";

/* hCaptcha. value = { token, enabled }. The sitekey comes from the server (/api/captcha); the secret never reaches the browser.
   A token works for one attempt, so the parent bumps resetKey after any failed try and we ask for a fresh one. */
let loader = null;
function loadHcaptcha() {
  if (window.hcaptcha?.render) return Promise.resolve(window.hcaptcha);
  if (!loader) loader = new Promise((ok, no) => {
    window.__hcOnLoad = () => ok(window.hcaptcha);
    const s = document.createElement("script");
    s.src = "https://js.hcaptcha.com/1/api.js?render=explicit&onload=__hcOnLoad"; s.async = true; s.defer = true;
    s.onerror = () => { loader = null; s.remove(); no(new Error("Couldn't load the human check. Check your connection or ad-blocker, then try again.")); };
    document.head.appendChild(s);
  });
  return loader;
}

export default function Captcha({ value, onChange, resetKey = 0 }) {
  const box = useRef(null), wid = useRef(null), cb = useRef(onChange), first = useRef(true);
  const [cfg, setCfg] = useState(null), [err, setErr] = useState(""), [attempt, setAttempt] = useState(0);
  cb.current = onChange;

  useEffect(() => {
    let dead = false; setErr(""); setCfg(null);
    (async () => {
      try {
        const c = await api("/api/captcha");
        if (dead) return;
        if (c.enabled === false) { cb.current({ token: "", enabled: false }); return setCfg(c); }
        const hc = await loadHcaptcha();
        if (dead) return;
        setCfg(c);
        // wait one tick so the container is in the DOM
        await new Promise(r => setTimeout(r, 0));
        if (dead || !box.current) return;
        cb.current({ token: "", enabled: true });
        wid.current = hc.render(box.current, {
          sitekey: c.sitekey, size: box.current.parentElement.clientWidth < 310 ? "compact" : "normal", theme: document.documentElement.dataset.theme === "dark" ? "dark" : "light",
          callback: t => cb.current({ token: t, enabled: true }),
          "expired-callback": () => cb.current({ token: "", enabled: true }),
          "error-callback": () => { cb.current({ token: "", enabled: true }); setErr("The human check hit a problem. Press “Try again”."); },
        });
      } catch (e) { if (!dead) setErr(e.message); }
    })();
    return () => { dead = true; try { if (wid.current != null) window.hcaptcha?.remove(wid.current); } catch { /* widget already gone */ } wid.current = null; };
  }, [attempt]);

  useEffect(() => {          // parent asked for a fresh challenge (after a failed sign-in)
    if (first.current) { first.current = false; return; }
    cb.current({ token: "", enabled: true });
    try { if (wid.current != null) window.hcaptcha?.reset(wid.current); } catch { /* ignore */ }
  }, [resetKey]);

  if (cfg && cfg.enabled === false) return null;
  return (
    <div className="captcha">
      <div className="cap-top"><span className="cap-title">Human check</span>{err && <button type="button" className="link" onClick={() => setAttempt(a => a + 1)}><RefreshCw size={14} /> Try again</button>}</div>
      <div className="cap-box">
        {!cfg && !err && <Skeleton h={78} r={12} />}
        <div ref={box} data-captcha-widget="" />
      </div>
      {err && <span className="err-t" role="alert">{err}</span>}
    </div>
  );
}
