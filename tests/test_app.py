"""Run:  python -m unittest discover -s tests -v   (from the project folder)"""
import os, sys, time, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["DEMO_SHOW_OTP"] = "1"; os.environ["APAAR_TESTING"] = "1"
os.environ["HCAPTCHA_SECRET"] = "test-secret"
import app as A

# hCaptcha is never contacted in tests: tokens that start with "ok-" count as solved, and each one works once (like the real service).
USED = set(); VERIFY_CALLS = []
def fake_verify(token, remoteip=""):
    VERIFY_CALLS.append((token, remoteip))
    if not token.startswith("ok-") or token in USED: return False
    USED.add(token); return True
REAL_VERIFY_ = A.hcaptcha_verify
A.hcaptcha_verify = fake_verify
_n = [0]

def session(role="student", user=None):
    c = A.app.test_client(); csrf = c.get("/api/csrf").get_json()["csrf"]
    return c, {"X-CSRF-Token": csrf}

def solve(c=None, text=False):
    _n[0] += 1; return {"captcha_token": f"ok-{_n[0]:030d}"}

def pwpost(c, h, role, user, pw, cap=True):
    body = {"role": role, "username": user, "password": pw}
    if cap: body.update(solve(c))
    return c.post("/api/auth/password", json=body, headers=h)

def login(role, user=None, pw=None):
    """Full sign-in with the demo account of this role (or a given one). Returns (client, headers, user)."""
    user = user or A._demo_accounts()[role]
    c, h = session()
    r = pwpost(c, h, role, user, pw or A.demo_pw(user))
    assert r.status_code == 200, r.get_json()
    d = r.get_json(); r = c.post("/api/auth/otp", json={"code": d["demo_otp"]}, headers=h); d = r.get_json()
    if d.get("stage") == "totp":
        r = c.post("/api/auth/totp", json={"code": d["demo_totp"]}, headers=h); d = r.get_json()
    assert d.get("done"), d
    return c, {"X-CSRF-Token": d["csrf"]}, user

class Base(unittest.TestCase):
    def setUp(self):                      # each test starts with clean rate limits and lockouts
        A.RL.clear(); A.FAILS.clear(); A.LOCKED.clear(); A.DB.ctr.clear(); A.TOTP_LAST.clear(); A.RST.clear(); A.DB.c.pop("pwchg", None)   # passwords go back to their demo values

class AuthFlow(Base):
    def test_all_roles_can_sign_in_with_password_then_code(self):
        for role in A.ROLES:
            c, h, u = login(role)
            self.assertEqual(c.get("/api/me").get_json()["role"], role)

    def test_aicte_needs_a_third_step(self):
        c, h = session(); u = "aicte.officer"
        d = pwpost(c, h, "aicte", u, A.demo_pw(u)).get_json()
        d = c.post("/api/auth/otp", json={"code": d["demo_otp"]}, headers=h).get_json()
        self.assertEqual(d["stage"], "totp")
        self.assertIsNone(c.get("/api/me").get_json()["role"])          # not signed in yet
        self.assertEqual(c.get("/api/aicte/overview").status_code, 401)

    def test_wrong_password_and_unknown_user_look_the_same(self):
        c, h = session()
        a = pwpost(c, h, "student", "r001-0001", "nope")
        b = pwpost(c, h, "student", "nobody", "nope")
        self.assertEqual((a.status_code, a.get_json()), (b.status_code, b.get_json()))

    def test_role_mismatch_is_rejected(self):
        c, h = session(); u = A._demo_accounts()["institution"]
        r = pwpost(c, h, "aicte", u, A.demo_pw(u))
        self.assertEqual(r.status_code, 401)

    def test_wrong_otp_five_times_restarts_sign_in(self):
        c, h = session(); u = "acme.hr"
        pwpost(c, h, "employer", u, A.demo_pw(u))
        for _ in range(4): self.assertEqual(c.post("/api/auth/otp", json={"code": "000000"}, headers=h).status_code, 400)
        last = c.post("/api/auth/otp", json={"code": "000000"}, headers=h)
        self.assertEqual(last.status_code, 401); self.assertTrue(last.get_json()["restart"])

    def test_account_locks_after_five_wrong_passwords(self):
        c, h = session(); u = "globex.hr"
        for _ in range(5): pwpost(c, h, "employer", u, "bad")
        r = pwpost(c, h, "employer", u, A.demo_pw(u))
        self.assertEqual(r.status_code, 429)
        A.unlock(u)

    def test_otp_is_single_use(self):
        c, h = session(); u = "acme.hr"
        d = pwpost(c, h, "employer", u, A.demo_pw(u)).get_json()
        done = c.post("/api/auth/otp", json={"code": d["demo_otp"]}, headers=h).get_json(); self.assertTrue(done["done"])
        new = {"X-CSRF-Token": done["csrf"]}                                   # the CSRF token is renewed at sign-in
        self.assertEqual(c.post("/api/auth/otp", json={"code": d["demo_otp"]}, headers=new).status_code, 401)
        self.assertEqual(c.post("/api/auth/otp", json={"code": d["demo_otp"]}, headers=h).status_code, 403)   # stale token refused

