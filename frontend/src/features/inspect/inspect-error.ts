import { tClient } from "@/i18n/client-translate";
import { ApiRequestError } from "@/lib/api";

export function inspectErrorMessage(err: unknown): string {
  if (err instanceof ApiRequestError && err.status === 404) {
    return tClient("errors.inspectDisabled");
  }
  if (err instanceof ApiRequestError && err.status === 403) {
    return tClient("errors.inspectForbidden");
  }
  if (err instanceof ApiRequestError) {
    return err.message;
  }
  return tClient("errors.inspectFailed");
}
