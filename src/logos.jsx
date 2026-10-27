import { BRAND } from "./brand.js";

export function AicteLogo({ size = 56, className = "", title = "AICTE logo" }) {
  return <img className={"aicte-logo " + className} src="/static/img/aicte-logo.png" width={size} height={size} alt={title} decoding="async" />;
}

export function BrandMark({ size = 36 }) {
  return (
    <svg viewBox="0 0 64 64" width={size} height={size} role="img" aria-label={BRAND.name + " mark"}>
      <rect width="64" height="64" rx="15" fill="#0B1B33" />
      <path d="M32 10 15 17.5v14c0 11.5 7.3 19.6 17 22.5 9.7-2.9 17-11 17-22.5v-14z" fill="#E98A15" />
      <path d="m23.5 32.5 6.2 6.2 11.3-12.6" fill="none" stroke="#0B1B33" strokeWidth="5.2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/* A decorative gear (echoes the AICTE emblem). */
export function Gear({ teeth = 18, r1 = 98, r2 = 82, hole = 34, className = "", style }) {
  const pts = [], step = (2 * Math.PI) / teeth;
  for (let i = 0; i < teeth; i++) { const a = i * step; [[a - step * .22, r2], [a - step * .13, r1], [a + step * .13, r1], [a + step * .22, r2]].forEach(([t, r]) => pts.push([100 + r * Math.cos(t), 100 + r * Math.sin(t)])); }
  const d = "M" + pts.map(p => p.map(n => n.toFixed(1)).join(" ")).join("L") + `Z M${100 + hole} 100 A${hole} ${hole} 0 1 0 ${100 - hole} 100 A${hole} ${hole} 0 1 0 ${100 + hole} 100Z`;
  return <svg viewBox="0 0 200 200" className={className} style={style} aria-hidden="true"><path d={d} fill="currentColor" fillRule="evenodd" /></svg>;
}

/* ---------- demo college logos: unique and deterministic for each college code ---------- */
const PAL = [["#12315F", "#E9B949"], ["#7A1F2B", "#F3E3C3"], ["#14532D", "#E9C46A"], ["#1D4ED8", "#E5E7EB"], ["#0F766E", "#F59E0B"], ["#581C87", "#FCD34D"], ["#27272A", "#FBBF24"], ["#9F1239", "#FDE68A"]];
const hash = s => { let h = 2166136261; for (const c of String(s)) { h ^= c.charCodeAt(0); h = Math.imul(h, 16777619); } return h >>> 0; };
const EMBLEMS = [
  c => <><path d="M32 17 20 21.5v9c0 8 5 13.6 12 15.7 7-2.1 12-7.7 12-15.7v-9z" fill="none" stroke={c} strokeWidth="2.4" strokeLinejoin="round" /><path d="M32 25v17M25 30c4-1.4 7 0 7 0s3-1.400 7 0" fill="none" stroke={c} strokeWidth="2" strokeLinecap="round" /></>,
  c => <><path d="M32 15c5 5.500 6 9 3 12 5-.5 7 4 5 8-1.500 3.200-5 5-8 5s-6.500-1.800-8-5c-2-4.500.500-8 3.500-9.500-.5-3 .5-6.500 4.500-10.500z" fill={c} /><path d="M24 47h16" stroke={c} strokeWidth="2.600" strokeLinecap="round" /></>,
  c => <><circle cx="32" cy="31" r="9" fill="none" stroke={c} strokeWidth="2.400" /><circle cx="32" cy="31" r="3" fill={c} />{[0, 45, 90, 135, 180, 225, 270, 315].map(a => <rect key={a} x="30.600" y="14" width="2.800" height="6" rx="1" fill={c} transform={`rotate(${a} 32 31)`} />)}</>,
  c => <><path d="M32 46V28" stroke={c} strokeWidth="2.600" strokeLinecap="round" /><path d="M32 30c-8 0-12-5-12-11 8 0 12 4 12 11zM32 36c8 0 12-5 12-11-8 0-12 4-12 11z" fill={c} /></>,
  c => <><path d="M14 40c5-4 9-4 14 0s9 4 14 0 7-3 8-3" fill="none" stroke={c} strokeWidth="2.400" strokeLinecap="round" /><path d="M20 33a12 12 0 0 1 24 0" fill="none" stroke={c} strokeWidth="2.400" strokeLinecap="round" /><path d="M32 14v5M18 19l3 3.500M46 19l-3 3.500" stroke={c} strokeWidth="2.200" strokeLinecap="round" /></>,
  c => <path d="M32 14l4.400 9.400 10.300 1.300-7.600 7.100 2 10.200L32 36.900 22.900 42l2-10.200-7.600-7.100 10.300-1.300z" fill={c} />,
  c => <><path d="M16 22c6-2 12-1 16 3 4-4 10-5 16-3v22c-6-2-12-1-16 3-4-4-10-5-16-3z" fill="none" stroke={c} strokeWidth="2.400" strokeLinejoin="round" /><path d="M32 25v22" stroke={c} strokeWidth="2.200" /></>,
  c => <><path d="M12 46 25 24l7 11 5-8 15 19z" fill={c} /><circle cx="43" cy="19" r="4" fill={c} /></>,
];
export function collegeInitials(name = "") { const w = name.split(/\s+/).filter(x => x && !/^(of|and|the|for)$/i.test(x)); return w.slice(0, 3).map(x => x[0].toUpperCase()).join(""); }
export function CollegeLogo({ code = "", name = "", size = 44, ring = true }) {
  const h = hash(code), [a, b] = PAL[(h >>> 4) % PAL.length], E = EMBLEMS[h % EMBLEMS.length], id = "cl" + h;
  return (
    <svg viewBox="0 0 64 64" width={size} height={size} role="img" aria-label={`Demo logo of ${name || code}`} style={{ flex: "none", display: "block" }}>
      <defs><linearGradient id={id} x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor={a} /><stop offset="1" stopColor={a} stopOpacity=".78" /></linearGradient></defs>
      <circle cx="32" cy="32" r="31" fill={`url(#${id})`} />
      {ring && <circle cx="32" cy="32" r="28" fill="none" stroke={b} strokeWidth="1.200" strokeOpacity=".85" />}
      <g transform="translate(0 -2)">{E(b)}</g>
      <text x="32" y="55.500" textAnchor="middle" fontFamily="'Source Serif 4',Georgia,serif" fontWeight="700" fontSize="8.500" letterSpacing=".6" fill={b}>{collegeInitials(name) || "—"}</text>
    </svg>
  );
}

/* ---------- illustrated demo avatars (no real photos) ---------- */
const SK = ["#f2c6a0", "#e2ad84", "#c58a62", "#8f5d3d", "#f5d5bd"], BG = ["#dbe7f5", "#e3f1ee", "#f6ead2", "#e9e4f5", "#fbe3e0"], SHIRT = ["#2b4f78", "#0d7a6f", "#7a4a8a", "#b0302b", "#9a5b00"];
const HAIR = [["#1b1b1f", "", "M20 27c0-11 5-16 12-16s12 5 12 16c-2-5-6-8-12-8s-10 3-12 8z"], ["#5a3a22", "", "M20 28c0-12 5-17 12-17 8 0 12 5 12 17-1-6-3-9-9-10-4 3-10 5-15 10z"],
  ["#201a17", '<circle cx="22" cy="22" r="5"/><circle cx="32" cy="17" r="6"/><circle cx="42" cy="22" r="5"/>', "M21 28c0-8 4-11 11-11s11 3 11 11c-3-4-6-6-11-6s-8 2-11 6z"], ["#2a2420", "", "M21 26c1-9 5-13 11-13s10 4 11 13c-3-3-6-4-11-4s-8 1-11 4z"],
  ["#3a2a1e", "", "M20 27c0-11 5-16 12-16s12 5 12 16c-2-5-6-8-12-8s-10 3-12 8z", 1], ["#1c1517", '<path d="M19 28c0-13 6-19 13-19s13 6 13 19v24H38V30H26v22h-7z"/>', "M20 27c3-9 8-12 12-12s9 3 12 12c-5-4-8-5-12-5s-7 1-12 5z"],
  ["#5b3a24", '<path d="M19 27c0-12 6-17 13-17s13 5 13 17v8H19z"/>', "M20 28c1-9 6-13 12-13s11 4 12 13c-6-3-8-6-12-7-4 1-7 4-12 7z"], ["#3b2a2a", '<circle cx="32" cy="9" r="6"/>', "M20 27c0-10 5-15 12-15s12 5 12 15c-4-4-7-6-12-6s-8 2-12 6z"],
  ["#7a3b1d", '<path d="M18 30c0-14 6-20 14-20s14 6 14 20v22h-7V32H25v20h-7z"/>', "M19 28c2-9 8-13 13-13s11 4 13 13c-6-4-9-6-13-6s-7 2-13 6z"], ["#241b22", '<path d="M43 20c6 2 9 8 7 22l-5-2c1-8 0-13-2-16z"/>', "M20 27c0-11 5-16 12-16s12 5 12 16c-2-5-6-8-12-8s-10 3-12 8z"]];
export function Avatar({ i = 0, size = 48 }) {
  i = (((+i || 0) % 10) + 10) % 10; const k = SK[(i * 3) % 5], h = HAIR[i];
  return (
    <svg viewBox="0 0 64 64" width={size} height={size} role="img" aria-label="Demo avatar" style={{ borderRadius: size > 40 ? 16 : 10, flex: "none", display: "block" }}>
      <rect width="64" height="64" fill={BG[i % 5]} />
      <g fill={h[0]} dangerouslySetInnerHTML={{ __html: h[1] }} />
      <path d="M8 64c2-13 13-17 24-17s22 4 24 17z" fill={SHIRT[(i * 2) % 5]} />
      <rect x="28" y="38" width="8" height="11" rx="3" fill={k} style={{ filter: "brightness(.9)" }} />
      <ellipse cx="32" cy="28" rx="11" ry="13" fill={k} />
      <path d={h[2]} fill={h[0]} />
      {h[3] ? <path d="M22 32c1 9 5 12 10 12s9-3 10-12c-2 4-5 5-10 5s-8-1-10-5z" fill={h[0]} /> : null}
      <circle cx="27.500" cy="28.500" r="1.300" fill="#231a14" /><circle cx="36.500" cy="28.500" r="1.300" fill="#231a14" />
      <path d="M28.500 34q3.500 2.600 7 0" stroke="#7a3d2a" strokeWidth="1.400" fill="none" strokeLinecap="round" />
    </svg>
  );
}