class Captcha(Base):
    def test_sign_in_needs_a_captcha(self):
        c, h = session(); u = "acme.hr"
        r = pwpost(c, h, "employer", u, A.demo_pw(u), cap=False)
        self.assertEqual(r.status_code, 400); self.assertTrue(r.get_json()["captcha"])

    def test_wrong_captcha_is_refused_and_does_not_count_against_the_account(self):
        c, h = session(); u = "acme.hr"
        for _ in range(6):
            r = c.post("/api/auth/password", json={"role": "employer", "username": u, "password": A.demo_pw(u), "captcha_token": "bad-" + "x" * 30}, headers=h)
            self.assertEqual(r.status_code, 400)
        self.assertEqual(pwpost(c, h, "employer", u, A.demo_pw(u)).status_code, 200)      # account was not locked by CAPTCHA failures

    def test_each_captcha_works_once(self):
        c, h = session(); u = "acme.hr"; cap = solve(c)
        body = {"role": "employer", "username": u, "password": "wrong-pass", **cap}
        self.assertEqual(c.post("/api/auth/password", json=body, headers=h).status_code, 401)     # captcha passed, password wrong
        self.assertEqual(c.post("/api/auth/password", json=body, headers=h).status_code, 400)     # same token again: refused

    def test_junk_tokens_never_reach_hcaptcha(self):
        c, h = session(); u = "acme.hr"; VERIFY_CALLS.clear()
        for tok in (None, 123, "", "short", "x" * 30000, ["ok-" + "1" * 30], {"a": 1}):
            r = c.post("/api/auth/password", json={"role": "employer", "username": u, "password": "x", "captcha_token": tok}, headers=h)
            self.assertEqual(r.status_code, 400)
        self.assertEqual(VERIFY_CALLS, [])

    def test_old_style_answers_are_not_accepted(self):
        c, h = session(); u = "acme.hr"
        r = c.post("/api/auth/password", json={"role": "employer", "username": u, "password": A.demo_pw(u), "captcha_id": "abc", "captcha": "ABCDE"}, headers=h)
        self.assertEqual(r.status_code, 400)

    def test_config_endpoint_sends_only_the_public_sitekey(self):
        j = A.app.test_client().get("/api/captcha").get_json()
        self.assertTrue(j["enabled"]); self.assertEqual(j["sitekey"], A.HCAPTCHA_SITEKEY)
        self.assertNotIn("test-secret", str(j))
        self.assertNotIn("test-secret", A.app.test_client().get("/api/me").get_data(as_text=True))

    def test_server_without_a_secret_reports_it_and_lets_nobody_in(self):
        old = A.HCAPTCHA_SECRET; A.HCAPTCHA_SECRET = ""
        try:
            self.assertEqual(A.app.test_client().get("/api/captcha").status_code, 503)
        finally: A.HCAPTCHA_SECRET = old

    def test_csp_allows_hcaptcha_and_nothing_inline(self):
        csp = A.app.test_client().get("/").headers["Content-Security-Policy"]
        for d in ("script-src", "frame-src", "style-src", "connect-src"): self.assertIn("https://*.hcaptcha.com", csp.split(d)[1].split(";")[0])
        self.assertNotIn("unsafe-eval", csp); self.assertNotIn("unsafe-inline", csp.split("script-src")[1].split(";")[0])      # scripts stay strict; only styles need inline for hCaptcha's frame

