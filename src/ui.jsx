import { createContext, useContext, useEffect, useRef, useState, useCallback } from "react";
import { createPortal } from "react-dom";
import { Eye, EyeOff, X, CheckCircle2, AlertTriangle, XCircle, Info, Loader2, ChevronLeft, ChevronRight, Inbox } from "lucide-react";
import { useCountUp, useFocusTrap, useInView } from "./hooks.js";

export const LBL = { DUPLICATE_ACROSS_COLLEGES: "Same APAAR ID at more than one college", NAME_MISMATCH: "Name mismatch", DOB_MISMATCH: "Date of birth mismatch", DOB_UNREADABLE: "Date of birth not readable (use DD-MM-YYYY)", INVALID_APAAR: "Invalid APAAR ID",
  NOT_IN_REGISTRY: "Not in registry", REGISTRY_INSTITUTION_DIFFERS: "Registry shows another college", OVER_INTAKE: "Over approved intake", DUPLICATE_APAAR: "Duplicate APAAR IDs", MISMATCHES: "Data mismatches", STUDENTS_MISSING: "Students say they are missing from the college's list" };
export const ST = { VERIFIED: ["Verified", "ok"], REVIEW: ["Needs review", "warn"], FLAGGED: ["Flagged", "bad"], VALID: ["Valid", "ok"], "UNDER REVIEW": ["Under review", "warn"], REVOKED: ["Revoked", "bad"], EXPIRED: ["Expired", "bad"], PAUSED: ["Paused by student", "mute"], "NOT FOUND": ["Not found", "mute"] };
export const Status = ({ s, tone, children }) => { const [l, t] = ST[s] || [s, "mute"]; return <span className={"status " + (tone || t)}>{children || l}</span>; };
export const reviewTone = t => (/Upheld/.test(t) ? "bad" : /Cleared|Corrected|Dismissed|Resolved/.test(t) ? "ok" : "warn");

/* ---------- toasts ---------- */
const ToastCtx = createContext(() => {});
export const useToast = () => useContext(ToastCtx);
export function ToastProvider({ children }) {
  const [items, setItems] = useState([]);
  const push = useCallback((msg, tone = "ok") => { const id = Math.random(); setItems(a => [...a.slice(-2), { id, msg, tone }]); setTimeout(() => setItems(a => a.filter(x => x.id !== id)), 4200); }, []);
  const Ico = { ok: CheckCircle2, bad: XCircle, warn: AlertTriangle, info: Info };
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="toasts" role="status" aria-live="polite">
        {items.map(t => { const I = Ico[t.tone] || Info; return <div key={t.id} className={"toast " + t.tone}><I size={18} /><span>{t.msg}</span></div>; })}
      </div>
    </ToastCtx.Provider>
  );
}

