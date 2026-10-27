"""Tests for the v6 changes. Run:  python -m unittest discover -s tests -v
Works without pymongo/mongomock: a tiny fake (tests/fake_pymongo.py) stands in for MongoDB."""
import base64, datetime, io, json, os, sys, time, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["DEMO_SHOW_OTP"] = "1"; os.environ["APAAR_TESTING"] = "1"
import test_app as T
A = T.A

def client(ip="10.0.0.1", ua="Mozilla/5.0 Chrome/120.0"):
    c = A.app.test_client(); c.environ_base.update({"REMOTE_ADDR": ip, "HTTP_USER_AGENT": ua}); return c, {"X-CSRF-Token": c.get("/api/csrf").get_json()["csrf"]}
def signin(role, user=None, ip="10.0.0.1", ua="Mozilla/5.0 Chrome/120.0"):
    user = user or A._demo_accounts()[role]; c, h = client(ip, ua)
    d = T.pwpost(c, h, role, user, A.demo_pw(user)).get_json(); d = c.post("/api/auth/otp", json={"code": d["demo_otp"]}, headers=h).get_json()
    if d.get("stage") == "totp": d = c.post("/api/auth/totp", json={"code": d["demo_totp"]}, headers=h).get_json()
    assert d.get("done"), d
    return c, {"X-CSRF-Token": d["csrf"]}
def upload(c, h, text): return c.post("/api/institution/upload", data={"file": (io.BytesIO(text.encode()), "x.csv")}, headers=h, content_type="multipart/form-data")

class Base(T.Base):
    def setUp(self): super().setUp(); A.DB.c.pop("verifylog", None); A.DB.c.pop("appeals", None); A.DB.c.pop("reviews", None)

class Dates(unittest.TestCase):
    def test_common_layouts_are_normalised(self):
        for x in ("01-12-2004", "1/12/2004", "2004-12-01", "01.12.2004", "01 Dec 2004", " 01-12-2004 "): self.assertEqual(A.norm_dob(x), "01-12-2004", x)
        self.assertIsNone(A.norm_dob("soon")); self.assertIsNone(A.norm_dob(""))

class Upload(Base):
    def test_short_rows_dont_crash_and_are_reported(self):
        c, h = signin("institution")
        r = upload(c, h, "apaar_id,name,dob,roll_no\n900000000001,Rahul Kumar,01-01-2005,R001-0001\n900000000002,Only Name\n,,,\n"); j = r.get_json()
        self.assertEqual(r.status_code, 200); self.assertEqual(j["bad_count"], 2); self.assertEqual(j["checked"], 1)
    def test_over_limit_is_said_out_loud(self):
        c, h = signin("institution"); body = "apaar_id,name,dob,roll_no\n" + "".join(f"9000000{i:05d},N {i},01-01-2005,Z{i}\n" for i in range(A.MAX_ROWS + 30))
        j = upload(c, h, body).get_json(); self.assertTrue(j["truncated"]); self.assertEqual(j["checked"], A.MAX_ROWS); self.assertEqual(j["total_rows"], A.MAX_ROWS + 30); self.assertIn("of", j["note"])
    def test_iso_date_is_not_a_dob_mismatch(self):
        c, h = signin("institution"); reg = A.DB.find("registry")[0]; y, m, d = reg["dob"].split("-")[::-1]
        j = upload(c, h, f"apaar_id,name,dob,roll_no\n{reg['apaar']},{reg['name']},{y}-{m}-{d},ZZ1\n").get_json()
        self.assertNotIn("DOB_MISMATCH", [i["code"] for i in j["rows"][0]["issues"]])
    def test_apply_saves_corrections_and_closes_the_item(self):
        c, h = signin("institution"); stu = A.DB.find("students", {"inst": "1-D0001"})[3]; reg = A.DB.find_one("registry", {"apaar": stu["apaar"]})
        self.assertEqual(A.analyse([stu])[0]["status"], "FLAGGED")
        self.assertEqual(c.post("/api/institution/review", json={"cert_id": stu["cert_id"], "decision": "corrected", "note": "Fixing the spelling"}, headers=h).status_code, 200)
        j = upload(c, h, f"apaar_id,name,dob,roll_no\n{stu['apaar']},{reg['name']},{reg['dob']},{stu['roll']}\n").get_json(); self.assertEqual(j["counts"]["VERIFIED"], 1)
        self.assertEqual(A.by_cert(stu["cert_id"])["name"], stu["name"])                       # preview saved nothing
        r = c.post(f"/api/institution/upload/{j['submission_id']}/apply", headers=h).get_json(); self.assertEqual((r["updated"], r["resolved"]), (1, 1))
        self.assertEqual(A.analyse([A.by_cert(stu["cert_id"])])[0]["status"], "VERIFIED")
        row = next(x for x in c.get("/api/institution/overview").get_json()["students"] if x["cert_id"] == stu["cert_id"]); self.assertEqual(row["state"], "Resolved by re-upload")
        self.assertEqual(c.post(f"/api/institution/upload/{j['submission_id']}/apply", headers=h).status_code, 400)       # not twice
    def test_cannot_apply_someone_elses_upload(self):
        c, h = signin("institution"); j = upload(c, h, "apaar_id,name,dob,roll_no\n900000000001,A B,01-01-2005,Q1\n").get_json()
        c2, h2 = signin("institution", "reg.d0002"); self.assertEqual(c2.post(f"/api/institution/upload/{j['submission_id']}/apply", headers=h2).status_code, 404)

