"use client"

import { apiRouters, queryKeys } from "$/constants"
import { axios } from "$/services/axios"
import type { ErrorResponse } from "$/types/generals"
import { pathVariable } from "$/utils/path-variable"
import type { KnowledgeBaseDeleteResponse } from "@open-grounding/types"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import type { AxiosError } from "axios"

const deleteKnowledgeBase = async (id: string) => {
  return axios<KnowledgeBaseDeleteResponse>({
    method: "DELETE",
    url: pathVariable(apiRouters.rag.knowledgeBases.delete, { id }),
  })
}

export const useDeleteKnowledgeBase = () => {
  const queryClient = useQueryClient()

  return useMutation<
    KnowledgeBaseDeleteResponse,
    ErrorResponse<AxiosError>,
    string
  >({
    mutationKey: [queryKeys.rag.knowledgeBases.delete],
    mutationFn: deleteKnowledgeBase,
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: [queryKeys.rag.knowledgeBases.list],
      })
    },
  })
}

export default useDeleteKnowledgeBase
