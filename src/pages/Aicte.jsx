import { useEffect, useState } from "react";
import { Building2, CopyX, Download, Flag, Landmark, ShieldAlert, ShieldCheck, Target, TriangleAlert, Lock, ScrollText, Activity, Users, KeyRound } from "lucide-react";
import { api, post } from "../api.js";
import { useAsync } from "../hooks.js";
import { AicteLogo, Avatar, CollegeLogo, Gear } from "../logos.jsx";
import { Async, BarList, Button, Card, Checks, Donut, Drawer, Empty, Field, Hint, KV, Kpi, LBL, LeadKpi, Num, Pager, Risk, Skeleton, Status, reviewTone, useToast, downloadCsv } from "../ui.jsx";
import { PageHead } from "../Shell.jsx";

const Flags = ({ f }) => <>{f.map(x => <span key={x} className="status bad m">{LBL[x]}</span>)}{!f.length && <span className="status ok">Clean</span>}</>;

const fmtN = v => Number(v).toLocaleString("en-IN");

export function AicteDash({ me }) {
  const s = useAsync(() => api("/api/aicte/overview"));
  return (
    <Async s={s}>{j => { const t = j.totals, st = Object.entries(j.states).sort((a, b) => b[1] - a[1]).slice(0, 8), pct = Math.round((t.VERIFIED / (t.VERIFIED + t.REVIEW + t.FLAGGED || 1)) * 100),
      fst = Object.entries(j.flag_states).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0])).slice(0, 6), ft = Object.entries(j.flag_types).map(([k, v]) => [LBL[k], v]).sort((a, b) => b[1] - a[1]); return (
      <div className="stack">
        <section className="banner"><Gear className="banner-gear" /><AicteLogo size={84} className="banner-logo" />
          <div><span className="badge sm"><Landmark size={14} /> Regulator console</span><h1>National dashboard</h1><p>Admissions across {fmtN(t.institutions)} approved institutions, anomalies and escalations. Demo data only: {t.live} colleges have student-level records, the rest of the register is simulated.</p></div>
          <ul className="banner-facts"><li><Lock size={16} /><span>Signed in as <b>{me.name}</b></span></li><li><KeyRound size={16} /><span>Password · code · authenticator</span></li><li><ScrollText size={16} /><span>Every action is logged</span></li></ul></section>
        <div className="kpis">
          <LeadKpi label="Reported admissions" value={t.reported} parts={[{ label: "Verified", v: t.VERIFIED, color: "var(--ok)" }, { label: "Review", v: t.REVIEW, color: "var(--saffron)" }, { label: "Flagged", v: t.FLAGGED, color: "var(--bad)" }]} />
          <Kpi label="Institutions" value={t.institutions} icon={Building2} note={`Approved intake ${fmtN(t.intake)}`} /><Kpi label="Institutions flagged" value={t.flagged_institutions} tone="bad" icon={Flag} note={`${((t.flagged_institutions / t.institutions) * 100).toFixed(1)}% of the register`} />
          <Kpi label="Over approved intake" value={t.over_institutions} tone="warn" icon={Target} note="Admissions above intake" /><Kpi label="Duplicate APAAR IDs" value={t.dup_total} tone="bad" icon={CopyX} note="Claimed by 2+ colleges" />
        </div>
        <div className="grid3">
          <Card title="Verification status" sub="Records checked"><div className="center"><Donut center={pct + "%"} sub="verified" data={[{ label: "Verified", v: t.VERIFIED, color: "var(--ok)" }, { label: "Needs review", v: t.REVIEW, color: "var(--saffron)" }, { label: "Flagged", v: t.FLAGGED, color: "var(--bad)" }]} /></div>
            <div className="legend big"><span><i style={{ background: "var(--ok)" }} />Verified <b>{fmtN(t.VERIFIED)}</b></span><span><i style={{ background: "var(--saffron)" }} />Review <b>{fmtN(t.REVIEW)}</b></span><span><i style={{ background: "var(--bad)" }} />Flagged <b>{fmtN(t.FLAGGED)}</b></span></div></Card>
          <Card title="Admissions by state" sub="Reported by institutions"><BarList rows={st} fmt={fmtN} /></Card>
          <Card title="Needs attention" sub="Highest-risk institutions"><ul className="rank">{j.top.map(i => <li key={i.code}><CollegeLogo code={i.code} name={i.name} size={38} /><div><b>{i.name}</b><small>{i.code} · {i.city}</small><Risk n={i.risk} /></div></li>)}</ul></Card>
        </div>
        <div className="grid2">
          <Card title="Flagged institutions by reason" sub={`${fmtN(t.flagged_institutions)} institutions carry at least one flag`}><BarList rows={ft} fmt={fmtN} /><div className="mini3 gap"><div><b className="bad-t"><Num v={t.flagged_institutions} /></b><span>Flagged</span></div><div><b className="ok-t"><Num v={t.institutions - t.flagged_institutions} /></b><span>Clean</span></div><div><b>{((t.flagged_institutions / t.institutions) * 100).toFixed(1)}%</b><span>Flag rate</span></div></div><p className="hint">One institution can have several flags. A flag is a prompt for review, not a finding of wrongdoing.</p></Card>
          <Card title="Flagged institutions by state" sub="Where the flags are concentrated"><BarList rows={fst} fmt={fmtN} /></Card>
        </div>
      </div>); }}</Async>
  );
}