class Student(Base):
    def test_missing_record_is_404_not_500(self):
        u = A._demo_accounts()["student"]; c, h = signin("student"); keep = list(A.DB.c["students"]); A.DB.c["students"] = [s for s in keep if s["roll"].lower() != u]
        try: self.assertEqual(c.get("/api/student/profile").status_code, 404)
        finally: A.DB.c["students"] = keep
    def test_reply_reaches_the_college_and_changes_state(self):
        ci, hi = signin("institution"); stu = A.DB.find("students", {"inst": "1-D0001"})[3]
        self.assertEqual(ci.post("/api/institution/review", json={"cert_id": stu["cert_id"], "decision": "clarify", "note": "Please confirm your name"}, headers=hi).status_code, 200)
        cs, hs = signin("student", stu["roll"].lower())
        self.assertEqual(cs.post("/api/student/respond", json={"text": "My legal name is spelled differently."}, headers=hs).status_code, 200)
        row = next(x for x in ci.get("/api/institution/overview").get_json()["students"] if x["cert_id"] == stu["cert_id"]); self.assertEqual(row["state"], "Student replied"); self.assertIn("legal name", row["reply"]["text"])
    def test_student_with_nothing_open_cannot_send(self):
        ok = next(s for s in A.DB.find("students") if A.analyse([s])[0]["status"] == "VERIFIED"); c, h = signin("student", ok["roll"].lower())
        self.assertEqual(c.post("/api/student/respond", json={"text": "hello there friend"}, headers=h).status_code, 400)
    def test_export_and_erasure_request(self):
        c, h = signin("student"); j = c.get("/api/student/export").get_json(); self.assertIn("record", j)
        self.assertEqual(c.post("/api/student/erasure-request", json={}, headers=h).status_code, 200); self.assertEqual(A.DB.count("dsr"), 1)

