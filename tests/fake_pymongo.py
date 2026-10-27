"""A tiny stand-in for pymongo, used only when neither pymongo nor mongomock is installed. Covers just the calls NAVS makes."""
import copy, itertools, sys, threading, types

class DuplicateKeyError(Exception): pass
class BulkWriteError(Exception): pass
class ReturnDocument: BEFORE, AFTER = 0, 1
errors = types.SimpleNamespace(DuplicateKeyError=DuplicateKeyError, BulkWriteError=BulkWriteError)
_ids, _lock = itertools.count(1), threading.RLock()

def _get(d, path):
    for p in path.split("."):
        if not isinstance(d, dict) or p not in d: return None
        d = d[p]
    return d
def _set(d, path, v):
    ps = path.split(".")
    for p in ps[:-1]: d = d.setdefault(p, {})
    d[ps[-1]] = v
def _unset(d, path):
    ps = path.split(".")
    for p in ps[:-1]:
        d = d.get(p, {})
    d.pop(ps[-1], None)
def _m(d, q):
    for k, v in q.items():
        x = _get(d, k) if "." in k else d.get(k)
        if isinstance(v, dict) and any(o.startswith("$") for o in v):
            for o, w in v.items():
                if o == "$in" and x not in w: return False
                if o == "$lt" and not (x is not None and x < w): return False
                if o == "$lte" and not (x is not None and x <= w): return False
                if o == "$ne" and x == w: return False
                if o == "$exists" and (x is not None) != w: return False
        elif x != v: return False
    return True
class Cursor:
    def __init__(s, docs, proj): s.d, s.proj = docs, proj
    def sort(s, key, direction=1): s.d.sort(key=lambda d: (d.get(key) is None, d.get(key)), reverse=direction < 0); return s
    def skip(s, n): s.d = s.d[n:]; return s
    def limit(s, n): s.d = s.d[:n]; return s
    def __iter__(s):
        for d in s.d:
            d = copy.deepcopy(d)
            if s.proj and s.proj.get("_id") == 0: d.pop("_id", None)
            yield d
class Res:
    def __init__(s, matched=0, deleted=0): s.matched_count, s.deleted_count = matched, deleted
class Coll:
    def __init__(s): s.docs, s.uniq = [], []
    def _check(s, d):
        for f, partial in s.uniq:
            if partial and f not in d: continue
            if any(x is not d and x.get(f) == d.get(f) and (f in d) for x in s.docs): raise DuplicateKeyError(f)
    def create_index(s, f, unique=False, **kw):
        if unique: s.uniq.append((f, "partialFilterExpression" in kw))
    def insert_one(s, d):
        with _lock:
            d = copy.deepcopy(d); d.setdefault("_id", next(_ids)); s._check(d); s.docs.append(d)
    def insert_many(s, ds, ordered=True):
        bad = False
        for d in ds:
            try: s.insert_one(d)
            except DuplicateKeyError:
                bad = True
                if ordered: raise
        if bad: raise BulkWriteError()
    def find(s, q=None, proj=None):
        with _lock: return Cursor([d for d in s.docs if _m(d, q or {})], proj)
    def find_one(s, q=None, proj=None):
        with _lock:
            for d in s.docs:
                if _m(d, q or {}): return copy.deepcopy(d)
    def find_one_and_delete(s, q):
        with _lock:
            for d in s.docs:
                if _m(d, q): s.docs.remove(d); return d
    def _apply(s, d, u):
        for k, v in u.get("$set", {}).items(): _set(d, k, copy.deepcopy(v))
        for k in u.get("$unset", {}): _unset(d, k)
        for k, v in u.get("$inc", {}).items(): _set(d, k, (_get(d, k) or 0) + v)
    def update_one(s, q, u, upsert=False):
        with _lock:
            for d in s.docs:
                if _m(d, q): s._apply(d, u); return Res(1)
            if upsert:
                d = {k: v for k, v in q.items() if not isinstance(v, dict)}; d["_id"] = d.get("_id", next(_ids)); s._apply(d, u)
                for k, v in u.get("$setOnInsert", {}).items(): d[k] = v
                s._check(d); s.docs.append(d)
            return Res(0)
    def find_one_and_update(s, q, u, upsert=False, return_document=0):
        with _lock:
            for d in s.docs:
                if _m(d, q): s._apply(d, u); return copy.deepcopy(d)
            if upsert:
                d = {"_id": q.get("_id", next(_ids))}; s._apply(d, u)
                for k, v in u.get("$setOnInsert", {}).items(): d[k] = v
                s.docs.append(d); return copy.deepcopy(d)
    def delete_many(s, q):
        with _lock: n = len(s.docs); s.docs[:] = [d for d in s.docs if not _m(d, q)]; return Res(deleted=n - len(s.docs))
    def count_documents(s, q):
        with _lock: return sum(1 for d in s.docs if _m(d, q))
    def drop(s): s.docs.clear()
class DB:
    def __init__(s): s.c = {}
    def __getitem__(s, n): return s.c.setdefault(n, Coll())
    def command(s, *a): return {"ok": 1}
class MongoClient:
    _dbs = {}
    def __init__(s, *a, **k): pass
    def __getitem__(s, n): return MongoClient._dbs.setdefault(n, DB())
def install():
    m = types.ModuleType("pymongo"); m.MongoClient, m.ReturnDocument, m.errors = MongoClient, ReturnDocument, errors; sys.modules["pymongo"] = m; return m
