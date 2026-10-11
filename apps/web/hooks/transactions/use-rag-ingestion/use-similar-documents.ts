"use client"

import { apiRouters, queryKeys } from "$/constants"
import { axios } from "$/services/axios"
import type { SimilarDocumentsResponse } from "@open-grounding/types"
import { useQuery } from "@tanstack/react-query"

const fetchSimilarDocuments = async (
  versionId: string,
): Promise<SimilarDocumentsResponse> => {
  const url = apiRouters.rag.ingestion.similarDocuments.replace(
    ":versionId",
    versionId,
  )
  return axios<SimilarDocumentsResponse>({
    method: "GET",
    url,
  })
}

export const useSimilarDocuments = (versionId: string) => {
  return useQuery<SimilarDocumentsResponse>({
    queryKey: [queryKeys.rag.ingestion.similarDocuments, versionId],
    queryFn: () => fetchSimilarDocuments(versionId),
    enabled: !!versionId,
  })
}

export default useSimilarDocuments
