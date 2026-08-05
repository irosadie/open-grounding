"use client"

import { apiRouters, queryKeys } from "$/constants"
import { axios } from "$/services/axios"
import type { ErrorResponse } from "$/types/generals"
import {
  type KnowledgeBaseCreateProps,
  knowledgeBaseCreateSchema,
} from "@open-grounding/schemas"
import type { KnowledgeBaseCreateResponse } from "@open-grounding/types"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import type { AxiosError } from "axios"

const createKnowledgeBase = async (payload: KnowledgeBaseCreateProps) => {
  const validated = knowledgeBaseCreateSchema.parse(payload)
  return axios<KnowledgeBaseCreateResponse>({
    method: "POST",
    url: apiRouters.rag.knowledgeBases.create,
    data: validated,
  })
}

export const useCreateKnowledgeBase = () => {
  const queryClient = useQueryClient()

  return useMutation<
    KnowledgeBaseCreateResponse,
    ErrorResponse<AxiosError>,
    KnowledgeBaseCreateProps
  >({
    mutationKey: [queryKeys.rag.knowledgeBases.create],
    mutationFn: createKnowledgeBase,
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: [queryKeys.rag.knowledgeBases.list],
      })
    },
  })
}

export default useCreateKnowledgeBase
