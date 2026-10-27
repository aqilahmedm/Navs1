import { useState } from "react";
import { Printer, Download } from "lucide-react";
import { api, post } from "../api.js";
import { useAsync } from "../hooks.js";
import { Avatar, CollegeLogo } from "../logos.jsx";
import { Async, Button, Card, Checks, Field, Hint, KV, useToast } from "../ui.jsx";
import { PageHead } from "../Shell.jsx";
import Certificate from "./Cert.jsx";
import { MyCollege } from "./College.jsx";

function Reply({ j, reload }) {
  const [t, setT] = useState(""), [busy, setBusy] = useState(false), [err, setErr] = useState(""), toast = useToast();
  const send = async () => { setBusy(true); setErr(""); try { await post("/api/student/respond", { text: t }); toast("Sent to your college"); setT(""); reload(); } catch (e) { if (!e.silent) setErr(e.message); } finally { setBusy(false); } };
  return (
    <Card title="Reply to your college" sub="Explain a mismatch or answer their question. Your college and AICTE can read this.">
      {j.reply && <Hint tone="info">Your last message: “{j.reply.text}” · {j.reply.ts}</Hint>}
      <Field label="Your message" htmlFor="rep"><textarea id="rep" className="input" rows={3} maxLength={500} value={t} onChange={e => setT(e.target.value)} placeholder="For example: my legal name is spelled differently on my school records." /></Field>
      {err && <Hint tone="bad">{err}</Hint>}
      <Button variant="primary" loading={busy} disabled={t.trim().length < 8} onClick={send}>Send</Button>
    </Card>);
}
function Privacy2({ j, reload }) {
  const s = useAsync(() => api("/api/student/checks")), toast = useToast();
  const toggle = async () => { await post("/api/student/sharing", { enabled: !s.data?.sharing }); toast(s.data?.sharing ? "Employer checks paused" : "Employer checks allowed"); s.reload(); };
  const erase = async kind => { try { await post("/api/student/erasure-request", { kind }); toast("Request recorded"); } catch (e) { if (!e.silent) toast(e.message, "warn"); } };
  return (
    <Card title="Who has checked my certificate" sub="Employers who looked you up, newest first.">
      {s.data && <><Button onClick={toggle}>{s.data.sharing ? "Pause employer checks" : "Allow employer checks again"}</Button>
        {s.data.items.length ? <ul className="hist">{s.data.items.map((l, i) => <li key={i}>{l.by} · {l.status}<br /><small>{l.at}</small></li>)}</ul> : <p className="muted">Nobody yet.</p>}</>}
      <div className="row c mt"><a className="btn" href="/api/student/export" download><Download size={16} /> Download my data</a><Button size="sm" onClick={() => erase("correction")}>Ask for a correction</Button><Button size="sm" onClick={() => erase("erasure")}>Ask for erasure</Button></div>
    </Card>);
}
export function StudentProfile() {
  const s = useAsync(() => api("/api/student/profile"));
  return (
    <Async s={s}>{j => { const p = j.profile, i = j.institution; return (
      <div className="stack">
        <PageHead title="My profile" sub="Your APAAR-linked record. A flag is a prompt for review, not a finding of fraud." />
        <div className="grid2">
          <Card title="Student details">
            <div className="profile"><Avatar i={p.face} size={84} /><div><h2>{p.name}</h2><span className="muted">APAAR {p.apaar}</span><div className="org-line"><CollegeLogo code={i.code} name={i.name} size={26} /><span>{i.name}</span></div></div></div>
            <KV rows={[["Roll no.", p.roll], ["Date of birth", p.dob], ["Category", p.category], ["Email", p.email], ["Phone", p.phone]]} />
            <p className="hint">Demo avatar only. No real photos are used.</p>
          </Card>
          <Card title="Data verification" sub="How your college record compares with the registry">
            <Checks items={j.checks} />
            {j.review && <div className="mt"><Hint tone="warn">Review status: <b>{j.review}</b></Hint></div>}
          </Card>
        </div>
        {j.checks.length > 0 && <Reply j={j} reload={s.reload} />}
        <MyCollege />
        <Privacy2 />
      </div>); }}</Async>
  );
}
export function StudentCerts() {
  const s = useAsync(() => api("/api/student/profile"));
  return (
    <Async s={s}>{j => (
      <div className="stack">
        <PageHead title="My certificates" sub="Share the QR code. Anyone can verify it without seeing your marks."><Button variant="primary" icon={Printer} onClick={() => print()}>Print or save as PDF</Button></PageHead>
        <div className="certs">{j.certs.map(c => <Certificate key={c.kind} c={c} />)}</div>
      </div>)}</Async>
  );
}