export function AicteInst() {
  const [q, setQ] = useState(""), [dq, setDq] = useState(""), [sf, setSf] = useState(""), [ff, setFf] = useState(""), [src, setSrc] = useState(""), [pg, setPg] = useState(0), [open, setOpen] = useState(null), [busy, setBusy] = useState(false), [P, setP] = useState(10);
  const qs = (page, per) => `/api/aicte/institutions?page=${page}&per=${per}&q=${encodeURIComponent(dq)}&state=${encodeURIComponent(sf)}&result=${ff}&source=${src}`;
  useEffect(() => { const t = setTimeout(() => { setDq(q.trim()); setPg(0); }, 250); return () => clearTimeout(t); }, [q]);
  const s = useAsync(() => api(qs(pg, P)), [dq, sf, ff, src, pg, P]), toast = useToast(), j = s.data;
  const exp = async () => { setBusy(true); try { const x = await api(qs(0, 3000)); downloadCsv("institutions_demo.csv", [["AICTE ID", "Institution", "City", "State", "Approved intake", "Reported admissions", "Over intake", "Risk", "Flags", "Source"], ...x.rows.map(i => [i.code, i.name, i.city, i.state, i.intake, i.reported, i.over, i.risk, i.flags.map(f => LBL[f]).join("; "), i.sim ? "Simulated" : "Demo college"])]); toast(`Exported ${fmtN(x.rows.length)} institutions`); } catch (e) { if (!e.silent) toast(e.message); } finally { setBusy(false); } };
  const sel = j && j.rows.find(i => i.code === open) || (open && open.row) || null;
  return (
    <div className="stack">
      <PageHead lead={<AicteLogo size={52} />} title="Approved institutions" sub="Search, filter and export the national register. Admissions above approved intake are highlighted." />
      <Card flush title="All institutions" sub={j ? `${fmtN(j.total)} of ${fmtN(j.all)} institutions · ${fmtN(j.flagged)} flagged` : "Loading…"} actions={<div className="tools">
        <input className="search" type="search" placeholder="Search name, city or ID" aria-label="Search" value={q} onChange={e => setQ(e.target.value)} />
        <select className="search" aria-label="State" value={sf} onChange={e => { setSf(e.target.value); setPg(0); }}><option value="">All states</option>{(j?.states || []).map(x => <option key={x}>{x}</option>)}</select>
        <select className="search" aria-label="Result" value={ff} onChange={e => { setFf(e.target.value); setPg(0); }}><option value="">All results</option><option value="flag">Has flags</option><option value="over">Over intake</option><option value="clean">Clean</option></select>
        <select className="search" aria-label="Source" value={src} onChange={e => { setSrc(e.target.value); setPg(0); }}><option value="">All records</option><option value="live">Demo colleges (60)</option><option value="sim">Simulated register</option></select>
        <select className="search" aria-label="Rows per page" value={P} onChange={e => { setP(+e.target.value); setPg(0); }}>{[10, 25, 50, 100].map(n => <option key={n} value={n}>{n} per page</option>)}</select>
        <Button size="sm" icon={Download} loading={busy} onClick={exp}>Export CSV</Button></div>}>
        {s.error ? <div className="card-b"><Hint tone="bad">{s.error}</Hint></div> : !j ? <div className="card-b"><Skeleton h={320} r={14} /></div> : <>
          <div className={"tbl-wrap" + (s.loading ? " busy" : "")}><table className="tbl" style={{ minWidth: 880 }}><thead><tr><th>Institution</th><th>State</th><th>Approved</th><th>Reported</th><th>Risk</th><th>Flags</th></tr></thead>
            <tbody>{j.rows.map(i => <tr key={i.code} className="clk" tabIndex={0} onClick={() => setOpen({ code: i.code, row: i })} onKeyDown={e => e.key === "Enter" && setOpen({ code: i.code, row: i })}>
              <td><span className="who-c"><CollegeLogo code={i.code} name={i.name} size={38} /><span><b>{i.name}</b><div className="id">{i.code} · {i.city}{i.sim ? "" : " · demo college"}</div></span></span></td><td>{i.state}</td><td>{fmtN(i.intake)}</td>
              <td><b style={{ color: i.over ? "var(--bad)" : "inherit" }}>{fmtN(i.reported)}</b>{i.over ? <span className="id"> (+{fmtN(i.over)})</span> : null}</td><td><Risk n={i.risk} /></td><td className="flagcell"><Flags f={i.flags} /></td></tr>)}</tbody></table></div>
          {!j.rows.length && <Empty>No institutions match.</Empty>}
          {j.total > P && <div className="card-b"><Pager page={j.page} pages={j.pages} onPage={setPg} /></div>}</>}
      </Card>
      <Drawer open={!!sel} onClose={() => setOpen(null)} title={sel && <span className="who-c"><CollegeLogo code={sel.code} name={sel.name} size={52} />{sel.name}</span>} status={sel && <Risk n={sel.risk} />}>
        {sel && <><KV rows={[["AICTE ID", sel.code], ["Location", `${sel.city}, ${sel.state}`], ["Approved intake", fmtN(sel.intake)], ["Reported admissions", fmtN(sel.reported) + (sel.over ? ` (+${fmtN(sel.over)} over)` : "")], ["Records checked", fmtN(sel.sample)]]} />
          <h4>Check results</h4><div className="mini3"><div><b className="ok-t"><Num v={sel.VERIFIED} /></b><span>Verified</span></div><div><b className="warn-t"><Num v={sel.REVIEW} /></b><span>Review</span></div><div><b className="bad-t"><Num v={sel.FLAGGED} /></b><span>Flagged</span></div></div>
          <h4>Flags</h4><p><Flags f={sel.flags} /></p><p className="hint">A flag is a prompt for review, not a finding of wrongdoing.</p>
          {sel.sim && <p className="hint">Simulated register entry: summary figures only, no student-level records.</p>}</>}
      </Drawer>
    </div>
  );
}