class TestHook(unittest.TestCase):
    def test_test_pass_tokens_only_work_in_test_mode(self):
        self.assertTrue(REAL_VERIFY_("test-pass-" + "a" * 30))
        A.TESTING, old = False, A.HCAPTCHA_SECRET; A.HCAPTCHA_SECRET = ""      # no secret: fails before any network call
        try: self.assertFalse(REAL_VERIFY_("test-pass-" + "a" * 30))      # real use: no shortcut
        finally: A.TESTING, A.HCAPTCHA_SECRET = True, old

class CaptchaHardening(Base):
    def post(self, c, h, tok): return c.post("/api/auth/password", json={"role": "employer", "username": "acme.hr", "password": "wrong-pass", "captcha_token": tok}, headers=h)
    def test_replayed_token_never_reaches_hcaptcha_twice(self):
        c, h = session(); tok = "ok-" + "r" * 30; VERIFY_CALLS.clear()
        self.assertEqual(self.post(c, h, tok).status_code, 401)
        for _ in range(3): self.assertEqual(self.post(c, h, tok).status_code, 400)
        self.assertEqual(len(VERIFY_CALLS), 1)
    def test_odd_characters_in_a_token_are_refused_outright(self):
        c, h = session(); VERIFY_CALLS.clear()
        for t in ("ok-" + "a b" * 10, "ok-" + "a\n" * 20, "ok-<script>" + "a" * 20, "ok-" + "é" * 30): self.assertEqual(self.post(c, h, t).status_code, 400)
        self.assertEqual(VERIFY_CALLS, [])
    def test_many_failed_checks_pause_that_ip(self):
        c, h = session(); VERIFY_CALLS.clear()
        for i in range(A.CAP_FAIL_MAX): self.assertEqual(self.post(c, h, f"bad-{i:030d}").status_code, 400)
        n = len(VERIFY_CALLS); r = self.post(c, h, "ok-" + "z" * 30)
        self.assertEqual(r.status_code, 429); self.assertEqual(len(VERIFY_CALLS), n)         # paused: not even a good token is checked
        A.DB.ctr.clear(); self.assertEqual(self.post(c, h, "ok-" + "y" * 30).status_code, 401)   # window over: works again
    def test_forgot_is_paused_too(self):
        c, h = session()
        for i in range(A.CAP_FAIL_MAX): c.post("/api/auth/forgot", json={"role": "student", "username": "x", "captcha_token": f"bad-{i:030d}"}, headers=h)
        self.assertEqual(c.post("/api/auth/forgot", json={"role": "student", "username": "x", **solve(c)}, headers=h).status_code, 429)

