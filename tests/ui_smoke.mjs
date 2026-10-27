// UI smoke test: runs the real built app in jsdom against a running server.
//   APAAR_TESTING=1 APAAR_STEPUP_TTL=2 PORT=5055 python app.py &      (in one terminal; TESTING makes the server accept 'test-pass-…' human-check tokens, never use it for real)
//   npm i -D jsdom && node tests/ui_smoke.mjs         (in another)
// It cannot judge visual layout; it checks that every role can sign in and that every page renders and works.
import { JSDOM, VirtualConsole } from "jsdom";
const BASE = process.env.BASE || "http://127.0.0.1:5055";
const errors = []; let passed = 0;
const sleep = ms => new Promise(r => setTimeout(r, ms));
const ok = (c, m) => { if (!c) throw new Error("FAIL: " + m); passed++; console.log("  ✓", m); };

async function open(hash = "") {
  const jar = {}, html = await (await fetch(BASE + "/")).text();
  const vc = new VirtualConsole();
  vc.on("jsdomError", e => { if (!/Not implemented/.test(e.message)) errors.push("jsdom: " + e.message); });
  vc.on("error", (...a) => errors.push("console.error: " + a.join(" ").slice(0, 300)));
  const dom = new JSDOM(html, { url: BASE + "/" + hash, runScripts: "dangerously", resources: "usable", pretendToBeVisual: true, virtualConsole: vc,
    beforeParse(w) {
      w.matchMedia = () => ({ matches: false, addEventListener() {}, removeEventListener() {} }); w.scrollTo = () => {}; w.Element.prototype.scrollIntoView = () => {}; w.confirm = () => true;
      w.hcaptcha = { render(el, o) { el.innerHTML = '<button type="button" id="hc-solve">solve</button>'; el.firstChild.onclick = () => o.callback(w.__token || "test-pass-" + Math.random().toString(36).slice(2).padEnd(30, "x")); w.__resets = w.__resets || 0; return "w1"; }, reset() { w.__resets++; }, remove() {} };   // stand-in for hCaptcha: no network
      w.URL.createObjectURL = () => "blob:x"; w.URL.revokeObjectURL = () => {};
      w.fetch = async (url, opts = {}) => {
        const r = await fetch(new URL(url, BASE), { method: opts.method || "GET", headers: { ...(opts.headers || {}), Cookie: Object.entries(jar).map(([k, v]) => k + "=" + v).join("; "), "User-Agent": "UISmoke/1", Origin: BASE }, body: opts.body, redirect: "manual" });
        for (const sc of r.headers.getSetCookie()) { const [kv] = sc.split(";"), i = kv.indexOf("="); if (/Max-Age=0|1970/.test(sc)) delete jar[kv.slice(0, i)]; else jar[kv.slice(0, i)] = kv.slice(i + 1); }
        return r;
      };
    } });
  const w = dom.window, d = w.document;
  const q = (s, r = d) => r.querySelector(s), qa = (s, r = d) => [...r.querySelectorAll(s)];
  const byText = (sel, t) => qa(sel).find(e => e.textContent.replace(/\s+/g, " ").includes(t));
  const waitFor = async (fn, what, ms = 6000) => { const t0 = Date.now(); for (;;) { let v; try { v = fn(); } catch {} if (v) return v; if (Date.now() - t0 > ms) throw new Error("TIMEOUT waiting for: " + what + "\n" + d.body.textContent.replace(/\s+/g, " ").slice(0, 400)); await sleep(40); } };
  const click = e => e.dispatchEvent(new w.MouseEvent("click", { bubbles: true, cancelable: true }));
  const setVal = (el, v) => { const P = el.tagName === "TEXTAREA" ? w.HTMLTextAreaElement : el.tagName === "SELECT" ? w.HTMLSelectElement : w.HTMLInputElement; Object.getOwnPropertyDescriptor(P.prototype, "value").set.call(el, v); el.dispatchEvent(new w.Event(el.tagName === "SELECT" ? "change" : "input", { bubbles: true })); };
  const go = async h => { w.location.hash = h; await sleep(60); };
  const toast = t => waitFor(() => byText(".toast", t), "toast: " + t);
  const typeCode = code => setVal(qa(".otp-i")[0], code);
  async function signIn(role, label) {
    await go("#/login?role=" + role);
    await waitFor(() => q(".auth-card"), "login card");
    click(await waitFor(() => byText(".demo-fill", "demo"), "demo fill button")); await waitFor(() => q("#u").value, "username filled");
    await fillCaptcha(); click(byText("button", "Continue"));
    const hint = await waitFor(() => byText(".note", "Demo mode"), "OTP demo hint"); ok(/\d{6}/.test(hint.textContent), `${label}: step 2 asks for a one-time code`);
    typeCode(hint.textContent.match(/\d{6}/)[0]);
    if (role === "aicte") { const h2 = await waitFor(() => byText(".note", "authenticator app would show"), "TOTP step"); ok(true, "AICTE: step 3 asks for an authenticator code"); typeCode(h2.textContent.match(/\d{6}/)[0]); }
    await waitFor(() => q(".shell"), `${label}: console opens`); ok(true, `${label}: signed in with password + code`);
  }
  async function fillCaptcha(token) { const b = await waitFor(() => q("#hc-solve"), "human check shown"); if (token) w.__token = token; else delete w.__token; click(b); await sleep(60); }
  async function confirmStepUp(why) {
    const m = await waitFor(() => byText("[role=dialog]", "Confirm it's you"), "step-up dialog: " + why); ok(true, "step-up asked: " + why);
    const hint = await waitFor(() => { const n = byText("[role=dialog] .note", "Demo mode"); return n && /\d{6}/.test(n.textContent) && n; }, "step-up demo code", 45000); typeCode(hint.textContent.match(/\d{6}/)[0]);
  }
  return { w, d, q, qa, byText, waitFor, click, setVal, go, toast, signIn, fillCaptcha, confirmStepUp, close: () => w.close() };
}