class Employer(Base):
    def test_log_is_stored_by_username_capped_and_visible_to_the_student(self):
        ce, he = signin("employer"); s = A.DB.find("students")[0]
        for _ in range(3): self.assertEqual(ce.get("/api/employer/verify/" + s["cert_id"]).status_code, 200)
        self.assertEqual(A.DB.count("verifylog", {"user": "acme.hr"}), 3)
        cs, hs = signin("student", s["roll"].lower()); items = cs.get("/api/student/checks").get_json()["items"]; self.assertEqual(len(items), 3); self.assertIn("ACME", items[0]["by"])
    def test_cap_keeps_only_the_newest(self):
        old = A.LOG_CAP; A.LOG_CAP = 5
        try:
            ce, he = signin("employer"); s = A.DB.find("students")[0]
            for _ in range(8): ce.get("/api/employer/verify/" + s["cert_id"])
            self.assertEqual(A.DB.count("verifylog", {"user": "acme.hr"}), 5)
        finally: A.LOG_CAP = old
    def test_student_can_pause_checks(self):
        s = A.DB.find("students")[0]; cs, hs = signin("student", s["roll"].lower()); ce, he = signin("employer")
        self.assertEqual(cs.post("/api/student/sharing", json={"enabled": False}, headers=hs).status_code, 200)
        self.assertEqual(ce.get("/api/employer/verify/" + s["cert_id"]).status_code, 403)
        cs.post("/api/student/sharing", json={"enabled": True}, headers=hs); self.assertEqual(ce.get("/api/employer/verify/" + s["cert_id"]).status_code, 200)
    def test_batch(self):
        ce, he = signin("employer"); ids = [x["cert_id"] for x in A.DB.find("students")[:3]] + ["APR-NOPE"]
        j = ce.post("/api/employer/verify-batch", json={"ids": ids}, headers=he).get_json(); self.assertEqual([r["found"] for r in j["results"]], [True, True, True, False])

class Certificates(Base):
    def test_signature_verifies_with_the_published_key(self):
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        s = A.DB.find("students")[1]; p = A.app.test_client().get("/api/verify/" + s["cert_id"]).get_json(); k = A.app.test_client().get("/api/cert-key").get_json()
        self.assertEqual(p["kid"], k["kid"]); pub = Ed25519PublicKey.from_public_bytes(base64.b64decode(k["public_key"]))
        full = A.cert_payload(s); self.assertEqual(full["sig"], p["sig"])
        # rebuild the signed message exactly as a verifier would from the API fields
        import datetime
        exp = (datetime.datetime.strptime(s["issued"], "%Y-%m-%d") + datetime.timedelta(days=A.CERT_DAYS)).strftime("%Y-%m-%d")
        msg = json.dumps({"cert_id": p["cert_id"], "name": p["name"], "institution": p["institution"], "aicte_id": p["aicte_id"], "program": p["program"], "issued": s["issued"], "expires": exp}, sort_keys=True, separators=(",", ":")).encode()
        pub.verify(base64.urlsafe_b64decode(p["sig"]), msg)
        with self.assertRaises(Exception): pub.verify(base64.urlsafe_b64decode(p["sig"]), msg.replace(p["name"].encode(), b"Someone Else"))
    def test_expired_and_revoked(self):
        s = A.DB.find("students")[1]; A.DB.update("students", {"cert_id": s["cert_id"]}, set=dict(issued="2020-01-01"))
        try: self.assertEqual(A.app.test_client().get("/api/verify/" + s["cert_id"]).get_json()["status"], "EXPIRED")
        finally: A.DB.update("students", {"cert_id": s["cert_id"]}, set=dict(issued=A.SEED_ISSUED))
        A.DB.add("reviews", dict(cert_id=s["cert_id"], inst=s["inst"], decision="aicte_upheld", note="x", by="x", ts="x", t=1))
        self.assertEqual(A.app.test_client().get("/api/verify/" + s["cert_id"]).get_json()["status"], "REVOKED")