class HcaptchaVerify(unittest.TestCase):
    """The real verify function, with the network call replaced by a local fake."""
    def setUp(self):
        import urllib.request, json as _j
        self.real_urlopen, self.seen = urllib.request.urlopen, {}
        self._j = _j; self.urllib = urllib.request; self.old = A.HCAPTCHA_SECRET; A.HCAPTCHA_SECRET = "sekret"
    def tearDown(self): self.urllib.urlopen = self.real_urlopen; A.HCAPTCHA_SECRET = self.old
    def fake(self, reply=None, raises=None):
        import io
        seen = self.seen
        def f(req, timeout=None, context=None):
            seen["url"], seen["body"], seen["timeout"] = req.full_url, req.data.decode(), timeout
            if raises: raise raises
            return io.BytesIO(reply if isinstance(reply, bytes) else self._j.dumps(reply).encode())
        self.urllib.urlopen = f
    def real(self, tok, ip="1.2.3.4"): return REAL_VERIFY(tok, ip)
    def test_sends_secret_token_sitekey_and_ip_to_hcaptcha(self):
        from urllib.parse import parse_qs
        self.fake({"success": True}); self.assertTrue(self.real("tok-123"))
        self.assertEqual(self.seen["url"], "https://api.hcaptcha.com/siteverify")
        q = {k: v[0] for k, v in parse_qs(self.seen["body"]).items()}
        self.assertEqual(q, {"secret": "sekret", "response": "tok-123", "sitekey": A.HCAPTCHA_SITEKEY, "remoteip": "1.2.3.4"}); self.assertLessEqual(self.seen["timeout"], 10)
    def test_hostname_pinning_and_freshness(self):
        import datetime as dt
        now = lambda d=0: (dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=d)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        self.fake({"success": True, "challenge_ts": now(5), "hostname": "navs.example"}); self.assertTrue(self.real("t"))
        self.fake({"success": True, "challenge_ts": now(900), "hostname": "navs.example"}); self.assertFalse(self.real("t"))      # too old
        self.fake({"success": True, "challenge_ts": "garbage"}); self.assertFalse(self.real("t"))
        old = A.HCAPTCHA_HOSTS; A.HCAPTCHA_HOSTS = {"navs.example"}
        try:
            self.fake({"success": True, "challenge_ts": now(5), "hostname": "navs.example"}); self.assertTrue(self.real("t"))
            self.fake({"success": True, "challenge_ts": now(5), "hostname": "evil.example"}); self.assertFalse(self.real("t"))   # solved on someone else's site
            self.fake({"success": True, "challenge_ts": now(5)}); self.assertFalse(self.real("t"))
        finally: A.HCAPTCHA_HOSTS = old
    def test_refusal_network_error_garbage_and_missing_secret_all_fail_closed(self):
        self.fake({"success": False, "error-codes": ["invalid-input-response"]}); self.assertFalse(self.real("t"))
        self.fake(raises=OSError("down")); self.assertFalse(self.real("t"))
        self.fake(b"<html>502</html>"); self.assertFalse(self.real("t"))
        self.fake([1, 2]); self.assertFalse(self.real("t"))
        self.fake({"success": "true"}); self.assertFalse(self.real("t"))           # only a real boolean true counts
        self.seen.clear(); self.fake({"success": True}); A.HCAPTCHA_SECRET = ""; self.assertFalse(self.real("t")); self.assertNotIn("url", self.seen)
REAL_VERIFY = REAL_VERIFY_

