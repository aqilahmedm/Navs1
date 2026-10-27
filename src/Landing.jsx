import { useEffect, useMemo, useState } from "react";
import { ArrowRight, BadgeCheck, Briefcase, Building2, EyeOff, FileUp, Fingerprint, GraduationCap, KeyRound, Landmark, Menu, Moon, QrCode, ScrollText, Search, ShieldCheck, Sun, Timer, UserCheck, Users, X, Check, Sparkles } from "lucide-react";
import { api } from "./api.js";
import { useInView, useTheme } from "./hooks.js";
import { AicteLogo, BrandMark, CollegeLogo, Gear } from "./logos.jsx";
import { BRAND, NOTICE } from "./brand.js";
import { Button, Donut, BarList, Num, Status } from "./ui.jsx";
import Privacy from "./Privacy.jsx";

const goto = id => document.getElementById(id)?.scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start" });

function Lockup({ compact }) {
  return (
    <div className="lockup">
      <AicteLogo size={compact ? 34 : 42} />
      <span className="lk-sep" />
      <BrandMark size={compact ? 28 : 34} />
      <span className="lk-name"><b>{BRAND.name}</b><small className="lk-full">{BRAND.full}</small></span>
    </div>
  );
}

function TopNav({ me, go }) {
  const [open, setOpen] = useState(false), [theme, toggle] = useTheme(), [stuck, setStuck] = useState(false);
  useEffect(() => { const f = () => setStuck(scrollY > 12); f(); addEventListener("scroll", f, { passive: true }); return () => removeEventListener("scroll", f); }, []);
  const links = [["how", "How it works"], ["roles", "Who it's for"], ["security", "Security"], ["colleges", "Colleges"]];
  const jump = id => { setOpen(false); goto(id); };
  return (
    <header className={"l-nav" + (stuck ? " stuck" : "")}>
      <div className="l-nav-in">
        <button className="plain" onClick={() => scrollTo({ top: 0, behavior: "smooth" })} aria-label="Back to top"><Lockup compact /></button>
        <nav className={"l-links" + (open ? " open" : "")} aria-label="Sections">{links.map(([id, l]) => <button key={id} onClick={() => jump(id)}>{l}</button>)}
          <button className="only-m" onClick={() => { setOpen(false); go("/verify"); }}>Verify a certificate</button></nav>
        <div className="l-act">
          <button className="icon-btn" onClick={toggle} aria-label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}>{theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}</button>
          <Button variant="ghost-l hide-m" onClick={() => go("/verify")}>Verify certificate</Button>
          <Button variant="accent" icon={ArrowRight} onClick={() => go(me ? "/app/" : "/login")}>{me ? "Open console" : "Sign in"}</Button>
          <button className="icon-btn only-m" onClick={() => setOpen(o => !o)} aria-label="Menu" aria-expanded={open}>{open ? <X size={20} /> : <Menu size={20} />}</button>
        </div>
      </div>
    </header>
  );
}

const SCEN = [
  { name: "Aarav Mehta", id: "••••••••4821", code: "1-D0004", college: "Alder Institute of Technology", steps: ["ID format valid", "Found in registry", "Name matches", "Date of birth matches", "No duplicate at another college"], out: "VERIFIED" },
  { name: "Meera Iyer", id: "••••••••7305", code: "1-D0012", college: "Orchid College of Engineering", steps: ["ID format valid", "Found in registry", "Name: near match (91%)", "Date of birth matches", "No duplicate at another college"], out: "REVIEW", bad: 2 },
  { name: "Kabir Singh", id: "••••••••1190", code: "1-D0031", college: "Granite Institute of Technology", steps: ["ID format valid", "Found in registry", "Name matches", "Date of birth differs", "Same ID claimed at 2 colleges"], out: "FLAGGED", bad: 3 },
];
function LiveCard() {
  const [i, setI] = useState(0), [k, setK] = useState(0), s = SCEN[i];
  useEffect(() => {
    const still = matchMedia("(prefers-reduced-motion: reduce)").matches; if (still) { setK(99); return; }
    const t = setInterval(() => setK(n => { if (n >= s.steps.length + 3) { setI(x => (x + 1) % SCEN.length); return 0; } return n + 1; }), 650);
    return () => clearInterval(t);
  }, [i]);
  const done = k >= s.steps.length;
  return (
    <div className="live" aria-label="Example of a record being checked">
      <div className="live-h"><CollegeLogo code={s.code} name={s.college} size={40} /><div><b>{s.name}</b><small>APAAR {s.id} · {s.college}</small></div><span className="live-dot"><i />Live demo</span></div>
      <ul className="live-steps">
        {s.steps.map((t, n) => { const state = k > n ? (s.bad !== undefined && n >= s.bad && n === s.bad ? "warn" : "ok") : k === n ? "run" : "wait"; return <li key={t} className={state}><i>{state === "ok" ? <Check size={13} /> : state === "warn" ? "!" : ""}</i><span>{t}</span></li>; })}
      </ul>
      <div className={"live-out" + (done ? " on" : "")}>{done ? <><Status s={s.out} /><small>{s.out === "VERIFIED" ? "Certificate issued with QR" : s.out === "REVIEW" ? "Sent to a reviewer with the evidence" : "Held for review. Not a finding of fraud"}</small></> : <small>Checking…</small>}</div>
    </div>
  );
}

