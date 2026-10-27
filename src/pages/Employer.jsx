import { useState } from "react";
import { History, ScanLine } from "lucide-react";
import { api, post } from "../api.js";
import { Button, Card, Field, Hint, Status } from "../ui.jsx";
import { PageHead } from "../Shell.jsx";
export default function Employer() {
  const [id, setId] = useState(""), [res, setRes] = useState(null), [err, setErr] = useState(""), [busy, setBusy] = useState(false);
  const run = async e => { e?.preventDefault(); if (!id.trim()) return; setBusy(true); setErr(""); try { setRes(await api("/api/employer/verify/" + encodeURIComponent(id.trim()))); } catch (x) { if (!x.silent) { setErr(x.message); setRes(null); } } finally { setBusy(false); } };
  const [many, setMany] = useState(""), [rows, setRows] = useState(null), [mb, setMb] = useState(false);
  const batch = async () => { setMb(true); setErr(""); try { const ids = many.split(/[\s,;]+/).filter(Boolean); setRows((await post("/api/employer/verify-batch", { ids })).results); } catch (x) { if (!x.silent) setErr(x.message); } finally { setMb(false); } };
  return (
    <div className="stack">
      <PageHead title="Verify a certificate" sub="Enter the certificate ID printed under the QR code." />
      <div className="grid2">
        <Card title="Certificate check" sub="Employers see identity and validity only, never marks or internal flags.">
          <form onSubmit={run} className="stack"><Field label="Certificate ID" htmlFor="cid"><input id="cid" className="input lg" value={id} onChange={e => setId(e.target.value)} placeholder="APR-XXXXXXXXXXXX" autoComplete="off" /></Field><Button variant="primary lg" icon={ScanLine} type="submit" loading={busy} disabled={!id.trim()}>Verify</Button></form>
          {err && <div className="mt"><Hint tone="bad">{err}</Hint></div>}
        </Card>
        <Card title={res ? "Result" : "Your recent checks"}>
          {res ? <div className="stack"><Status s={res.status || (res.valid ? "VALID" : "UNDER REVIEW")} /><h2 className="serif">{res.name}</h2><div className="muted">{res.program} · {res.institution} · APAAR {res.apaar}</div></div> : <p className="muted">Results appear here.</p>}
          <h4 className="mt"><History size={16} /> Your recent checks</h4>
          {res?.log?.length ? <ul className="hist">{res.log.map((l, i) => <li key={i}>{l.cert} · {l.status}<br /><small>{l.at}</small></li>)}</ul> : <p className="muted">None yet.</p>}
        </Card>
      </div>
      <Card title="Check several at once" sub="Paste up to 20 certificate IDs, separated by spaces, commas or new lines.">
        <textarea className="input" rows={3} value={many} onChange={e => setMany(e.target.value)} aria-label="Certificate IDs" />
        <Button variant="primary" loading={mb} disabled={!many.trim()} onClick={batch}>Verify all</Button>
        {rows && <div className="tbl-wrap"><table className="tbl"><thead><tr><th>ID</th><th>Result</th><th>Name</th></tr></thead><tbody>{rows.map(r => <tr key={r.cert_id}><td className="mono">{r.cert_id}</td><td><Status s={r.status} /></td><td>{r.name ? `${r.name} · ${r.institution}` : "—"}</td></tr>)}</tbody></table></div>}
      </Card>
    </div>
  );
}