/* ---------- basics ---------- */
export function Button({ variant = "", size = "", icon: Icon, loading, children, className = "", ...p }) {
  return <button className={`btn ${variant} ${size} ${className}`} disabled={loading || p.disabled} {...p}>{loading ? <Loader2 size={16} className="spin" /> : Icon ? <Icon size={size === "sm" ? 15 : 17} /> : null}{children}</button>;
}
export function Card({ title, sub, actions, children, className = "", flush, id }) {
  return (
    <section className={"card " + className} id={id}>
      {(title || actions) && <header className="card-h"><div>{title && <h3>{title}</h3>}{sub && <p>{sub}</p>}</div>{actions && <div className="card-x">{actions}</div>}</header>}
      <div className={flush ? "" : "card-b"}>{children}</div>
    </section>
  );
}
export function Field({ label, hint, error, children, htmlFor }) {
  return <div className="field"><label htmlFor={htmlFor}>{label}</label>{children}{hint && !error && <span className="hint">{hint}</span>}{error && <span className="err-t">{error}</span>}</div>;
}
export function PasswordInput({ id, value, onChange, autoComplete = "current-password", placeholder, onKeyDown }) {
  const [show, setShow] = useState(false), [caps, setCaps] = useState(false);
  return (
    <div className="pw">
      <input id={id} className="input" type={show ? "text" : "password"} value={value} onChange={e => onChange(e.target.value)} autoComplete={autoComplete} placeholder={placeholder} spellCheck="false" autoCapitalize="off"
        onKeyDown={e => { setCaps(e.getModifierState?.("CapsLock")); onKeyDown?.(e); }} onKeyUp={e => setCaps(e.getModifierState?.("CapsLock"))} />
      <button type="button" className="pw-t" onClick={() => setShow(s => !s)} aria-label={show ? "Hide password" : "Show password"}>{show ? <EyeOff size={18} /> : <Eye size={18} />}</button>
      {caps && <span className="caps"><AlertTriangle size={13} /> Caps Lock is on</span>}
    </div>
  );
}
export function OtpBoxes({ value, onChange, onComplete, disabled, ariaLabel = "6-digit code", autoFocus = true }) {
  const refs = useRef([]);
  useEffect(() => { if (autoFocus) refs.current[0]?.focus(); }, []);
  const apply = (v, focusAt) => { v = v.replace(/\D/g, "").slice(0, 6); onChange(v); const n = Math.min(focusAt ?? v.length, 5); setTimeout(() => refs.current[n]?.focus(), 0); if (v.length === 6) onComplete?.(v); };
  return (
    <div className="otp" role="group" aria-label={ariaLabel} onPaste={e => { e.preventDefault(); apply(e.clipboardData.getData("text")); }}>
      {[0, 1, 2, 3, 4, 5].map(i => (
        <input key={i} ref={el => (refs.current[i] = el)} className={"otp-i" + (value[i] ? " on" : "")} inputMode="numeric" pattern="[0-9]*" maxLength={1} disabled={disabled}
          autoComplete={i === 0 ? "one-time-code" : "off"} aria-label={`Digit ${i + 1}`} value={value[i] || ""}
          onChange={e => { const d = e.target.value.replace(/\D/g, ""); if (!d) return apply(value.slice(0, i) + value.slice(i + 1), i); apply((value.slice(0, i) + d + value.slice(i + 1)), i + d.length); }}
          onKeyDown={e => { if (e.key === "Backspace" && !value[i] && i > 0) { e.preventDefault(); apply(value.slice(0, i - 1) + value.slice(i), i - 1); } if (e.key === "ArrowLeft" && i > 0) refs.current[i - 1]?.focus(); if (e.key === "ArrowRight" && i < 5) refs.current[i + 1]?.focus(); }}
          onFocus={e => e.target.select()} />
      ))}
    </div>
  );
}
export function Segmented({ options, value, onChange, label }) {
  return <div className="seg" role="tablist" aria-label={label}>{options.map(o => <button key={o.k} role="tab" aria-selected={value === o.k} className={value === o.k ? "on" : ""} onClick={() => onChange(o.k)}>{o.icon && <o.icon size={16} />}<span>{o.label}</span></button>)}</div>;
}
export const Chips = ({ options, value, onChange }) => <div className="chips">{options.map(([k, l]) => <button key={k} className="chip" aria-pressed={value === k} onClick={() => onChange(k)}>{l}</button>)}</div>;
export const Empty = ({ children = "Nothing to show.", icon: I = Inbox }) => <div className="empty"><I size={26} /><span>{children}</span></div>;
export const Skeleton = ({ h = 16, w = "100%", r = 8, className = "" }) => <div className={"skel " + className} style={{ height: h, width: w, borderRadius: r }} />;
export const PageSkeleton = () => <div className="stack"><div className="kpis">{[0, 1, 2, 3, 4].map(i => <Skeleton key={i} h={92} r={14} />)}</div><Skeleton h={260} r={18} /><Skeleton h={180} r={18} /></div>;
export function Pager({ page, pages, onPage }) {
  return <div className="pager"><Button size="sm" icon={ChevronLeft} disabled={page <= 0} onClick={() => onPage(page - 1)}>Previous</Button><span>Page {page + 1} of {pages}</span><Button size="sm" disabled={page >= pages - 1} onClick={() => onPage(page + 1)}>Next <ChevronRight size={15} /></Button></div>;
}
export function Checks({ items }) {
  if (!items?.length) return <ul className="checks"><li><i className="ic pass">✓</i><div><b>All checks passed</b><span>Matches the registry and no duplicates were found.</span></div></li></ul>;
  return <ul className="checks">{items.map((i, k) => <li key={k}><i className={"ic " + (i.sev === "high" ? "fail" : "review")}>{i.sev === "high" ? "✕" : "!"}</i><div><b>{LBL[i.code] || i.code}</b><span>{i.msg}</span></div></li>)}</ul>;
}

