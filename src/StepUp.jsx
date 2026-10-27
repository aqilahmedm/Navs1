import { useEffect, useState } from "react";
import { ShieldCheck, Smartphone, Wand2, RefreshCw } from "lucide-react";
import { post } from "./api.js";
import { Button, Hint, Modal, OtpBoxes } from "./ui.jsx";

export default function StepUp({ method, onDone, onCancel }) {
  const [code, setCode] = useState(""), [err, setErr] = useState(""), [busy, setBusy] = useState(false), [info, setInfo] = useState({}), totp = method === "totp";
  const send = async () => { setErr(""); try { setInfo(await post("/api/stepup/send")); setCode(""); } catch (e) { if (!e.silent) setErr(e.message); } };
  useEffect(() => { send(); }, []);
  useEffect(() => { if (!info.demo_wait) return; const t = setTimeout(send, 3000); return () => clearTimeout(t); }, [info]);   // demo: keep checking until the next authenticator code is valid
  const verify = async v => {
    const c = v ?? code; if (busy || c.length !== 6) return; setBusy(true); setErr("");
    try { await post("/api/stepup/verify", { code: c }); onDone(); } catch (e) { if (!e.silent) { setErr(e.message); setCode(""); } } finally { setBusy(false); }
  };
  return (
    <Modal open onClose={onCancel} title="Confirm it's you" sub="This action needs a fresh check, even though you are signed in."
      footer={<><Button onClick={onCancel}>Cancel</Button><Button variant="primary" icon={ShieldCheck} loading={busy} disabled={code.length !== 6} onClick={() => verify()}>Confirm</Button></>}>
      <div className="sent">{totp ? <ShieldCheck size={20} /> : <Smartphone size={20} />}<div><b>{totp ? "Authenticator app code" : "One-time code"}</b><span>{totp ? "Enter the 6-digit code from your authenticator app." : <>We sent a 6-digit code to <b>{info.masked || "your registered contact"}</b>.</>}</span></div></div>
      {info.demo_otp && <Hint tone="warn" icon={Wand2}>Demo mode: your code is <b className="mono big">{info.demo_otp}</b></Hint>}
      {info.demo_totp && <Hint tone="warn" icon={Wand2}>Demo mode: your authenticator app would show <b className="mono big">{info.demo_totp}</b></Hint>}
      {info.demo_wait && <Hint tone="warn" icon={Wand2}>Demo mode: that authenticator code was just used, and each code works once. Waiting for the next one (up to 30 seconds)…</Hint>}
      <div className="mt"><OtpBoxes value={code} onChange={setCode} onComplete={verify} disabled={busy} ariaLabel="Confirmation code" /></div>
      {err && <div className="mt"><Hint tone="bad">{err}</Hint></div>}
      {!totp && <p className="mt"><button className="link" onClick={send}><RefreshCw size={14} /> Send a new code</button></p>}
    </Modal>
  );
}
