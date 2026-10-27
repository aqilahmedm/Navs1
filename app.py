"""NAVS (National Academic Verification System), an APAAR verification platform PROTOTYPE (v5). Every person, college, ID and certificate here is FICTIONAL.
Run: pip install -r requirements.txt && python app.py  ->  http://127.0.0.1:5000
Sign-in = username + password, then a one-time code (and, for the AICTE console, an authenticator-app code).
Optional MongoDB: set MONGO_URI; otherwise an in-memory store is used (demo data is re-created on every start)."""
import datetime, base64, csv, functools, hashlib, hmac, io, ipaddress, json, os, random, re, secrets, struct, threading, time
from difflib import SequenceMatcher
import ssl, urllib.parse, urllib.request
from urllib.parse import urlparse
from flask import Flask, Response, g, jsonify, request, session, send_from_directory, has_request_context
from werkzeug.security import check_password_hash, generate_password_hash

BASE = os.path.dirname(os.path.abspath(__file__))
SECURE = bool(os.environ.get("APAAR_HTTPS") or os.environ.get("APAAR_PROXY"))
app = Flask(__name__, static_folder=None)
if os.environ.get("APAAR_PROXY"):      # behind Caddy / nginx / Cloudflare that terminates HTTPS
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
def _secret():
    p = os.path.join(BASE, ".secret_key")
    if os.environ.get("SECRET_KEY"): return os.environ["SECRET_KEY"]
    if not os.path.exists(p):
        try:
            with open(p, "w") as f: f.write(secrets.token_hex(32))
        except OSError: raise RuntimeError("Set the SECRET_KEY environment variable (this host's disk is read-only).")
        try: os.chmod(p, 0o600)
        except OSError: pass
    return open(p).read().strip()
SECRET_B = _secret().encode()
def subkey(purpose): return hmac.new(SECRET_B, b"navs-key|" + purpose.encode(), hashlib.sha256).digest()      # one master secret, a separate key per job
app.secret_key = subkey("cookie").hex()
try:
    import certifi; _SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except Exception: _SSL_CTX = ssl.create_default_context()
app.config.update(SESSION_COOKIE_NAME="__Host-navs" if SECURE else "navs_s", SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax", PERMANENT_SESSION_LIFETIME=datetime.timedelta(hours=8),
                  SESSION_COOKIE_SECURE=SECURE, MAX_CONTENT_LENGTH=1_000_000)

# ------------------------------------------------------------ storage (Mongo or memory)
import datetime
class Dup(Exception): pass                                                   # unique-index clash (same for Mongo and memory)
def _match(d, q):
    for k, v in (q or {}).items():
        x = d.get(k)
        if isinstance(v, dict):
            for op, w in v.items():
                if (op == "$in" and x not in w) or (op == "$lt" and not (x is not None and x < w)) or (op == "$lte" and not (x is not None and x <= w)) or (op == "$ne" and x == w): return False
        elif x != v: return False
    return True
