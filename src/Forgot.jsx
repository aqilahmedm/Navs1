import { useState } from "react";
import { ArrowLeft, KeyRound, ShieldCheck, Wand2 } from "lucide-react";
import { post } from "./api.js";
import Captcha from "./Captcha.jsx";
import { Button, Field, Hint, OtpBoxes, PasswordInput, PwRules, pwOk } from "./ui.jsx";

export default function Forgot({ role, label, initialUser = "", onBack, onDone }) {
  const [stage, setStage] = useState("ask"), [user, setUser] = useState(initialUser), [cap, setCap] = useState({ token: "", enabled: true }), [capKey, setCapKey] = useState(0);
  const [info, setInfo] = useState({}), [code, setCode] = useState(""), [totp, setTotp] = useState(""), [pw, setPw] = useState(""), [pw2, setPw2] = useState(""), [err, setErr] = useState(""), [busy, setBusy] = useState(false);
  const aicte = role === "aicte";

  const ask = async e => {
    e.preventDefault(); if (busy) return; setErr(""); setBusy(true);
    try { setInfo(await post("/api/auth/forgot", { role, username: user, captcha_token: cap.token })); setCode(""); setTotp(""); setStage("reset"); }
    catch (x) { if (!x.silent) setErr(x.message); setCapKey(k => k + 1); } finally { setBusy(false); }
  };
  const reset = async e => {
    e.preventDefault(); if (busy) return; setErr(""); if (pw !== pw2) return setErr("The new passwords don't match."); setBusy(true);
    try { await post("/api/auth/reset", { code, totp, new_password: pw }); onDone("Password updated. Sign in with your new password."); }
    catch (x) { if (x.silent) return; setErr(x.message); if (x.data?.restart) { setStage("ask"); setCapKey(k => k + 1); } else setCode(""); } finally { setBusy(false); }
  };
  const ready = cap.enabled === false || !!cap.token;

  return (
    <div className="stack" key={stage}>
      <button className="link" onClick={onBack}><ArrowLeft size={14} /> Back to sign in</button>
      <div><h3 className="serif" style={{ fontSize: 22 }}>Reset your password</h3><p className="muted">{stage === "ask" ? `Enter your ${label.toLowerCase()} username. We'll send a one-time code to the contact registered for it.` : "Enter the code, then choose a new password."}</p></div>

      {stage === "ask" && (
        <form className="stack" onSubmit={ask} noValidate>
          <Field label="Username" htmlFor="fu" hint={role === "student" ? "Students: your roll number is your username. Ask your college if you're not sure." : undefined}>
            <input id="fu" className="input" value={user} onChange={e => setUser(e.target.value)} autoComplete="username" autoCapitalize="off" spellCheck="false" />
          </Field>
          <Captcha value={cap} onChange={setCap} resetKey={capKey} />
          {err && <Hint tone="bad">{err}</Hint>}
          <Button variant="primary lg block" type="submit" loading={busy} icon={KeyRound} disabled={!user.trim() || !ready}>Send reset code</Button>
        </form>
      )}

      {stage === "reset" && (
        <form className="stack" onSubmit={reset} noValidate>
          <Hint tone="info" icon={ShieldCheck}>{info.message}</Hint>
          {info.demo_otp && <Hint tone="warn" icon={Wand2}>Demo mode: no message is sent, so the code is shown here: <b className="mono big">{info.demo_otp}</b> <button type="button" className="link" onClick={() => setCode(info.demo_otp)}>Use it</button></Hint>}
          <Field label="One-time code"><OtpBoxes value={code} onChange={setCode} disabled={busy} ariaLabel="One-time code" /></Field>
          {info.needs_totp && <>
            {info.demo_totp && <Hint tone="warn" icon={Wand2}>Demo mode: your authenticator app would show <b className="mono big">{info.demo_totp}</b> <button type="button" className="link" onClick={() => setTotp(info.demo_totp)}>Use it</button></Hint>}
            <Field label="Authenticator app code" hint="AICTE accounts need both codes. If you've lost your authenticator, ask your administrator."><OtpBoxes value={totp} onChange={setTotp} disabled={busy} autoFocus={false} ariaLabel="Authenticator code" /></Field></>}
          <Field label="New password" htmlFor="np1"><PasswordInput id="np1" value={pw} onChange={setPw} autoComplete="new-password" /></Field>
          <PwRules pw={pw} user={user} />
          <Field label="Repeat new password" htmlFor="np2"><PasswordInput id="np2" value={pw2} onChange={setPw2} autoComplete="new-password" /></Field>
          {err && <Hint tone="bad">{err}</Hint>}
          <Button variant="primary lg block" type="submit" loading={busy} icon={KeyRound} disabled={code.length !== 6 || (info.needs_totp && totp.length !== 6) || !pwOk(pw, user) || pw !== pw2}>Set new password</Button>
          <p className="hint">Setting a new password signs you out on every device.</p>
        </form>
      )}
    </div>
  );
}
