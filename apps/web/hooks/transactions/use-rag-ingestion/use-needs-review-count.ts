"use client"

import { apiRouters, queryKeys } from "$/constants"
import { axios } from "$/services/axios"
import { useQuery } from "@tanstack/react-query"

const fetchPendingReviewCount = async (): Promise<number> => {
  const result = await axios<{ count: number }>({
    method: "GET",
    url: apiRouters.rag.ingestion.pendingReviewCount,
  })
  return result.count
}

type UseNeedsReviewCountArgs = {
  enabled?: boolean
}

export const useNeedsReviewCount = (args?: UseNeedsReviewCountArgs) => {
  const { enabled = true } = args ?? {}
  return useQuery({
    queryKey: [queryKeys.rag.ingestion.pendingReviewCount],
    queryFn: fetchPendingReviewCount,
    enabled,
    refetchInterval: 30_000,
    // Tidak ada poller permanen saat tab hidden (visibility bawaan react-query).
    refetchIntervalInBackground: false,
    staleTime: 30_000,
  })
}

export default useNeedsReviewCount
