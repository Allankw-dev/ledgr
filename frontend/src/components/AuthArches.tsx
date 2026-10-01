/**
 * Decorative architectural arches behind the sign-in / sign-up card:
 * nested arches rising from the bottom edge (like a row of doorways), plus a
 * few small floating ones. Purely visual — hidden from screen readers and
 * ignoring the pointer — and tinted with the same violet / cyan / green as
 * the rest of the auth page.
 */

const CX = 600; // horizontal centre of the artwork
const BASE = 800; // bottom edge
const SIDE = 170; // length of the straight sides below each arch's curve

/** One arch outline: straight sides up from the base, then a semicircle. */
function archPath(cx: number, r: number, base = BASE, side = SIDE) {
  const springY = base - side; // where the curve starts
  return `M ${cx - r} ${base} V ${springY} A ${r} ${r} 0 0 1 ${cx + r} ${springY} V ${base}`;
}

const NESTED = [
  { r: 120, o: 0.75 },
  { r: 200, o: 0.6 },
  { r: 280, o: 0.46 },
  { r: 360, o: 0.34 },
  { r: 440, o: 0.24 },
  { r: 520, o: 0.16 },
];

export function AuthArches() {
  return (
    <svg
      className="auth-arches"
      viewBox="0 0 1200 800"
      preserveAspectRatio="xMidYMax slice"
      aria-hidden="true"
      focusable="false"
    >
      <defs>
        <linearGradient id="arch-stroke" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#3FD9FF" />
          <stop offset="55%" stopColor="#8B6CFF" />
          <stop offset="100%" stopColor="#39FF88" />
        </linearGradient>
        <linearGradient id="arch-door" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#8B6CFF" stopOpacity="0.14" />
          <stop offset="100%" stopColor="#8B6CFF" stopOpacity="0" />
        </linearGradient>
      </defs>

      {/* the innermost "doorway" gets a soft glow fill */}
      <path d={`${archPath(CX, NESTED[0].r)} Z`} fill="url(#arch-door)" stroke="none" />

      {NESTED.map(({ r, o }) => (
        <path key={r} d={archPath(CX, r)} fill="none" stroke="url(#arch-stroke)" strokeOpacity={o} strokeWidth={1.5} />
      ))}

      {/* small floating arches for depth */}
      <g fill="none" stroke="url(#arch-stroke)" strokeWidth={1.25}>
        <path d={archPath(150, 46, 210, 44)} strokeOpacity={0.35} />
        <path d={archPath(150, 70, 210, 44)} strokeOpacity={0.18} />
        <path d={archPath(1070, 38, 330, 36)} strokeOpacity={0.3} />
        <path d={archPath(1070, 58, 330, 36)} strokeOpacity={0.15} />
        <path d={archPath(1010, 30, 90, 28)} strokeOpacity={0.22} />
      </g>
    </svg>
  );
}

/** A quieter white-on-gradient version for the sliding "New to Ledgr?" panel. */
export function OverlayArches() {
  const radii = [70, 120, 170, 220];
  return (
    <svg
      className="auth-overlay-arches"
      viewBox="0 0 400 600"
      preserveAspectRatio="xMidYMax slice"
      aria-hidden="true"
      focusable="false"
    >
      {radii.map((r, i) => (
        <path
          key={r}
          d={archPath(200, r, 600, 110)}
          fill={i === 0 ? 'rgba(255,255,255,0.06)' : 'none'}
          stroke="#fff"
          strokeOpacity={0.3 - i * 0.06}
          strokeWidth={1.25}
        />
      ))}
    </svg>
  );
}
