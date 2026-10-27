# NAVS: National Academic Verification System (APAAR verification prototype)

**Everything here is fictional.** 60 invented colleges with student records, a simulated national register of 2,650 institutions, 600 invented students, invented certificates. It is not connected to AICTE, NAD, APAAR or DigiLocker and is not an official AICTE service. Prototype for SIH26263.
The product name is one constant in `src/brand.js`. Check availability of the name before adopting it.

## Run it locally (Termux or any computer)
    pip install -r requirements.txt
    python app.py                 # http://127.0.0.1:5000
No Node.js needed: the React front end is already built into `static/`. Without `MONGO_URI` the app keeps data in memory.

## MongoDB
Set `MONGO_URI` (Atlas `mongodb+srv://...` or a normal `mongodb://...`). Optional `MONGO_DB` (default `navs`).
- Collections: `institutions` (60 live colleges), `national` (the 2,590 simulated register entries the AICTE console reads), `students`, `registry`, `users` (every account: students, registrars, AICTE officer, employers; with status and a per-user authenticator secret), `reviews`, `appeals` (student replies), `submissions` (CSV uploads), `verifylog` (employer checks), `dsr` (student data requests), `pwchg`, `audit`, `meta`, and `_state` (sessions, codes, counters; expires by itself).
- The demo data is loaded **once**; later restarts keep it, and an older database is upgraded in place on start (new collections, indexes, accounts) without touching reviews, password changes or the audit log.
- `RESEED=1` for one start re-creates the demo colleges, students and accounts.
- If the URI is wrong the app falls back to memory and says so on the AICTE "Security & audit" page (Database row) and at `/healthz`.
- Atlas: *Network Access* must allow Render. Easiest for a demo: add `0.0.0.0/0`. Use a database user with access to one database only.
- Never paste the URI into code or chat. Keep it in the host's environment settings.

## Deploy on Render
1. Push this folder to a GitHub repo (`.gitignore` already keeps secrets out).
2. Render: **New + > Blueprint**, pick the repo (it reads `render.yaml`). Or **New + > Web Service** with
   build `pip install -r requirements.txt` and start `gunicorn app:app --workers 1 --threads 8 --timeout 60 --bind 0.0.0.0:$PORT`.
3. Set environment variables: `MONGO_URI` (yours), `SECRET_KEY` (random, keep it fixed), `APAAR_PROXY=1`, `MONGO_DB=navs`.
4. Open the `onrender.com` URL. Health check: `/healthz`.
Sessions, one-time codes, rate limits and lockouts live in **MongoDB**, so a restart or a sleeping free instance no longer signs people out (set `MONGO_REQUIRED=1`, as `render.yaml` does, so a bad Atlas connection stops the deploy instead of silently falling back to memory). One worker is used only because the free plan has little RAM.
Demo mode shows demo passwords and one-time codes on screen so anyone can try it. Fine for fictional data; set `DEMO_SHOW_OTP=0` only once a real delivery channel exists.

## Demo sign-in
Every role signs in the same way: **username + password + human check (hCaptcha), then a one-time code.** The AICTE console adds a third check, an authenticator-app code.
In demo mode (default) the page offers a "Use a demo account" button and shows one-time codes on screen, because no SMS or email is really sent.
Institutions: pick any of the 60 colleges on the sign-in page to see its own logo and records.

| Role | Username | Extra |
|---|---|---|
| Student | roll number (e.g. `r001-0001`) | |
| Institution | `reg.d0001` … `reg.d0060` | step-up code before uploads and reviews |
| AICTE | `aicte.officer` | authenticator code at sign-in and before decisions |
| Employer | `acme.hr`, `globex.hr` | |

## The AICTE national dashboard
- **2,650 institutions** in the register: the 60 demo colleges (real checks on their student records) plus 2,590 **simulated** entries with summary figures only. The simulated block uses a fixed seed, so numbers are identical on every start.
- **118 institutions flagged** (78 simulated + those the checks flag among the 60 demo colleges), split by reason (over approved intake, duplicate APAAR IDs, data mismatches) and by state.
- The institutions table is searched, filtered and paged on the server (state, result, source: demo college or simulated), with CSV export (logged in the audit trail).
- Constants to tune: `NAT_TOTAL` and `NAT_FLAGGED` in `app.py`.