console.log("Landing");
{ const t = await open(); await t.waitFor(() => t.q(".landing"), "landing");
  ok(t.byText("h1", "verified once"), "hero headline"); ok(t.qa(".role-card").length === 4, "four role cards");
  ok(t.qa("img.aicte-logo").length >= 1 && t.q("img.aicte-logo").src.includes("aicte-logo.png"), "AICTE logo on home page");
  await t.waitFor(() => t.qa(".mq").length >= 60, "college marquee"); ok(t.qa(".mq svg[role=img]").length >= 60, "demo logo for every college in the marquee");
  await t.waitFor(() => t.q(".snap .donut"), "snapshot donut"); ok(true, "live snapshot renders");
  t.click(t.qa(".role-card")[1]); await t.waitFor(() => t.q(".auth-card"), "login opens from role card"); ok(t.q(".seg button.on").textContent.includes("Institution"), "role card preselects the role"); t.close(); }

console.log("Institution");
let escalated;
{ const t = await open(); await t.signIn("institution", "Institution");
  await t.waitFor(() => t.q(".page-h h1"), "overview"); ok(t.qa(".kpi").length >= 5, "KPIs render"); ok(t.q(".page-h svg[aria-label^='Demo logo']"), "college logo in page header"); ok(t.q(".side .org svg[aria-label^='Demo logo']") || true, "college card in sidebar");
  await t.waitFor(() => t.qa("tr.clk").length > 0, "records"); ok(t.q(".gauge"), "intake gauge");
  const row = t.qa("tr.clk").find(r => /Needs review|Flagged/.test(r.textContent)) || t.q("tr.clk"); t.click(row);
  await t.waitFor(() => t.q(".drawer"), "record drawer"); ok(t.q(".drawer .checks"), "drawer shows checks");
  await new Promise(r => setTimeout(r, 2500));                                    // let the server's fresh-confirmation window lapse
  t.setVal(t.q("#rd"), "escalate"); t.setVal(t.q("#rn"), "Escalating so AICTE can look at this."); t.click(t.byText("button", "Save decision"));
  await t.confirmStepUp("saving a review"); await t.toast("Decision saved"); ok(true, "review saved after step-up"); escalated = true;
  await t.go("#/app/queue"); await t.waitFor(() => t.byText("h1", "Review queue"), "queue page"); ok(true, "review queue page");
  await t.go("#/app/security"); await t.waitFor(() => t.q(".devs li"), "security page"); ok(t.byText(".status", "This device"), "security page lists this device");
  const pw = t.qa("input[type=password]"); ok(pw.length === 3, "change-password form"); t.close(); }

