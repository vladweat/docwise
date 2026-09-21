const CITATION_HINT_KEY = "dw_citation_hint_seen";

export function hasSeenCitationHint(): boolean {
  if (typeof window === "undefined") return true;
  return window.localStorage.getItem(CITATION_HINT_KEY) === "1";
}

export function markCitationHintSeen(): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(CITATION_HINT_KEY, "1");
}
