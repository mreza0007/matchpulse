import { useState } from "react";
import { COMPETITIONS } from "../../config/competitions.js";

export default function CompetitionLogo({ competition }) {
  const [hasError, setHasError] = useState(false);
  const trustedConfig = COMPETITIONS[competition.competition_key];
  const logoSrc = trustedConfig?.logoSrc || "";

  if (!logoSrc || hasError) {
    return (
      <span className="competition-directory-logo-fallback" aria-hidden="true">
        {trustedConfig?.logoFallback || "⚽"}
      </span>
    );
  }

  return (
    <img
      alt=""
      className="competition-directory-logo"
      onError={() => setHasError(true)}
      src={logoSrc}
    />
  );
}
