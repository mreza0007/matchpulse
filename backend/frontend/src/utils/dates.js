export function parseKickoffDate(match) {
  const kickoffValue = match?.kickoff_iso || match?.kickoff_utc || match?.kickoff;

  if (!kickoffValue || typeof kickoffValue !== "string") return null;
  if (!/^\d{4}-\d{2}-\d{2}T/.test(kickoffValue)) return null;

  const isoValue = kickoffValue.endsWith("Z") || /[+-]\d{2}:\d{2}$/.test(kickoffValue)
    ? kickoffValue
    : `${kickoffValue}Z`;
  const date = new Date(isoValue);

  return Number.isNaN(date.getTime()) ? null : date;
}

export function getKickoffTime(match) {
  const kickoffTs = Number(match?.kickoff_ts ?? match?.kickoff_timestamp);

  if (Number.isFinite(kickoffTs)) {
    return kickoffTs * 1000;
  }

  return parseKickoffDate(match)?.getTime() ?? Number.POSITIVE_INFINITY;
}

export function getMatchDateKey(match) {
  if (match?.date_key) return match.date_key;

  const kickoffDate = parseKickoffDate(match);
  if (!kickoffDate) {
    return String(match?.date_iran || match?.date || match?.date_fa || "").trim();
  }

  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Tehran",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(kickoffDate);
}

export function formatTehranMatchDateTime(match, lang) {
  const kickoffDate = parseKickoffDate(match);

  if (!kickoffDate) {
    return {
      date: match?.date_iran || "",
      time: match?.time_iran || "",
      compact: [match?.date_iran, match?.time_iran].filter(Boolean).join(" - "),
    };
  }

  const locale = lang === "fa" ? "fa-IR-u-ca-persian" : "en-US";
  const date = new Intl.DateTimeFormat(locale, {
    timeZone: "Asia/Tehran",
    month: "short",
    day: "numeric",
    weekday: "short",
  }).format(kickoffDate);
  const time = new Intl.DateTimeFormat(locale, {
    timeZone: "Asia/Tehran",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(kickoffDate);

  return {
    date,
    time,
    compact: `${date} - ${time}`,
  };
}

export function getGroupLabel(match, lang) {
  if (lang === "fa") {
    return [match.weekday_fa, match.date_label_fa || match.date_iran].filter(Boolean).join(" - ");
  }

  return formatTehranMatchDateTime(match, lang).date;
}

export function groupMatchesByDate(matches, lang) {
  const groups = [];

  matches.forEach((match) => {
    const dateKey = getMatchDateKey(match) || `unknown-${groups.length}`;
    const currentGroup = groups[groups.length - 1];

    if (currentGroup?.dateKey === dateKey) {
      currentGroup.matches.push(match);
      return;
    }

    groups.push({
      dateKey,
      label: getGroupLabel(match, lang),
      match,
      matches: [match],
    });
  });

  return groups;
}


export function localizeCountdownDigits(value, lang) {
  if (lang !== "fa") return value;
  return value.replace(/\d/g, (digit) => "۰۱۲۳۴۵۶۷۸۹"[Number(digit)]);
}

export function formatCountdown(milliseconds, lang) {
  const totalSeconds = Math.max(0, Math.floor(milliseconds / 1000));
  const days = Math.floor(totalSeconds / 86400);
  const hours = Math.floor((totalSeconds % 86400) / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  const twoDigits = (value) => String(value).padStart(2, "0");

  if (days > 0) {
    const dayCountdown = lang === "fa"
      ? `${days} روز و ${twoDigits(hours)}:${twoDigits(minutes)}`
      : `${days}d ${twoDigits(hours)}:${twoDigits(minutes)}`;
    return localizeCountdownDigits(dayCountdown, lang);
  }

  return localizeCountdownDigits(
    `${twoDigits(hours)}:${twoDigits(minutes)}:${twoDigits(seconds)}`,
    lang,
  );
}

export function getTehranCalendarDates(now = new Date()) {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: "Asia/Tehran",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(now);
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  const year = Number(values.year);
  const month = Number(values.month);
  const day = Number(values.day);

  const formatOffset = (offset) => {
    const date = new Date(Date.UTC(year, month - 1, day + offset));
    return [date.getUTCFullYear(), date.getUTCMonth() + 1, date.getUTCDate()]
      .map((value, index) => String(value).padStart(index === 0 ? 4 : 2, "0"))
      .join("-");
  };

  return {
    today: formatOffset(0),
    tomorrow: formatOffset(1),
  };
}
