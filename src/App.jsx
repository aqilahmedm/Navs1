import { useCallback, useEffect, useRef, useState } from "react";
import { api, post, loadCsrf, setCsrf, onAuthLost, onStepUp } from "./api.js";
import { useHashRoute } from "./hooks.js";
import { ToastProvider, useToast, PageSkeleton } from "./ui.jsx";
import Landing from "./Landing.jsx";
import Login from "./Login.jsx";
import Shell, { defaultPage, NAV } from "./Shell.jsx";
import StepUp from "./StepUp.jsx";
import PublicVerify from "./pages/Verify.jsx";
import ReportCollege from "./pages/College.jsx";
import { StudentProfile, StudentCerts } from "./pages/Student.jsx";
import Institution from "./pages/Institution.jsx";
import { AicteDash, AicteInst, AicteAnomalies, AicteAudit, AicteReports } from "./pages/Aicte.jsx";
import Employer from "./pages/Employer.jsx";
import Security from "./pages/Security.jsx";

const PAGES = {
  student: { profile: StudentProfile, certs: StudentCerts },
  institution: { overview: p => <Institution {...p} />, queue: p => <Institution {...p} queue /> },
  aicte: { dash: AicteDash, inst: AicteInst, ano: AicteAnomalies, rep: AicteReports, audit: AicteAudit },
  employer: { verify: Employer },
};

function Inner() {
  const [route, go] = useHashRoute(), toast = useToast();
  const [me, setMe] = useState(undefined), [su, setSu] = useState(null), meRef = useRef(null), dest = useRef(null);
  meRef.current = me;

  const load = useCallback(async () => {
    for (let n = 0; n < 4; n++) {                      // a network or server hiccup must not look like being signed out: retry before giving up
      try { const d = await api("/api/me"); if (d.role) { setCsrf(d.csrf); setMe(d); } else setMe(null); return; } catch { await new Promise(r => setTimeout(r, 1200)); }
    }
    if (!meRef.current) { setMe(null); toast("We couldn't reach the server. Check your connection and reload.", "warn"); }
  }, []);
  useEffect(() => {
    const v = new URLSearchParams(location.search).get("verify");          // links from QR codes: /?verify=ID
    if (v) { history.replaceState(null, "", location.pathname); location.hash = "#/verify/" + encodeURIComponent(v); }
    loadCsrf().catch(() => {}).then(load);
  }, []);
  useEffect(() => { onAuthLost(msg => { if (!meRef.current) return; setMe(null); toast(msg || "You were signed out.", "warn"); go("/login", true); }); onStepUp(method => new Promise((res, rej) => setSu({ method, res, rej }))); }, []);

  const signedIn = async d => { await loadCsrf().catch(() => {}); setCsrf(d.csrf); const m = await api("/api/me"); setMe(m); go("/app/" + defaultPage(d.role), true); toast(`Welcome, ${d.name.split(/[ ,]+/)[0]}.`); };
  const signOut = async () => { try { await post("/api/logout"); } catch {} await loadCsrf().catch(() => {}); dest.current = "/"; setMe(null); toast("You have been signed out.", "info"); };
  const expire = () => { if (!meRef.current) return; setMe(null); toast("Your session expired from inactivity. Please sign in again.", "warn"); go("/login", true); };

  const { path, q } = route, parts = path.split("/").filter(Boolean);
  let view;
  if (me === undefined) view = <div className="boot"><PageSkeleton /></div>;
  else if (parts[0] === "verify") view = <PublicVerify id={decodeURIComponent(parts[1] || "")} go={go} />;
  else if (parts[0] === "report") view = <ReportCollege go={go} />;
  else if (parts[0] === "login") view = me ? (go("/app/" + defaultPage(me.role), true), null) : <Login go={go} initialRole={q.get("role")} onSignedIn={signedIn} />;
  else if (parts[0] === "app") {
    if (!me) { const to = dest.current || "/login"; dest.current = null; go(to, true); view = null; }
    else {
      const page = parts[1] && (NAV[me.role].some(n => n[0] === parts[1])) ? parts[1] : defaultPage(me.role);
      const C = page === "security" ? Security : PAGES[me.role][page];
      view = <Shell me={me} page={page} go={go} onSignOut={signOut} onExpire={expire}><C key={page} me={me} go={go} /></Shell>;
    }
  } else view = <Landing me={me} go={go} />;
  return <>{view}{su && <StepUp method={su.method} onDone={() => { su.res(); setSu(null); }} onCancel={() => { su.rej(Object.assign(new Error("Cancelled"), { silent: true })); setSu(null); }} />}</>;
}
export default function App() { return <ToastProvider><Inner /></ToastProvider>; }
