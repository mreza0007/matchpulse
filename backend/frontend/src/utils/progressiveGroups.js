export const INITIAL_VISIBLE_MATCH_GROUPS = 10;
export const MATCH_GROUP_CHUNK_SIZE = 8;

export function initialVisibleGroupCount(totalGroups) {
  return Math.min(INITIAL_VISIBLE_MATCH_GROUPS, Math.max(0, totalGroups));
}

export function nextVisibleGroupCount(currentCount, totalGroups) {
  return Math.min(
    Math.max(0, totalGroups),
    Math.max(0, currentCount) + MATCH_GROUP_CHUNK_SIZE,
  );
}

export function visibleGroupSlice(groups, visibleCount) {
  return groups.slice(0, Math.max(0, visibleCount));
}
