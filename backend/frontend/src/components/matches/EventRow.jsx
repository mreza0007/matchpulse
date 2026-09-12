import TeamFlag from "../teams/TeamFlag.jsx";
import {
  getEventPlayer,
  getEventTypeLabel,
  getFirstEventValue,
  getNormalizedEventType,
  getRenderedEventIcon,
  resolveEventTeam,
} from "../../utils/events.js";

export default function EventRow({ event, match, lang, t, index }) {
  const type = getNormalizedEventType(event);
  const team = resolveEventTeam(event, match, lang);
  const player = getEventPlayer(event);
  const eventMinute = event.display_minute || event.raw_minute || event.minute || "";
  const assist = getFirstEventValue(event, ["assist", "assist_name", "assistName"]);
  const playerIn = getFirstEventValue(
    event,
    ["player_in_name", "player_in", "playerIn", "in_player"],
  );
  const playerOut = getFirstEventValue(
    event,
    ["player_out_name", "player_out", "playerOut", "out_player"],
  );
  const providedLabel = lang === "fa" ? event.label_fa : event.label_en;
  const title = providedLabel || getEventTypeLabel(type, lang);
  const eventIcon = event.icon || getRenderedEventIcon(type);
  const isGoal = ["goal", "penalty_goal", "own_goal"].includes(type);
  const hasScore = (
    Number.isInteger(event.home_score)
    && Number.isInteger(event.away_score)
    && event.home_score >= 0
    && event.away_score >= 0
  );
  const description = getFirstEventValue(event, ["description"]);
  const key = [eventMinute, type, player, playerIn, playerOut, index].join("-");

  return (
    <li className={`event-row ${type}`} key={key}>
      <span className="event-minute">{eventMinute}'</span>
      <span className="event-icon" aria-hidden="true">
        {eventIcon}
      </span>
      <div className="event-body">
        <strong>{title}</strong>
        {type === "substitution" ? (
          <div className="event-lines">
            {playerIn && <span>{"\ud83d\udfe2\u2b06\ufe0f "}{playerIn}</span>}
            {playerOut && <span>{"\ud83d\udd34\u2b07\ufe0f "}{playerOut}</span>}
          </div>
        ) : (
          player && <span className="event-player">{player}</span>
        )}
        {isGoal && assist && (
          <span className="event-assist">{"\ud83d\udc5f "}{t.assistLabel}: {assist}</span>
        )}
        {hasScore && (
          <span className="event-score">{event.home_score} - {event.away_score}</span>
        )}
        {description && <span className="event-description">{description}</span>}
        {(team.name || team.flag || team.logo) && (
          <small className="event-team">
            <TeamFlag
              flagEmoji={team.flag}
              logoUrl={team.logo}
              teamName={team.englishName}
            />
            {team.name}
          </small>
        )}
      </div>
    </li>
  );
}
