import { useEffect, useState } from "react";
import { getHeroStatusLine } from "../../utils/matches.js";

export default function HeroMatchCard({ label, mode, match, lang, t, children }) {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (mode !== "upcoming") return undefined;

    const countdownTimer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(countdownTimer);
  }, [match?.id, mode]);

  const statusLine = getHeroStatusLine(match, mode, lang, t, now);

  return (
    <section className={`smart-hero-card ${mode}`} aria-label={label}>
      <div className="smart-hero-heading">
        <span className="smart-hero-kicker">{label}</span>
      </div>
      <div className={`smart-hero-status ${statusLine.isCountdown ? "countdown" : ""}`}>
        {statusLine.label && <span>{statusLine.label}</span>}
        <strong dir={statusLine.isCountdown ? "ltr" : t.dir}>{statusLine.value}</strong>
      </div>
      {children}
    </section>
  );
}