function Hero({ go, ov }) {
  return (
    <section className="hero">
      <Gear className="hero-gear g1" /><Gear className="hero-gear g2" teeth={14} /><div className="hero-glow" />
      <div className="wrap hero-grid">
        <div className="hero-copy">
          <span className="badge"><Sparkles size={14} /> Prototype for {BRAND.ps}</span>
          <h1>Every APAAR record, <em>verified once</em>, trusted everywhere.</h1>
          <p className="lead">{BRAND.name}, the {BRAND.full}, checks admissions against the registry, flags what doesn't add up for a person to review, and issues certificates that anyone can verify with a QR code.</p>
          <div className="hero-cta"><Button variant="accent lg" icon={ArrowRight} onClick={() => go("/login")}>Sign in to your portal</Button><Button variant="ghost-l lg" icon={QrCode} onClick={() => go("/verify")}>Verify a certificate</Button></div>
          <ul className="trust"><li><KeyRound size={16} />Two-step sign-in</li><li><ScrollText size={16} />Tamper-evident audit trail</li><li><EyeOff size={16} />IDs masked by default</li></ul>
          <div className="hero-stats">
            <div><b><Num v={ov?.totals.institutions ?? 0} /></b><span>colleges</span></div>
            <div><b><Num v={ov?.totals.students ?? 0} /></b><span>student records</span></div>
            <div><b><Num v={ov ? Math.round((ov.totals.verified / ov.totals.students) * 100) : 0} />%</b><span>verified</span></div>
          </div>
        </div>
        <div className="hero-art"><LiveCard /><div className="float f1"><BadgeCheck size={16} /> Certificate valid</div><div className="float f2"><ShieldCheck size={16} /> Reviewed by a person</div></div>
      </div>
    </section>
  );
}

const ROLES = [
  { k: "student", icon: GraduationCap, title: "Students", tag: "Own your record", pts: ["See what matches the registry", "Download certificates with a QR code", "Understand why a flag was raised"] },
  { k: "institution", icon: Building2, title: "Institutions", tag: "Clean data, fewer queries", pts: ["Upload and check a batch", "Review flags with a written reason", "Track admissions against approved intake"] },
  { k: "aicte", icon: Landmark, title: "AICTE", tag: "National oversight", pts: ["Anomalies across all colleges", "Escalations decided on the record", "Tamper-evident audit trail"] },
  { k: "employer", icon: Briefcase, title: "Employers", tag: "Verify in seconds", pts: ["Scan a QR or enter an ID", "See identity and validity only", "No marks, no internal flags"] },
];
function Roles({ go }) {
  const spot = e => { const r = e.currentTarget.getBoundingClientRect(); e.currentTarget.style.setProperty("--mx", ((e.clientX - r.left) / r.width) * 100 + "%"); e.currentTarget.style.setProperty("--my", ((e.clientY - r.top) / r.height) * 100 + "%"); };
  return (
    <section className="sec" id="roles"><div className="wrap">
      <header className="sec-h"><span className="eyebrow">One platform, four doors</span><h2>Built for everyone who touches a student record</h2><p>Pick your role to sign in. Each portal shows only what that role needs.</p></header>
      <div className="role-grid">{ROLES.map(r => (
        <button key={r.k} className="role-card" onPointerMove={spot} onClick={() => go("/login?role=" + r.k)}>
          <span className="rc-i"><r.icon size={26} /></span><span className="rc-tag">{r.tag}</span><h3>{r.title}</h3>
          <ul>{r.pts.map(p => <li key={p}><Check size={15} />{p}</li>)}</ul>
          <span className="rc-go">Continue as {r.title.replace(/s$/, "").toLowerCase()} <ArrowRight size={16} /></span>
        </button>))}</div>
    </div></section>
  );
}

