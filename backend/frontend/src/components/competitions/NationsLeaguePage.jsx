import { useState } from "react";
import CompetitionPage from "../../pages/CompetitionPage.jsx";
import {
  nationsLeagueDivision,
  nationsLeaguePresentation,
  resolveNationsLeagueDivision,
} from "../../utils/competitionPresentation.js";

export default function NationsLeaguePage({ divisions, initialKey, ...props }) {
  const [selectedKey, setSelectedKey] = useState(initialKey);
  const competition = resolveNationsLeagueDivision(divisions, selectedKey);
  if (!competition) return null;

  const selector = (
    <div
      className="competition-division-selector"
      dir={props.lang === "fa" ? "rtl" : "ltr"}
      role="tablist"
      aria-label={props.lang === "fa" ? "انتخاب لیگ" : "Select division"}
    >
      {divisions.map((division) => (
        <button
          key={division.competition_key}
          role="tab"
          type="button"
          aria-selected={division.competition_key === competition.competition_key}
          className={division.competition_key === competition.competition_key ? "active" : ""}
          onClick={() => setSelectedKey(division.competition_key)}
        >
          {props.lang === "fa" ? "لیگ" : "League"} <bdi>{nationsLeagueDivision(division.competition_key).toUpperCase()}</bdi>
        </button>
      ))}
    </div>
  );

  return (
    <CompetitionPage
      {...props}
      competition={competition}
      presentation={nationsLeaguePresentation()}
      divisionSelector={selector}
      divisionLabel={`${props.lang === "fa" ? "لیگ" : "League"} ${nationsLeagueDivision(competition.competition_key).toUpperCase()}`}
      key={`${competition.competition_key}:${competition.season_key}`}
    />
  );
}
