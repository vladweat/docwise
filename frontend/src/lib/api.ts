/** HTTP client barrel — import domain modules from `@/lib/api/...` when adding new calls. */

export {
  API_V1,
  ApiRequestError,
  apiFetch,
  apiUrl,
  authorizedFetch,
  fetchDocumentRaw,
  shouldRefreshOn401,
  v1Path,
  v1Url,
} from "@/lib/api/client";

export {
  createOrganizationInvite,
  fetchMe,
  fetchOrganizationMembers,
  login,
  loginWithGoogle,
  loginWithSso,
  logout,
  register,
  ssoLoginUrl,
  switchOrganization,
} from "@/lib/api/auth";

export {
  changeBillingPlan,
  fetchBillingSubscription,
  fetchBillingUsage,
  simulateDevBilling,
} from "@/lib/api/billing";

export {
  fetchOrganizationDomain,
  fetchOrganizationSso,
  upsertOrganizationDomain,
  upsertOrganizationSso,
  verifyOrganizationDomain,
} from "@/lib/api/organization";

export {
  deleteChatSession,
  fetchChatSession,
  fetchChatSessions,
  sendChatFeedback,
  streamChat,
} from "@/lib/api/chat";

export {
  deleteDocument,
  fetchDocumentStatus,
  fetchDocuments,
  uploadDocument,
} from "@/lib/api/documents";

export { fetchHealth } from "@/lib/api/health";

export { inspectSearch } from "@/lib/api/inspect";
