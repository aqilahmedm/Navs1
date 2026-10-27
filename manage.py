"""Admin commands (there is no admin web console yet). Run from this folder with the same environment variables as the app (MONGO_URI, SECRET_KEY ...).

  python manage.py unlock <username>                 lift a lockout
  python manage.py disable <username> | enable <username>
  python manage.py reset-totp <username>             new authenticator secret (lost phone); prints the setup key
  python manage.py recovery <username>               8 new single-use recovery codes
  python manage.py add-employer <ORG-CODE> "<Org name>" <email> <phone>      -> username <org-code>.hr
  python manage.py add-institution <1-Dxxxx> "<Name>" <City> <State> <approved_intake> <reported>   -> username reg.<xxxx>
  python manage.py requests                          student data requests (correction / erasure) waiting for a decision
  python manage.py backup <folder>                   dump every collection to JSON files (do this before risky changes)
Passwords: a new account starts with the demo-derived password; the person should use "Forgot password" at first sign-in."""
import json, os, sys, time
import app as A

def need(u):
    if u.lower() not in A.ACCTS: sys.exit("No such account: " + u)
    return u.lower()
def main(a):
    if not a: print(__doc__); return
    c, x = a[0], a[1:]
    if c == "unlock": A.unlock(need(x[0])); print("unlocked", x[0])
    elif c in ("disable", "enable"): A.DB.update("users", {"username": need(x[0])}, set=dict(status="disabled" if c == "disable" else "active")); A.ACCTS.t = 0; print(c + "d", x[0])
    elif c == "reset-totp":
        u = need(x[0]); sec = A.new_totp(); A.DB.update("users", {"username": u}, set=dict(totp=sec)); A.ACCTS.t = 0; print("New authenticator setup key for", u, ":", sec)
    elif c == "recovery": print("\n".join(A.new_recovery(need(x[0]))))
    elif c == "add-employer":
        ref, name, email, phone = x[:4]; d = A.user_doc("employer", email, phone, name, ref.upper(), None); A.DB.add_many("users", [d]); A.ACCTS.t = 0; print("created", d["username"])
    elif c == "add-institution":
        code, name, city, state, intake, rep = x[:6]
        A.DB.add("institutions", dict(code=code, name=name, city=city, state=state, intake=int(intake), reported=int(rep)))
        d = A.user_doc("institution", f"admin@{code.lower()}.example", "0000000000", f"Registrar, {name}", code); A.DB.add_many("users", [d]); A.ACCTS.t = 0; print("created", d["username"])
    elif c == "requests":
        for r in A.DB.find("dsr", {"status": "pending"}): print(r["ts"], r["kind"], r["cert_id"], r["inst"])
    elif c == "backup":
        os.makedirs(x[0], exist_ok=True)
        for n in ("students", "registry", "institutions", "users", "reviews", "appeals", "submissions", "verifylog", "pwchg", "audit", "dsr", "meta"):
            with open(os.path.join(x[0], n + ".json"), "w") as f: json.dump(A.DB.find(n), f, default=str)
        print("saved to", x[0], "(contains personal data and password hashes: keep it private)")
    else: print(__doc__)
if __name__ == "__main__": main(sys.argv[1:])
