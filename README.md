# NAVS: National Academic Verification System (APAAR verification prototype)

**Everything here is fictional.** 60 invented colleges with student records, a simulated national register of 2,650 institutions, 600 invented students, invented certificates. It is not connected to AICTE, NAD, APAAR or DigiLocker and is not an official AICTE service. Prototype for SIH26263.
The product name is one constant in `src/brand.js`. Check availability of the name before adopting it.


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


## Honest limits
Not independently security-tested. Demo codes are shown on screen. The registry is fake and most of the national register is simulated. If hCaptcha is unreachable or the secret is wrong, nobody can sign in (it fails closed). The AICTE logo is used only to identify the problem statement
