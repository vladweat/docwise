import { ApiRequestError } from "@/lib/api";

export function inspectErrorMessage(err: unknown): string {
  if (err instanceof ApiRequestError && err.status === 404) {
    return "Инспекция выключена (ENABLE_SEARCH_INSPECT). В Compose она включена вне production.";
  }
  if (err instanceof ApiRequestError && err.status === 403) {
    return "Недостаточно прав.";
  }
  if (err instanceof ApiRequestError) {
    return err.message;
  }
  return "Не удалось выполнить inspect";
}
