import { useEffect, useRef, useState } from "react";
import { ArrowLeft, ArrowRight, Briefcase, Building2, Check, ChevronDown, GraduationCap, KeyRound, Landmark, LockKeyhole, RefreshCw, ShieldCheck, Smartphone, Wand2, Search, ScrollText, Fingerprint } from "lucide-react";
import { api, post, setCsrf } from "./api.js";
import { useTheme, mmss } from "./hooks.js";
import { AicteLogo, BrandMark, CollegeLogo, Gear } from "./logos.jsx";
import { BRAND, NOTICE, ROLE_META } from "./brand.js";
import { Button, Field, OtpBoxes, PasswordInput, Segmented, Hint } from "./ui.jsx";
import Privacy from "./Privacy.jsx";
import Captcha from "./Captcha.jsx";
import Forgot from "./Forgot.jsx";

const ICONS = { student: GraduationCap, institution: Building2, aicte: Landmark, employer: Briefcase };

function CollegePicker({ list, value, onChange }) {
  const [open, setOpen] = useState(false), [q, setQ] = useState(""), ref = useRef(null);
  useEffect(() => { const f = e => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); }; addEventListener("pointerdown", f); return () => removeEventListener("pointerdown", f); }, []);
  const shown = list.filter(c => (c.name + c.city + c.state + c.code).toLowerCase().includes(q.toLowerCase())).slice(0, 40);
  return (
    <div className="picker" ref={ref}>
      <button type="button" className="picker-b" aria-haspopup="listbox" aria-expanded={open} onClick={() => setOpen(o => !o)}>
        {value ? <><CollegeLogo code={value.code} name={value.name} size={34} /><span><b>{value.name}</b><small>{value.city}, {value.state} · {value.code}</small></span></> : <span className="muted">Choose a demo college</span>}
        <ChevronDown size={18} />
      </button>
      {open && <div className="picker-pop">
        <div className="picker-s"><Search size={16} /><input autoFocus value={q} onChange={e => setQ(e.target.value)} placeholder="Search name, city or ID" aria-label="Search colleges" /></div>
        <ul role="listbox" aria-label="Colleges">{shown.map(c => <li key={c.code}><button type="button" role="option" aria-selected={value?.code === c.code} onClick={() => { onChange(c); setOpen(false); setQ(""); }}><CollegeLogo code={c.code} name={c.name} size={30} /><span><b>{c.name}</b><small>{c.city}, {c.state}</small></span></button></li>)}{!shown.length && <li className="muted pad">No match</li>}</ul>
      </div>}
    </div>
  );
}

