export type HomeView = "landing" | "loading" | "chat";

export function resolveHomeView({
  isAuthenticated,
  loading,
  hasSessionCookie,
}: {
  isAuthenticated: boolean;
  loading: boolean;
  hasSessionCookie: boolean;
}): HomeView {
  if (isAuthenticated) return "chat";
  if (loading && hasSessionCookie) return "loading";
  return "landing";
}
