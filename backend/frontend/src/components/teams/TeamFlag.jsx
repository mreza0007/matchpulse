import { useState } from "react";
import { getFlagImageUrl } from "../../utils/teams.js";

export default function TeamFlag({ flagEmoji, teamName, logoUrl = "" }) {
  const flagImageUrl = getFlagImageUrl(flagEmoji, teamName);
  const backendLogoUrl = typeof logoUrl === "string" && /^https?:\/\//i.test(logoUrl.trim())
    ? logoUrl.trim()
    : "";
  const imageUrl = flagImageUrl || backendLogoUrl;
  const isTeamLogo = !flagImageUrl && Boolean(backendLogoUrl);
  const [failedImageUrl, setFailedImageUrl] = useState("");
  const hasError = failedImageUrl === imageUrl;

  return (
    <span className={`team-flag ${isTeamLogo ? "team-logo" : ""}`} aria-hidden="true">
      {imageUrl && !hasError ? (
        <img
          className={isTeamLogo ? "team-logo-img" : "team-flag-img"}
          src={imageUrl}
          alt=""
          loading="lazy"
          onError={() => setFailedImageUrl(imageUrl)}
        />
      ) : (
        <span className="team-flag-fallback">{flagEmoji || "⚽"}</span>
      )}
    </span>
  );
}
