"use client"

import { apiRouters, queryKeys } from "$/constants"
import { axios } from "$/services/axios"
import type { ErrorResponse } from "$/types/generals"
import type { KnowledgeBaseListResponse } from "@open-grounding/types"
import { useQuery } from "@tanstack/react-query"
import type { AxiosError } from "axios"

const fetchKnowledgeBases = async () => {
  return axios<KnowledgeBaseListResponse>({
    method: "GET",
    url: apiRouters.rag.knowledgeBases.list,
  })
}

export const useKnowledgeBases = () => {
  return useQuery<KnowledgeBaseListResponse, ErrorResponse<AxiosError>>({
    queryKey: [queryKeys.rag.knowledgeBases.list],
    queryFn: fetchKnowledgeBases,
  })
}

export default useKnowledgeBases