class Reset(Base):
    def forgot(self, c, h, role, user, text=False):
        return c.post("/api/auth/forgot", json={"role": role, "username": user, **solve(c, text)}, headers=h)
    def reset(self, c, h, code, pw, totp=None):
        return c.post("/api/auth/reset", json={"code": code, "new_password": pw, "totp": totp}, headers=h)

    def test_student_can_reset_and_old_password_stops_working(self):
        u = A._demo_accounts()["student"]; c0, h0, _ = login("student", u)                # an existing session
        c, h = session(); d = self.forgot(c, h, "student", u).get_json()
        self.assertTrue(d["ok"]); self.assertFalse(d["needs_totp"])
        self.assertEqual(self.reset(c, h, d["demo_otp"], "short").status_code, 400)         # weak password, code not used up
        self.assertEqual(self.reset(c, h, "000000", "Fresh-Start-Pass-42").status_code, 400)
        self.assertEqual(self.reset(c, h, d["demo_otp"], "Fresh-Start-Pass-42").status_code, 200)
        self.assertIsNone(c0.get("/api/me").get_json()["role"])                              # other sessions were ended
        c2, h2 = session()
        self.assertEqual(pwpost(c2, h2, "student", u, A.demo_pw(u)).status_code, 401)
        self.assertEqual(pwpost(c2, h2, "student", u, "Fresh-Start-Pass-42").status_code, 200)

    def test_unknown_account_gets_the_same_reply(self):
        c, h = session(); real = self.forgot(c, h, "student", A._demo_accounts()["student"]).get_json()
        c2, h2 = session(); fake = self.forgot(c2, h2, "student", "nobody-here").get_json()
        self.assertEqual(sorted(real), sorted(fake)); self.assertEqual(real["message"], fake["message"])
        self.assertEqual(self.reset(c2, h2, fake["demo_otp"], "Fresh-Start-Pass-42").status_code, 400)   # the fake code opens nothing

    def test_role_mismatch_gets_the_same_reply_and_no_reset(self):
        c, h = session(); u = A._demo_accounts()["student"]
        d = self.forgot(c, h, "employer", u).get_json(); self.assertTrue(d["ok"])
        self.assertEqual(self.reset(c, h, d["demo_otp"], "Fresh-Start-Pass-42").status_code, 400)

    def test_forgot_needs_a_captcha(self):
        c, h = session()
        self.assertEqual(c.post("/api/auth/forgot", json={"role": "student", "username": "x"}, headers=h).status_code, 400)

    def test_five_wrong_codes_end_the_request(self):
        c, h = session(); self.forgot(c, h, "student", A._demo_accounts()["student"])
        for _ in range(4): self.assertEqual(self.reset(c, h, "000000", "Fresh-Start-Pass-42").status_code, 400)
        r = self.reset(c, h, "000000", "Fresh-Start-Pass-42"); self.assertEqual(r.status_code, 401); self.assertTrue(r.get_json()["restart"])

    def test_aicte_reset_needs_the_authenticator_code_too(self):
        u = "aicte.officer"; c, h = session(); d = self.forgot(c, h, "aicte", u).get_json(); self.assertTrue(d["needs_totp"])
        self.assertEqual(self.reset(c, h, d["demo_otp"], "Fresh-Start-Pass-42").status_code, 400)          # one code is not enough
        c, h = session(); d = self.forgot(c, h, "aicte", u).get_json()
        self.assertEqual(self.reset(c, h, d["demo_otp"], "Fresh-Start-Pass-42", d["demo_totp"]).status_code, 200)

    def test_reset_requests_are_limited_per_account(self):
        u = A._demo_accounts()["student"]
        for _ in range(3): c, h = session(); self.assertEqual(self.forgot(c, h, "student", u).status_code, 200)
        c, h = session(); d = self.forgot(c, h, "student", u).get_json()                                   # 4th in an hour: same reply, but the code is a dud
        self.assertEqual(self.reset(c, h, d["demo_otp"], "Fresh-Start-Pass-42").status_code, 400)

    def test_reset_also_clears_a_lockout(self):
        u = "globex.hr"
        for _ in range(5): c, h = session(); pwpost(c, h, "employer", u, "bad-password")
        with A.app.test_request_context(environ_base={"REMOTE_ADDR": "127.0.0.1"}): self.assertTrue(A.locked(u))
        c, h = session(); d = self.forgot(c, h, "employer", u).get_json(); self.assertEqual(self.reset(c, h, d["demo_otp"], "Fresh-Start-Pass-42").status_code, 200)
        with A.app.test_request_context(environ_base={"REMOTE_ADDR": "127.0.0.1"}): self.assertFalse(A.locked(u))