## What is built in
- Two-step sign-in with an hCaptcha human check (verified on the server with your secret), lockout after 5 wrong tries, rate limits, same reply for known and unknown accounts.
- Step-up confirmation for sensitive actions; server-side sessions tied to the browser with idle limits (AICTE 10 min, colleges 15, others 30); sign out of all devices; password change with a policy.
- Authenticator codes are standard TOTP (RFC 6238): scan the QR on the AICTE "My security" page into any authenticator app and the codes will match.
- Strict content security policy (no inline scripts), CSRF + origin checks, HSTS over HTTPS, no-store on API responses, hash-chained audit log (keyed with the server secret), optional AICTE network allow-list.
- APAAR IDs masked everywhere; public certificate check shows identity and validity only; certificates show the college's demo logo, never AICTE's.
- Tests: `python -m unittest discover -s tests` (87 backend tests; a small built-in fake stands in for MongoDB, or `pip install mongomock`) and `tests/ui_smoke.mjs` (UI checks, see the file header).

## Settings (environment variables)
| Variable | Meaning |
|---|---|
| `MONGO_URI`, `MONGO_DB` | MongoDB connection and database name (default `navs`) |
| `RESEED=1` | reload demo colleges, students and accounts into MongoDB on this start |
| `SECRET_KEY` | fixed secret for hosting (otherwise one is created in `.secret_key`). Changing it changes demo passwords and breaks the audit chain check |
| `APAAR_PROXY=1` | trust a reverse proxy that handles HTTPS (Render, Caddy, nginx, Cloudflare) |
| `DEMO_SHOW_OTP=0` | stop showing codes on screen (needs a real delivery channel) |
| `HCAPTCHA_SECRET` | **required** while the human check is on: your hCaptcha secret. Keep it private; set it in the Render dashboard or your shell, never in git |
| `HCAPTCHA_SITEKEY` | your hCaptcha sitekey (public). Defaults to the one this project was set up with |
| `HCAPTCHA_HOSTNAMES=navs.onrender.com` | optional but recommended in production: only accept tokens solved on these site names (comma-separated) |
| `CAPTCHA=0` | turn the human check off (not recommended) |
| `GMAIL_USER`, `GMAIL_APP_PASSWORD`, `DEMO_OTP_REDIRECT` | send demo codes to **your own** inbox (free) |
| `AICTE_ALLOW_IPS=203.0.113.0/24,...` | open the AICTE console only from these networks |
| `APAAR_HTTPS=1` | serve over HTTPS directly (see `make_cert.sh`, `run_https.sh`) and mark cookies secure |
| `APAAR_HOST=0.0.0.0` | listen on your network (use HTTPS) |
| `APAAR_TESTING=1` | **tests only**: lets the UI test use stand-in human-check tokens. Never use it for real |

## Admin commands
There is no admin web page yet; `python manage.py` covers unlocking accounts, disabling accounts, resetting an authenticator (lost phone), recovery codes, adding employers and colleges, listing student data requests, and a JSON backup. AICTE officers can also unlock accounts through `/api/aicte/unlock`.

## What changed in v6
Sessions and counters moved fully to MongoDB with atomic counters; lockouts are per device (30 failures anywhere lock the account for 15 min; officers can unlock); browser-family binding instead of the full User-Agent; cookies persist; the page keeps the session alive while you are active. Certificates are Ed25519-signed (public key at `/api/cert-key`), expire after a year and can be revoked (AICTE "upheld"). CSV uploads are previewed, then applied to the student records; re-checks close the matching review item. Students can reply to their college, pause employer checks, see who checked them, and export their data. Employers get batch checks and a stored, capped log. Dates are read in common layouts. Audit entries carry sequence numbers and a stored head, so forks and cut-off tails are caught; noisy anonymous events are counted rather than stored.

## Rebuild the front end (only if you edit `src/`)
    npm install && npm run build      # Termux: pkg install nodejs

## Honest limits
Not independently security-tested. Demo codes are shown on screen. The registry is fake and most of the national register is simulated. If hCaptcha is unreachable or the secret is wrong, nobody can sign in (it fails closed). The AICTE logo is used only to identify the problem statement: get permission before publishing. See `LEGAL_REVIEW_CHECKLIST.md`.