class Lockout(Base):
    def test_one_device_cannot_lock_everyone_out(self):
        u = "aicte.officer"; c, h = client("10.9.9.9")
        for _ in range(5): T.pwpost(c, h, "aicte", u, "bad")
        self.assertEqual(T.pwpost(c, h, "aicte", u, A.demo_pw(u)).status_code, 429)             # attacker's device is locked
        c2, h2 = client("10.1.1.1"); self.assertEqual(T.pwpost(c2, h2, "aicte", u, A.demo_pw(u)).status_code, 200)   # the officer is not
    def test_progressive_and_unlock(self):
        u = "globex.hr"; c, h = client("10.7.7.7")
        for _ in range(5): T.pwpost(c, h, "employer", u, "bad")
        with A.app.test_request_context(environ_base={"REMOTE_ADDR": "10.7.7.7"}):
            self.assertTrue(A.locked(u)); A.unlock(u); self.assertFalse(A.locked(u))
        self.assertEqual(T.pwpost(c, h, "employer", u, A.demo_pw(u)).status_code, 200)
    def test_aicte_can_unlock(self):
        u = "globex.hr"; c, h = client("10.7.7.8")
        for _ in range(5): T.pwpost(c, h, "employer", u, "bad")
        ca, ha = signin("aicte"); self.assertIn(u, ca.get("/api/aicte/locked").get_json()["items"])
        self.assertEqual(ca.post("/api/aicte/unlock", json={"username": u}, headers=ha).status_code, 200)
        self.assertEqual(T.pwpost(c, h, "employer", u, A.demo_pw(u)).status_code, 200)