export function AicteAnomalies() {
  const s = useAsync(() => Promise.all([api("/api/aicte/overview"), api("/api/aicte/escalations")]));
  const [open, setOpen] = useState(null), [o, setO] = useState("cleared"), [n, setN] = useState(""), [busy, setBusy] = useState(false), [err, setErr] = useState(""), toast = useToast();
  const decide = async () => { setBusy(true); setErr(""); try { await post("/api/aicte/resolve", { cert_id: open.cert_id, outcome: o, note: n }); toast("Decision recorded and logged"); setOpen(null); setN(""); s.reload(); } catch (e) { if (!e.silent) setErr(e.message); } finally { setBusy(false); } };
  return (
    <Async s={s}>{([j, E]) => { const waiting = E.items.filter(i => i.open).length; return (
      <div className="stack">
        <PageHead lead={<AicteLogo size={52} />} title="Anomaly detection" sub="Duplicates and mismatches found by comparing every college record with the registry." />
        <Card flush title="Escalated by institutions" sub={`${waiting} awaiting your decision`}>
          <div className="tbl-wrap"><table className="tbl" style={{ minWidth: 760 }}><thead><tr><th>Student</th><th>College</th><th>What we found</th><th>College note</th><th>State</th></tr></thead>
            <tbody>{E.items.map(x => <tr key={x.cert_id} className="clk" tabIndex={0} onClick={() => { setOpen(x); setErr(""); }} onKeyDown={e => e.key === "Enter" && setOpen(x)}>
              <td><span className="who-c"><Avatar i={x.face} size={30} /><span><b>{x.name}</b><div className="id mono">{x.apaar}</div></span></span></td><td>{x.inst}</td>
              <td className="find">{x.issues.map(y => <div key={y.code}>{LBL[y.code]}</div>)}</td><td className="find">{x.review.note}</td><td><Status tone={reviewTone(x.state)}>{x.state}</Status></td></tr>)}</tbody></table></div>
          {!E.items.length && <Empty>Nothing escalated yet. Sign in as a college, escalate a flagged record, then come back.</Empty>}
        </Card>
        <Card flush title="Same APAAR ID at more than one college" sub={`${j.duplicates.length} found in the ${j.totals.live} demo colleges with student-level records`}><div className="tbl-wrap"><table className="tbl" style={{ minWidth: 420 }}><thead><tr><th>APAAR ID</th><th>Colleges</th></tr></thead><tbody>{j.duplicates.map(d => <tr key={d.apaar}><td className="mono">{d.apaar}</td><td>{d.colleges.map(c => <span key={c} className="status bad m">{c}</span>)}</td></tr>)}</tbody></table></div></Card>
        <Card flush title="Flagged student records" sub={`${j.flagged.length} records in the ${j.totals.live} demo colleges with student-level records`}><div className="tbl-wrap"><table className="tbl" style={{ minWidth: 760 }}><thead><tr><th>Student</th><th>College</th><th>What we found</th></tr></thead><tbody>{j.flagged.slice(0, 60).map(x => <tr key={x.cert_id}><td><span className="who-c"><Avatar i={x.face} size={30} /><span><b>{x.name}</b><div className="id mono">{x.apaar}</div></span></span></td><td>{x.inst}</td><td className="find">{x.issues.map(y => <div key={y.code}>{LBL[y.code]}: <span className="id">{y.msg}</span></div>)}</td></tr>)}</tbody></table></div>
          {j.flagged.length > 60 && <div className="card-b"><p className="hint">Showing the first 60 of {j.flagged.length}.</p></div>}</Card>
        <Drawer open={!!open} onClose={() => setOpen(null)} title={open && <span className="who-c"><Avatar i={open.face} size={44} />{open.name}</span>} status={open && <Status tone={reviewTone(open.state)}>{open.state}</Status>}>
          {open && <><h4>Findings</h4><Checks items={open.issues} /><div className="note warn"><div><b>College note</b> · {open.review.by} · {open.review.ts}<br />“{open.review.note}”</div></div>
            {open.open ? <div className="rev"><h4>AICTE decision</h4>
              <Field label="Outcome" htmlFor="ro"><select id="ro" className="input" value={o} onChange={e => setO(e.target.value)}><option value="cleared">Cleared: data is correct, certificate becomes valid</option><option value="upheld">Upheld: flag stands, certificate stays under review</option></select></Field>
              <Field label="Reason (required, logged)" htmlFor="rn2"><textarea id="rn2" className="input" rows={3} maxLength={300} value={n} onChange={e => setN(e.target.value)} /></Field>
              {err && <Hint tone="bad">{err}</Hint>}<Button variant="primary" loading={busy} disabled={n.trim().length < 8} onClick={decide}>Record decision</Button><p className="hint">Recording a decision asks for a fresh authenticator code.</p></div> : null}</>}
        </Drawer>
      </div>); }}</Async>
  );
}

