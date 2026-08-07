"use client"

import { apiRouters, queryKeys } from "$/constants"
import { axios } from "$/services/axios"
import type { ParsedTextResponse } from "@open-grounding/types"
import { useQuery } from "@tanstack/react-query"

const fetchParsedText = async (versionId: string) => {
  const url = apiRouters.rag.ingestion.parsedText.replace(":versionId", versionId)
  const result = await axios<ParsedTextResponse>({
    method: "GET",
    url,
  })
  return result
}

export const useIngestionParsedText = (versionId: string) => {
  return useQuery<ParsedTextResponse>({
    queryKey: [queryKeys.rag.ingestion.parsedText, versionId],
    queryFn: () => fetchParsedText(versionId),
    enabled: !!versionId,
  })
}

export default useIngestionParsedText