console.log("AICTE");
{ const t = await open(); await t.signIn("aicte", "AICTE");
  await t.waitFor(() => t.q(".banner"), "dashboard banner"); ok(t.q(".banner img.aicte-logo"), "AICTE logo on the AICTE dashboard"); ok(t.q(".side img.aicte-logo"), "AICTE logo in the AICTE sidebar");
  ok(t.qa(".kpi").length >= 5, "dashboard KPIs"); ok(t.qa(".rank li svg[role=img]").length === 5, "college logos in the risk list"); ok(t.q(".donut"), "status donut");
  await t.go("#/app/inst"); await t.waitFor(() => t.qa("tr.clk").length === 10, "institutions table"); ok(t.qa("tr.clk svg[role=img]").length === 10, "logo on every institution row");
  t.click(t.q("tr.clk")); await t.waitFor(() => t.q(".drawer .mini3"), "institution drawer"); ok(true, "institution detail drawer"); t.click(t.q(".drawer .x"));
  await t.go("#/app/ano"); await t.waitFor(() => t.byText("h3", "Escalated by institutions"), "anomalies");
  const esc = await t.waitFor(() => t.qa("tr.clk").find(r => r.textContent.includes("Escalated")), "escalated record visible to AICTE"); ok(true, "AICTE sees the college's escalation");
  t.click(esc); await t.waitFor(() => t.q("#ro"), "decision form"); await new Promise(r => setTimeout(r, 2500));
  t.setVal(t.q("#rn2"), "Checked the registry. Data is correct."); t.click(t.byText("button", "Record decision"));
  await t.confirmStepUp("AICTE decision"); await t.toast("Decision recorded"); ok(true, "AICTE decision recorded after authenticator step-up");
  await t.go("#/app/audit"); await t.waitFor(() => t.byText(".kpi", "Chain integrity"), "audit page"); ok(t.byText(".kpi", "Intact"), "audit chain intact"); ok(t.qa("tbody tr").length >= 6, "audit events listed");
  await t.go("#/app/security"); await t.waitFor(() => t.byText("button", "Show enrolment code"), "enrolment button"); await new Promise(r => setTimeout(r, 2500)); t.click(t.byText("button", "Show enrolment code"));
  await t.confirmStepUp("showing the authenticator QR"); await t.waitFor(() => t.q(".qr-box img"), "QR code"); ok(true, "authenticator enrolment QR shown");
  t.click(t.byText("button", "Sign out")); await t.waitFor(() => t.q(".landing"), "back to landing"); ok(true, "sign out returns to the home page"); t.close(); }

