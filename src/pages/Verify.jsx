import { useEffect, useState } from "react";
import { ArrowLeft, Search, QrCode } from "lucide-react";
import { api } from "../api.js";
import { BrandMark, AicteLogo } from "../logos.jsx";
import { BRAND, NOTICE } from "../brand.js";
import { Button, Hint, Skeleton } from "../ui.jsx";
import Certificate from "./Cert.jsx";
export default function PublicVerify({ id, go }) {
  const [v, setV] = useState(id), [res, setRes] = useState(null), [err, setErr] = useState(""), [busy, setBusy] = useState(false);
  const run = async val => { val = (val ?? v).trim(); if (!val) return; setBusy(true); setErr(""); setRes(null); try { const j = await api("/api/verify/" + encodeURIComponent(val)); j.kind = "Enrolment Verification"; setRes(j); } catch (e) { setErr(e.message); } finally { setBusy(false); } };
  useEffect(() => { if (id) run(id); }, [id]);
  return (
    <div className="public">
      <header className="pub-h"><button className="plain" onClick={() => go("/")}><ArrowLeft size={16} /> Home</button><div className="lockup"><BrandMark size={30} /><span className="lk-name"><b>{BRAND.name}</b><small>Public certificate check</small></span></div></header>
      <main className="pub-m">
        <div className="pub-card">
          <span className="rc-i"><QrCode size={24} /></span><h1>Verify a certificate</h1><p className="muted">Enter the ID printed under the QR code, or scan the code with your phone. No sign-in needed. You will see identity and validity only.</p>
          <form className="band-f" onSubmit={e => { e.preventDefault(); go("/verify/" + encodeURIComponent(v.trim())); run(); }}>
            <input className="input lg" value={v} onChange={e => setV(e.target.value)} placeholder="APR-XXXXXXXXXXXX" aria-label="Certificate ID" autoComplete="off" />
            <Button variant="primary lg" icon={Search} type="submit" loading={busy}>Verify</Button>
          </form>
        </div>
        {busy && <Skeleton h={360} r={20} />}
        {err && <Hint tone="bad">{err}</Hint>}
        {res && <div className="certs one"><Certificate c={res} /></div>}
        <p className="pub-note">{NOTICE}</p>
      </main>
    </div>
  );
}
