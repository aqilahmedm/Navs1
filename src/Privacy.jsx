import { Modal } from "./ui.jsx";
import { BRAND } from "./brand.js";
const WHO = [["Student", "Own record, own certificates, own check results"], ["Institution", "Only its own students, with APAAR IDs masked"], ["AICTE officer", "All institutions, flags, escalations and the audit log"], ["Employer / public QR", "Name, college, programme and validity only. No marks, roll number, photo or flags"]];
const HOW = ["Demo data lives in memory (or MongoDB if you configure it) and is re-created on restart", "One-time codes are stored hashed, used once and never logged", "The audit log records the action and the actor, not personal details", "Reviewer decisions need a written reason and are logged"];
export default function Privacy({ open, onClose }) {
  return (
    <Modal open={open} onClose={onClose} title="Privacy & data use" sub="Demo notice, not legal advice">
      <div className="note warn">This prototype runs on invented data only. It is not connected to AICTE, NAD, APAAR or DigiLocker.</div>
      <h4 className="mt">Who sees what</h4>
      <table className="kv-table"><tbody>{WHO.map(([a, b]) => <tr key={a}><th>{a}</th><td>{b}</td></tr>)}</tbody></table>
      <h4 className="mt">How data is handled</h4>
      <ul className="checks">{HOW.map(x => <li key={x}><i className="ic pass">✓</i><div><span>{x}</span></div></li>)}</ul>
      <h4 className="mt">Before any real use</h4>
      <p className="muted">{BRAND.name} would need a lawful basis and notice, parental consent for under-18 students, retention limits, a way to handle access, correction and erasure requests, a breach process, and an independent security test. See LEGAL_REVIEW_CHECKLIST.md for the list to take to a lawyer.</p>
    </Modal>
  );
}
