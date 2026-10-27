import { useState } from "react";
import { Check, KeyRound, LogOut, MonitorSmartphone, QrCode, ShieldCheck, Smartphone, Timer, X } from "lucide-react";
import { api, post } from "../api.js";
import { fmtAgo, useAsync } from "../hooks.js";
import { Async, Button, Card, Field, Hint, PasswordInput, useToast } from "../ui.jsx";
import { PageHead } from "../Shell.jsx";

const rules = (pw, u) => [["At least 12 characters", pw.length >= 12], ["Three of: a–z, A–Z, 0–9, symbol", [/[a-z]/, /[A-Z]/, /\d/, /[^A-Za-z0-9]/].filter(r => r.test(pw)).length >= 3], ["Doesn't contain your username", pw.length > 0 && !pw.toLowerCase().includes((u || "").toLowerCase())]];

export default function Security({ me }) {
  const s = useAsync(() => api("/api/account/security")), toast = useToast();
  const [cur, setCur] = useState(""), [nw, setNw] = useState(""), [cf, setCf] = useState(""), [busy, setBusy] = useState(false), [err, setErr] = useState(""), [qr, setQr] = useState(null);
  const change = async e => {
    e.preventDefault(); setErr(""); if (nw !== cf) return setErr("The new passwords don't match."); setBusy(true);
    try { const d = await post("/api/account/password", { current: cur, new: nw }); toast(d.ended ? `Password changed. ${d.ended} other session(s) signed out.` : "Password changed."); setCur(""); setNw(""); setCf(""); s.reload(); }
    catch (x) { if (!x.silent) setErr(x.message); } finally { setBusy(false); }
  };
  const outAll = async () => { if (!confirm("Sign out of every device, including this one?")) return; try { await post("/api/account/signout-all"); location.href = "/"; } catch (x) { if (!x.silent) toast(x.message, "bad"); } };
  const showQr = async () => { try { setQr(await api("/api/account/mfa")); } catch (x) { if (!x.silent) toast(x.message, "bad"); } };
  const r = rules(nw, me.username), ok = r.every(x => x[1]) && nw === cf && cur;
  return (
    <Async s={s}>{j => (
      <div className="stack">
        <PageHead title="Security" sub="How you sign in, where you're signed in, and your password." />
        <div className="grid2">
          <Card title="How you sign in" sub={`Signed in as ${j.username}`}>
            <ul className="checks"><li><i className="ic pass"><KeyRound size={14} /></i><div><b>Password</b><span>Stored as a salted hash. Never shown or logged.</span></div></li>
              <li><i className="ic pass"><Smartphone size={14} /></i><div><b>One-time code</b><span>A 6-digit code, valid for 5 minutes, usable once.</span></div></li>
              {j.factors.includes("totp") && <li><i className="ic pass"><ShieldCheck size={14} /></i><div><b>Authenticator app</b><span>A third check for AICTE accounts. Codes change every 30 seconds and work once.</span></div></li>}
              <li><i className="ic pass"><Timer size={14} /></i><div><b>Re-confirm sensitive actions</b><span>{j.stepup ? `Uploads, reviews and decisions ask for a fresh ${j.stepup === "totp" ? "authenticator" : "one-time"} code if it's been more than ${j.stepup_ttl / 60} minutes.` : "Changing your password asks for a fresh one-time code."}</span></div></li></ul>
            <p className="hint">Session ends after {j.idle / 60} idle minutes, or {j.abs / 3600} hours in total.</p>
          </Card>
          <Card title="Where you're signed in" actions={<Button size="sm" icon={LogOut} onClick={outAll}>Sign out everywhere</Button>}>
            <ul className="devs">{j.sessions.map(d => <li key={d.ref}><MonitorSmartphone size={22} /><div><b>{d.device}{d.current && <span className="status ok m">This device</span>}</b><small>Started {fmtAgo(d.started_ago)} · active {fmtAgo(d.active_ago)}</small></div></li>)}</ul>
            <p className="hint">Don't recognise a device? Change your password. That signs out every other device.</p>
          </Card>
        </div>
        <div className="grid2">
          <Card title="Change password" sub="You'll be asked to confirm with a fresh code.">
            <form onSubmit={change} className="stack" noValidate>
              <Field label="Current password" htmlFor="cp"><PasswordInput id="cp" value={cur} onChange={setCur} /></Field>
              <Field label="New password" htmlFor="np"><PasswordInput id="np" value={nw} onChange={setNw} autoComplete="new-password" /></Field>
              <ul className="rules">{r.map(([l, o]) => <li key={l} className={o ? "ok" : ""}>{o ? <Check size={14} /> : <X size={14} />}{l}</li>)}</ul>
              <Field label="Repeat new password" htmlFor="rp"><PasswordInput id="rp" value={cf} onChange={setCf} autoComplete="new-password" /></Field>
              {err && <Hint tone="bad">{err}</Hint>}
              <Button variant="primary" type="submit" loading={busy} disabled={!ok}>Change password</Button>
            </form>
          </Card>
          {j.mfa_qr && <Card title="Authenticator app (demo)" sub="Add this account to a real authenticator app.">
            <p className="muted">Scan the code with Google Authenticator, Aegis, Microsoft Authenticator or any TOTP app. The 6-digit codes it shows will match the demo codes, which proves this is genuine TOTP.</p>
            {qr ? <div className="qr-box"><img src={qr.qr} width="176" height="176" alt="Authenticator enrolment QR code" /><div><small>Or enter this key by hand</small><code className="mono big">{qr.secret.match(/.{1,4}/g).join(" ")}</code></div></div> : <Button icon={QrCode} onClick={showQr}>Show enrolment code</Button>}
            <Hint tone="warn">Demo only. In a real deployment each officer gets a private secret during enrolment, and it is never shown again.</Hint>
          </Card>}
          {!j.mfa_qr && <Card title="Good to know"><ul className="checks"><li><i className="ic pass">✓</i><div><b>We never ask for your password by email or phone</b><span>Anyone who does is not us.</span></div></li><li><i className="ic pass">✓</i><div><b>Sign out on shared devices</b><span>Closing the tab does not end the session.</span></div></li></ul></Card>}
        </div>
      </div>)}</Async>
  );
}