const STEPS = [
  { i: FileUp, t: "Upload", d: "Colleges upload an admission batch or add a record. Full APAAR IDs are masked on screen." },
  { i: Search, t: "Cross-check", d: "Each record is compared with the registry: ID format, name, date of birth, and duplicates across colleges." },
  { i: UserCheck, t: "Human review", d: "Anything unusual goes to a reviewer with the evidence. A flag is a prompt, never a verdict. Decisions need a written reason." },
  { i: QrCode, t: "Certificate", d: "Clean or cleared records get a certificate. Anyone can verify it from the QR code and see validity only." },
];
function How() {
  const [ref, seen] = useInView({ threshold: 0.25 });
  return (
    <section className="sec alt" id="how"><div className="wrap">
      <header className="sec-h"><span className="eyebrow">How it works</span><h2>From upload to a certificate anyone can trust</h2></header>
      <ol ref={ref} className={"steps" + (seen ? " in" : "")}>{STEPS.map((s, n) => <li key={s.t} style={{ transitionDelay: n * 120 + "ms" }}><span className="st-n">{n + 1}</span><span className="st-i"><s.i size={22} /></span><h3>{s.t}</h3><p>{s.d}</p></li>)}</ol>
    </div></section>
  );
}

function Snapshot({ ov }) {
  const t = ov?.totals, pct = t ? Math.round((t.verified / t.students) * 100) : 0;
  const states = useMemo(() => Object.entries(ov?.states || {}).sort((a, b) => b[1] - a[1]).slice(0, 8), [ov]);
  return (
    <section className="sec" id="snapshot"><div className="wrap">
      <header className="sec-h"><span className="eyebrow">Live snapshot</span><h2>The demo network at a glance</h2><p>Fictional colleges and students. Numbers update from the running server.</p></header>
      {!ov ? <div className="skel" style={{ height: 280, borderRadius: 20 }} /> :
        <div className="snap">
          <div className="snap-card center"><Donut size={190} thick={20} center={pct + "%"} sub="verified" data={[{ label: "Verified", v: t.verified, color: "var(--ok)" }, { label: "Needs attention", v: t.attention, color: "var(--saffron)" }]} />
            <div className="legend big"><span><i style={{ background: "var(--ok)" }} />Verified <b>{t.verified}</b></span><span><i style={{ background: "var(--saffron)" }} />Needs attention <b>{t.attention}</b></span></div></div>
          <div className="snap-card"><h4>Colleges by state</h4><BarList rows={states} /></div>
          <div className="snap-card nums"><div><Building2 size={22} /><b><Num v={t.institutions} /></b><span>colleges onboarded</span></div><div><Users size={22} /><b><Num v={t.students} /></b><span>records checked</span></div><div><BadgeCheck size={22} /><b><Num v={t.verified} /></b><span>certificates valid</span></div></div>
        </div>}
    </div></section>
  );
}