class Security(Base):
    def test_post_without_csrf_token_is_blocked(self):
        c, h = session()
        self.assertEqual(c.post("/api/auth/password", json={}).status_code, 403)

    def test_cross_site_origin_is_blocked(self):
        c, h = session()
        r = c.post("/api/auth/cancel", headers={**h, "Origin": "https://evil.example"})
        self.assertEqual(r.status_code, 403)

    def test_role_boundaries(self):
        c, h, _ = login("student")
        for url in ("/api/aicte/overview", "/api/aicte/audit", "/api/institution/overview"):
            self.assertEqual(c.get(url).status_code, 403, url)
        ce, he, _ = login("employer")
        self.assertEqual(ce.get("/api/student/profile").status_code, 403)

    def test_session_is_bound_to_the_browser(self):
        c, h, _ = login("student")
        self.assertEqual(c.get("/api/me", headers={"User-Agent": "Mozilla/5.0 Firefox/120.0"}).get_json()["role"], None)

    def test_idle_timeout_ends_the_session(self):
        c, h, _ = login("aicte", "aicte.officer")
        for r in A.SES.values():
            if r["user"] == "aicte.officer": r["t"] -= A.POLICY["aicte"]["idle"] + 5
        r = c.get("/api/aicte/overview"); self.assertEqual(r.status_code, 401); self.assertTrue(r.get_json()["expired"])

    def test_logout_revokes_the_session_on_the_server(self):
        c, h, _ = login("student")
        old = c.get_cookie(A.app.config["SESSION_COOKIE_NAME"]).value
        c.post("/api/logout", headers=h)
        c2 = A.app.test_client(); c2.set_cookie(A.app.config["SESSION_COOKIE_NAME"], old)
        self.assertIsNone(c2.get("/api/me").get_json()["role"])

    def test_headers(self):
        r = A.app.test_client().get("/")
        csp = r.headers["Content-Security-Policy"]
        self.assertNotIn("unsafe-inline", csp.split("script-src")[1].split(";")[0]); self.assertNotIn("unsafe-eval", csp)      # scripts stay strict; only styles need inline for hCaptcha's frame
        self.assertEqual(r.headers["X-Frame-Options"], "DENY")
        self.assertNotIn("<script>", r.get_data(as_text=True).replace('<script src', ''))

    def test_aicte_network_allowlist(self):
        import ipaddress
        old = list(A.ALLOW); A.ALLOW[:] = [ipaddress.ip_network("203.0.113.0/24")]
        try:
            c, h = session(); u = "aicte.officer"
            r = pwpost(c, h, "aicte", u, A.demo_pw(u))
            self.assertEqual(r.status_code, 403)
        finally: A.ALLOW[:] = old