class Mem:
    kind, persistent = "In-memory (demo)", False
    def __init__(s): s.c, s.lock, s.ctr, s.uniq = {}, threading.RLock(), {}, {}
    def add(s, n, d):
        with s.lock:
            u = s.uniq.get(n)
            if u and u in d and any(x.get(u) == d[u] for x in s.c.get(n, [])): raise Dup(u)
            s.c.setdefault(n, []).append(dict(d))
    def reset(s, n, docs):
        with s.lock: s.c[n] = [dict(d) for d in docs]
    def add_many(s, n, docs):
        for d in docs:
            try: s.add(n, d)
            except Dup: pass
    def find(s, n, q=None, sort=None, limit=0, skip=0):
        with s.lock:
            r = [dict(d) for d in s.c.get(n, []) if _match(d, q)]
        if sort and sort[0] == "_id": r = r[::-1] if sort[1] < 0 else r
        elif sort: r.sort(key=lambda d: d.get(sort[0], 0), reverse=sort[1] < 0)
        r = r[skip:]; return r[:limit] if limit else r
    def find_one(s, n, q=None): r = s.find(n, q, limit=1); return r[0] if r else None
    def last(s, n):
        with s.lock: return dict(s.c[n][-1]) if s.c.get(n) else None
    def count(s, n, q=None):
        with s.lock: return sum(1 for d in s.c.get(n, []) if _match(d, q))
    def update(s, n, q, set=None, upsert=False):
        with s.lock:
            for d in s.c.get(n, []):
                if _match(d, q): d.update(set or {}); return 1
            if upsert: s.c.setdefault(n, []).append({**{k: v for k, v in (q or {}).items() if not isinstance(v, dict)}, **(set or {})}); return 1
        return 0
    def delete(s, n, q):
        with s.lock: before = len(s.c.get(n, [])); s.c[n] = [d for d in s.c.get(n, []) if not _match(d, q)]; return before - len(s.c[n])
    def index(s, n, field, unique=False):
        if unique: s.uniq[n] = field
    def bump(s, key, win):
        now = time.time(); wid = int(now // win)
        with s.lock:
            if len(s.ctr) > 5000: s.ctr = {k: v for k, v in s.ctr.items() if v[1] > now}
            c = s.ctr.setdefault((key, wid), [0, (wid + 1) * win + 60]); c[0] += 1; return c[0]
    def peek(s, key, win):
        with s.lock: c = s.ctr.get((key, int(time.time() // win))); return c[0] if c else 0
class Mongo:
    persistent = True
    def __init__(s, uri):
        import pymongo; from pymongo import MongoClient
        kw = dict(serverSelectionTimeoutMS=8000, connectTimeoutMS=8000, retryWrites=True, maxPoolSize=20)
        try:                                   # Atlas (mongodb+srv) needs an up-to-date CA bundle on some hosts
            import certifi
            if uri.startswith("mongodb+srv") or "mongodb.net" in uri: kw["tlsCAFile"] = certifi.where()
        except ImportError: pass
        s.pm, s.d = pymongo, MongoClient(uri, **kw)[os.environ.get("MONGO_DB", "navs")]
        s.d.command("ping"); s.kind = "MongoDB"
    def add(s, n, d):
        try: s.d[n].insert_one(dict(d))
        except s.pm.errors.DuplicateKeyError: raise Dup(n)
    def reset(s, n, docs):
        s.d[n].delete_many({})                                              # not drop(): keeps the indexes
        if docs: s.d[n].insert_many([dict(d) for d in docs])
    def add_many(s, n, docs):
        if not docs: return
        try: s.d[n].insert_many([dict(d) for d in docs], ordered=False)
        except s.pm.errors.BulkWriteError: pass                              # duplicates (another process seeded at the same time) are fine
    def find(s, n, q=None, sort=None, limit=0, skip=0):
        c = s.d[n].find(q or {}, {"_id": 0}).sort(*(sort or ("_id", 1)))
        if skip: c = c.skip(skip)
        if limit: c = c.limit(limit)
        return list(c)
    def find_one(s, n, q=None): r = s.find(n, q, limit=1); return r[0] if r else None
    def last(s, n): return next(iter(s.d[n].find({}, {"_id": 0}).sort("_id", -1).limit(1)), None)
    def count(s, n, q=None): return s.d[n].count_documents(q or {})
    def update(s, n, q, set=None, upsert=False): return s.d[n].update_one(q, {"$set": set}, upsert=upsert).matched_count if set else 0
    def delete(s, n, q): return s.d[n].delete_many(q).deleted_count
    def index(s, n, field, unique=False):
        try:
            if unique and n == "audit": s.d[n].create_index(field, unique=True, partialFilterExpression={field: {"$exists": True}})
            else: s.d[n].create_index(field, unique=unique)
        except Exception as e: print("index", n, field, type(e).__name__)
    def peek(s, key, win):
        """Current value of a bump() counter, without counting this call."""
        try: d = s.d["_state"].find_one({"_id": f"CNT:{key}:{int(time.time() // win)}"}); return d["v"] if d else 0
        except Exception: return 0
    def bump(s, key, win):
        """Atomic fixed-window counter: every parallel request gets its own number, and the record expires with its window."""
        wid, i = int(time.time() // win), "CNT:" + key
        for _ in range(3):
            try:
                r = s.d["_state"].find_one_and_update({"_id": f"{i}:{wid}"}, {"$inc": {"v": 1}, "$setOnInsert": {"n": "CNT", "exp": datetime.datetime.utcfromtimestamp((wid + 1) * win + 60)}}, upsert=True, return_document=s.pm.ReturnDocument.AFTER)
                return r["v"]
            except s.pm.errors.DuplicateKeyError: continue
        return 1
def open_store():
    uri = (os.environ.get("MONGO_URI") or "").strip()
    if uri:
        last = None
        for k in range(3):
            try: return Mongo(uri)
            except Exception as e:
                last = e
                if k < 2: time.sleep(1.5)
        print("MongoDB unavailable:", type(last).__name__, str(last)[:200].replace(uri, "<MONGO_URI>"))
        if os.environ.get("MONGO_REQUIRED") == "1": raise SystemExit("MONGO_REQUIRED=1 and MongoDB is unreachable. Not starting with a memory-only store (everyone would be signed out on every restart).")
        print("Using memory instead: sign-ins and data will be lost on restart.")
    return Mem()
DB = open_store()

# ---- shared auth state. On serverless hosts (Vercel) every request may run in a different process, so sessions, one-time codes,
# lockouts, rate limits and human-check replay records must live in MongoDB, not in process memory. Without MongoDB this is a plain dict.
import copy
_PMAPS = []
class PMap:
    """dict-like. Records are read once per request and written back (changed fields only) when the request ends."""
    def __init__(s, name, ttl):
        s.name, s.ttl, s.mem, s.tl = name, ttl, {}, threading.local(); _PMAPS.append(s)
    def shared(s): return bool(getattr(DB, "persistent", False)) and hasattr(DB, "d")
    def _col(s): return DB.d["_state"]
    def _id(s, k): return s.name + ":" + ("|".join(map(str, k)) if isinstance(k, tuple) else str(k))
    def _exp(s): return datetime.datetime.utcnow() + datetime.timedelta(seconds=s.ttl)
    def _cache(s):
        if not has_request_context(): return None
        c = getattr(s.tl, "c", None)
        if c is None: c = s.tl.c = {}
        return c
    def get(s, k, d=None):
        if not s.shared(): return s.mem.get(k, d)
        c, i = s._cache(), s._id(k)
        if c is not None and i in c: return c[i][1]
        try: doc = s._col().find_one({"_id": i})
        except Exception:
            time.sleep(.25); doc = s._col().find_one({"_id": i})                # one retry: a brief Atlas hiccup must not sign people out
        if not doc: return d
        if c is not None: c[i] = (k, doc["v"], copy.deepcopy(doc["v"]))
        return doc["v"]
    def __getitem__(s, k):
        v = s.get(k, KeyError)
        if v is KeyError: raise KeyError(k)
        return v
    def __contains__(s, k): return s.get(k, KeyError) is not KeyError
    def __setitem__(s, k, v):
        if not s.shared(): s.mem[k] = v; return
        i, c = s._id(k), s._cache()
        s._col().update_one({"_id": i}, {"$set": {"n": s.name, "v": v, "exp": s._exp()}}, upsert=True)
        if c is not None: c[i] = (k, v, copy.deepcopy(v))
    def pop(s, k, d=None):
        if not s.shared(): return s.mem.pop(k, d)
        i, c = s._id(k), s._cache()
        if c is not None: c.pop(i, None)
        doc = s._col().find_one_and_delete({"_id": i})
        return doc["v"] if doc else d
    def items(s):
        if not s.shared(): return list(s.mem.items())
        return [(d["_id"][len(s.name) + 1:], d["v"]) for d in s._col().find({"n": s.name}).limit(5000)]
    def setdefault(s, k, d=None):
        if not s.shared(): return s.mem.setdefault(k, d)
        v = s.get(k, KeyError)
        if v is KeyError: s[k] = d; v = s.get(k, d)
        return v
    def values(s): return [v for _, v in s.items()]
    def keys(s): return [k for k, _ in s.items()]
    def clear(s):
        s.mem.clear()
        if s.shared(): s._col().delete_many({"n": s.name})
    def __len__(s): return len(s.mem) if not s.shared() else s._col().count_documents({"n": s.name})
    def flush(s):
        c = getattr(s.tl, "c", None)
        if not c or not s.shared(): return
        for i, (k, v, snap) in list(c.items()):
            if v == snap: continue
            try:
                if isinstance(v, dict) and isinstance(snap, dict):
                    up = {"$set": {**{"v." + f: x for f, x in v.items() if f not in snap or snap[f] != x}, "exp": s._exp()}}
                    gone = {"v." + f: "" for f in snap if f not in v}
                    if gone: up["$unset"] = gone
                    s._col().update_one({"_id": i}, up)          # no upsert: a record signed out in parallel must stay gone
                else: s._col().update_one({"_id": i}, {"$set": {"n": s.name, "v": v, "exp": s._exp()}}, upsert=True)
            except Exception as e: print("state write failed:", type(e).__name__)
@app.after_request
def _pmap_flush(resp):
    for m in _PMAPS: m.flush()
    return resp
@app.teardown_request
def _pmap_clear(exc):
    for m in _PMAPS: m.tl.c = {}
if getattr(DB, "persistent", False) and hasattr(DB, "d"):
    try: DB.d["_state"].create_index("exp", expireAfterSeconds=0); DB.d["_state"].create_index("n")
    except Exception as e: print("state index:", type(e).__name__)

class Accts:
    """Accounts live in the MongoDB `users` collection. This keeps a 30-second per-process copy, so an account added, disabled or unlocked elsewhere shows up quickly."""
    def __init__(s): s.m, s.t, s.lock = {}, 0, threading.Lock()
    def _load(s):
        if s.m and time.time() - s.t < 30: return
        with s.lock:
            try:
                m = {u["username"]: dict(username=u["username"], role=u["role"], name=u["name"], ref=u["ref"], inst=u.get("inst"), email=u["ident"], phone=u["phone"],
                                         status=u.get("status", "active"), totp=u.get("totp"), recovery=u.get("recovery", [])) for u in DB.find("users") if u.get("username")}
                s.m, s.t = m, time.time()
            except Exception as e: print("accounts reload failed:", type(e).__name__); s.t = time.time() - 20
    def get(s, k, d=None): s._load(); return s.m.get(k, d)
    def __getitem__(s, k): s._load(); return s.m[k]
    def __contains__(s, k): s._load(); return k in s.m
    def items(s): s._load(); return list(s.m.items())
ACCTS = Accts()
# ------------------------------------------------------------ fictional seed data (60 colleges, 600 students)
FNM = "Aarav Vivaan Ishaan Rahul Arjun Vikram Rohit Kabir Aditya Karthik Sanjay Dev Nikhil Varun".split()
FNF = "Priya Ananya Sneha Neha Meera Diya Isha Pooja Tara Kavya Riya Anjali Nandini Sana".split()
LN = "Kumar Sharma Nair Verma Mehta Jain Reddy Iyer Singh Das Patel Menon Gupta Rao".split()
PRE = "Northfield Riverbend Kestrel Alder Quill Harbour Zenith Orchid Meridian Cobalt Juniper Saffron Lakeview Pinecrest Sunrise Granite Maple Aster Beacon Cedar".split()
KIND = ["Institute of Technology", "College of Engineering", "School of Management", "Institute of Applied Sciences", "Polytechnic"]
PLACES = [("Pune","Maharashtra"),("Nagpur","Maharashtra"),("Chennai","Tamil Nadu"),("Coimbatore","Tamil Nadu"),("Bengaluru","Karnataka"),("Mysuru","Karnataka"),
 ("Lucknow","Uttar Pradesh"),("Kanpur","Uttar Pradesh"),("Ahmedabad","Gujarat"),("Surat","Gujarat"),("Jaipur","Rajasthan"),("Hyderabad","Telangana"),
 ("Kolkata","West Bengal"),("Kochi","Kerala"),("Bhopal","Madhya Pradesh"),("Indore","Madhya Pradesh"),("Patna","Bihar"),("Bhubaneswar","Odisha"),
 ("Chandigarh","Punjab"),("Dehradun","Uttarakhand"),("Guwahati","Assam"),("Ranchi","Jharkhand"),("Raipur","Chhattisgarh"),("Visakhapatnam","Andhra Pradesh")]
COURSES = [("B.Tech","CSE"),("B.Tech","ECE"),("B.Tech","Mechanical"),("B.Tech","AI&DS")]
def make_insts():
    R, out = random.Random(7), []
    for k in range(60):
        city, state = PLACES[(k * 5) % len(PLACES)]; intake = R.choice([120, 180, 240, 300, 360, 420])
        rep = int(intake * R.uniform(1.18, 1.4)) if k % 9 == 4 else intake - R.randint(0, intake // 20)   # every 9th college reports more than its approved intake
        out.append((f"1-D{k+1:04d}", f"{PRE[k % 20]} {KIND[(k // 20 + k % 2) % 5]}", city, state, intake, rep))
    return out
INSTS = make_insts()
SEED_VERSION = "navs-5"
SEED_ISSUED = "2026-10-25"
def username_for(role, ref):
    return "reg." + ref.split("-")[1].lower() if role == "institution" else "aicte.officer" if role == "aicte" else ref.lower() + ".hr"
def new_totp(): return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")      # random per-user authenticator secret
def user_doc(role, ident, phone, name, ref, inst=None, username=None):
    d = dict(role=role, ident=ident, phone=phone, name=name, ref=ref, username=username or username_for(role, ref), inst=ref if role == "institution" else inst, status="active")
    if role == "aicte": d["totp"] = new_totp()
    return d
def seed():
    if DB.persistent and os.environ.get("RESEED") != "1":
        m = DB.find("meta", {"k": "seed"})
        if m and m[0].get("v") == SEED_VERSION and DB.count("students") and DB.count("institutions") and DB.count("users"): return migrate()    # already loaded in MongoDB
    R, stu, reg, n = random.Random(26263), [], {}, 0
    for code, nm, city, st, intake, rep in INSTS:
        for _ in range(10):
            n += 1; g = R.choice("MF"); f = R.choice(FNM if g == "M" else FNF); l = R.choice(LN)
            if n == 1: g, f, l = "M", "Rahul", "Kumar"
            c = ("MBA", "Finance") if "Management" in nm else R.choice(COURSES)
            s = dict(apaar=str(900000000000 + n), name=f"{f} {l}", dob=f"{R.randint(1,28):02d}-{R.randint(1,12):02d}-{R.randint(2004,2007)}", gender=g, program=c[0], branch=c[1],
                     year=R.choice([2023, 2024, 2025]), inst=code, roll=f"R{code[-3:]}-{n:04d}", category=R.choice(["General", "OBC", "SC", "ST", "EWS"]), cgpa=round(R.uniform(6.2, 9.4), 2),
                     phone=f"98{n:08d}", email=f"{f.lower()}.{l.lower()}{n}@demo.example", status="ACTIVE", face=(n % 5) + (5 if g == "F" else 0))
            reg[s["apaar"]] = dict(apaar=s["apaar"], name=s["name"].upper(), dob=s["dob"], inst=code); stu.append(s)
    for a in range(15, 300, 37): stu[a + 211]["apaar"] = stu[a]["apaar"]                       # same APAAR ID claimed by two colleges
    for i in range(3, 600, 41): stu[i]["name"] = stu[i]["name"].split()[0] + " X"                # clear name mismatch
    for i in range(23, 600, 61): stu[i]["name"] = stu[i]["name"].replace("a", "aa", 1)           # near-match spelling -> needs review
    for i in range(7, 600, 53): stu[i]["dob"] = "01-01-2005"                                      # DOB mismatch
    for i in range(11, 600, 97): stu[i]["apaar"] = stu[i]["apaar"][:11]                           # invalid format
    for i in range(19, 600, 89): reg.pop(stu[i]["apaar"], None)                                   # missing from registry
    stu[0].update(name="Rahul Kumar", apaar="900000000001")
    for s in stu: s["cert_id"] = "APR-" + hashlib.sha1((s["apaar"] + s["inst"] + s["roll"]).encode()).hexdigest()[:12].upper()
    inst = [dict(code=c, name=nm, city=ci, state=st, intake=i, reported=r) for c, nm, ci, st, i, r in INSTS]
    for x in stu: x.update(issued=SEED_ISSUED, share=True)
    users = [user_doc("institution", f"admin@{c.lower()}.demo.example", f"97{k:08d}", f"Registrar, {nm}", c) for k, (c, nm, *_) in enumerate(INSTS, 1)]
    users += [user_doc("aicte", "officer@aicte.demo.example", "9600000001", "AICTE Verification Officer (demo)", "AICTE"),
              user_doc("employer", "hr@acme.demo.example", "9500000001", "ACME Talent Team (demo)", "ACME"),
              user_doc("employer", "hr@globex.demo.example", "9500000002", "Globex HR (demo)", "GLOBEX")]
    users += [user_doc("student", s["email"], s["phone"], s["name"], s["apaar"], inst=s["inst"], username=s["roll"].lower()) for s in stu]
    DB.reset("students", stu); DB.reset("registry", list(reg.values())); DB.reset("institutions", inst); DB.reset("users", users)
    DB.reset("meta", [dict(k="seed", v=SEED_VERSION)]); migrate()

# ------------------------------------------------------------ simulated national register (summary rows only, no student records)
# The 60 colleges above are "live": they have student records, logins and real mismatch checks. To make the AICTE console look like a national
# register, a further block of SIMULATED institutions is generated (fixed seed, so the numbers never change between restarts or workers).
NAT_TOTAL, NAT_FLAGGED = 2650, 78          # institutions in the national register (live + simulated); simulated ones that carry a flag
PRE2 = "Vindhya Himalaya Sahyadri Kaveri Narmada Godavari Ganga Aravali Nilgiri Konark Deccan Malwa Kalinga Avadh Mithila Coastal Capital Heritage Emerald Crescent Lotus Ashoka Tagore Raman Bose Sarabhai Visvesvaraya Kalam Bhabha".split()
NAT_PREFIXES = PRE + PRE2     # captured now: the name PRE is re-used further down for pending sign-ins
NAT_PLACES = [("Mumbai","Maharashtra",5),("Pune","Maharashtra",6),("Nagpur","Maharashtra",3),("Nashik","Maharashtra",2),("Aurangabad","Maharashtra",2),("Chennai","Tamil Nadu",6),("Coimbatore","Tamil Nadu",4),("Madurai","Tamil Nadu",3),
 ("Tiruchirappalli","Tamil Nadu",3),("Salem","Tamil Nadu",2),("Bengaluru","Karnataka",6),("Mysuru","Karnataka",3),("Mangaluru","Karnataka",2),("Hubballi","Karnataka",2),("Lucknow","Uttar Pradesh",4),("Kanpur","Uttar Pradesh",3),
 ("Noida","Uttar Pradesh",4),("Varanasi","Uttar Pradesh",2),("Agra","Uttar Pradesh",2),("Ghaziabad","Uttar Pradesh",3),("Hyderabad","Telangana",6),("Warangal","Telangana",2),("Visakhapatnam","Andhra Pradesh",4),("Vijayawada","Andhra Pradesh",3),
 ("Guntur","Andhra Pradesh",2),("Tirupati","Andhra Pradesh",2),("Ahmedabad","Gujarat",4),("Surat","Gujarat",3),("Vadodara","Gujarat",3),("Rajkot","Gujarat",2),("Jaipur","Rajasthan",4),("Jodhpur","Rajasthan",2),("Kota","Rajasthan",2),
 ("Udaipur","Rajasthan",1),("Kolkata","West Bengal",4),("Durgapur","West Bengal",2),("Siliguri","West Bengal",1),("Kochi","Kerala",3),("Thiruvananthapuram","Kerala",3),("Kozhikode","Kerala",2),("Bhopal","Madhya Pradesh",3),("Indore","Madhya Pradesh",4),
 ("Gwalior","Madhya Pradesh",2),("Jabalpur","Madhya Pradesh",2),("Patna","Bihar",3),("Gaya","Bihar",1),("Muzaffarpur","Bihar",1),("Bhubaneswar","Odisha",3),("Rourkela","Odisha",1),("Cuttack","Odisha",1),("Chandigarh","Chandigarh",2),
 ("Ludhiana","Punjab",3),("Amritsar","Punjab",2),("Jalandhar","Punjab",2),("Gurugram","Haryana",3),("Faridabad","Haryana",2),("Ambala","Haryana",2),("New Delhi","Delhi",4),("Dwarka","Delhi",2),("Dehradun","Uttarakhand",3),("Haridwar","Uttarakhand",1),
 ("Guwahati","Assam",2),("Ranchi","Jharkhand",2),("Jamshedpur","Jharkhand",2),("Raipur","Chhattisgarh",2),("Bhilai","Chhattisgarh",1),("Shimla","Himachal Pradesh",1),("Solan","Himachal Pradesh",1),("Jammu","Jammu and Kashmir",1),
 ("Srinagar","Jammu and Kashmir",1),("Panaji","Goa",1),("Imphal","Manipur",1),("Shillong","Meghalaya",1),("Puducherry","Puducherry",1)]
def make_national():
    R, seen, out = random.Random(2026), {(i[1], i[2]) for i in INSTS}, []
    pre, cities, wts = NAT_PREFIXES, [(c, st) for c, st, _ in NAT_PLACES], [w for *_, w in NAT_PLACES]
    flagged = set(R.sample(range(NAT_TOTAL - len(INSTS)), NAT_FLAGGED))
    scen = [["OVER_INTAKE"], ["MISMATCHES"], ["MISMATCHES"], ["MISMATCHES"], ["DUPLICATE_APAAR", "MISMATCHES"], ["OVER_INTAKE", "MISMATCHES"], ["OVER_INTAKE", "DUPLICATE_APAAR", "MISMATCHES"]]
    for k in range(NAT_TOTAL - len(INSTS)):
        while True:
            city, state = R.choices(cities, wts)[0]; nm = f"{R.choice(pre)} {R.choice(KIND)}"
            if (nm, city) not in seen: seen.add((nm, city)); break
        intake = R.choice([60, 120, 120, 180, 240, 300, 360, 420, 480, 600]); fl = k in flagged; flags = R.choice(scen) if fl else []
        rep_ = int(intake * R.uniform(1.08, 1.45)) if "OVER_INTAKE" in flags else intake - R.randint(0, intake // 10)
        over, sample = max(rep_ - intake, 0), int(rep_ * R.uniform(.55, .95))
        bad = R.randint(1, 7) if "MISMATCHES" in flags else 0; rev = R.randint(0, 6) if fl else R.randint(0, 3)
        out.append(dict(code=f"1-N{k + 1:05d}", name=nm, city=city, state=state, intake=intake, reported=rep_, over=over, sample=sample, VERIFIED=sample - bad - rev, REVIEW=rev, FLAGGED=bad,
                        flags=flags, risk=min(100, over * 100 // intake * 2 + bad * 12 + rev * 4), dups=R.randint(1, 3) if "DUPLICATE_APAAR" in flags else 0, sim=True))
    return out
NAT = make_national()
SCHEMA = 2
def migrate():
    """Idempotent. Brings an existing MongoDB up to date without touching reviews, password changes or the audit log: indexes, account records for every
    student, per-user authenticator secrets, and the simulated national register (so the AICTE console reads it from MongoDB, not from code)."""
    for n, f, u in [("students", "cert_id", True), ("students", "roll", False), ("students", "apaar", False), ("students", "inst", False), ("registry", "apaar", True),
                    ("institutions", "code", True), ("users", "username", True), ("national", "code", True), ("national", "state", False), ("reviews", "cert_id", False), ("enrol_reports", "college", False),
                    ("pwchg", "username", False), ("audit", "seq", True), ("verifylog", "cert_id", False), ("verifylog", "user", False), ("appeals", "cert_id", False),
                    ("submissions", "inst", False), ("dsr", "cert_id", False)]:
        DB.index(n, f, u)
    users = DB.find("users"); have = {u.get("username") for u in users}
    for u in users:                                                           # accounts saved by older versions have no username / status / authenticator secret
        fix = {}
        if not u.get("username"): fix["username"] = username_for(u["role"], u["ref"])
        if "status" not in u: fix["status"] = "active"
        if u["role"] == "institution" and not u.get("inst"): fix["inst"] = u["ref"]
        if u["role"] == "aicte" and not u.get("totp"): fix["totp"] = new_totp()
        if fix: DB.update("users", {"ref": u["ref"], "role": u["role"], "ident": u["ident"]}, set=fix); have.add(fix.get("username", u.get("username")))
    stu = DB.find("students")
    DB.add_many("users", [user_doc("student", s["email"], s["phone"], s["name"], s["apaar"], inst=s["inst"], username=s["roll"].lower()) for s in stu if s["roll"].lower() not in have])
    for s in stu:
        if "issued" not in s or "share" not in s: DB.update("students", {"cert_id": s["cert_id"]}, set=dict(issued=s.get("issued", SEED_ISSUED), share=s.get("share", True)))
    if DB.count("national") != len(NAT): DB.reset("national", NAT)
    DB.index("users", "username", True)
    DB.reset("meta", [m for m in DB.find("meta") if m.get("k") != "schema"] + [dict(k="schema", v=SCHEMA)])
    ACCTS.t = 0
_NATC = dict(t=0, v=None)
def national():
    """The simulated register, read from MongoDB (cached 60 s per process)."""
    if time.time() - _NATC["t"] > 60 or _NATC["v"] is None: _NATC.update(t=time.time(), v=DB.find("national") or NAT)
    return _NATC["v"]
seed()

# ------------------------------------------------------------ mismatch engine
DATE_FMTS = ("%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y", "%Y-%m-%d", "%Y/%m/%d", "%d %b %Y", "%d %B %Y", "%d-%b-%Y", "%d %b, %Y")
def norm_dob(x):
    """Any common date layout -> DD-MM-YYYY (day first, as in India). None when it can't be read."""
    x = re.sub(r"\s+", " ", str(x or "")).strip()
    for f in DATE_FMTS:
        try: return datetime.datetime.strptime(x, f).strftime("%d-%m-%Y")
        except ValueError: pass
    return None
def sim(a, b):
    t = lambda x: " ".join(sorted(re.sub(r"[^A-Za-z ]", " ", x).upper().split()))
    return SequenceMatcher(None, t(a), t(b)).ratio()
def dupmap(stu):
    m = {}
    for s in stu: m.setdefault(s["apaar"], set()).add(s["inst"])
    return m
def check(s, reg, dm):
    out, a = [], s["apaar"]
    if not re.fullmatch(r"\d{12}", a): return [("high", "INVALID_APAAR", "APAAR ID must be exactly 12 digits")]
    if len(dm.get(a, ())) > 1: out.append(("high", "DUPLICATE_ACROSS_COLLEGES", "Same APAAR ID is claimed by " + ", ".join(sorted(dm[a]))))
    r = reg.get(a)
    if not r: return out + [("high", "NOT_IN_REGISTRY", "APAAR ID not found in the (demo) registry")]
    q = sim(s["name"], r["name"])
    if q < 1: out.append(("medium" if q >= .85 else "high", "NAME_MISMATCH", f"College: {s['name']} | Registry: {r['name'].title()} ({q:.0%})"))
    sd, rd = norm_dob(s["dob"]), norm_dob(r["dob"])
    if sd is None: out.append(("medium", "DOB_UNREADABLE", f"Date of birth \"{str(s['dob'])[:20]}\" is not a date we can read. Use DD-MM-YYYY."))
    elif sd != rd: out.append(("high", "DOB_MISMATCH", f"College: {sd} | Registry: {rd or r['dob']}"))
    if r["inst"] != s["inst"]: out.append(("medium", "REGISTRY_INSTITUTION_DIFFERS", f"Registry shows {r['inst']}"))
    return out
def verdict(iss): return "FLAGGED" if any(i[0] == "high" for i in iss) else "REVIEW" if iss else "VERIFIED"
def mask(a): return "•" * max(len(a) - 4, 0) + a[-4:]
def analyse(stu):
    aps = sorted({s["apaar"] for s in stu})
    if len(aps) > 300: regd, others = DB.find("registry"), DB.find("students")          # whole-table views read everything once
    else: regd, others = DB.find("registry", {"apaar": {"$in": aps}}), DB.find("students", {"apaar": {"$in": aps}})   # one record: two small indexed queries
    reg, dm, rows = {r["apaar"]: r for r in regd}, dupmap(others), []
    for s in stu:
        iss = check(s, reg, dm); rows.append({**{k: s[k] for k in ("name", "roll", "program", "branch", "year", "inst", "cert_id", "face")},
            "apaar": mask(s["apaar"]), "status": verdict(iss), "issues": [dict(sev=a, code=b, msg=c) for a, b, c in iss]})
    return rows
def cnt(rows): return {k: sum(r["status"] == k for r in rows) for k in ("VERIFIED", "REVIEW", "FLAGGED")}


# ------------------------------------------------------------ security: accounts, 2-step sign-in, sessions, CSRF, audit
CAPTCHA_ON = os.environ.get("CAPTCHA", "1") == "1"                    # hCaptcha human check on every sign-in and password reset
HCAPTCHA_SITEKEY = os.environ.get("HCAPTCHA_SITEKEY", "9e0af896-09e6-4b0e-b16c-0f8e4c6cd512").strip()   # public: shown to browsers
HCAPTCHA_SECRET = os.environ.get("HCAPTCHA_SECRET", "").strip()        # PRIVATE: set in the environment / Render dashboard, never in code or git
HCAPTCHA_VERIFY_URL = "https://api.hcaptcha.com/siteverify"
HCAPTCHA_HOSTS = {h.strip().lower() for h in os.environ.get("HCAPTCHA_HOSTNAMES", "").split(",") if h.strip()}   # optional: only accept tokens solved on these sites, e.g. navs.onrender.com
CAP_TOKEN_RE = re.compile(r"^[A-Za-z0-9._~+/=-]{20,20000}$")
TESTING = os.environ.get("APAAR_TESTING") == "1"                       # test runs only. NEVER set in real use.
DEMO_SHOW_OTP = os.environ.get("DEMO_SHOW_OTP", "1") == "1"        # set DEMO_SHOW_OTP=0 when a real SMS/email gateway is wired in
ROLES = {"student": "Student", "institution": "Institution", "aicte": "AICTE", "employer": "Employer"}
FACTORS = {"student": ["otp"], "employer": ["otp"], "institution": ["otp"], "aicte": ["otp", "totp"]}   # after the password
POLICY = {"student": dict(idle=1800, abs=8 * 3600), "employer": dict(idle=1800, abs=8 * 3600),
          "institution": dict(idle=900, abs=6 * 3600), "aicte": dict(idle=600, abs=4 * 3600)}              # seconds
STEPUP_TTL, STEPUP_METHOD = int(os.environ.get("APAAR_STEPUP_TTL", 600)), {"institution": "otp", "aicte": "totp"}   # seconds a confirmation stays fresh
OTPS, PRE, SES, FAILS, LOCKED, RL, TOTP_LAST, PWH = PMap("OTPS", 400), PMap("PRE", 1800), PMap("SES", 30000), PMap("FAILS", 1000), PMap("LOCKED", 8000), PMap("RL", 700), PMap("TOTP_LAST", 400), {}
AUDIT_LOCK = threading.Lock()
ALLOW = [ipaddress.ip_network(c.strip(), strict=False) for c in os.environ.get("AICTE_ALLOW_IPS", "").split(",") if c.strip()]

def now_utc(): return datetime.datetime.now(datetime.timezone.utc)
IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
def now_ist(): return datetime.datetime.now(IST).strftime("%d %b %Y %H:%M IST")        # shown to people
def hm(*parts): return hmac.new(subkey("hm:" + parts[0]), "|".join(parts).encode(), hashlib.sha256).hexdigest()
def ip(): return request.remote_addr or "?"
def ip_tag(): return hm("ip", ip())[:8]
def browser_family(ua): return "edge" if "Edg" in ua else "firefox" if "Firefox" in ua or "FxiOS" in ua else "chrome" if "Chrome" in ua or "CriOS" in ua else "safari" if "Safari" in ua else "other"
def ua_tag(): return hm("ua", browser_family(request.headers.get("User-Agent", "")))[:16]       # browser family only: updates, "desktop site" and OS tweaks don't sign people out
def utag(u): return hm("u", u.lower())[:8]
def limited(key, n, win=600):
    """Atomic fixed-window limiter: parallel requests can't undercount, and the record expires with its window."""
    return DB.bump("|".join(map(str, key)) if isinstance(key, tuple) else str(key), win) > n
def net_ok(role):
    if role != "aicte" or not ALLOW: return True
    try: a = ipaddress.ip_address(ip())
    except ValueError: return False
    return any(a in n for n in ALLOW)

# ---- hash-chained audit log. Entries get a sequence number (unique index), so two writers can't fork the chain; the newest head is also kept in `meta`,
# so cutting entries off the end is detected. Entries written by older versions (no "kv") still verify with the old key.
NOISY = {"public_verify", "rate_limited", "captcha_failed", "password_failed", "otp_failed", "totp_failed", "net_blocked", "reset_failed"}
def chain(prev, e):
    f = ("ts", "actor", "role", "ip", "action", "detail") + (("seq",) if e.get("kv") == 2 else ())
    body = json.dumps({k: e[k] for k in f}, sort_keys=True)
    return hmac.new(subkey("audit") if e.get("kv") == 2 else SECRET_B, (prev + body).encode(), hashlib.sha256).hexdigest()[:16]
def audit(action, detail="", actor=None, role=None):
    ses = getattr(g, "ses", None) if has_request_context() else None
    if action in NOISY and has_request_context() and DB.bump("auditnoise|" + action + "|" + ip_tag(), 600) > 20:      # a flood is counted, not stored
        DB.bump("auditdrop|" + action, 3600); return
    for _ in range(8):
        la = DB.last("audit"); prev = la["h"] if la else "0" * 16; seq = (la.get("seq") or DB.count("audit")) + 1 if la else 1
        e = dict(ts=now_utc().strftime("%Y-%m-%d %H:%M:%S UTC"), actor=actor or (ses["name"] if ses else "anonymous"), role=role or (ses["role"] if ses else "-"),
                 ip=ip_tag() if has_request_context() else "-", action=action, detail=str(detail)[:140], prev=prev, seq=seq, kv=2)
        e["h"] = chain(prev, e)
        try: DB.add("audit", e)
        except Dup: continue                                                 # someone else took this sequence number: re-read and try again
        if not DB.update("meta", {"k": "audit_head", "seq": {"$lt": seq}}, set=dict(seq=seq, h=e["h"])) and not DB.find_one("meta", {"k": "audit_head"}): DB.add("meta", dict(k="audit_head", seq=seq, h=e["h"]))   # only ever moves forward
        return
def posture(_=None):
    c = lambda *k: DB.count("audit", {"action": {"$in": list(k)}})
    return dict(failed_logins=c("password_failed", "otp_failed", "totp_failed"), lockouts=c("account_locked"), blocked=c("access_denied", "net_blocked", "rate_limited"),
                stepups=c("stepup_ok"), active_sessions=len(SES), allowlist=bool(ALLOW), demo_otp=DEMO_SHOW_OTP, https=SECURE, store=DB.kind, persistent=DB.persistent)

# ---- accounts (demo): username + password. Demo passwords are derived from the server secret and shown only in demo mode.
def demo_pw(u): return "Demo@" + hm("pw", u)[:8]
def hash_pw(pw):
    try: return generate_password_hash(pw)                                   # scrypt
    except Exception: return generate_password_hash(pw, method="pbkdf2:sha256:600000")
DUMMY_HASH = hash_pw("not-a-real-password")                                 # unknown users cost the same time as known ones
def pw_hash(u):
    ov = DB.find("pwchg", {"username": u})                                   # always one lookup, known user or not (no timing difference)
    if ov and u in ACCTS: return ov[-1]["h"]
    if u not in ACCTS: return DUMMY_HASH
    if u not in PWH: PWH[u] = hash_pw(demo_pw(u))
    return PWH[u]
def pw_check(u, pw):
    ok = check_password_hash(pw_hash(u), pw)
    a = ACCTS.get(u); return bool(ok and a and a.get("status", "active") == "active")
COMMON = {"password", "password123", "qwerty123456", "123456789012", "welcome12345", "iloveyou1234", "admin1234567", "letmein123456", "demo@12345678"}
def pw_problem(pw, un):
    if len(pw) < 12: return "Use at least 12 characters."
    if len(pw) > 128: return "Use at most 128 characters."
    if un.lower() in pw.lower() or pw.lower() in COMMON: return "That password is too easy to guess."
    if sum(bool(re.search(p, pw)) for p in (r"[a-z]", r"[A-Z]", r"\d", r"[^A-Za-z0-9]")) < 3: return "Mix at least three of: lower case, upper case, digits, symbols."
    return None
def locked(u): return max(LOCKED.get((u, ip_tag()), 0), LOCKED.get((u, "*"), 0)) > time.time()
def register_fail(u, kind):
    """5 wrong tries from one device lock that device out of that account (15 min, doubling on repeats, up to 2 h). 30 wrong tries from anywhere lock the account
    for everyone for 15 min; an AICTE officer or `manage.py unlock` lifts it. Counts are atomic."""
    now, t, ep = time.time(), ip_tag(), int(LOCKED.get((u, "epoch"), 0))
    audit(kind + "_failed", "u:" + utag(u), actor="anonymous", role="-")
    if DB.bump(f"fail|{u}|{ep}|{t}", 900) >= 5:
        n = DB.bump(f"lockrep|{u}|{ep}|{t}", 86400); dur = min(900 * 2 ** (n - 1), 7200)
        LOCKED[(u, t)] = now + dur; audit("account_locked", f"u:{utag(u)} {dur // 60} min (this device)", actor="anonymous", role="-")
    if DB.bump(f"failall|{u}|{ep}", 900) >= 30 and not LOCKED.get((u, "*"), 0) > now:
        LOCKED[(u, "*")] = now + 900; audit("account_locked", f"u:{utag(u)} 15 min (many devices)", actor="anonymous", role="-")
def unlock(u):
    """Lift every lock on an account and start its failure counts from zero."""
    for k, _ in LOCKED.items():
        ks = "|".join(k) if isinstance(k, tuple) else k
        if ks.split("|")[0] == u and not ks.endswith("|epoch"): LOCKED.pop(k, None)
    LOCKED[(u, "epoch")] = time.time()

# ---- one-time codes (email/SMS) and authenticator-app codes (TOTP, RFC 6238)
def mask_dest(a):
    l, _, d = a["email"].partition("@"); return (l[:1] + "•••@" + d) if d else "•••"
def deliver_otp(a, code):
    to, u, p = os.environ.get("DEMO_OTP_REDIRECT", "").strip(), os.environ.get("GMAIL_USER"), os.environ.get("GMAIL_APP_PASSWORD")
    if not (to and u and p): return                                           # demo addresses can't receive mail; set the 3 variables to test real delivery
    try:
        import smtplib; from email.message import EmailMessage
        m = EmailMessage(); m["Subject"] = "Your NAVS demo sign-in code"; m["From"] = f"NAVS (Demo) <{u}>"; m["To"] = to
        m.set_content(f"Demo project. Not from AICTE, DigiLocker or any government service.\n\nYour 6-digit code is {code}. It is valid for 5 minutes. Do not share it.\n(Test mode: intended for {mask_dest(a)}.)\n")
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as s: s.login(u, p); s.send_message(m)
    except Exception: pass
def issue_otp(key, a):
    code, salt = f"{secrets.randbelow(10**6):06d}", secrets.token_hex(8)
    OTPS[key] = dict(h=hashlib.sha256((salt + code).encode()).hexdigest(), salt=salt, t=time.time(), tries=0)
    deliver_otp(a, code); return code
def check_otp(key, code, burn=True):
    o = OTPS.get(key)
    if not o or time.time() - o["t"] > 300: return "expired"
    if hmac.compare_digest(o["h"], hashlib.sha256((o["salt"] + re.sub(r"\D", "", str(code))[:6]).encode()).hexdigest()):
        if burn: OTPS.pop(key, None)
        return "ok"
    if DB.bump("otptry|" + "|".join(map(str, key)) + "|" + o["salt"], 400) >= 5: OTPS.pop(key, None); return "locked"
    return "bad"
def totp_secret(u):
    a = ACCTS.get(u)
    if a and a.get("totp"): return a["totp"]                                 # random per-user secret stored in MongoDB
    return base64.b32encode(hmac.new(SECRET_B, b"totp|" + u.encode(), hashlib.sha256).digest()[:20]).decode().rstrip("=")   # legacy fallback
def new_recovery(u):
    """8 single-use recovery codes for a lost phone. Only their hashes are stored; the plain codes are shown once."""
    codes = [secrets.token_hex(2).upper() + "-" + secrets.token_hex(2).upper() for _ in range(8)]
    DB.update("users", {"username": u}, set=dict(recovery=[hmac.new(subkey("recovery"), c.encode(), hashlib.sha256).hexdigest() for c in codes])); ACCTS.t = 0
    return codes
def use_recovery(u, code):
    a = ACCTS.get(u); c = re.sub(r"[^A-Z0-9]", "", str(code).upper())
    if not a or len(c) != 8: return False
    h = hmac.new(subkey("recovery"), (c[:4] + "-" + c[4:]).encode(), hashlib.sha256).hexdigest(); left = list(a.get("recovery") or [])
    if h not in left: return False
    left.remove(h); DB.update("users", {"username": u}, set=dict(recovery=left)); ACCTS.t = 0; audit("recovery_code_used", "u:" + utag(u), actor="anonymous", role="aicte"); return True
def totp_at(sec, counter):
    key = base64.b32decode(sec + "=" * ((8 - len(sec) % 8) % 8)); h = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest(); o = h[-1] & 15
    return f"{(struct.unpack('>I', h[o:o + 4])[0] & 0x7fffffff) % 10**6:06d}"
def demo_totp_hint(u):
    """Demo only: the next code that will still be accepted (a code works once, so the one just used is skipped)."""
    now = int(time.time() // 30); c = max(now, TOTP_LAST.get(u, 0) + 1)
    return totp_at(totp_secret(u), c) if c <= now + 1 else None
def match_totp(u, code):
    code, now = re.sub(r"\D", "", str(code))[:6], int(time.time() // 30)
    for c in (now - 1, now, now + 1):                                          # allow 30 s clock drift either way
        if hmac.compare_digest(code, totp_at(totp_secret(u), c)) and c > TOTP_LAST.get(u, 0): return c   # a code works once
    return 0
def check_totp(u, code):
    if not re.fullmatch(r"\s*\d{3}\s?\d{3}\s*", str(code)): return use_recovery(u, code)        # not 6 digits: maybe a recovery code
    c = match_totp(u, code)
    if c: TOTP_LAST[u] = c
    return bool(c)

# ---- request guard: CSRF + origin + server-side sessions (revocable, bound to the browser)
@app.before_request
def api_guard():
    g.ses, g.sid, g.expired = None, None, False
    if not request.path.startswith("/api/"): return
    if request.method != "GET":
        if request.headers.get("Sec-Fetch-Site") == "cross-site": return jsonify(error="Blocked cross-site request."), 403
        o = request.headers.get("Origin")
        if o and urlparse(o).netloc != request.host: return jsonify(error="Blocked cross-site request."), 403
        tok = request.headers.get("X-CSRF-Token", "")
        if not session.get("csrf") or not hmac.compare_digest(tok.encode(), session["csrf"].encode()): return jsonify(error="Session check failed. Reload the page."), 403
    sid = session.get("sid")
    if sid:
        r, now = SES.get(sid), time.time()
        if r and now - r["t"] <= POLICY[r["role"]]["idle"] and now - r["t0"] <= POLICY[r["role"]]["abs"] and r["ua"] == ua_tag():
            if now - r["t"] >= 20: r["t"] = now                                  # last-seen is written at most every 20 s (fewer database writes)
            g.ses, g.sid = r, sid; session.permanent = True
        else: SES.pop(sid, None); session.pop("sid", None); g.expired = True
@app.get("/api/csrf")
def csrf(): session.setdefault("csrf", secrets.token_urlsafe(24)); return jsonify(csrf=session["csrf"])
def guard(*roles, fresh=False):
    def deco(fn):
        @functools.wraps(fn)
        def w(*a, **k):
            if not g.ses: return jsonify(error="Your session expired. Please sign in again." if g.expired else "Please sign in.", expired=True), 401
            if roles and g.ses["role"] not in roles: audit("access_denied", request.path[:60]); return jsonify(error="Your role can't do this."), 403
            if not net_ok(g.ses["role"]): audit("net_blocked", request.path[:60]); return jsonify(error="This console isn't available from your network."), 403
            if fresh and time.time() - g.ses["mfa"] > STEPUP_TTL: return jsonify(error="Please confirm it's you to continue.", step_up=STEPUP_METHOD.get(g.ses["role"], "otp")), 428
            return fn(*a, **k)
        return w
    return deco


# ---- Human check: hCaptcha. The browser shows the widget and gets a one-time token; we verify that token with hCaptcha here, using the secret (which never leaves the server).
def hcaptcha_verify(token, remoteip=""):
    """True only if hCaptcha confirms the token. Any error (no secret, network down, bad reply) counts as a failure, so a broken check never lets anyone in."""
    if TESTING and token.startswith("test-pass-"): return True      # automated tests only (APAAR_TESTING=1): lets the UI test run without reaching hCaptcha
    if not HCAPTCHA_SECRET: print("hCaptcha: HCAPTCHA_SECRET is not set, so every human check fails."); return False
    data = {"secret": HCAPTCHA_SECRET, "response": token, "sitekey": HCAPTCHA_SITEKEY}
    if remoteip and remoteip != "?": data["remoteip"] = remoteip
    try:
        req = urllib.request.Request(HCAPTCHA_VERIFY_URL, data=urllib.parse.urlencode(data).encode(), headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=6, context=_SSL_CTX) as r: j = json.loads(r.read(65536).decode("utf-8", "replace"))
    except Exception as e: print("hCaptcha: could not reach the verification service:", type(e).__name__); return False
    if not (isinstance(j, dict) and j.get("success") is True): print("hCaptcha: token refused:", j.get("error-codes") if isinstance(j, dict) else "bad reply"); return False
    if HCAPTCHA_HOSTS and str(j.get("hostname", "")).lower() not in HCAPTCHA_HOSTS: print("hCaptcha: token was solved on another site:", str(j.get("hostname"))[:60]); return False
    ts = j.get("challenge_ts")
    if ts is not None:      # a token should be fresh: hCaptcha expires them after 2 minutes, we allow a little slack
        try: age = time.time() - datetime.datetime.fromisoformat(str(ts).replace("Z", "+00:00")).timestamp()
        except ValueError: print("hCaptcha: unreadable challenge time"); return False
        if age > 180 or age < -60: print("hCaptcha: stale token"); return False
    return True
@app.get("/api/captcha")
def captcha_config():
    """Tells the page which sitekey to show. Only the public sitekey is sent."""
    if not CAPTCHA_ON: return jsonify(enabled=False)
    if not (HCAPTCHA_SITEKEY and HCAPTCHA_SECRET): return jsonify(error="The human check isn't set up on this server yet. Ask the administrator."), 503
    return jsonify(enabled=True, sitekey=HCAPTCHA_SITEKEY)
CAP_FAIL_MAX = 10                                   # failed human checks per IP per 10 minutes, then a pause (also stops us hammering hCaptcha)
def captcha_blocked(): return DB.peek("capfail|" + ip(), 600) >= CAP_FAIL_MAX
def _cap_fail(): DB.bump("capfail|" + ip(), 600); return False
def captcha_ok(b):
    """The page sends the token hCaptcha gave it. A token is used once here (and hCaptcha accepts it once too), has to look right, and has to verify."""
    if not CAPTCHA_ON: return True
    tok = b.get("captcha_token")
    if not isinstance(tok, str) or not CAP_TOKEN_RE.match(tok): return _cap_fail()
    if DB.bump("capseen|" + hashlib.sha256(tok.encode()).hexdigest(), 600) > 1: return _cap_fail()      # replay: never ask hCaptcha twice. Atomic (shared in MongoDB), so parallel requests and workers can't both use it
    return True if hcaptcha_verify(tok, ip()) else _cap_fail()
CAP_FAIL = ("The human check didn't pass. Please try it again.", 400)

# ---- sign-in: step 1 password, step 2 one-time code, step 3 (AICTE only) authenticator code
def _pre():
    pid = session.get("pre"); p = PRE.get(pid) if pid else None
    if p and time.time() - p["t"] < 600 and p["ua"] == ua_tag(): return pid, p
    PRE.pop(pid, None); session.pop("pre", None); return None, None
def _finish(pid, p):
    a, now = ACCTS[p["user"]], time.time(); sid = secrets.token_urlsafe(32); PRE.pop(pid, None)
    SES[sid] = dict(user=a["username"], role=a["role"], name=a["name"], ref=a["ref"], inst=a["inst"], ua=ua_tag(), ua_raw=request.headers.get("User-Agent", "")[:200], t0=now, t=now, mfa=now)
    session.clear(); session.permanent = True; session["sid"] = sid; session["csrf"] = secrets.token_urlsafe(24); g.ses = SES[sid]
    audit("login", a["role"] + " u:" + utag(a["username"])); return jsonify(done=True, role=a["role"], name=a["name"], csrf=session["csrf"])
@app.post("/api/auth/password")
def auth_password():
    b = request.get_json(silent=True) or {}; role = str(b.get("role")); un = str(b.get("username", "")).strip().lower()[:60]; pw = str(b.get("password", ""))[:200]
    if role not in ROLES: return jsonify(error="Choose a role."), 400
    if limited(("pw", ip()), 25): audit("rate_limited", "password", actor="anonymous"); return jsonify(error="Too many attempts. Wait a few minutes."), 429
    if not net_ok(role): audit("net_blocked", "login " + role, actor="anonymous", role=role); return jsonify(error="This console isn't available from your network."), 403
    if captcha_blocked(): audit("rate_limited", "captcha login", actor="anonymous"); return jsonify(error="Too many failed human checks. Wait a few minutes.", captcha=True), 429
    if not captcha_ok(b): audit("captcha_failed", "login", actor="anonymous", role=role); return jsonify(error=CAP_FAIL[0], captcha=True), 400
    if locked(un): return jsonify(error="Too many attempts. Try again in 15 minutes."), 429
    ok = pw_check(un, pw); a = ACCTS.get(un)
    if not (ok and a and a["role"] == role): register_fail(un, "password"); return jsonify(error="Incorrect username or password."), 401
    pid = secrets.token_urlsafe(24); PRE[pid] = dict(user=un, role=role, stage="otp", t=time.time(), ua=ua_tag())
    session.pop("sid", None); session["pre"] = pid; code = issue_otp(("login", pid), a)
    audit("password_ok", role + " u:" + utag(un), actor="anonymous", role=role)
    out = dict(stage="otp", masked=mask_dest(a), expires_in=300, factors=FACTORS[role], name=a["name"])
    if DEMO_SHOW_OTP: out["demo_otp"] = code
    return jsonify(out)
@app.post("/api/auth/resend")
def auth_resend():
    pid, p = _pre()
    if not p or p["stage"] != "otp": return jsonify(error="Your sign-in timed out. Start again.", restart=True), 401
    if limited(("resend", pid), 3): return jsonify(error="Too many code requests. Start again in a few minutes."), 429
    code = issue_otp(("login", pid), ACCTS[p["user"]]); out = dict(stage="otp", masked=mask_dest(ACCTS[p["user"]]), expires_in=300)
    if DEMO_SHOW_OTP: out["demo_otp"] = code
    return jsonify(out)
@app.post("/api/auth/otp")
def auth_otp():
    pid, p = _pre()
    if not p or p["stage"] != "otp": return jsonify(error="Your sign-in timed out. Start again.", restart=True), 401
    r = check_otp(("login", pid), (request.get_json(silent=True) or {}).get("code", ""))
    if r == "expired": return jsonify(error="That code has expired. Send a new one."), 400
    if r in ("bad", "locked"):
        register_fail(p["user"], "otp")
        if r == "locked": PRE.pop(pid, None); session.pop("pre", None); return jsonify(error="Too many wrong codes. Start again.", restart=True), 401
        return jsonify(error="Incorrect code."), 400
    if "totp" in FACTORS[p["role"]]:
        p["stage"] = "totp"; out = dict(stage="totp")
        if DEMO_SHOW_OTP: out["demo_totp"] = demo_totp_hint(p["user"])
        return jsonify(out)
    return _finish(pid, p)
@app.post("/api/auth/totp")
def auth_totp():
    pid, p = _pre()
    if not p or p["stage"] != "totp": return jsonify(error="Your sign-in timed out. Start again.", restart=True), 401
    if check_totp(p["user"], (request.get_json(silent=True) or {}).get("code", "")): return _finish(pid, p)
    p["tries"] = p.get("tries", 0) + 1; register_fail(p["user"], "totp")
    if p["tries"] >= 5: PRE.pop(pid, None); session.pop("pre", None); return jsonify(error="Too many wrong codes. Start again.", restart=True), 401
    return jsonify(error="Incorrect or already-used code."), 400

# ---- forgot password: one-time code to the registered contact (AICTE also needs the authenticator code). Same reply whether or not the account exists.
RST = PMap("RST", 1000)
@app.post("/api/auth/forgot")
def auth_forgot():
    b = request.get_json(silent=True) or {}; role = str(b.get("role")); un = str(b.get("username", "")).strip().lower()[:60]
    if role not in ROLES: return jsonify(error="Choose a role."), 400
    if limited(("forgot", ip()), 8): audit("rate_limited", "forgot", actor="anonymous"); return jsonify(error="Too many attempts. Wait a few minutes."), 429
    if captcha_blocked(): audit("rate_limited", "captcha forgot", actor="anonymous"); return jsonify(error="Too many failed human checks. Wait a few minutes.", captcha=True), 429
    if not captcha_ok(b): audit("captcha_failed", "forgot", actor="anonymous", role=role); return jsonify(error=CAP_FAIL[0], captcha=True), 400
    a, totp = ACCTS.get(un), "totp" in FACTORS[role]
    out = dict(ok=True, needs_totp=totp, expires_in=300, message="If that account exists, we've sent a one-time code to its registered contact.")
    rid = secrets.token_urlsafe(24); real = bool(a and a["role"] == role) and not limited(("forgot_u", un), 3, 3600)
    RST[rid] = dict(user=un if real else None, role=role, t=time.time(), ua=ua_tag(), tries=0); session["rst"] = rid
    code = issue_otp(("reset", rid), a) if real else f"{secrets.randbelow(10**6):06d}"
    if real: audit("reset_requested", role + " u:" + utag(un), actor="anonymous", role=role)
    if DEMO_SHOW_OTP:                                                         # demo shows a code even for unknown accounts, so the reply can't be used to find accounts
        out["demo_otp"] = code
        if totp: out["demo_totp"] = (demo_totp_hint(un) if real else f"{secrets.randbelow(10**6):06d}")
    return jsonify(out)
@app.post("/api/auth/reset")
def auth_reset():
    b = request.get_json(silent=True) or {}; rid = session.get("rst"); rec = RST.get(rid) if rid else None
    if not rec or time.time() - rec["t"] > 600 or rec["ua"] != ua_tag(): RST.pop(rid, None); session.pop("rst", None); return jsonify(error="Your reset request timed out. Start again.", restart=True), 401
    new, u = str(b.get("new_password", ""))[:200], rec["user"]
    pr = pw_problem(new, u or "")
    if pr: return jsonify(error=pr), 400                                      # policy problems say nothing about the account, so they don't use up a try
    ok = bool(u) and check_otp(("reset", rid), b.get("code", ""), burn=False) == "ok"
    tc = (match_totp(u, b.get("totp", "")) or (1 if use_recovery(u, b.get("totp", "")) else 0)) if ok and "totp" in FACTORS[rec["role"]] else 1      # authenticator code, or one recovery code
    if not (ok and tc):
        rec["tries"] += 1; audit("reset_failed", "u:" + utag(u or "-"), actor="anonymous", role=rec["role"])
        if rec["tries"] >= 5: RST.pop(rid, None); OTPS.pop(("reset", rid), None); session.pop("rst", None); return jsonify(error="Too many wrong codes. Start again.", restart=True), 401
        return jsonify(error="That code isn't valid or has expired."), 400
    OTPS.pop(("reset", rid), None)
    if "totp" in FACTORS[rec["role"]] and tc > 1: TOTP_LAST[u] = tc
    DB.add("pwchg", dict(username=u, h=hash_pw(new), ts=now_utc().strftime("%Y-%m-%d %H:%M:%S UTC")))
    n = 0
    for sid in [k for k, x in SES.items() if x["user"] == u]: SES.pop(sid, None); n += 1
    unlock(u); RST.pop(rid, None); session.pop("rst", None); audit("password_reset", f"{rec['role']} u:{utag(u)} {n} session(s) ended", actor="anonymous", role=rec["role"])
    return jsonify(ok=True)
@app.post("/api/auth/cancel")
def auth_cancel(): PRE.pop(session.get("pre"), None); session.pop("pre", None); return jsonify(ok=True)
@app.post("/api/logout")
def logout():
    if g.ses: audit("logout")
    SES.pop(session.get("sid"), None); session.pop("sid", None); session.pop("pre", None); return jsonify(ok=True)
@app.get("/api/me")
def me():
    s = g.ses
    if not s: return jsonify(role=None, demo=DEMO_SHOW_OTP, store=DB.kind, captcha=CAPTCHA_ON)
    p, now = POLICY[s["role"]], time.time()
    return jsonify(role=s["role"], name=s["name"], username=s["user"], inst=s["inst"], store=DB.kind, demo=DEMO_SHOW_OTP, csrf=session.get("csrf"), idle=p["idle"],
                   abs_left=int(p["abs"] - (now - s["t0"])), stepup_ttl=STEPUP_TTL, mfa_age=int(now - s["mfa"]), factors=FACTORS[s["role"]])

# ---- step-up: re-confirm before sensitive actions (institution: email/SMS code, AICTE: authenticator code)
@app.post("/api/stepup/send")
@guard("institution", "aicte")
def stepup_send():
    if limited(("su", g.sid), 6): return jsonify(error="Too many code requests. Wait a few minutes."), 429
    if STEPUP_METHOD[g.ses["role"]] == "totp":                       # AICTE: the code comes from the authenticator app, nothing is sent
        h = demo_totp_hint(g.ses["user"]) if DEMO_SHOW_OTP else None
        return jsonify(method="totp", demo_totp=h, demo_wait=bool(DEMO_SHOW_OTP and not h))
    a = ACCTS[g.ses["user"]]; code = issue_otp(("step", g.sid), a); out = dict(method="otp", masked=mask_dest(a))
    if DEMO_SHOW_OTP: out["demo_otp"] = code
    return jsonify(out)
@app.post("/api/stepup/verify")
@guard("institution", "aicte")
def stepup_verify():
    code, u = (request.get_json(silent=True) or {}).get("code", ""), g.ses["user"]
    if STEPUP_METHOD[g.ses["role"]] == "otp": r = check_otp(("step", g.sid), code)
    else: r = "ok" if check_totp(u, code) else "bad"
    if r == "ok": g.ses["mfa"] = time.time(); g.ses["su_fail"] = 0; audit("stepup_ok"); return jsonify(ok=True)
    g.ses["su_fail"] = g.ses.get("su_fail", 0) + 1; audit("stepup_failed", "u:" + utag(u))
    if r == "locked" or g.ses["su_fail"] >= 5: SES.pop(g.sid, None); session.pop("sid", None); audit("session_terminated", "step-up failures", actor=g.ses["name"], role=g.ses["role"]); return jsonify(error="Too many wrong codes. You were signed out.", expired=True), 401
    return jsonify(error="That code was not accepted." if r != "expired" else "That code has expired. Send a new one."), 400

# ---- account security page
def device_name(ua):
    o = "Android" if "Android" in ua else "iPhone" if "iPhone" in ua else "Windows" if "Windows" in ua else "Mac" if "Mac OS" in ua else "Linux" if "Linux" in ua else "Unknown device"
    b = "Edge" if "Edg/" in ua else "Firefox" if "Firefox" in ua else "Chrome" if "Chrome" in ua else "Safari" if "Safari" in ua else "Browser"
    return f"{b} on {o}"
@app.get("/api/account/security")
@guard()
def acct_security():
    s = g.ses; ago = lambda t: int(time.time() - t); r = s["role"]
    mine = [dict(ref=hm("sid", sid)[:8], device=device_name(x["ua_raw"]), started_ago=ago(x["t0"]), active_ago=ago(x["t"]), current=sid == g.sid) for sid, x in SES.items() if x["user"] == s["user"]]
    return jsonify(role=r, username=s["user"], factors=FACTORS[r], idle=POLICY[r]["idle"], abs=POLICY[r]["abs"], stepup=STEPUP_METHOD.get(r), stepup_ttl=STEPUP_TTL, sessions=mine,
                   mfa_qr=DEMO_SHOW_OTP and "totp" in FACTORS[r], allowlist=bool(ALLOW) and r == "aicte", https=SECURE)
@app.post("/api/account/password")
@guard(fresh=True)
def acct_password():
    b = request.get_json(silent=True) or {}; u = g.ses["user"]; cur, new = str(b.get("current", ""))[:200], str(b.get("new", ""))[:200]
    if not pw_check(u, cur): register_fail(u, "password"); return jsonify(error="Your current password is not correct."), 400
    if new == cur: return jsonify(error="Choose a password different from the current one."), 400
    pr = pw_problem(new, u)
    if pr: return jsonify(error=pr), 400
    DB.add("pwchg", dict(username=u, h=hash_pw(new), ts=now_utc().strftime("%Y-%m-%d %H:%M:%S UTC"))); n = 0
    for sid in [k for k, x in SES.items() if x["user"] == u and k != g.sid]: SES.pop(sid, None); n += 1
    audit("password_changed", f"{n} other session(s) ended"); return jsonify(ok=True, ended=n)
@app.post("/api/account/signout-all")
@guard(fresh=True)
def acct_signout_all():
    u = g.ses["user"]; audit("signout_all"); [SES.pop(k, None) for k in [k for k, x in SES.items() if x["user"] == u]]; session.pop("sid", None); return jsonify(ok=True)
@app.get("/api/account/mfa")
@guard("aicte", fresh=True)
def acct_mfa():
    if not DEMO_SHOW_OTP: return jsonify(error="Authenticator enrolment is handled by your administrator."), 404
    import segno; sec = totp_secret(g.ses["user"]); uri = f"otpauth://totp/NAVS%20(demo):{g.ses['user']}?secret={sec}&issuer=NAVS%20demo&digits=6&period=30"
    buf = io.BytesIO(); segno.make(uri, error="m").save(buf, kind="svg", scale=5, border=2, dark="#0B1B33")
    audit("mfa_enrol_viewed"); return jsonify(qr="data:image/svg+xml;base64," + base64.b64encode(buf.getvalue()).decode(), secret=sec)

@app.post("/api/account/recovery")
@guard("aicte", fresh=True)
def acct_recovery():
    audit("recovery_codes_made"); return jsonify(codes=new_recovery(g.ses["user"]), note="Keep these somewhere safe. Each works once, in place of an authenticator code. Making new codes cancels the old ones.")

# ---- demo helpers (only when DEMO_SHOW_OTP=1) and the public landing-page numbers
def _demo_accounts():
    first_student = min(u for u, a in ACCTS.items() if a["role"] == "student")
    return {"student": first_student, "institution": "reg.d0001", "aicte": "aicte.officer", "employer": "acme.hr"}
@app.get("/api/demo")
def demo():
    if not DEMO_SHOW_OTP or limited(("demo", ip()), 90): return jsonify({})
    return jsonify(accounts={r: dict(username=u, password=demo_pw(u), name=ACCTS[u]["name"]) for r, u in _demo_accounts().items()})
@app.get("/api/demo/college/<code>")
def demo_college(code):
    u = "reg." + code.split("-")[-1].lower()
    if not DEMO_SHOW_OTP or limited(("demo", ip()), 90) or u not in ACCTS: return jsonify({}), 404
    return jsonify(username=u, password=demo_pw(u), name=ACCTS[u]["name"])
_PUB = dict(t=0, v=None)
@app.get("/api/public/overview")
def public_overview():
    if limited(("po", ip()), 120): return jsonify(error="Too many requests."), 429
    now = time.time()
    if now - _PUB["t"] > 30:
        rows = analyse(DB.find("students")); c = cnt(rows); insts = DB.find("institutions"); states = {}
        for i in insts: states[i["state"]] = states.get(i["state"], 0) + 1
        _PUB.update(t=now, v=dict(institutions=[dict(code=i["code"], name=i["name"], city=i["city"], state=i["state"]) for i in insts], states=states,
                                 totals=dict(institutions=len(insts), students=len(rows), verified=c["VERIFIED"], attention=c["REVIEW"] + c["FLAGGED"])))
    return jsonify(_PUB["v"])

# ------------------------------------------------------------ reviewer workflow
STATE = {"corrected": "Corrected, re-upload pending", "clarify": "Awaiting student", "escalate": "Escalated to AICTE", "dismiss": "Dismissed", "aicte_upheld": "Upheld by AICTE", "aicte_cleared": "Cleared by AICTE",
         "resolved_upload": "Resolved by re-upload"}
def latest_reviews():
    m = {}
    for r in DB.find("reviews"): m[r["cert_id"]] = r
    return m
def latest_review(cid):
    r = DB.find("reviews", {"cert_id": cid}); return r[-1] if r else None
def latest_appeals():
    m = {}
    for a in DB.find("appeals"): m[a["cert_id"]] = a
    return m
def annotate(rows):
    rv, ap = latest_reviews(), latest_appeals()
    for r in rows:
        x, a = rv.get(r["cert_id"]), ap.get(r["cert_id"]); r["state"] = STATE.get(x["decision"], "Open") if x else "Open"
        if x and x["decision"] == "clarify" and a and a.get("t", 0) > x.get("t", 0): r["state"] = "Student replied"
        r["review"] = dict(note=x["note"], by=x["by"], ts=x["ts"], decision=x["decision"]) if x else None
        r["reply"] = dict(text=a["text"], ts=a["ts"], kind=a.get("kind", "reply")) if a else None
    return rows
# ------------------------------------------------------------ certificates (signed, expiring, revocable)
CERT_DAYS = 365
_SIGN = {}
def signer():
    """Ed25519 key for certificates. Production: set CERT_SIGNING_KEY (any long random string) and keep it in a secrets manager / HSM. Without it a key is derived from SECRET_KEY."""
    if not _SIGN:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives import serialization
        raw = hashlib.sha256(os.environ["CERT_SIGNING_KEY"].encode()).digest() if os.environ.get("CERT_SIGNING_KEY") else subkey("cert-sign")
        k = Ed25519PrivateKey.from_private_bytes(raw[:32]); pub = k.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        _SIGN.update(k=k, pub=base64.b64encode(pub).decode(), kid=hashlib.sha256(pub).hexdigest()[:8])
    return _SIGN
SIGNED = ("cert_id", "name", "institution", "aicte_id", "program", "issued", "expires")
def sign_cert(p):
    try: sg = signer()
    except Exception: return {}                                              # `cryptography` missing: certificates are simply unsigned
    msg = json.dumps({k: p[k] for k in SIGNED}, sort_keys=True, separators=(",", ":")).encode()
    return dict(sig=base64.urlsafe_b64encode(sg["k"].sign(msg)).decode(), kid=sg["kid"], signed_fields=list(SIGNED))
def fmt_day(iso):
    try: return datetime.datetime.strptime(iso, "%Y-%m-%d").strftime("%d %b %Y")
    except (ValueError, TypeError): return str(iso)
def cert_payload(s, public=False):
    inst = DB.find_one("institutions", {"code": s["inst"]}) or {}; iss = analyse([s])[0]; lr = latest_review(s["cert_id"])
    issued = s.get("issued", SEED_ISSUED)
    try: exp = (datetime.datetime.strptime(issued, "%Y-%m-%d") + datetime.timedelta(days=CERT_DAYS)).strftime("%Y-%m-%d")
    except ValueError: exp = issued
    cleared = bool(lr and lr["decision"] == "aicte_cleared"); revoked = bool(lr and lr["decision"] == "aicte_upheld"); expired = exp < now_utc().strftime("%Y-%m-%d")
    ok = (iss["status"] != "FLAGGED" or cleared) and not revoked and not expired
    status = "REVOKED" if revoked else "EXPIRED" if expired else "VALID" if ok else "UNDER REVIEW"
    p = dict(cert_id=s["cert_id"], valid=ok, status=status, name=s["name"], apaar=mask(s["apaar"]), roll=s["roll"],
             program=f"{s['program']} ({s['branch']})", admitted=s["year"], institution=inst.get("name", "-"), aicte_id=s["inst"], city=inst.get("city", ""),
             cgpa=s["cgpa"], issued=fmt_day(issued), expires=fmt_day(exp), note="Demo certificate. Not issued by AICTE, DigiLocker or any government body.", issues=iss["issues"], face=s["face"])
    p.update(sign_cert({**p, "issued": issued, "expires": exp}))
    if public:
        for k in ("roll", "cgpa", "issues", "face"): p.pop(k)       # public/QR view: identity + validity only
    return p
def by_cert(cid): return DB.find_one("students", {"cert_id": str(cid).upper()})
@app.get("/api/cert-key")
def cert_key():
    try: sg = signer()
    except Exception: return jsonify(error="Signing is not available on this server."), 404
    return jsonify(alg="Ed25519", kid=sg["kid"], public_key=sg["pub"], signed_fields=list(SIGNED), how="JSON of the signed fields, keys sorted, no spaces, UTF-8; signature is urlsafe-base64. Status (valid / revoked) is always read live from the API.")
@app.get("/api/verify/<cid>")
def verify(cid):
    if limited(("pv", ip()), 40): return jsonify(error="Too many lookups. Try again shortly."), 429
    s = by_cert(cid[:40]); audit("public_verify", "found" if s else "not found")
    return (jsonify(cert_payload(s, True)) if s else (jsonify(error="No certificate with this ID."), 404))
def public_base():
    b = os.environ.get("PUBLIC_URL") or os.environ.get("RENDER_EXTERNAL_URL")     # a configured address beats whatever Host header the request came with
    return (b or request.host_url).rstrip("/")
@app.get("/api/qr/<cid>.svg")
def qr_svg(cid):
    import segno
    buf = io.BytesIO(); segno.make(f"{public_base()}/?verify={re.sub('[^A-Za-z0-9-]', '', cid)[:40]}", error="m").save(buf, kind="svg", scale=4, border=2, dark="#10243b")
    return app.response_class(buf.getvalue(), mimetype="image/svg+xml", headers={"Cache-Control": "public, max-age=3600"})
# ---- employers: every check is logged in MongoDB (by username, capped), and the student can see it and can pause it
LOG_CAP = 200
def log_check(cert_id, status):
    u, now = g.ses["user"], time.time()
    DB.add("verifylog", dict(user=u, by=g.ses["name"], cert_id=cert_id, status=status, at=now_ist(), t=now))
    old = DB.find("verifylog", {"user": u}, sort=("t", -1), limit=1, skip=LOG_CAP)
    if old: DB.delete("verifylog", {"user": u, "t": {"$lte": old[0]["t"]}})
def my_log(): return [dict(cert=l["cert_id"], status=l["status"], at=l["at"]) for l in DB.find("verifylog", {"user": g.ses["user"]}, sort=("t", -1), limit=8)]
@app.get("/api/employer/verify/<cid>")
@guard("employer")
def emp_verify(cid):
    if limited(("ev", g.ses["user"]), 40): return jsonify(error="Too many lookups. Try again shortly."), 429
    s = by_cert(cid[:40])
    if not s: audit("employer_verify", "not found"); return jsonify(error="No certificate with this ID."), 404
    if s.get("share", True) is False: log_check(s["cert_id"], "PAUSED"); audit("employer_verify", s["cert_id"] + " paused"); return jsonify(error="The student has paused employer checks for this certificate.", paused=True), 403
    p = cert_payload(s, True); audit("employer_verify", p["cert_id"] + " " + p["status"]); log_check(p["cert_id"], p["status"])
    return jsonify(**p, log=my_log())
@app.post("/api/employer/verify-batch")
@guard("employer")
def emp_verify_batch():
    ids = (request.get_json(silent=True) or {}).get("ids", [])
    if not isinstance(ids, list) or not ids: return jsonify(error="Send a list of certificate IDs."), 400
    ids = [str(i).strip()[:40] for i in ids if str(i).strip()][:20]
    if DB.bump("evb|" + g.ses["user"], 600) > 10: return jsonify(error="Too many batch checks. Try again shortly."), 429
    out = []
    for cid in ids:
        s = by_cert(cid)
        if not s: out.append(dict(cert_id=cid, found=False, status="NOT FOUND")); continue
        if s.get("share", True) is False: log_check(s["cert_id"], "PAUSED"); out.append(dict(cert_id=s["cert_id"], found=True, status="PAUSED")); continue
        p = cert_payload(s, True); log_check(p["cert_id"], p["status"]); out.append(dict(cert_id=p["cert_id"], found=True, status=p["status"], name=p["name"], institution=p["institution"], program=p["program"]))
    audit("employer_verify_batch", f"{len(ids)} ids"); return jsonify(results=out, log=my_log())

# ------------------------------------------------------------ role dashboards
def my_student():
    u = g.ses["user"]; return next((x for x in DB.find("students", {"inst": g.ses["inst"]}) if x["roll"].lower() == u), None)
@app.get("/api/student/profile")
@guard("student")
def sprofile():
    s = my_student()
    if not s: return jsonify(error="We couldn't find your student record. Please contact your college's registrar."), 404
    p = cert_payload(s); a = latest_appeals().get(s["cert_id"])
    return jsonify(institution=DB.find_one("institutions", {"code": s["inst"]}), profile=dict(face=s["face"], name=s["name"], apaar=mask(s["apaar"]), roll=s["roll"], dob=s["dob"], category=s["category"], email=s["email"], phone=s["phone"][:2] + "••••" + s["phone"][-3:]),
                   review=(annotate([analyse([s])[0]])[0]["state"] if p["issues"] else None), certs=[dict(p, kind="Enrolment Verification"), dict(p, kind="Academic Standing", note="Demo CGPA shown for illustration only.")], checks=p["issues"],
                   reply=dict(text=a["text"], ts=a["ts"]) if a else None, sharing=s.get("share", True))
@app.post("/api/student/respond")
@guard("student")
def student_respond():
    b = request.get_json(silent=True) or {}; text = str(b.get("text", "")).strip()[:500]; s = my_student()
    if not s: return jsonify(error="Record not found."), 404
    if len(text) < 8: return jsonify(error="Write a short explanation (at least 8 characters)."), 400
    if limited(("appeal", g.ses["user"]), 5, 3600): return jsonify(error="Too many messages. Try again later."), 429
    if not analyse([s])[0]["issues"]: return jsonify(error="Nothing is open on your record."), 400
    DB.add("appeals", dict(cert_id=s["cert_id"], inst=s["inst"], text=text, by=g.ses["name"], kind="reply" if b.get("kind") != "appeal" else "appeal", ts=now_ist(), t=time.time()))
    audit("student_reply", s["cert_id"]); return jsonify(ok=True)
@app.post("/api/student/sharing")
@guard("student")
def student_sharing():
    s = my_student(); on = bool((request.get_json(silent=True) or {}).get("enabled"))
    if not s: return jsonify(error="Record not found."), 404
    DB.update("students", {"cert_id": s["cert_id"]}, set=dict(share=on)); audit("sharing_" + ("on" if on else "off"), s["cert_id"]); return jsonify(ok=True, sharing=on)
@app.get("/api/student/checks")
@guard("student")
def student_checks():
    s = my_student()
    if not s: return jsonify(error="Record not found."), 404
    return jsonify(items=[dict(by=l["by"], at=l["at"], status=l["status"]) for l in DB.find("verifylog", {"cert_id": s["cert_id"]}, sort=("t", -1), limit=50)], sharing=s.get("share", True))
@app.get("/api/student/export")
@guard("student")
def student_export():
    s = my_student()
    if not s: return jsonify(error="Record not found."), 404
    keep = ("apaar", "name", "dob", "gender", "program", "branch", "year", "inst", "roll", "category", "cgpa", "phone", "email", "cert_id", "issued")
    audit("student_export", s["cert_id"])
    r = jsonify(record={k: s.get(k) for k in keep}, checks=[dict(by=l["by"], at=l["at"], status=l["status"]) for l in DB.find("verifylog", {"cert_id": s["cert_id"]}, sort=("t", -1))],
                messages=[dict(text=a["text"], ts=a["ts"]) for a in DB.find("appeals", {"cert_id": s["cert_id"]})], exported=now_utc().isoformat())
    r.headers["Content-Disposition"] = "attachment; filename=my-navs-data.json"; return r
@app.post("/api/student/erasure-request")
@guard("student")
def student_erasure():
    s = my_student()
    if not s: return jsonify(error="Record not found."), 404
    if limited(("dsr", g.ses["user"]), 3, 86400): return jsonify(error="You have already sent a request today."), 429
    kind = "correction" if (request.get_json(silent=True) or {}).get("kind") == "correction" else "erasure"
    DB.add("dsr", dict(cert_id=s["cert_id"], inst=s["inst"], user=g.ses["user"], kind=kind, status="pending", ts=now_ist(), t=time.time())); audit("dsr_" + kind, s["cert_id"])
    return jsonify(ok=True, message="Your request is recorded. Your college registrar and the data controller will respond.")
# ------------------------------------------------------------ student-reported college (notifies AICTE when a college hasn't submitted its CSV)
# kind "unlisted": a student says they study at college X but X's CSV doesn't list them (X may have skipped the upload because it is over its approved intake).
# kind "differs":  a signed-in student says they study at X, but the CSV that holds their record came from another college.
def college_map():
    m = {i["code"]: dict(code=i["code"], name=i["name"], city=i["city"], state=i["state"]) for i in national()}
    m.update({i["code"]: dict(code=i["code"], name=i["name"], city=i["city"], state=i["state"]) for i in DB.find("institutions")}); return m
def clean(v, n): return re.sub(r"\s+", " ", str(v or "")).strip()[:n]
@app.get("/api/public/colleges")
def public_colleges():
    if limited(("colq", ip()), 120, 600): return jsonify(error="Too many searches. Try again shortly."), 429
    q = clean(request.args.get("q"), 60).lower()
    if len(q) < 2: return jsonify(items=[])
    hit = [c for c in college_map().values() if q in (c["name"] + " " + c["city"] + " " + c["code"]).lower()]
    return jsonify(items=sorted(hit, key=lambda c: (not c["name"].lower().startswith(q), c["name"]))[:15])
@app.post("/api/public/enrolment-report")
def public_enrolment_report():
    b = request.get_json(silent=True) or {}
    if captcha_blocked() or not captcha_ok(b): return jsonify(error=CAP_FAIL[0]), CAP_FAIL[1]
    if limited(("enrep", ip()), 5, 3600): return jsonify(error="Too many reports from this network. Try again later."), 429
    col = college_map().get(clean(b.get("college"), 20)); name, roll, l4, contact = clean(b.get("name"), 80), clean(b.get("roll"), 40), clean(b.get("apaar_last4"), 4), clean(b.get("contact"), 80)
    if not col: return jsonify(error="Choose your college from the list."), 400
    if len(name) < 3 or not roll: return jsonify(error="Enter your name and your roll or enrolment number."), 400
    if l4 and not re.fullmatch(r"\d{4}", l4): return jsonify(error="APAAR: enter only the last 4 digits, or leave it empty."), 400
    if DB.find_one("enrol_reports", {"kind": "unlisted", "college": col["code"], "roll_l": roll.lower(), "status": "open"}): return jsonify(ok=True, message="A report for this roll number is already with AICTE. Thank you.")
    DB.add("enrol_reports", dict(id=secrets.token_urlsafe(9), kind="unlisted", college=col["code"], name=name, roll=roll, roll_l=roll.lower(), apaar_last4=l4, contact=contact, status="open", ts=now_ist(), t=time.time()))
    audit("enrolment_report", col["code"], actor="anonymous", role="public"); _PUB["t"] = 0
    return jsonify(ok=True, message=f"Thank you. AICTE and {col['name']} have been told that your record is missing from the college's list. Nothing about you is shown publicly.")
@app.get("/api/student/college")
@guard("student")
def student_college():
    s = my_student()
    if not s: return jsonify(error="Record not found."), 404
    cm = college_map(); d = DB.find_one("enrol_reports", {"kind": "differs", "cert_id": s["cert_id"]})
    return jsonify(record=cm.get(s["inst"]), declared=cm.get(s.get("declared_inst") or s["inst"]), confirmed=bool(s.get("declared_inst")), reported=bool(d), status=d["status"] if d else None)
@app.post("/api/student/college")
@guard("student")
def student_set_college():
    s = my_student(); b = request.get_json(silent=True) or {}
    if not s: return jsonify(error="Record not found."), 404
    col = college_map().get(clean(b.get("college"), 20))
    if not col: return jsonify(error="Choose your college from the list."), 400
    if limited(("setcol", g.ses["user"]), 5, 3600): return jsonify(error="Too many changes. Try again later."), 429
    DB.update("students", {"cert_id": s["cert_id"]}, set=dict(declared_inst=col["code"])); DB.delete("enrol_reports", {"kind": "differs", "cert_id": s["cert_id"]})
    if col["code"] != s["inst"]:
        DB.add("enrol_reports", dict(id=secrets.token_urlsafe(9), kind="differs", college=col["code"], record_inst=s["inst"], cert_id=s["cert_id"], name=s["name"], roll=s["roll"], roll_l=s["roll"].lower(), apaar_last4=s["apaar"][-4:], status="open", ts=now_ist(), t=time.time()))
        audit("student_college_differs", s["cert_id"]); _PUB["t"] = 0
        return jsonify(ok=True, differs=True, message=f"AICTE has been told you study at {col['name']}, while your record came from another college.")
    audit("student_college_confirmed", s["cert_id"]); return jsonify(ok=True, differs=False, message="Saved. Your college matches the record.")
def report_counts():
    out = {}
    for r in DB.find("enrol_reports", {"status": "open"}):
        o = out.setdefault(r["college"], dict(unlisted=0, differs_in=0, disputed_out=0, last=""))
        o["unlisted" if r["kind"] == "unlisted" else "differs_in"] += 1; o["last"] = r["ts"]
        if r["kind"] == "differs": out.setdefault(r["record_inst"], dict(unlisted=0, differs_in=0, disputed_out=0, last=""))["disputed_out"] += 1
    return out
def with_reports(rows, rc=None):
    rc = report_counts() if rc is None else rc; out = []
    for i in rows:
        r = rc.get(i["code"])
        if not r or not (r["unlisted"] or r["differs_in"]): out.append(i); continue
        n = r["unlisted"] + r["differs_in"]; i = dict(i, flags=i["flags"] + ["STUDENTS_MISSING"], risk=min(100, i["risk"] + 10 + 5 * min(n, 10)), reports=n); out.append(i)
    return out
@app.get("/api/aicte/reports")
@guard("aicte")
def aicte_reports():
    rc, cm = report_counts(), college_map(); live = {i["code"]: i for i in DB.find("institutions")}; nat = {i["code"]: i for i in national()}; cnts = {}
    for st in DB.find("students"): cnts[st["inst"]] = cnts.get(st["inst"], 0) + 1
    rows = []
    for code, r in rc.items():
        c = cm.get(code); i = live.get(code) or nat.get(code)
        if not c or not i: continue
        recs = cnts.get(code, 0) if code in live else i.get("sample", 0)
        rows.append(dict(c, intake=i["intake"], reported=i["reported"], over=max(i["reported"] - i["intake"], 0), records=recs, csv_submitted=recs > 0, unlisted=r["unlisted"], differs_in=r["differs_in"], disputed_out=r["disputed_out"], last=r["last"], sim=code not in live))
    rows.sort(key=lambda x: (x["csv_submitted"], -(x["unlisted"] + x["differs_in"]), x["code"]))
    return jsonify(rows=rows, open=sum(r["unlisted"] + r["differs_in"] for r in rc.values()), no_csv=sum(1 for r in rows if not r["csv_submitted"] and (r["unlisted"] or r["differs_in"])))
@app.get("/api/aicte/reports/<code>")
@guard("aicte")
def aicte_report_detail(code):
    code = code[:20]; cm = college_map()
    if code not in cm: return jsonify(error="Unknown college."), 404
    items = [dict(id=r["id"], kind=r["kind"], name=r["name"], roll=r["roll"], apaar_last4=r.get("apaar_last4", ""), contact=r.get("contact", ""), ts=r["ts"], record_college=(cm.get(r.get("record_inst")) or {}).get("name"))
             for r in DB.find("enrol_reports", {"college": code, "status": "open"}, sort=("t", -1), limit=200)]
    return jsonify(college=cm[code], items=items)
@app.post("/api/aicte/reports/resolve")
@guard("aicte", fresh=True)
def aicte_reports_resolve():
    b = request.get_json(silent=True) or {}; code, note = clean(b.get("college"), 20), clean(b.get("note"), 300)
    if code not in college_map() or len(note) < 8: return jsonify(error="Choose a college and add a note (8+ characters)."), 400
    n = 0
    for r in DB.find("enrol_reports", {"college": code, "status": "open"}): DB.update("enrol_reports", {"id": r["id"]}, set=dict(status="closed", note=note, by=g.ses["name"], closed=now_ist())); n += 1
    audit("reports_closed", f"{code}: {n}"); _PUB["t"] = 0; return jsonify(ok=True, closed=n)
@app.get("/api/institution/overview")
@guard("institution")
def inst_overview():
    code = g.ses["inst"]; rows = analyse(DB.find("students", {"inst": code})); i = DB.find_one("institutions", {"code": code})
    rep = [dict(kind=r["kind"], name=r["name"], roll=r["roll"], ts=r["ts"]) for r in DB.find("enrol_reports", {"college": code, "status": "open"}, sort=("t", -1), limit=100)]
    return jsonify(institution=i, counts=cnt(rows), students=annotate(rows), over_intake=max(i["reported"] - i["intake"], 0), student_reports=rep)
@app.post("/api/institution/review")
@guard("institution", fresh=True)
def inst_review():
    b = request.get_json(silent=True) or {}; d = str(b.get("decision")); note = str(b.get("note", "")).strip()[:300]
    if d not in ("corrected", "clarify", "escalate", "dismiss"): return jsonify(error="Choose a decision."), 400
    if len(note) < 8: return jsonify(error="Add a short reason (at least 8 characters)."), 400
    s = by_cert(str(b.get("cert_id", ""))[:40])
    if not s or s["inst"] != g.ses["inst"]: return jsonify(error="Record not found in your institution."), 404
    row = analyse([s])[0]; codes = {i["code"] for i in row["issues"]}
    if row["status"] == "VERIFIED": return jsonify(error="Nothing to review: this record passed every check."), 400
    if d == "dismiss" and (row["status"] == "FLAGGED" or "DUPLICATE_ACROSS_COLLEGES" in codes):
        return jsonify(error="Flagged records can't be dismissed by the college. Escalate to AICTE or ask the student."), 400
    DB.add("reviews", dict(cert_id=s["cert_id"], inst=s["inst"], decision=d, note=note, by=g.ses["name"], ts=now_ist(), t=time.time()))
    audit("review_" + d, s["cert_id"]); return jsonify(row=annotate([row])[0])
@app.get("/api/aicte/escalations")
@guard("aicte")
def escalations():
    out = []
    for cid, r in latest_reviews().items():
        if r["decision"] in ("escalate", "aicte_upheld", "aicte_cleared"):
            s = by_cert(cid)
            if not s: continue
            row = analyse([s])[0]; out.append({**row, "state": STATE[r["decision"]], "review": dict(note=r["note"], by=r["by"], ts=r["ts"], decision=r["decision"]), "open": r["decision"] == "escalate"})
    return jsonify(items=sorted(out, key=lambda x: not x["open"]))
@app.post("/api/aicte/resolve")
@guard("aicte", fresh=True)
def resolve():
    b = request.get_json(silent=True) or {}; o = str(b.get("outcome")); note = str(b.get("note", "")).strip()[:300]
    if o not in ("upheld", "cleared") or len(note) < 8: return jsonify(error="Choose an outcome and add a reason (8+ characters)."), 400
    cid = str(b.get("cert_id", ""))[:40]; r = latest_review(cid)
    if not r or r["decision"] != "escalate": return jsonify(error="This record is not awaiting an AICTE decision."), 400
    DB.add("reviews", dict(cert_id=cid, inst=r["inst"], decision="aicte_" + o, note=note, by=g.ses["name"], ts=now_ist(), t=time.time()))
    audit("aicte_" + o, cid); return jsonify(ok=True)
@app.get("/api/aicte/locked")
@guard("aicte")
def locked_accounts():
    now = time.time(); us = set()
    for k, v in LOCKED.items():
        ks = "|".join(k) if isinstance(k, tuple) else k
        if not ks.endswith("|epoch") and v > now: us.add(ks.split("|")[0])
    return jsonify(items=sorted(us))
@app.post("/api/aicte/unlock")
@guard("aicte", fresh=True)
def aicte_unlock():
    u = str((request.get_json(silent=True) or {}).get("username", "")).strip().lower()[:60]
    if u not in ACCTS: return jsonify(error="No such account."), 404
    unlock(u); audit("account_unlocked", "u:" + utag(u)); return jsonify(ok=True)

# ---- CSV upload: preview first (saved as a submission), then "apply" writes the corrections to the student records
MAX_ROWS = 2000
def cell(r, k): return str(r.get(k) or "").strip()
@app.post("/api/institution/upload")
@guard("institution", fresh=True)
def inst_upload():
    f = request.files.get("file")
    if not f or not f.filename.lower().endswith(".csv"): return jsonify(error="Choose a .csv file."), 400
    raw = f.read()
    try: txt = raw.decode("utf-8-sig")
    except UnicodeDecodeError: txt = raw.decode("cp1252", "replace")
    try: rd = list(csv.DictReader(io.StringIO(txt)))
    except Exception: return jsonify(error="Could not read this file as CSV."), 400
    if rd and any("aadhaar" in (k or "").lower() or "aadhar" in (k or "").lower() for k in rd[0]): return jsonify(error="This system does not accept Aadhaar numbers. Remove that column and upload again."), 400
    need = {"apaar_id", "name", "dob", "roll_no"}
    if not rd or not need <= {(k or "").strip() for k in rd[0]}: return jsonify(error="CSV needs columns: apaar_id, name, dob, roll_no"), 400
    rd = [{(k or "").strip(): v for k, v in r.items() if k} for r in rd]
    total, stu, bad, seen_roll = len(rd), [], [], set()
    for n, r in enumerate(rd[:MAX_ROWS], start=2):                           # line 1 is the header
        row = dict(inst=g.ses["inst"], apaar=cell(r, "apaar_id"), name=cell(r, "name"), dob=cell(r, "dob"), roll=cell(r, "roll_no"), program=cell(r, "program") or "B.Tech", branch=cell(r, "branch") or "-")
        miss = [k for k, v in (("apaar_id", row["apaar"]), ("name", row["name"]), ("dob", row["dob"]), ("roll_no", row["roll"])) if not v]
        if miss: bad.append(dict(line=n, problem="Missing " + ", ".join(miss))); continue
        if row["roll"].lower() in seen_roll: bad.append(dict(line=n, problem="Roll number appears twice in this file")); continue
        seen_roll.add(row["roll"].lower()); stu.append(row)
    allst = [s for s in DB.find("students") if s["inst"] != g.ses["inst"]] + stu; reg = {r["apaar"]: r for r in DB.find("registry", {"apaar": {"$in": sorted({s["apaar"] for s in stu})}})}
    dm = dupmap(allst); rows = []
    for s in stu:
        iss = check(s, reg, dm); rows.append(dict(roll=s["roll"], name=s["name"], apaar=mask(s["apaar"]), status=verdict(iss), issues=[dict(sev=a, code=b, msg=c) for a, b, c in iss]))
    sid = secrets.token_urlsafe(12); now = time.time()
    DB.delete("submissions", {"inst": g.ses["inst"], "status": "preview", "t": {"$lt": now - 7 * 86400}})
    DB.add("submissions", dict(id=sid, inst=g.ses["inst"], by=g.ses["name"], ts=now_ist(), t=now, status="preview", rows=stu, counts=cnt(rows), total=total, bad=len(bad)))
    audit("batch_checked", f"{len(rows)} rows"); trunc = total > MAX_ROWS
    return jsonify(rows=rows, counts=cnt(rows), bad_rows=bad[:50], bad_count=len(bad), total_rows=total, checked=len(rows), truncated=trunc, submission_id=sid,
                   note=(f"Checked {len(rows)} of {total} rows (the limit is {MAX_ROWS} per file): upload the rest as a second file. " if trunc else "") + "Nothing is saved yet. Review the result, then apply it.")
@app.post("/api/institution/upload/<sid>/apply")
@guard("institution", fresh=True)
def inst_apply(sid):
    sub = DB.find_one("submissions", {"id": sid[:40], "inst": g.ses["inst"]})
    if not sub: return jsonify(error="Upload not found. Upload the file again."), 404
    if sub["status"] != "preview": return jsonify(error="This upload was already applied."), 400
    DB.update("submissions", {"id": sid[:40]}, set=dict(status="applying"))
    code, upd, add, same, fixed = g.ses["inst"], 0, 0, 0, 0; mine = {x["roll"].lower(): x for x in DB.find("students", {"inst": code})}; touched = []
    for r in sub["rows"]:
        old = mine.get(r["roll"].lower())
        if old:
            ch = {k: r[k] for k in ("apaar", "name", "dob") if old.get(k) != r[k]}
            if not ch: same += 1; continue
            DB.update("students", {"cert_id": old["cert_id"]}, set=ch); DB.update("users", {"username": old["roll"].lower()}, set={k: v for k, v in (("ref", ch.get("apaar")), ("name", ch.get("name"))) if v})
            touched.append(old["cert_id"]); upd += 1
        else:
            cid = "APR-" + secrets.token_hex(6).upper()
            DB.add("students", dict(apaar=r["apaar"], name=r["name"], dob=r["dob"], gender="M", program=r["program"], branch=r["branch"], year=now_utc().year, inst=code, roll=r["roll"], category="General", cgpa=0.0,
                                    phone="", email="", status="ACTIVE", face=0, cert_id=cid, issued=now_utc().strftime("%Y-%m-%d"), share=True))
            DB.add_many("users", [user_doc("student", "", "", r["name"], r["apaar"], inst=code, username=r["roll"].lower())]); add += 1
    ACCTS.t = 0; _PUB["t"] = 0
    for cid in touched:                                                       # a record that now passes every check closes its open "corrected / ask student" item
        s = by_cert(cid); lr = latest_review(cid)
        if s and analyse([s])[0]["status"] == "VERIFIED" and lr and lr["decision"] in ("corrected", "clarify"):
            DB.add("reviews", dict(cert_id=cid, inst=code, decision="resolved_upload", note="Passed every check after upload " + sid[:6], by=g.ses["name"], ts=now_ist(), t=time.time())); fixed += 1
    DB.update("submissions", {"id": sid[:40]}, set=dict(status="applied", applied=now_ist(), summary=dict(updated=upd, added=add, unchanged=same, resolved=fixed)))
    audit("batch_applied", f"{upd} updated, {add} added, {fixed} resolved"); return jsonify(ok=True, updated=upd, added=add, unchanged=same, resolved=fixed)
def live_inst_rows(rows=None, dm=None):
    insts, stu = DB.find("institutions"), DB.find("students")
    rows = rows if rows is not None else analyse(stu); dm = dm if dm is not None else dupmap(stu); by, out = {}, []
    for x in rows: by.setdefault(x["inst"], []).append(x)
    for i in insts:
        r = by.get(i["code"], []); c = cnt(r); over = i["reported"] - i["intake"]
        flags = (["OVER_INTAKE"] if over > 0 else []) + (["DUPLICATE_APAAR"] if any(x["code"] == "DUPLICATE_ACROSS_COLLEGES" for y in r for x in y["issues"]) else []) + (["MISMATCHES"] if c["FLAGGED"] else [])
        out.append(dict(i, over=max(over, 0), sample=len(r), **c, flags=flags, risk=min(100, max(over, 0) * 100 // i["intake"] * 2 + c["FLAGGED"] * 12 + c["REVIEW"] * 4), sim=False))
    return out
def all_inst_rows(): rc = report_counts(); return with_reports(live_inst_rows(), rc) + with_reports(national(), rc)
@app.get("/api/aicte/overview")
@guard("aicte")
def aicte():
    stu = DB.find("students"); rows = analyse(stu); dm = dupmap(stu); rc = report_counts(); live = with_reports(live_inst_rows(rows, dm), rc); nat = with_reports(national(), rc); allr = live + nat
    dups = [dict(apaar=mask(a), colleges=sorted(c)) for a, c in dm.items() if len(c) > 1 and re.fullmatch(r"\d{12}", a)]
    states = {}
    for i in allr: states[i["state"]] = states.get(i["state"], 0) + i["reported"]
    tot = lambda k: sum(i[k] for i in allr); top = sorted(allr, key=lambda i: (-i["risk"], i["code"]))[:5]
    fs = {}
    for i in allr:
        if i["flags"]: fs[i["state"]] = fs.get(i["state"], 0) + 1
    ft = {k: sum(1 for i in allr if k in i["flags"]) for k in ("OVER_INTAKE", "DUPLICATE_APAAR", "MISMATCHES", "STUDENTS_MISSING")}
    return jsonify(top=top, duplicates=dups, states=states, flag_states=fs, flag_types=ft, flagged=annotate([r for r in rows if r["status"] == "FLAGGED"]),
                   totals=dict(institutions=len(allr), live=len(live), simulated=len(nat), reported=tot("reported"), intake=tot("intake"), VERIFIED=tot("VERIFIED"), REVIEW=tot("REVIEW"), FLAGGED=tot("FLAGGED"),
                               flagged_institutions=sum(1 for i in allr if i["flags"]), over_institutions=sum(1 for i in allr if i["over"]), dup_total=len(dups) + sum(i["dups"] for i in nat), live_flagged=cnt(rows)["FLAGGED"]))
@app.get("/api/aicte/institutions")
@guard("aicte")
def aicte_institutions():
    a = request.args; q = a.get("q", "").strip().lower()[:60]; st = a.get("state", "")[:40]; res = a.get("result", "")[:8]; src = a.get("source", "")[:8]
    try: page, per = max(0, int(a.get("page", 0))), min(max(int(a.get("per", 10)), 1), 3000)
    except ValueError: return jsonify(error="Bad paging values."), 400
    allr = sorted(all_inst_rows(), key=lambda i: (-i["risk"], i["code"])); f = [i for i in allr if (not q or q in (i["name"] + " " + i["city"] + " " + i["code"]).lower()) and (not st or i["state"] == st)
         and (not res or (i["flags"] if res == "flag" else i["over"] if res == "over" else not i["flags"])) and (not src or (i["sim"] if src == "sim" else not i["sim"]))]
    pages = max(1, -(-len(f) // per)); page = min(page, pages - 1)
    if per > 100: audit("institutions_export", f"{len(f)} rows")
    return jsonify(rows=f[page * per:(page + 1) * per], total=len(f), all=len(allr), flagged=sum(1 for i in allr if i["flags"]), page=page, pages=pages, states=sorted({i["state"] for i in allr}))
@app.get("/healthz")
def healthz(): return jsonify(ok=True, store=DB.kind)
@app.get("/api/aicte/audit")
@guard("aicte")
def aicte_audit():
    audit("audit_viewed")
    tail = DB.find("audit", sort=("_id", -1), limit=2000)[::-1]; ok, why = True, ""
    prev = tail[0]["prev"] if tail else "0" * 16
    for i, e in enumerate(tail):
        if e["prev"] != prev or e["h"] != chain(prev, e): ok, why = False, "an entry was changed or removed"
        prev = e["h"]
    head = DB.find_one("meta", {"k": "audit_head"})
    if tail and head and (head["seq"] > tail[-1].get("seq", 0) or (head["seq"] == tail[-1].get("seq", 0) and head["h"] != tail[-1]["h"])): ok, why = False, "the end of the log was cut off"
    return jsonify(entries=tail[::-1][:150], chain_ok=ok, chain_note=why, checked=len(tail), total=DB.count("audit"), posture=posture())

@app.get("/static/<path:p>")
def static_files(p):
    r = send_from_directory(os.path.join(BASE, "static"), p); r.headers["Cache-Control"] = "public, max-age=3600"; return r
@app.get("/")
def home():
    js = os.path.join(BASE, "static", "app.js"); v = str(int(os.path.getmtime(js))) if os.path.exists(js) else "0"
    with open(os.path.join(BASE, "index.html"), encoding="utf-8") as f: html = f.read().replace("__V__", v)
    return Response(html, mimetype="text/html", headers={"Cache-Control": "no-cache"})
@app.after_request
def hdr(r):
    r.headers.update({"X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY", "Referrer-Policy": "no-referrer", "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
        "Cross-Origin-Opener-Policy": "same-origin", "Cross-Origin-Resource-Policy": "same-origin",
        "Content-Security-Policy": "default-src 'self'; script-src 'self' https://hcaptcha.com https://*.hcaptcha.com; style-src 'self' 'unsafe-inline' https://hcaptcha.com https://*.hcaptcha.com; font-src 'self'; img-src 'self' data: blob: https://hcaptcha.com https://*.hcaptcha.com; frame-src https://hcaptcha.com https://*.hcaptcha.com; connect-src 'self' https://hcaptcha.com https://*.hcaptcha.com; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"})
    if request.path.startswith("/api/"): r.headers["Cache-Control"] = "no-store"
    if request.is_secure: r.headers["Strict-Transport-Security"] = "max-age=31536000"
    return r
if __name__ == "__main__":
    ctx, host = None, os.environ.get("APAAR_HOST", "127.0.0.1")
    if os.environ.get("APAAR_HTTPS"):
        c, k = os.environ.get("APAAR_CERT", os.path.join(BASE, "certs", "cert.pem")), os.environ.get("APAAR_KEY", os.path.join(BASE, "certs", "key.pem"))
        if not (os.path.exists(c) and os.path.exists(k)): raise SystemExit("HTTPS needs a certificate. Run:  sh make_cert.sh   (or set APAAR_CERT and APAAR_KEY)")
        ctx = (c, k)
    if host not in ("127.0.0.1", "localhost") and not (ctx or os.environ.get("APAAR_PROXY")): print("WARNING: listening beyond this device without HTTPS. Passwords and sessions are not encrypted on the network.")
    if TESTING: print("!!! APAAR_TESTING=1: hCaptcha test tokens are accepted. Use for automated tests only. !!!")
    if CAPTCHA_ON and not HCAPTCHA_SECRET: print("WARNING: HCAPTCHA_SECRET is not set, so nobody can sign in. Set it (see .env.example) or run with CAPTCHA=0 for a quick local look.")
    print(f"NAVS prototype · {DB.kind} · hCaptcha: {CAPTCHA_ON} · demo codes on screen: {DEMO_SHOW_OTP} · AICTE network allow-list: {'on' if ALLOW else 'off'}")
    app.run(host=host, port=int(os.environ.get("PORT", 5000)), ssl_context=ctx, debug=False)