const CONTROLS = [["Two-step sign-in", "Password and a human check (hCaptcha), then a one-time code. AICTE adds an authenticator-app code (TOTP) as a third check. Password resets need the same codes."], ["Confirm sensitive actions", "Uploads, reviews and AICTE decisions need a fresh code, even inside a session."],
  ["Lockout and rate limits", "5 wrong passwords or codes lock that account for 15 minutes. Requests are also limited per network address."], ["Sessions", "Kept on the server, tied to the browser, revocable. Idle limits: AICTE 10 min, colleges 15 min, others 30 min."],
  ["Request checks", "CSRF token and origin check on every change. Strict content policy with no inline scripts. API responses are never cached."], ["Audit trail", "Each entry is chained to the previous one with a secret key. Editing history breaks the chain."],
  ["Privacy", "APAAR IDs are masked everywhere. QR and employer checks show identity and validity only."]];
export function AicteAudit() {
  const s = useAsync(() => api("/api/aicte/audit")), [pg, setPg] = useState(0);
  return (
    <Async s={s}>{j => { const p = j.posture, P = 15, pages = Math.max(1, Math.ceil(j.entries.length / P)); return (
      <div className="stack">
        <PageHead lead={<AicteLogo size={52} />} title="Security & audit" sub="Sign-ins, code requests, decisions and uploads. Entries are chained, so editing one breaks the chain." />
        <div className="kpis five">
          <Kpi label="Events logged" value={j.total} icon={Activity} /><Kpi label="Chain integrity" value={j.chain_ok ? "Intact" : "Broken"} tone={j.chain_ok ? "ok" : "bad"} icon={ShieldCheck} />
          <Kpi label="Failed sign-in steps" value={p.failed_logins} tone={p.failed_logins ? "warn" : ""} icon={TriangleAlert} /><Kpi label="Lockouts" value={p.lockouts} icon={Lock} /><Kpi label="Active sessions" value={p.active_sessions} icon={Users} />
        </div>
        <Card title="Security controls" sub="Active in this prototype">
          <ul className="checks two">{CONTROLS.map(([a, b]) => <li key={a}><i className="ic pass">✓</i><div><b>{a}</b><span>{b}</span></div></li>)}
            <li><i className={"ic " + (p.allowlist ? "pass" : "review")}>{p.allowlist ? "✓" : "!"}</i><div><b>AICTE network allow-list</b><span>{p.allowlist ? "On: the console opens only from approved networks." : "Off in the demo. Set AICTE_ALLOW_IPS to restrict the console to approved networks."}</span></div></li>
            <li><i className={"ic " + (p.https ? "pass" : "review")}>{p.https ? "✓" : "!"}</i><div><b>HTTPS</b><span>{p.https ? "On: secure cookies and HSTS." : "Off on this device. Use run_https.sh or a proxy before any real use."}</span></div></li>
            <li><i className={"ic " + (p.persistent ? "pass" : "review")}>{p.persistent ? "✓" : "!"}</i><div><b>Database</b><span>{p.persistent ? "MongoDB connected: data and the audit log survive restarts." : "In-memory demo store: everything resets when the server restarts. Set MONGO_URI to keep data."}</span></div></li>
            <li><i className={"ic " + (p.demo_otp ? "review" : "pass")}>{p.demo_otp ? "!" : "✓"}</i><div><b>One-time code delivery</b><span>{p.demo_otp ? "Demo mode: codes are shown on screen. A real SMS or email gateway is needed before real use." : "Codes are delivered by a gateway, not shown on screen."}</span></div></li></ul>
        </Card>
        <Card flush title="Recent events" sub="Newest first">
          <div className="tbl-wrap"><table className="tbl" style={{ minWidth: 760 }}><thead><tr><th>Time</th><th>Actor</th><th>Event</th><th>Detail</th><th>Hash</th></tr></thead>
            <tbody>{j.entries.slice(pg * P, pg * P + P).map(e => <tr key={e.h}><td className="mono">{e.ts}</td><td>{e.actor}<div className="id">{e.role} · {e.ip}</div></td><td><b>{e.action}</b></td><td className="find">{e.detail}</td><td className="mono id">{e.h}</td></tr>)}</tbody></table></div>
          <div className="card-b"><Pager page={pg} pages={pages} onPage={setPg} /></div>
        </Card>
      </div>); }}</Async>
  );
}

