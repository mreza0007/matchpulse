export const TEAM_FLAG_OVERRIDES = {
  England: "gb-eng",
  Scotland: "gb-sct",
  Wales: "gb-wls",
  "Northern Ireland": "gb-nir",
  "United States": "us",
  USA: "us",
  "Korea Republic": "kr",
  "South Korea": "kr",
  "Côte d'Ivoire": "ci",
  "Ivory Coast": "ci",
};

export function getCountryCodeFromFlagEmoji(flagEmoji) {
  if (!flagEmoji || typeof flagEmoji !== "string") return "";

  const codePoints = Array.from(flagEmoji.trim());
  if (codePoints.length < 2) return "";

  const letters = codePoints
    .slice(0, 2)
    .map((char) => char.codePointAt(0) - 127397);

  if (letters.some((letter) => letter < 65 || letter > 90)) return "";

  return letters.map((letter) => String.fromCharCode(letter).toLowerCase()).join("");
}

export function getFlagImageUrl(flagEmoji, teamName) {
  const code = TEAM_FLAG_OVERRIDES[teamName] || getCountryCodeFromFlagEmoji(flagEmoji);
  return code ? `https://flagcdn.com/w80/${code}.png` : "";
}

export function getLocalizedTeamName(match, side, lang) {
  const localizedKey = `${side}_${lang}`;
  const englishKey = `${side}_en`;
  const persianKey = `${side}_fa`;

  return match?.[localizedKey] || match?.[englishKey] || match?.[persianKey] || "";
}

export function normalizeTeamKey(value) {
  return String(value || "").trim().toLowerCase().replace(/\s+/g, "");
}
