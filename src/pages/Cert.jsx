import { Avatar, CollegeLogo } from "../logos.jsx";
import { Status } from "../ui.jsx";
/* Certificates carry the COLLEGE's demo logo, never the AICTE logo, so they can't be mistaken for an official AICTE document. */
export default function Certificate({ c }) {
  return (
    <article className="cert">
      <header className="cert-h"><CollegeLogo code={c.aicte_id} name={c.institution} size={58} /><div><small>Demo verification certificate</small><b>{c.institution}</b><span>{c.city} · {c.aicte_id}</span></div></header>
      <h3>{c.kind || "Enrolment Verification"}</h3>
      {c.face != null && <div className="cert-av"><Avatar i={c.face} size={78} /></div>}
      <p className="muted c">This certifies that</p>
      <div className="cert-nm">{c.name}</div>
      <div className="cert-line">APAAR ID <b>{c.apaar}</b>{c.roll ? <> · Roll <b>{c.roll}</b></> : null}</div>
      <p className="c">is recorded as a student of <b>{c.program}</b>, admitted {c.admitted}.</p>
      {c.kind === "Academic Standing" && <p className="c">Demo CGPA <b>{c.cgpa}</b></p>}
      <footer className="cert-f"><img src={`/api/qr/${encodeURIComponent(c.cert_id)}.svg`} width="112" height="112" alt={`QR code for certificate ${c.cert_id}`} /><div><small>Certificate ID</small><b className="mono">{c.cert_id}</b><small>Issued {c.issued}{c.expires ? ` · Valid until ${c.expires}` : ""}</small><Status s={c.status || (c.valid ? "VALID" : "UNDER REVIEW")} /></div></footer>
      <p className="cert-note">{c.note} Scan the QR code to verify.{c.sig ? ` Digitally signed (key ${c.kid}).` : ""}</p>
      <span className="cert-wm" aria-hidden="true">DEMO</span>
    </article>
  );
}