export function AicteReports() {
  const s = useAsync(() => api("/api/aicte/reports")), [open, setOpen] = useState(null), [d, setD] = useState(null), [n, setN] = useState(""), [busy, setBusy] = useState(false), [err, setErr] = useState(""), toast = useToast();
  const show = async r => { setOpen(r); setD(null); setErr(""); try { setD(await api("/api/aicte/reports/" + encodeURIComponent(r.code))); } catch (e) { if (!e.silent) setErr(e.message); } };
  const close = async () => { setBusy(true); setErr(""); try { await post("/api/aicte/reports/resolve", { college: open.code, note: n }); toast("Reports closed and logged"); setOpen(null); setN(""); s.reload(); } catch (e) { if (!e.silent) setErr(e.message); } finally { setBusy(false); } };
  return (
    <Async s={s}>{j => (
      <div className="stack">
        <PageHead lead={<AicteLogo size={52} />} title="Student reports" sub="Students who say they study at a college that has not listed them, or whose record came from another college. Colleges that skipped their CSV are shown first." />
        <div className="kpis"><Kpi label="Open reports" value={j.open} tone={j.open ? "warn" : ""} icon={Flag} /><Kpi label="Colleges with no CSV" value={j.no_csv} tone={j.no_csv ? "bad" : ""} icon={Building2} note="Students report them, no list submitted" /></div>
        <Card flush title="Colleges named by students" sub="A report is a prompt for review, not a finding of wrongdoing.">
          <div className="tbl-wrap"><table className="tbl" style={{ minWidth: 820 }}><thead><tr><th>College</th><th>CSV</th><th>Approved / reported</th><th>Not listed</th><th>Record elsewhere</th><th>Latest</th></tr></thead>
            <tbody>{j.rows.map(r => <tr key={r.code} className="clk" tabIndex={0} onClick={() => show(r)} onKeyDown={e => e.key === "Enter" && show(r)}>
              <td><span className="who-c"><CollegeLogo code={r.code} name={r.name} size={34} /><span><b>{r.name}</b><div className="id">{r.code} · {r.city}, {r.state}</div></span></span></td>
              <td>{r.csv_submitted ? <span className="status ok">{fmtN(r.records)} records</span> : <span className="status bad">Not submitted</span>}</td>
              <td>{fmtN(r.intake)} / <b style={{ color: r.over ? "var(--bad)" : "inherit" }}>{fmtN(r.reported)}</b>{r.over ? <span className="id"> (+{fmtN(r.over)})</span> : null}</td>
              <td>{r.unlisted}</td><td>{r.differs_in}{r.disputed_out ? <span className="id"> · {r.disputed_out} dispute this college's record</span> : null}</td><td className="id">{r.last}</td></tr>)}</tbody></table></div>
          {!j.rows.length && <Empty>No student reports yet.</Empty>}
        </Card>
        <Drawer open={!!open} onClose={() => setOpen(null)} title={open && <span className="who-c"><CollegeLogo code={open.code} name={open.name} size={44} />{open.name}</span>} status={open && (open.csv_submitted ? <span className="status warn">CSV submitted</span> : <span className="status bad">No CSV</span>)}>
          {open && <><KV rows={[["AICTE ID", open.code], ["Approved intake", fmtN(open.intake)], ["Reported admissions", fmtN(open.reported) + (open.over ? ` (+${fmtN(open.over)} over)` : "")], ["Records on file", fmtN(open.records)]]} />
            <h4>Reports from students</h4>
            {!d ? <Skeleton h={80} r={10} /> : <ul className="hist">{d.items.map(x => <li key={x.id}><b>{x.name}</b> · roll {x.roll}{x.apaar_last4 ? ` · APAAR ••••${x.apaar_last4}` : ""}<br /><small>{x.kind === "unlisted" ? "Says the college did not list them" : `Record came from ${x.record_college || "another college"}`} · {x.ts}{x.contact ? ` · ${x.contact}` : ""}</small></li>)}</ul>}
            <div className="rev"><h4>Close these reports</h4>
              <Field label="Note (required, logged)" htmlFor="rcn"><textarea id="rcn" className="input" rows={3} maxLength={300} value={n} onChange={e => setN(e.target.value)} placeholder="For example: college asked to upload its list by 15 Nov." /></Field>
              {err && <Hint tone="bad">{err}</Hint>}<Button variant="primary" loading={busy} disabled={n.trim().length < 8} onClick={close}>Close reports</Button><p className="hint">Closing asks for a fresh authenticator code.</p></div></>}
        </Drawer>
      </div>)}</Async>
  );
}
