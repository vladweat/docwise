const PENDING_QUESTION_KEY = "dw_pending_question";

export function stashPendingQuestion(text: string): void {
  if (typeof window === "undefined") return;
  window.sessionStorage.setItem(PENDING_QUESTION_KEY, text);
}

export function takePendingQuestion(): string | null {
  if (typeof window === "undefined") return null;
  const value = window.sessionStorage.getItem(PENDING_QUESTION_KEY);
  if (!value) return null;
  window.sessionStorage.removeItem(PENDING_QUESTION_KEY);
  return value;
}