class StepUp(Base):
    def test_institution_review_needs_a_fresh_code(self):
        c, h, u = login("institution")
        rows = c.get("/api/institution/overview").get_json()["students"]
        row = next(r for r in rows if r["status"] != "VERIFIED")
        for s in A.SES.values():
            if s["user"] == u: s["mfa"] -= A.STEPUP_TTL + 5
        body = {"cert_id": row["cert_id"], "decision": "clarify", "note": "Asking the student to confirm."}
        r = c.post("/api/institution/review", json=body, headers=h)
        self.assertEqual((r.status_code, r.get_json()["step_up"]), (428, "otp"))
        code = c.post("/api/stepup/send", headers=h).get_json()["demo_otp"]
        self.assertEqual(c.post("/api/stepup/verify", json={"code": "111111"}, headers=h).status_code, 400)
        self.assertEqual(c.post("/api/stepup/verify", json={"code": code}, headers=h).status_code, 200)
        self.assertEqual(c.post("/api/institution/review", json=body, headers=h).status_code, 200)

    def test_aicte_resolve_needs_authenticator_code_and_totp_is_single_use(self):
        c, h, u = login("aicte", "aicte.officer")
        for s in A.SES.values():
            if s["user"] == u: s["mfa"] -= A.STEPUP_TTL + 5
        r = c.post("/api/aicte/resolve", json={"cert_id": "x", "outcome": "cleared", "note": "long enough note"}, headers=h)
        self.assertEqual((r.status_code, r.get_json()["step_up"]), (428, "totp"))
        A.TOTP_LAST.pop(u, None); cur = A.totp_at(A.totp_secret(u), int(time.time() // 30)) 
        self.assertEqual(c.post("/api/stepup/verify", json={"code": cur}, headers=h).status_code, 200)
        self.assertEqual(c.post("/api/stepup/verify", json={"code": cur}, headers=h).status_code, 400)   # replay

    def test_totp_matches_rfc6238_vector(self):
        import base64
        sec = base64.b32encode(b"12345678901234567890").decode()
        self.assertEqual(A.totp_at(sec, 59 // 30)[-6:], "287082")

class Account(Base):
    def test_password_change_ends_other_sessions_and_old_password_stops_working(self):
        u = "globex.hr"; A.unlock(u)
        c1, h1, _ = login("employer", u); c2, h2, _ = login("employer", u)
        for s in A.SES.values():
            if s["user"] == u: s["mfa"] = time.time()
        r = c1.post("/api/account/password", json={"current": A.demo_pw(u), "new": "short"}, headers=h1); self.assertEqual(r.status_code, 400)
        r = c1.post("/api/account/password", json={"current": A.demo_pw(u), "new": "Correct-Horse-Battery-9"}, headers=h1)
        self.assertEqual(r.status_code, 200); self.assertGreaterEqual(r.get_json()["ended"], 1)
        self.assertIsNone(c2.get("/api/me").get_json()["role"])
        c, h = session()
        self.assertEqual(pwpost(c, h, "employer", u, A.demo_pw(u)).status_code, 401)
        self.assertEqual(pwpost(c, h, "employer", u, "Correct-Horse-Battery-9").status_code, 200)

    def test_security_page_lists_sessions(self):
        c, h, _ = login("institution")
        d = c.get("/api/account/security").get_json()
        self.assertTrue(any(s["current"] for s in d["sessions"])); self.assertEqual(d["stepup"], "otp")

class Data(Base):
    def test_audit_chain_is_intact_then_detects_tampering(self):
        c, h, _ = login("aicte", "aicte.officer")
        self.assertTrue(c.get("/api/aicte/audit").get_json()["chain_ok"])
        A.DB.c["audit"][3]["detail"] = "edited"
        self.assertFalse(c.get("/api/aicte/audit").get_json()["chain_ok"])

    def test_public_endpoints_leak_no_personal_data(self):
        j = A.app.test_client().get("/api/public/overview").get_json()
        txt = str(j); self.assertNotIn("@", txt); self.assertNotIn("900000", txt)
        self.assertEqual(j["totals"]["institutions"], 60)

    def test_public_verify_hides_marks_and_flags(self):
        cid = A.DB.find("students")[0]["cert_id"]; j = A.app.test_client().get("/api/verify/" + cid).get_json()
        for k in ("cgpa", "roll", "issues", "face"): self.assertNotIn(k, j)

    def test_institution_cannot_touch_another_college(self):
        c, h, _ = login("institution")
        other = next(s for s in A.DB.find("students") if s["inst"] != "1-D0001")
        r = c.post("/api/institution/review", json={"cert_id": other["cert_id"], "decision": "clarify", "note": "trying another college"}, headers=h)
        self.assertIn(r.status_code, (404, 428))

    def test_csv_with_aadhaar_column_is_rejected(self):
        import io
        c, h, _ = login("institution")
        for s in A.SES.values():
            if s["role"] == "institution": s["mfa"] = time.time()
        f = io.BytesIO(b"apaar_id,name,dob,roll_no,aadhaar_number\n900000000001,A B,01-01-2000,1,123\n")
        r = c.post("/api/institution/upload", data={"file": (f, "a.csv")}, headers=h)
        self.assertEqual(r.status_code, 400); self.assertIn("Aadhaar", r.get_json()["error"])

class NationalRegister(Base):
    def test_register_is_big_and_has_many_flagged_institutions(self):
        c, h, _ = login("aicte", "aicte.officer"); j = c.get("/api/aicte/overview").get_json(); t = j["totals"]
        self.assertGreaterEqual(t["institutions"], 2500); self.assertEqual(t["live"], 60)
        self.assertGreater(t["flagged_institutions"], 70); self.assertEqual(len(j["top"]), 5)
        self.assertNotIn("institutions", j)                                   # the big list is paged, never sent whole to the dashboard

    def test_institution_list_is_paged_and_filterable(self):
        c, h, _ = login("aicte", "aicte.officer")
        j = c.get("/api/aicte/institutions?page=0&per=10").get_json()
        self.assertEqual(len(j["rows"]), 10); self.assertGreaterEqual(j["all"], 2500); self.assertGreater(j["pages"], 100)
        f = c.get("/api/aicte/institutions?result=flag&per=500").get_json(); self.assertGreater(f["total"], 70); self.assertTrue(all(i["flags"] for i in f["rows"]))
        s = c.get("/api/aicte/institutions?source=live&per=100").get_json(); self.assertEqual(s["total"], 60); self.assertTrue(all(not i["sim"] for i in s["rows"]))
        q = c.get("/api/aicte/institutions?q=1-D0001").get_json(); self.assertEqual(q["total"], 1)
        self.assertEqual(c.get("/api/aicte/institutions?page=abc").status_code, 400)
        self.assertLessEqual(len(c.get("/api/aicte/institutions?per=99999").get_json()["rows"]), 3000)   # page size is capped
        self.assertEqual(c.get("/api/aicte/institutions?page=9999&per=10").get_json()["page"], c.get("/api/aicte/institutions?per=10").get_json()["pages"] - 1)

    def test_only_aicte_can_read_the_register(self):
        c, h, _ = login("institution")
        self.assertEqual(c.get("/api/aicte/institutions").status_code, 403)
        self.assertEqual(A.app.test_client().get("/api/aicte/institutions").status_code, 401)

    def test_numbers_are_stable_between_runs(self):
        self.assertEqual(A.make_national(), A.NAT); self.assertEqual(len({i["code"] for i in A.NAT}), len(A.NAT))
        for i in A.NAT: self.assertEqual(i["VERIFIED"] + i["REVIEW"] + i["FLAGGED"], i["sample"]); self.assertGreaterEqual(i["VERIFIED"], 0)

    def test_health_check_and_brand(self):
        self.assertEqual(A.app.test_client().get("/healthz").get_json()["ok"], True)
        html = A.app.test_client().get("/").get_data(as_text=True); self.assertIn("NAVS", html); self.assertNotIn("Satyapan", html)

class MongoStore(unittest.TestCase):
    """The MongoDB code path, exercised against an in-memory MongoDB look-alike (pip install mongomock)."""
    def test_mongo_store_round_trip_and_seed_is_kept(self):
        try: import mongomock
        except ImportError: self.skipTest("mongomock not installed")
        from unittest import mock
        with mock.patch("pymongo.MongoClient", mongomock.MongoClient):
            db = A.Mongo("mongodb://localhost/test"); self.assertEqual(db.kind, "MongoDB")
            db.reset("x", [dict(a=1), dict(a=2)]); self.assertEqual([d["a"] for d in db.find("x")], [1, 2]); self.assertEqual(db.last("x")["a"], 2); self.assertEqual(db.count("x"), 2)
            db.add("x", dict(a=3)); self.assertEqual(db.find("x", {"a": 3}), [dict(a=3)]); self.assertNotIn("_id", db.find("x")[0])
            old = A.DB
            try:
                A.DB = db; A.seed(); db.add("reviews", dict(cert_id="KEEP", decision="dismiss", note="n", by="b", ts="t"))
                n = db.count("students"); A.seed()                                    # second start: data (and reviews) must survive
                self.assertEqual(db.count("students"), n); self.assertEqual(db.count("reviews"), 1); self.assertEqual(db.count("institutions"), 60)
                A.seed.__globals__["os"].environ["RESEED"] = "1"
                try: A.seed()
                finally: del A.seed.__globals__["os"].environ["RESEED"]
                self.assertEqual(db.count("students"), n)
            finally: A.DB = old
    def test_bad_uri_falls_back_to_memory_without_leaking_it(self):
        import io, contextlib
        os.environ["MONGO_URI"] = "mongodb://user:secretpw@127.0.0.1:1/x?serverSelectionTimeoutMS=300"
        try:
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf): st = A.open_store()
        finally: del os.environ["MONGO_URI"]
        self.assertIsInstance(st, A.Mem); self.assertNotIn("secretpw", buf.getvalue())

if __name__ == "__main__":
    unittest.main()
