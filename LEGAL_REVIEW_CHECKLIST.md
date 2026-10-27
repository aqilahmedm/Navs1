# Legal review checklist (for your lawyer)

This is a list of questions to take to qualified counsel. It is **not legal advice**, and nothing here has been reviewed by a lawyer.
The demo uses invented data only, so none of this applies until real student data is involved.

## 1. Who is responsible
- Who is the data fiduciary / controller (AICTE, each institution, or both for different purposes), and who are the processors (hosting, SMS/email provider)?
- Written agreements with every processor; where the data is stored and whether it leaves India.

## 2. Personal data law (India)
- Digital Personal Data Protection Act, 2023 and its Rules: notice, lawful basis or consent, purpose limitation, data minimisation, retention and erasure.
- Students under 18: verifiable parental or guardian consent rules and any exemptions that may apply to educational bodies.
- Rights handling: access, correction, erasure, grievance officer and response times.
- Breach detection and notification process (to the regulator and to affected students).
- Information Technology Act obligations on reasonable security practices; CERT-In incident reporting.

## 3. APAAR, ABC and education rules
- Current Ministry of Education / UGC / AICTE guidelines on APAAR ID, consent for creating and sharing APAAR, and who may verify it.
- Whether this tool may hold or display APAAR IDs at all, and in what form (this demo masks them).
- Any rule on linking Aadhaar or other identifiers (this demo does not use Aadhaar).

## 4. Verification and certificates
- Whether a certificate from this system may carry AICTE branding or imply official issue. The demo certificates are labelled DEMO and carry the (invented) college logo only, never the AICTE logo, so they can't be mistaken for an official document.
- Legal effect of a "valid" or "under review" status, liability for wrong flags, and an appeal route for students who are flagged by mistake.
- Whether automated flags need a human decision before any adverse effect (this build requires a written reviewer decision and an AICTE decision for escalations).

## 5. Employers and third parties
- Basis and consent for employers to verify a student's status; what they may see (demo: name, college, programme, validity only).
- Retention of employer lookup logs.

## 6. Security and operations (ask your engineers and your lawyer)
- HTTPS everywhere, encryption at rest, key management, access control reviews, backups, log retention.
- Real SMS/email OTP gateway terms, and a persistent rate-limit store.
- Independent security testing before launch.

## 7. Accessibility and language
- Accessibility obligations for public-facing services; multilingual notices.
- CAPTCHAs are an accessibility barrier. hCaptcha offers an accessibility cookie and audio/alternative challenges, and it is a third-party processor (it sees visitors' IP addresses and browser signals), so list it in the privacy notice. A production service should use a bot defence that doesn't need a person to solve a puzzle (for example proof-of-work or a managed service), plus a non-CAPTCHA route for people who can't use either.

## 8. Intellectual property
- **Use of the AICTE name and logo.** This prototype shows the AICTE logo on the home page, login page and AICTE console to identify the problem statement it addresses (SIH26263), with a visible "not an official AICTE service" notice. Get written permission before publishing it publicly or using the logo beyond the hackathon, and remove it if permission is refused. Never put it on certificates or QR pages.
- College logos in the demo are invented and generated in code. Don't replace them with real institutions' logos without their permission.
- The product name "NAVS" (National Academic Verification System) is a placeholder: check that it isn't already used or registered before adopting it.
- Licences of the fonts and libraries used (Source Serif 4, Public Sans, Noto Sans Devanagari are SIL OFL; React, Lucide, Flask, segno and others have their own licences).
