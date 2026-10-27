import { useEffect, useState } from "react";
import { ArrowLeft, Building2, Send } from "lucide-react";
import { api, post, loadCsrf } from "../api.js";
import { useAsync } from "../hooks.js";
import { BrandMark } from "../logos.jsx";
import { BRAND, NOTICE } from "../brand.js";
import Captcha from "../Captcha.jsx";
import { Async, Button, Card, Field, Hint, useToast } from "../ui.jsx";

/* Type 2+ letters of a college's name, city or AICTE ID, then tap the right one. */
export function CollegeSearch({ value, onChange }) {
  const [q, setQ] = useState(""), [items, setItems] = useState([]);
  useEffect(() => {
    if (value || q.trim().length < 2) { setItems([]); return; }
    const t = setTimeout(() => api("/api/public/colleges?q=" + encodeURIComponent(q.trim())).then(d => setItems(d.items)).catch(() => setItems([])), 250);
    return () => clearTimeout(t);
  }, [q, value]);
  if (value) return <div className="row between"><span><b>{value.name}</b><div className="id">{value.code} · {value.city}, {value.state}</div></span><Button size="sm" onClick={() => { onChange(null); setQ(""); }}>Change</Button></div>;
  return <>
    <input className="input" type="search" value={q} onChange={e => setQ(e.target.value)} placeholder="Type your college name, city or AICTE ID" aria-label="Search colleges" autoComplete="off" />
    {items.length > 0 && <ul className="hist">{items.map(c => <li key={c.code}><button type="button" className="link" onClick={() => onChange(c)}>{c.name}</button><br /><small>{c.code} · {c.city}, {c.state}</small></li>)}</ul>}
    {q.trim().length >= 2 && !items.length && <p className="hint">No college found. Try fewer letters.</p>}
  </>;
}

/* Signed-in student: say which college you really study at. A different answer is sent to AICTE. */
export function MyCollege() {
  const s = useAsync(() => api("/api/student/college")), toast = useToast();
  const [pick, setPick] = useState(null), [busy, setBusy] = useState(false), [err, setErr] = useState(""), [msg, setMsg] = useState(null);
  const save = async () => { setBusy(true); setErr(""); try { const j = await post("/api/student/college", { college: pick.code }); setMsg(j); toast(j.differs ? "AICTE has been told" : "Saved"); setPick(null); s.reload(); } catch (e) { if (!e.silent) setErr(e.message); } finally { setBusy(false); } };
  return (
    <Async s={s}>{j => (
      <Card title="My college" sub="Tell us where you actually study. If it is not the college that submitted your record, AICTE is told.">
        <p>Record submitted by <b>{j.record?.name}</b>{j.confirmed && j.declared?.code === j.record?.code && <> · you confirmed this is your college</>}.</p>
        {j.reported && <Hint tone="warn">You told AICTE you study at <b>{j.declared?.name}</b>. AICTE and both colleges can see this. Status: {j.status === "closed" ? "closed by AICTE" : "open"}.</Hint>}
        {msg && <div className="mt"><Hint tone={msg.differs ? "warn" : "ok"}>{msg.message}</Hint></div>}
        <Field label="Change or confirm my college"><CollegeSearch value={pick} onChange={setPick} /></Field>
        {err && <Hint tone="bad">{err}</Hint>}
        {pick && <Button variant="primary" icon={Building2} loading={busy} onClick={save}>{pick.code === j.record?.code ? "Confirm this college" : "Save and tell AICTE"}</Button>}
      </Card>)}</Async>
  );
}

/* Public page (no sign-in): for students whose college never submitted a list, so they have no account. */
export default function ReportCollege({ go }) {
  const [col, setCol] = useState(null), [f, setF] = useState({ name: "", roll: "", apaar_last4: "", contact: "" }), [cap, setCap] = useState({}), [capKey, setCapKey] = useState(0);
  const [busy, setBusy] = useState(false), [err, setErr] = useState(""), [done, setDone] = useState("");
  const set = k => e => setF({ ...f, [k]: e.target.value });
  const ok = col && f.name.trim().length >= 3 && f.roll.trim() && (!cap.enabled || cap.token);
  const send = async e => {
    e.preventDefault(); setBusy(true); setErr("");
    try { await loadCsrf().catch(() => {}); const j = await post("/api/public/enrolment-report", { ...f, college: col.code, captcha_token: cap.token }); setDone(j.message); }
    catch (x) { setErr(x.message); setCapKey(k => k + 1); } finally { setBusy(false); }
  };
  return (
    <div className="public">
      <header className="pub-h"><button className="plain" onClick={() => go("/")}><ArrowLeft size={16} /> Home</button><div className="lockup"><BrandMark size={30} /><span className="lk-name"><b>{BRAND.name}</b><small>Student report</small></span></div></header>
      <main className="pub-m">
        <div className="pub-card">
          <span className="rc-i"><Building2 size={24} /></span><h1>My college didn't list me</h1>
          <p className="muted">If you study at a college but cannot sign in because it never submitted its student list, tell AICTE here. Your college is told too. We ask only for what is needed to find your record. Never enter an Aadhaar number.</p>
          {done ? <Hint tone="ok">{done}</Hint> : (
            <form className="stack" onSubmit={send} noValidate>
              <Field label="Your college"><CollegeSearch value={col} onChange={setCol} /></Field>
              <Field label="Full name" htmlFor="rn"><input id="rn" className="input" value={f.name} onChange={set("name")} maxLength={80} autoComplete="name" /></Field>
              <Field label="Roll or enrolment number" htmlFor="rr"><input id="rr" className="input" value={f.roll} onChange={set("roll")} maxLength={40} autoComplete="off" /></Field>
              <Field label="Last 4 digits of your APAAR ID (optional)" htmlFor="ra"><input id="ra" className="input" value={f.apaar_last4} onChange={e => setF({ ...f, apaar_last4: e.target.value.replace(/\D/g, "").slice(0, 4) })} inputMode="numeric" /></Field>
              <Field label="Email or phone, so we can reach you (optional)" htmlFor="rc"><input id="rc" className="input" value={f.contact} onChange={set("contact")} maxLength={80} autoComplete="email" /></Field>
              <Captcha value={cap} onChange={setCap} resetKey={capKey} />
              {err && <Hint tone="bad">{err}</Hint>}
              <Button variant="primary lg" type="submit" icon={Send} loading={busy} disabled={!ok}>Send to AICTE</Button>
            </form>)}
        </div>
        <p className="pub-note">{NOTICE}</p>
      </main>
    </div>
  );
}