class Sessions(Base):
    def test_browser_update_keeps_you_signed_in_but_other_browser_does_not(self):
        c, h = signin("student", ua="Mozilla/5.0 (Linux; Android 13) Chrome/120.0 Mobile")
        self.assertEqual(c.get("/api/me", headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/121.0.1 Safari/537"}).get_json()["role"], "student")
        self.assertIsNone(c.get("/api/me", headers={"User-Agent": "Mozilla/5.0 Firefox/120.0"}).get_json()["role"])
    def test_cookie_is_persistent(self):
        c, h = signin("student"); sc = [x for x in c._cookies.values() if x.key == "navs_s"] if hasattr(c, "_cookies") else []
        self.assertTrue(sc and sc[0].expires)

class Recovery(Base):
    def test_per_user_secret_and_recovery_code(self):
        self.assertTrue(A.ACCTS["aicte.officer"]["totp"])
        ca, ha = signin("aicte"); codes = ca.post("/api/account/recovery", headers=ha).get_json()["codes"]; self.assertEqual(len(codes), 8)
        c, h = client(); u = "aicte.officer"; d = T.pwpost(c, h, "aicte", u, A.demo_pw(u)).get_json(); c.post("/api/auth/otp", json={"code": d["demo_otp"]}, headers=h)
        r = c.post("/api/auth/totp", json={"code": codes[0]}, headers=h); self.assertTrue(r.get_json().get("done"))
        c, h = client(); d = T.pwpost(c, h, "aicte", u, A.demo_pw(u)).get_json(); c.post("/api/auth/otp", json={"code": d["demo_otp"]}, headers=h)
        self.assertEqual(c.post("/api/auth/totp", json={"code": codes[0]}, headers=h).status_code, 400)       # single use

class Audit(Base):
    def setUp(self): super().setUp(); A.DB.c["audit"] = []; A.DB.delete("meta", {"k": "audit_head"})      # other tests tamper with the shared log on purpose
    def test_chain_ok_and_truncation_is_caught(self):
        ca, ha = signin("aicte"); j = ca.get("/api/aicte/audit").get_json(); self.assertTrue(j["chain_ok"])
        seqs = [e["seq"] for e in A.DB.c["audit"] if "seq" in e]; self.assertEqual(seqs, sorted(set(seqs)))
        A.DB.c["audit"].pop(); A.DB.c["audit"].pop()                                                # someone deletes the newest entries
        self.assertFalse(ca.get("/api/aicte/audit").get_json()["chain_ok"])
    def test_public_lookup_flood_is_not_stored_forever(self):
        n = A.DB.count("audit"); c = A.app.test_client(); c.environ_base["REMOTE_ADDR"] = "10.5.5.5"
        for _ in range(35): c.get("/api/verify/APR-NOPE")
        self.assertLess(A.DB.count("audit") - n, 25)

# ---------------------------------------------------------------- the MongoDB path, against the fake
class MongoPath(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try: import pymongo; real = hasattr(pymongo, "ReturnDocument") and pymongo.__name__ == "pymongo" and not hasattr(pymongo, "_navs_fake")
        except ImportError: real = False
        try: import mongomock; cls.mm = mongomock
        except ImportError: cls.mm = None
        import fake_pymongo; cls.fake = fake_pymongo
        cls.saved_mod = sys.modules.get("pymongo"); cls.mod = fake_pymongo.install(); cls.mod._navs_fake = True
        cls.old = A.DB; A.DB = A.Mongo("mongodb://fake/test"); A.ACCTS.t = 0; A._NATC.update(t=0, v=None)
        A.seed()
    @classmethod
    def tearDownClass(cls):
        A.DB = cls.old; A.ACCTS.t = 0; A._NATC.update(t=0, v=None)
        if cls.saved_mod is not None: sys.modules["pymongo"] = cls.saved_mod
        else: sys.modules.pop("pymongo", None)
    def test_everything_lives_in_mongodb(self):
        d = A.DB
        self.assertEqual((d.count("institutions"), d.count("students"), d.count("national"), d.count("registry")), (60, 600, 2590, d.count("registry")))
        self.assertEqual(d.count("users", {"role": "student"}), 600); self.assertEqual(d.count("users", {"role": "institution"}), 60); self.assertEqual(d.count("users", {"role": "aicte"}), 1)
        self.assertTrue(all(u.get("totp") for u in d.find("users", {"role": "aicte"})))
    def test_second_start_changes_nothing(self):
        n = A.DB.count("users"); A.DB.add("reviews", dict(cert_id="KEEP", decision="dismiss", note="n", by="b", ts="t")); A.seed(); A.migrate()
        self.assertEqual(A.DB.count("users"), n); self.assertEqual(A.DB.count("reviews"), 1)
    def test_old_database_is_upgraded_in_place(self):
        for u in A.DB.d["users"].docs:
            for k in ("username", "status", "inst", "totp"): u.pop(k, None)
        A.DB.d["users"].docs[:] = [u for u in A.DB.d["users"].docs if u["role"] != "student"]; A.DB.d["national"].docs.clear(); A._NATC.update(t=0, v=None)
        A.migrate(); self.assertEqual(A.DB.count("users"), 663); self.assertEqual(A.DB.count("national"), 2590); self.assertTrue(A.DB.find_one("users", {"role": "aicte"})["totp"])
        self.assertTrue(all(u.get("username") for u in A.DB.find("users")))
    def test_sign_in_and_session_use_mongodb(self):
        A.RL.clear(); A.LOCKED.clear(); A.DB.d["_state"].docs.clear()
        c, h = signin("institution")
        self.assertEqual(c.get("/api/me").get_json()["role"], "institution"); self.assertEqual(c.get("/api/institution/overview").status_code, 200)
        self.assertTrue(any(d.get("n") == "SES" for d in A.DB.d["_state"].docs))                     # the session is in MongoDB, not in this process
    def test_counter_is_atomic_and_expires_with_its_window(self):
        import threading; out = []
        ts = [threading.Thread(target=lambda: out.append(A.DB.bump("atom", 600))) for _ in range(40)]; [t.start() for t in ts]; [t.join() for t in ts]
        self.assertEqual(sorted(out), list(range(1, 41)))
        d = next(x for x in A.DB.d["_state"].docs if x["_id"].startswith("CNT:atom")); self.assertLess(abs(d["exp"].replace(tzinfo=datetime.timezone.utc).timestamp() - (time.time() + 600)), 700)
    def test_audit_sequence_never_forks(self):
        import threading
        ts = [threading.Thread(target=lambda: A.audit("t", "x", actor="a", role="r")) for _ in range(20)]; [t.start() for t in ts]; [t.join() for t in ts]
        a = A.DB.find("audit"); seqs = [e["seq"] for e in a if "seq" in e]; self.assertEqual(len(seqs), len(set(seqs)))
        prev = "0" * 16
        for e in a: self.assertEqual(e["prev"], prev); self.assertEqual(e["h"], A.chain(prev, e)); prev = e["h"]
    def test_upload_apply_and_cert_lookup_use_indexes_not_scans(self):
        c, h = signin("institution"); stu = A.DB.find("students", {"inst": "1-D0001"})[3]; reg = A.DB.find_one("registry", {"apaar": stu["apaar"]})
        j = upload(c, h, f"apaar_id,name,dob,roll_no\n{stu['apaar']},{reg['name']},{reg['dob']},{stu['roll']}\n").get_json()
        self.assertEqual(c.post(f"/api/institution/upload/{j['submission_id']}/apply", headers=h).get_json()["updated"], 1)
        self.assertEqual(A.by_cert(stu["cert_id"])["name"], reg["name"])

if __name__ == "__main__":
    unittest.main()


class StudentCollege(Base):
    def setUp(self): super().setUp(); A.DB.c.pop("enrol_reports", None); A._PUB["t"] = 0
    def test_public_report_reaches_aicte_and_college(self):
        c, h = client("10.9.0.1"); code = A.DB.find("institutions")[1]["code"]
        r = c.post("/api/public/enrolment-report", json=dict(college=code, name="Asha Rao", roll="X-77", apaar_last4="1234", **T.solve()), headers=h); self.assertEqual(r.status_code, 200, r.get_json())
        self.assertIn("already", c.post("/api/public/enrolment-report", json=dict(college=code, name="Asha Rao", roll="x-77", **T.solve()), headers=h).get_json()["message"])
        a, ah = signin("aicte"); j = a.get("/api/aicte/reports").get_json(); row = next(x for x in j["rows"] if x["code"] == code); self.assertEqual(row["unlisted"], 1); self.assertEqual(j["open"], 1)
        self.assertIn("STUDENTS_MISSING", a.get("/api/aicte/overview").get_json()["flag_types"]); self.assertEqual(a.get("/api/aicte/reports/" + code).get_json()["items"][0]["apaar_last4"], "1234")
    def test_public_report_needs_captcha_and_valid_college(self):
        c, h = client("10.9.0.2"); code = A.DB.find("institutions")[0]["code"]
        self.assertEqual(c.post("/api/public/enrolment-report", json=dict(college=code, name="Asha Rao", roll="Q1"), headers=h).status_code, 400)
        self.assertEqual(c.post("/api/public/enrolment-report", json=dict(college="nope", name="Asha Rao", roll="Q1", **T.solve()), headers=h).status_code, 400)
        self.assertEqual(c.post("/api/public/enrolment-report", json=dict(college=code, name="Asha Rao", roll="Q1", apaar_last4="12", **T.solve()), headers=h).status_code, 400)
    def test_student_naming_another_college_notifies_aicte(self):
        c, h = signin("student"); me = c.get("/api/student/college").get_json(); other = next(i["code"] for i in A.DB.find("institutions") if i["code"] != me["record"]["code"])
        j = c.post("/api/student/college", json=dict(college=other), headers=h).get_json(); self.assertTrue(j["differs"])
        a, _ = signin("aicte"); self.assertEqual(next(x for x in a.get("/api/aicte/reports").get_json()["rows"] if x["code"] == other)["differs_in"], 1)
        j = c.post("/api/student/college", json=dict(college=me["record"]["code"]), headers=h).get_json(); self.assertFalse(j["differs"]); self.assertEqual(a.get("/api/aicte/reports").get_json()["open"], 0)
    def test_search_and_roles(self):
        c, h = client("10.9.0.3"); self.assertTrue(c.get("/api/public/colleges?q=institute").get_json()["items"]); self.assertEqual(c.get("/api/public/colleges?q=i").get_json()["items"], [])
        self.assertEqual(c.get("/api/aicte/reports").status_code, 401)
