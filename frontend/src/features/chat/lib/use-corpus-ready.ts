import { useQuery } from "@tanstack/react-query";

import { useAuth } from "@/features/auth/auth-provider";
import { fetchDocuments } from "@/lib/api";

export function useCorpusReady() {
  const { user } = useAuth();
  const query = useQuery({
    queryKey: ["documents", user?.id, user?.organization_id],
    queryFn: () => fetchDocuments(50, 0),
    enabled: Boolean(user),
  });

  const readyCount =
    query.data?.items.filter((doc) => doc.status === "ready").length ?? 0;
  const hasReadyCorpus = readyCount > 0;

  return {
    readyCount,
    hasReadyCorpus,
    loading: query.isLoading,
    isSuccess: query.isSuccess,
  };
}