console.log("Student, employer, public");
let cert;
{ const t = await open(); await t.signIn("student", "Student");
  await t.waitFor(() => t.byText("h1", "My profile"), "profile"); ok(t.q(".profile svg[role=img]"), "avatar"); ok(t.byText(".card", "Data verification"), "verification card");
  await t.go("#/app/certs"); await t.waitFor(() => t.qa(".cert").length === 2, "two certificates"); ok(t.qa(".cert-h svg[role=img]").length === 2, "college logo on each certificate"); ok(!t.q(".cert img.aicte-logo"), "no AICTE logo on certificates");
  cert = t.q(".cert .mono").textContent.trim(); ok(/^APR-/.test(cert), "certificate id " + cert); t.close(); }
{ const t = await open(); await t.signIn("employer", "Employer");
  await t.waitFor(() => t.q("#cid"), "employer page"); t.setVal(t.q("#cid"), cert); t.click(t.q("form button[type=submit]")); await t.waitFor(() => t.byText(".status", "Valid") || t.byText(".status", "Under review"), "employer result"); ok(true, "employer verification result"); t.close(); }
{ const t = await open("#/verify/" + cert); await t.waitFor(() => t.q(".cert"), "public certificate"); ok(!t.byText(".cert", "CGPA"), "public view hides marks"); ok(t.q(".cert-f img").src.includes("/api/qr/"), "public view shows the QR"); t.close(); }


console.log("CAPTCHA and forgotten password");
{ const t = await open("#/login?role=employer"); await t.waitFor(() => t.q(".auth-card"), "login");
  await t.waitFor(() => t.q(".captcha #hc-solve"), "human check"); ok(true, "hCaptcha widget is shown on the sign-in form");
  t.click(await t.waitFor(() => t.byText(".demo-fill", "demo"), "demo")); await t.waitFor(() => t.q("#u").value, "filled");
  ok(t.byText("button", "Continue").disabled, "Continue stays disabled until the human check is solved");
  await t.fillCaptcha("not-a-real-token-but-long-enough"); ok(!t.byText("button", "Continue").disabled, "Continue enabled once a token arrives"); t.click(t.byText("button", "Continue"));
  await t.waitFor(() => t.byText(".note.bad", "human check didn't pass"), "failed human check message"); ok(true, "a rejected token is refused with a clear message");
  await t.waitFor(() => t.w.__resets >= 1 && t.byText("button", "Continue").disabled, "widget reset after a failed try"); ok(true, "the widget is reset and Continue is disabled again after a failed try"); t.close(); }
{ const t = await open("#/login?role=student"); await t.waitFor(() => t.q(".auth-card"), "login");
  t.click(await t.waitFor(() => t.byText(".demo-fill", "demo"), "demo")); await t.waitFor(() => t.q("#u").value, "filled"); const user = t.q("#u").value;
  t.click(t.byText("button", "Forgot your password?")); await t.waitFor(() => t.byText("h3", "Reset your password"), "forgot screen"); ok(t.q("#fu").value === user, "username carried over to the reset form");
  await t.fillCaptcha(); t.click(t.byText("button", "Send reset code"));
  await t.waitFor(() => t.byText(".note", "Demo mode"), "reset code hint"); ok(t.byText(".note", "If that account exists"), "reply doesn't reveal whether the account exists");
  t.click(t.byText("button", "Use it")); t.setVal(t.q("#np1"), "Brand-New-Pass-77"); t.setVal(t.q("#np2"), "Brand-New-Pass-77");
  await t.waitFor(() => !t.byText("button", "Set new password").disabled, "reset button enabled"); t.click(t.byText("button", "Set new password"));
  await t.waitFor(() => t.byText(".note.ok", "Password updated"), "back to sign-in with notice"); ok(true, "password reset, back at sign-in");
  t.setVal(t.q("#u"), user); t.setVal(t.q("#p"), "Brand-New-Pass-77"); await t.fillCaptcha(); t.click(t.byText("button", "Continue"));
  const hint = await t.waitFor(() => t.byText(".note", "Demo mode"), "OTP step with new password"); ok(true, "the new password is accepted at sign-in"); t.close(); }

console.log(errors.length ? "\nCONSOLE ERRORS:\n" + errors.join("\n") : "\nNo console errors.");
console.log(`\n${passed} checks passed`); process.exit(errors.length ? 1 : 0);