/* ---------- overlays ---------- */
function Overlay({ open, onClose, children, kind }) {
  useEffect(() => { if (!open) return; const k = e => e.key === "Escape" && onClose(); addEventListener("keydown", k); document.body.classList.add("noscroll"); return () => { removeEventListener("keydown", k); document.body.classList.remove("noscroll"); }; }, [open]);
  if (!open) return null;
  return createPortal(<div className={"overlay " + kind}><div className="scrim" onClick={onClose} />{children}</div>, document.body);
}
export function Modal({ open, onClose, title, sub, children, footer, wide }) {
  const ref = useFocusTrap(open);
  return <Overlay open={open} onClose={onClose} kind="modal-wrap"><div ref={ref} tabIndex={-1} className={"modal" + (wide ? " wide" : "")} role="dialog" aria-modal="true" aria-label={title}>
    <header><div><h3>{title}</h3>{sub && <p>{sub}</p>}</div><button className="x" onClick={onClose} aria-label="Close"><X size={18} /></button></header><div className="modal-b">{children}</div>{footer && <footer>{footer}</footer>}</div></Overlay>;
}
export function Drawer({ open, onClose, title, status, children }) {
  const ref = useFocusTrap(open);
  return <Overlay open={open} onClose={onClose} kind="drawer-wrap"><aside ref={ref} tabIndex={-1} className="drawer" role="dialog" aria-modal="true" aria-label="Details">
    <header><div className="dr-t"><h3>{title}</h3>{status}</div><button className="x" onClick={onClose} aria-label="Close"><X size={18} /></button></header><div className="drawer-b">{children}</div></aside></Overlay>;
}

