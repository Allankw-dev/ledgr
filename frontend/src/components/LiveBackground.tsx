import { memo } from 'react';

// Fixed, deterministic set of floating motes (no Math.random, so the
// background never re-rolls when the app re-renders).
const MOTES = Array.from({ length: 16 }, (_, i) => ({
  left: (i * 37 + 9) % 100,
  size: 2 + (i % 3),
  dur: 22 + ((i * 7) % 17),
  delay: -((i * 5) % 26),
  dx: ((i % 2 === 0 ? 1 : -1) * (20 + ((i * 11) % 50))),
  color: i % 3 === 0 ? '#3FD9FF' : '#39FF88',
}));

/**
 * The living backdrop behind every screen: drifting green / teal / blue
 * lights, a soft band of light that sweeps across now and then, and tiny
 * motes floating upward. Mounted once at the app root. Pure CSS animation
 * (see "LIVE BACKGROUND" in index.css), so it costs almost nothing and
 * switches itself off for people who prefer reduced motion.
 */
export const LiveBackground = memo(function LiveBackground() {
  return (
    <div className="live-bg" aria-hidden="true">
      <span className="live-orb live-orb--a" />
      <span className="live-orb live-orb--b" />
      <span className="live-orb live-orb--c" />
      <span className="live-sweep" />
      {MOTES.map((m, i) => (
        <span
          key={i}
          className="live-mote"
          style={
            {
              left: `${m.left}%`,
              width: m.size,
              height: m.size,
              '--dur': `${m.dur}s`,
              '--delay': `${m.delay}s`,
              '--dx': `${m.dx}px`,
              '--mote': m.color,
            } as React.CSSProperties
          }
        />
      ))}
    </div>
  );
});