export default function Login({ go, initialRole, onSignedIn }) {
  const [role, setRole] = useState(ROLE_META[initialRole] ? initialRole : "student");
  const [step, setStep] = useState("creds");
  const [user, setUser] = useState(""), [pw, setPw] = useState(""), [code, setCode] = useState("");
  const [err, setErr] = useState(""), [busy, setBusy] = useState(false), [info, setInfo] = useState({}), [left, setLeft] = useState(0);
  const [cap, setCap] = useState({ token: "", enabled: true }), [capKey, setCapKey] = useState(0), [mode, setMode] = useState("signin"), [notice, setNotice] = useState("");
  const [demo, setDemo] = useState({}), [colleges, setColleges] = useState([]), [college, setCollege] = useState(null), [priv, setPriv] = useState(false), [theme, toggle] = useTheme();
  const aicte = role === "aicte", steps = aicte ? ["Password", "One-time code", "Authenticator"] : ["Password", "One-time code"], at = step === "creds" ? 0 : step === "otp" ? 1 : 2;

  useEffect(() => { api("/api/demo").then(d => setDemo(d.accounts || {})).catch(() => {}); api("/api/public/overview").then(d => setColleges(d.institutions)).catch(() => {}); }, []);
  useEffect(() => { if (step !== "otp") return; const t = setInterval(() => setLeft(s => Math.max(0, s - 1)), 1000); return () => clearInterval(t); }, [step, info.demo_otp]);

  const reset = () => { setStep("creds"); setCode(""); setErr(""); setInfo({}); };
  const pickRole = r => { if (r === role) return; post("/api/auth/cancel").catch(() => {}); setRole(r); reset(); setUser(""); setPw(""); setCollege(null); setMode("signin"); setNotice(""); };
  const fail = e => { if (e.silent) return; setErr(e.message); if (e.data?.restart) reset(); };

  const fillDemo = async () => {
    setErr("");
    try {
      if (role === "institution" && college) { const d = await api("/api/demo/college/" + encodeURIComponent(college.code)); setUser(d.username); setPw(d.password); }
      else { const a = demo[role]; if (!a) return setErr("Demo accounts are switched off on this server."); setUser(a.username); setPw(a.password); }
    } catch (e) { setErr(e.message); }
  };
  const onCollege = async c => { setCollege(c); setErr(""); try { const d = await api("/api/demo/college/" + encodeURIComponent(c.code)); setUser(d.username); setPw(d.password); } catch { /* demo credentials unavailable */ } };

  const submitCreds = async e => {
    e?.preventDefault(); if (busy) return; setErr(""); setBusy(true);
    try { const d = await post("/api/auth/password", { role, username: user, password: pw, captcha_token: cap.token }); setInfo(d); setLeft(d.expires_in || 300); setCode(""); setStep("otp"); setPw(""); }
    catch (e) { fail(e); setCapKey(k => k + 1); } finally { setBusy(false); }                  // a human-check token works for one try, so get a new one
  };
  const finish = d => { setCsrf(d.csrf); onSignedIn(d); };
  const submitOtp = async v => {
    const c = v ?? code; if (busy || c.length !== 6) return; setErr(""); setBusy(true);
    try { const d = await post("/api/auth/otp", { code: c }); if (d.done) return finish(d); setInfo(i => ({ ...i, demo_totp: d.demo_totp })); setCode(""); setStep("totp"); }
    catch (e) { fail(e); setCode(""); } finally { setBusy(false); }
  };
  const submitTotp = async v => {
    const c = v ?? code; if (busy || c.length !== 6) return; setErr(""); setBusy(true);
    try { finish(await post("/api/auth/totp", { code: c })); } catch (e) { fail(e); setCode(""); } finally { setBusy(false); }
  };
  const resend = async () => { setErr(""); try { const d = await post("/api/auth/resend"); setInfo(i => ({ ...i, ...d })); setLeft(d.expires_in || 300); setCode(""); } catch (e) { fail(e); } };
  const back = () => { post("/api/auth/cancel").catch(() => {}); reset(); };
  const roleOpts = Object.keys(ROLE_META).map(k => ({ k, label: ROLE_META[k].label, icon: ICONS[k] }));

  return (
    <div className="auth">
      <aside className="auth-brand">
        <Gear className="ab-gear" /><div className="hero-glow" />
        <div className="ab-in">
          <button className="plain light" onClick={() => go("/")}><ArrowLeft size={16} /> Back to home</button>
          <div className="ab-logo"><AicteLogo size={92} /></div>
          <h1><BrandMark size={34} /> {BRAND.name}</h1>
          <p className="ab-full">{BRAND.full}</p><p className="ab-hi" lang="hi">{BRAND.hindi}</p>
          <ul className="ab-list">
            <li><KeyRound size={18} /><div><b>Two-step sign-in</b><span>Password and a human check, then a one-time code.</span></div></li>
            <li><Fingerprint size={18} /><div><b>Re-confirm sensitive actions</b><span>Uploads and decisions need a fresh code.</span></div></li>
            <li><ScrollText size={18} /><div><b>Everything is on the record</b><span>A tamper-evident audit trail.</span></div></li>
          </ul>
          <small className="ab-note">{NOTICE}</small>
        </div>
      </aside>

      <main className="auth-main">
        <div className="auth-top"><button className="plain only-m" onClick={() => go("/")}><ArrowLeft size={16} /> Home</button><span className="spacer" />
          <button className="link" onClick={() => setPriv(true)}>Privacy</button><button className="link" onClick={toggle}>{theme === "dark" ? "Light" : "Dark"} theme</button></div>
        <div className="auth-card">
          {mode === "signin" && <header><h2>Sign in</h2><p>{ROLE_META[role].blurb}</p></header>}
          <Segmented options={roleOpts} value={role} onChange={pickRole} label="Choose your role" />
          {mode === "signin" && <ol className="stepper" aria-label="Sign-in progress">{steps.map((s, i) => <li key={s} className={i < at ? "done" : i === at ? "now" : ""}><i>{i < at ? <Check size={13} /> : i + 1}</i><span>{s}</span></li>)}</ol>}

          {mode === "forgot" && <Forgot role={role} label={ROLE_META[role].label} initialUser={user} onBack={() => setMode("signin")} onDone={m => { setNotice(m); setMode("signin"); setPw(""); setCapKey(k => k + 1); }} />}

          {mode === "signin" && step === "creds" && (
            <form onSubmit={submitCreds} className="stack" noValidate key="c">
              {notice && <Hint tone="ok">{notice}</Hint>}
              {role === "institution" && colleges.length > 0 && <Field label="College (demo)" hint="In the demo you can sign in as any college's registrar."><CollegePicker list={colleges} value={college} onChange={onCollege} /></Field>}
              <Field label="Username" htmlFor="u"><input id="u" className="input" value={user} onChange={e => setUser(e.target.value)} autoComplete="username" autoCapitalize="off" spellCheck="false" placeholder={role === "student" ? "Your roll number" : "Your username"} /></Field>
              <Field label="Password" htmlFor="p"><PasswordInput id="p" value={pw} onChange={setPw} placeholder="Your password" /></Field>
              <button type="button" className="link forgot" onClick={() => { setMode("forgot"); setErr(""); setNotice(""); }}>Forgot your password?</button>
              {role === "student" && <button type="button" className="link forgot" onClick={() => go("/report")}>Can't sign in because my college didn't list me</button>}
              <Captcha value={cap} onChange={setCap} resetKey={capKey} />
              {err && <Hint tone="bad">{err}</Hint>}
              <Button variant="primary lg block" type="submit" loading={busy} icon={LockKeyhole} disabled={!user || !pw || (cap.enabled && !cap.token)}>Continue</Button>
              {Object.keys(demo).length > 0 && <button type="button" className="demo-fill" onClick={fillDemo}><Wand2 size={16} />Use a demo {college && role === "institution" ? "account for this college" : ROLE_META[role].label.toLowerCase() + " account"}</button>}
            </form>
          )}

          {mode === "signin" && step === "otp" && (
            <div className="stack" key="o">
              <div className="sent"><Smartphone size={20} /><div><b>Enter your one-time code</b><span>We sent a 6-digit code to <b>{info.masked}</b>. It expires in <b>{mmss(left)}</b>.</span></div></div>
              {info.demo_otp && <Hint tone="warn" icon={Wand2}>Demo mode: no SMS or email is sent, so the code is shown here: <b className="mono big">{info.demo_otp}</b> <button type="button" className="link" onClick={() => { setCode(info.demo_otp); submitOtp(info.demo_otp); }}>Use it</button></Hint>}
              <OtpBoxes value={code} onChange={setCode} onComplete={submitOtp} disabled={busy} />
              {err && <Hint tone="bad">{err}</Hint>}
              <Button variant="primary lg block" icon={ShieldCheck} loading={busy} disabled={code.length !== 6} onClick={() => submitOtp()}>{aicte ? "Verify and continue" : "Verify and sign in"}</Button>
              <div className="row between"><button className="link" onClick={back}><ArrowLeft size={14} /> Use a different account</button><button className="link" onClick={resend}><RefreshCw size={14} /> Send a new code</button></div>
            </div>
          )}

          {mode === "signin" && step === "totp" && (
            <div className="stack" key="t">
              <div className="sent"><ShieldCheck size={20} /><div><b>Authenticator app code</b><span>AICTE accounts need a third check. Open your authenticator app and enter the 6-digit code for <b>NAVS</b>.</span></div></div>
              {info.demo_totp && <Hint tone="warn" icon={Wand2}>Demo mode: your authenticator app would show <b className="mono big">{info.demo_totp}</b> right now. <button type="button" className="link" onClick={() => { setCode(info.demo_totp); submitTotp(info.demo_totp); }}>Use it</button></Hint>}
              <OtpBoxes value={code} onChange={setCode} onComplete={submitTotp} disabled={busy} ariaLabel="Authenticator code" />
              {err && <Hint tone="bad">{err}</Hint>}
              <Button variant="primary lg block" icon={ShieldCheck} loading={busy} disabled={code.length !== 6} onClick={() => submitTotp()}>Verify and sign in</Button>
              <div className="row between"><button className="link" onClick={back}><ArrowLeft size={14} /> Start again</button></div>
            </div>
          )}
          <p className="auth-foot">Have a certificate QR code? <button className="link" onClick={() => go("/verify")}>Verify it without signing in</button></p>
        </div>
      </main>
      <Privacy open={priv} onClose={() => setPriv(false)} />
    </div>
  );
}