/* ---------- numbers & charts ---------- */
export function Num({ v, run = true }) { const n = useCountUp(typeof v === "number" ? v : 0, run); return typeof v === "number" ? n.toLocaleString("en-IN") : v; }
export function Kpi({ label, value, tone = "", icon: I, note }) {
  const [ref, seen] = useInView();
  return <div ref={ref} className={"kpi " + tone}><div className="kpi-top">{I && <span className="kpi-i"><I size={18} /></span>}<span className="l">{label}</span></div><div className="n"><Num v={value} run={seen} /></div>{note && <div className="kpi-n">{note}</div>}</div>;
}
export function LeadKpi({ label, value, parts }) {
  const [ref, seen] = useInView(); const t = parts.reduce((a, p) => a + p.v, 0) || 1;
  return <div ref={ref} className="kpi lead"><span className="l">{label}</span><div className="n"><Num v={value} run={seen} /></div>
    <div className="bar" role="img" aria-label={parts.map(p => `${p.label} ${p.v}`).join(", ")}>{parts.map(p => <i key={p.label} style={{ width: seen ? `${(p.v / t) * 100}%` : 0, background: p.color }} />)}</div>
    <div className="legend">{parts.map(p => <span key={p.label}><i style={{ background: p.color }} />{p.label} <b>{Number(p.v).toLocaleString("en-IN")}</b></span>)}</div></div>;
}
export function Donut({ data, size = 168, thick = 18, center, sub }) {
  const total = data.reduce((a, d) => a + d.v, 0) || 1, r = (size - thick) / 2, C = 2 * Math.PI * r; const [go, setGo] = useState(false);
  useEffect(() => { const t = setTimeout(() => setGo(true), 80); return () => clearTimeout(t); }, []);
  let off = 0;
  return (
    <div className="donut" style={{ width: size, height: size }}>
      <svg viewBox={`0 0 ${size} ${size}`} width={size} height={size} role="img" aria-label={data.map(d => `${d.label} ${d.v}`).join(", ")}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--line)" strokeWidth={thick} />
        {data.map(d => { const len = (C * d.v) / total; const el = <circle key={d.label} cx={size / 2} cy={size / 2} r={r} fill="none" stroke={d.color} strokeWidth={thick} strokeDasharray={`${go ? Math.max(len - 2, 0) : 0} ${C}`} strokeDashoffset={-off} transform={`rotate(-90 ${size / 2} ${size / 2})`} style={{ transition: "stroke-dasharray 1s cubic-bezier(.2,.8,.2,1)" }} />; off += len; return el; })}
      </svg>
      <div className="donut-c"><b>{center}</b><span>{sub}</span></div>
    </div>
  );
}
export function BarList({ rows, fmt = v => v }) {
  const [ref, seen] = useInView(); const mx = Math.max(...rows.map(r => r[1]), 1);
  return <div ref={ref} className="bars">{rows.map(([k, v, extra], i) => <div className="r" key={k}><span>{k}</span><div className="t"><i style={{ width: seen ? `${(v / mx) * 100}%` : 0, transitionDelay: `${i * 40}ms` }} /></div><b>{fmt(v)}</b></div>)}</div>;
}
export const Risk = ({ n }) => <div className="risk"><div className="t"><i style={{ width: n + "%", background: n > 60 ? "var(--bad)" : n > 25 ? "var(--saffron)" : "var(--ok)" }} /></div><small>{n}/100</small></div>;
export const Hint = ({ children, tone = "info", icon: I = Info }) => <div className={"note " + tone}><I size={17} /><div>{children}</div></div>;
export function Async({ s, children }) {
  if (s.error) return <Hint tone="bad">{s.error}</Hint>;
  if (s.loading && !s.data) return <PageSkeleton />;
  return children(s.data);
}
export const KV = ({ rows }) => <dl className="kv">{rows.map(([a, b]) => <div key={a}><dt>{a}</dt><dd>{b}</dd></div>)}</dl>;
export const downloadCsv = (name, rows) => {
  const c = v => { v = String(v ?? ""); return '"' + ((/^[=+\-@]/.test(v) ? "'" : "") + v).replace(/"/g, '""') + '"'; };
  const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([rows.map(r => r.map(c).join(",")).join("\n")], { type: "text/csv" })); a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 2000);
};
export function PwRules({ pw, user }) {
  const r = [["At least 12 characters", pw.length >= 12], ["Three of: a–z, A–Z, 0–9, symbol", [/[a-z]/, /[A-Z]/, /\d/, /[^A-Za-z0-9]/].filter(x => x.test(pw)).length >= 3], ["Doesn't contain your username", pw.length > 0 && !pw.toLowerCase().includes((user || "").toLowerCase())]];
  return <ul className="rules">{r.map(([l, o]) => <li key={l} className={o ? "ok" : ""}>{o ? <CheckCircle2 size={14} /> : <XCircle size={14} />}{l}</li>)}</ul>;
}
export const pwOk = (pw, user) => pw.length >= 12 && [/[a-z]/, /[A-Z]/, /\d/, /[^A-Za-z0-9]/].filter(x => x.test(pw)).length >= 3 && !pw.toLowerCase().includes((user || "x@@").toLowerCase());
