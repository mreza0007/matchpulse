import { useState } from "react";
import { COMPETITIONS } from "../../config/competitions.js";
import { getCompetitionName } from "../../utils/competitions.js";

export default function CompetitionLogo({ competition, eager = false, lang = "en" }) {
  const [failedSrc, setFailedSrc] = useState("");
  const trustedConfig = COMPETITIONS[competition.competition_key];
  const logoSrc = competition.logo_url
    || competition.logo
    || competition.logo_src
    || trustedConfig?.logoSrc
    || "";
  const competitionName = getCompetitionName(competition, lang);

  const hasError = Boolean(logoSrc && failedSrc === logoSrc);

  if (!logoSrc || hasError) {
    return (
      <span
        aria-label={competitionName}
        className="competition-directory-logo-fallback"
        role="img"
      >
        {trustedConfig?.logoFallback || "⚽"}
      </span>
    );
  }

  return (
    <img
      alt={competitionName}
      className="competition-directory-logo"
      decoding="async"
      loading={eager ? "eager" : "lazy"}
      onError={() => setFailedSrc(logoSrc)}
      src={logoSrc}
    />
  );
}