function Colleges({ list }) {
  const a = list.slice(0, 30), b = list.slice(30);
  const Row = ({ items, rev }) => <div className={"marq" + (rev ? " rev" : "")}><div className="marq-in">{[...items, ...items].map((c, i) => <div className="mq" key={c.code + i} aria-hidden={i >= items.length}><CollegeLogo code={c.code} name={c.name} size={40} /><div><b>{c.name}</b><small>{c.city}, {c.state}</small></div></div>)}</div></div>;
  return (
    <section className="sec alt" id="colleges"><div className="wrap">
      <header className="sec-h"><span className="eyebrow">Demo network</span><h2>{list.length || 60} fictional colleges, each with its own portal</h2><p>Every college gets its own demo logo. Sign in as any of them to see its records.</p></header>
    </div>
      {list.length ? <><Row items={a} /><Row items={b} rev /></> : <div className="wrap"><div className="skel" style={{ height: 150, borderRadius: 18 }} /></div>}
    </section>
  );
}

const PILLARS = [
  { i: KeyRound, t: "Two-step sign-in", d: "Username, password and a human check first, then a one-time code. AICTE officers add an authenticator-app code on top." },
  { i: Fingerprint, t: "Confirm sensitive actions", d: "Uploads and decisions ask you to re-confirm with a fresh code, even when you are already signed in." },
  { i: ScrollText, t: "Tamper-evident audit trail", d: "Every action is chained with a secret key. Editing a past entry breaks the chain and shows up." },
  { i: EyeOff, t: "Masked by default", d: "APAAR IDs show the last four digits. Certificates and employer checks reveal identity and validity only." },
  { i: Users, t: "Least privilege", d: "Each role sees only what it needs. A college can see only its own students." },
  { i: Timer, t: "Short sessions", d: "AICTE sessions end after 10 idle minutes, colleges after 15. You can sign out of every device." },
];
function Pillars() {
  return (
    <section className="sec" id="security"><div className="wrap">
      <header className="sec-h"><span className="eyebrow">Security & privacy</span><h2>Designed to be careful with student data</h2><p>These controls are built into this prototype. It has not yet had an independent security review.</p></header>
      <div className="pillars">{PILLARS.map((p, n) => <article key={p.t} className="pillar" style={{ "--d": n * 60 + "ms" }}><span className="pl-i"><p.i size={22} /></span><h3>{p.t}</h3><p>{p.d}</p></article>)}</div>
    </div></section>
  );
}

function VerifyBand({ go }) {
  const [v, setV] = useState("");
  return (
    <section className="band"><div className="wrap band-in">
      <div><h2>Have a certificate to check?</h2><p>Enter the ID printed under the QR code. No sign-in needed.</p></div>
      <form className="band-f" onSubmit={e => { e.preventDefault(); go("/verify/" + encodeURIComponent(v.trim())); }}>
        <input className="input lg" value={v} onChange={e => setV(e.target.value)} placeholder="APR-XXXXXXXXXXXX" aria-label="Certificate ID" autoComplete="off" />
        <Button variant="accent lg" icon={ArrowRight} type="submit">Verify</Button>
      </form>
    </div></section>
  );
}

function Footer({ go }) {
  const [priv, setPriv] = useState(false);
  return (
    <footer className="l-foot"><div className="wrap">
      <div className="lf-top"><Lockup /><div className="lf-links"><button onClick={() => go("/login")}>Sign in</button><button onClick={() => go("/verify")}>Verify a certificate</button><button onClick={() => go("/report")}>My college didn't list me</button><button onClick={() => setPriv(true)}>Privacy & data use</button></div></div>
      <p className="lf-note"><b>{NOTICE}.</b> The AICTE name and logo belong to AICTE and appear here only to identify the problem statement this prototype addresses. No endorsement or affiliation is implied. College logos are invented.</p>
      <p className="lf-small">© {new Date().getFullYear()} {BRAND.name} prototype · Built with fictional data · Fonts: Public Sans, Source Serif 4, Noto Sans Devanagari (SIL OFL)</p>
    </div><Privacy open={priv} onClose={() => setPriv(false)} /></footer>
  );
}

export default function Landing({ me, go }) {
  const [ov, setOv] = useState(null);
  useEffect(() => { api("/api/public/overview").then(setOv).catch(() => {}); }, []);
  return (
    <div className="landing">
      <TopNav me={me} go={go} /><Hero go={go} ov={ov} /><Roles go={go} /><How /><Snapshot ov={ov} /><Colleges list={ov?.institutions || []} /><Pillars /><VerifyBand go={go} /><Footer go={go} />
    </div>
  );
}
