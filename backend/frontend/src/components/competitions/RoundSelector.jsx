import { useEffect, useRef } from "react";
import { scopeLabel } from "../../utils/competitionRounds.js";

function reducedMotionPreferred() {
  return typeof window !== "undefined"
    && typeof window.matchMedia === "function"
    && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

export default function RoundSelector({
  lang,
  mode,
  onSelect,
  relevantReason,
  relevantScopeKey,
  scopes,
  selectedScopeKey,
  t,
}) {
  const chipRefs = useRef(new Map());

  useEffect(() => {
    const selectedChip = chipRefs.current.get(selectedScopeKey);
    if (typeof selectedChip?.scrollIntoView !== "function") return;
    selectedChip.scrollIntoView({
      behavior: reducedMotionPreferred() ? "auto" : "smooth",
      block: "nearest",
      inline: "center",
    });
  }, [selectedScopeKey]);

  if (!Array.isArray(scopes) || scopes.length === 0) return null;
  const showCurrentMarker = ["live", "active"].includes(relevantReason);

  return (
    <div className="competition-round-navigation">
      <div
        aria-label={t.selectCompetitionRound}
        className="competition-round-selector"
        dir={lang === "fa" ? "rtl" : "ltr"}
        role="tablist"
      >
        {scopes.map((scope) => {
          const selected = scope.key === selectedScopeKey;
          const current = scope.key === relevantScopeKey && showCurrentMarker;
          return (
            <button
              aria-selected={selected}
              className={selected ? "active" : ""}
              key={scope.key}
              onClick={() => onSelect(scope.key)}
              ref={(node) => {
                if (node) chipRefs.current.set(scope.key, node);
                else chipRefs.current.delete(scope.key);
              }}
              role="tab"
              type="button"
            >
              <span>{scopeLabel(scope, lang)}</span>
              {current && <small>{t.currentRoundMarker}</small>}
            </button>
          );
        })}
      </div>

      {relevantScopeKey && selectedScopeKey !== relevantScopeKey && (
        <button
          className="competition-current-round-button"
          onClick={() => onSelect(relevantScopeKey)}
          type="button"
        >
          {mode === "stage" ? t.returnCurrentStage : t.returnCurrentRound}
        </button>
      )}
    </div>
  );
}
