import { useEffect, useState } from "react";
import { BadgeCheck, ClipboardCheck, LayoutDashboard, Landmark, LogOut, Moon, Search, ShieldCheck, Sun, UserRound, Building2, ScrollText, ShieldAlert, QrCode, Clock, Timer, MessageSquareWarning } from "lucide-react";
import { api, lastActivity, userIdleFor } from "./api.js";
import { fmtAgo, mmss, useTheme } from "./hooks.js";
import { AicteLogo, BrandMark, CollegeLogo, Gear } from "./logos.jsx";
import { BRAND, NOTICE, ROLE_META } from "./brand.js";
import { Button } from "./ui.jsx";
import Privacy from "./Privacy.jsx";

export const NAV = {
  student: [["profile", "My profile", UserRound], ["certs", "Certificates", BadgeCheck], ["security", "Security", ShieldCheck]],
  institution: [["overview", "Overview", LayoutDashboard], ["queue", "Review queue", ClipboardCheck], ["security", "Security", ShieldCheck]],
  aicte: [["dash", "National dashboard", LayoutDashboard], ["inst", "Institutions", Building2], ["ano", "Anomalies", ShieldAlert], ["rep", "Student reports", MessageSquareWarning], ["audit", "Security & audit", ScrollText], ["security", "My security", ShieldCheck]],
  employer: [["verify", "Verify certificate", QrCode], ["security", "Security", ShieldCheck]],
};
export const defaultPage = role => NAV[role][0][0];

let collegeCache = null;
export function useCollege(code) {
  const [c, setC] = useState(null);
  useEffect(() => { if (!code) return; (collegeCache ? Promise.resolve(collegeCache) : api("/api/public/overview").then(d => (collegeCache = d.institutions))).then(l => setC(l.find(x => x.code === code) || null)).catch(() => {}); }, [code]);
  return c;
}

function SessionPill({ me, onExpire }) {
  const [left, setLeft] = useState(me.idle), [more, setMore] = useState(false);
  useEffect(() => { const t = setInterval(() => { const l = me.idle - Math.floor((Date.now() - lastActivity) / 1000); setLeft(l); if (l <= 0) onExpire(); }, 1000); return () => clearInterval(t); }, [me.idle]);
  // Keep-alive: while the person is really using the page (even just reading or typing a note), tell the server so the idle timer doesn't run out under them.
  useEffect(() => { const t = setInterval(() => { if (Date.now() - lastActivity > 30000 && userIdleFor() < 45000) api("/api/me").catch(() => {}); }, 15000); return () => clearInterval(t); }, []);
  const low = left <= 60;
  return (
    <button className={"sess" + (low ? " low" : "")} onClick={async () => { setMore(true); try { await api("/api/me"); } finally { setMore(false); } }} title="Your session ends after inactivity. Click to stay signed in." aria-label={`Session ends in ${mmss(left)} if idle. Click to stay signed in.`}>
      <Timer size={15} /><span>{mmss(left)}</span>{low && <em>Stay signed in</em>}
    </button>
  );
}

export default function Shell({ me, page, go, onSignOut, onExpire, children }) {
  const [theme, toggle] = useTheme(), [priv, setPriv] = useState(false), nav = NAV[me.role], college = useCollege(me.inst), isAicte = me.role === "aicte";
  useEffect(() => { document.title = `${nav.find(n => n[0] === page)?.[1] || "Console"} · ${BRAND.name}`; scrollTo(0, 0); }, [page]);
  const item = ([k, l, I]) => <button key={k} className="nav-i" aria-current={page === k ? "page" : undefined} onClick={() => go("/app/" + k)}><I size={19} /><span>{l}</span></button>;
  return (
    <div className={"shell role-" + me.role}>
      <aside className="side" aria-label="Main navigation">
        <Gear className="side-gear" />
        <div className="side-brand">
          {isAicte ? <><AicteLogo size={46} /><div><b>Regulator console</b><small>{BRAND.name} · AICTE</small></div></> : <><BrandMark size={38} /><div><b>{BRAND.name}</b><small>{BRAND.full}</small></div></>}
        </div>
        <nav className="side-nav">{nav.map(item)}</nav>
        <div className="side-foot">
          {college && !isAicte && <div className="org"><CollegeLogo code={college.code} name={college.name} size={40} /><div><b>{college.name}</b><small>{college.city} · {college.code}</small></div></div>}
          {isAicte && <div className="org sec-org"><ShieldCheck size={22} /><div><b>3-factor sign-in</b><small>Password · code · authenticator</small></div></div>}
          <button className="link-l" onClick={() => setPriv(true)}>Privacy & data use</button>
        </div>
      </aside>
      <div className="main">
        <div className="demo-strip" role="note">{NOTICE}</div>
        <header className="topbar">
          <div className="tb-l">{isAicte ? <AicteLogo size={30} className="only-m" /> : <BrandMark size={30} />}<span className="tb-t only-m">{BRAND.name}</span><span className="tb-r hide-m">{ROLE_META[me.role].label} portal</span></div>
          <div className="tb-r2">
            <SessionPill me={me} onExpire={onExpire} />
            <button className="icon-btn" onClick={toggle} aria-label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}>{theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}</button>
            <div className="who"><div className="who-t"><b>{me.name}</b><small>{ROLE_META[me.role].label}</small></div><Button size="sm" icon={LogOut} onClick={onSignOut} aria-label="Sign out"><span className="hide-m">Sign out</span></Button></div>
          </div>
        </header>
        <main className="content" id="content">{children}</main>
      </div>
      <nav className="bottomnav" aria-label="Main navigation">{nav.map(([k, l, I]) => <button key={k} aria-current={page === k ? "page" : undefined} onClick={() => go("/app/" + k)}><I size={20} /><span>{l.replace("National ", "").replace(" certificate", "").replace("Security & audit", "Audit").replace("dashboard", "Dashboard")}</span></button>)}</nav>
      <Privacy open={priv} onClose={() => setPriv(false)} />
    </div>
  );
}
export const PageHead = ({ title, sub, children, lead }) => <header className="page-h"><div className="ph-l">{lead}<div><h1>{title}</h1>{sub && <p>{sub}</p>}</div></div>{children && <div className="ph-x">{children}</div>}</header>;
