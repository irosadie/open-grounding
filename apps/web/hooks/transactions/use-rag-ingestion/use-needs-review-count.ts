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

export const useNeedsReviewCount = () => {
  return useQuery({
    queryKey: [queryKeys.rag.ingestion.pendingReviewCount],
    queryFn: fetchPendingReviewCount,
    refetchInterval: 30_000,
  })
}

export default useNeedsReviewCount
