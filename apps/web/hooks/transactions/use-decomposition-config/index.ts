"use client"

import { apiRouters, queryKeys } from "$/constants"
import { axios } from "$/services/axios"
import type { ErrorResponse } from "$/types/generals"
import { pathVariable } from "$/utils/path-variable"
import type { DecompositionConfigInput } from "@open-grounding/schemas"
import type {
  DecompositionConfigResponse,
  DecompositionDefaultsResponse,
} from "@open-grounding/types"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import type { AxiosError } from "axios"

export const useDecompositionConfig = (knowledgeBaseId: string | null) => {
  return useQuery<DecompositionConfigResponse, ErrorResponse<AxiosError>>({
    queryKey: [queryKeys.rag.knowledgeBases.decomposition, knowledgeBaseId],
    queryFn: () =>
      axios<DecompositionConfigResponse>({
        method: "GET",
        url: pathVariable(apiRouters.rag.knowledgeBases.decomposition, {
          id: knowledgeBaseId as string,
        }),
      }),
    enabled: !!knowledgeBaseId,
    retry: false,
  })
}

export const useUpsertDecompositionConfig = (knowledgeBaseId: string) => {
  const queryClient = useQueryClient()
  return useMutation<
    DecompositionConfigResponse,
    ErrorResponse<AxiosError>,
    DecompositionConfigInput
  >({
    mutationKey: [queryKeys.rag.knowledgeBases.decomposition, knowledgeBaseId],
    mutationFn: (data) =>
      axios<DecompositionConfigResponse>({
        method: "POST",
        url: pathVariable(apiRouters.rag.knowledgeBases.decomposition, {
          id: knowledgeBaseId,
        }),
        data: {
          enabled: data.enabled,
          model_profile_id: data.modelProfileId,
          system_prompt: data.systemPrompt,
          user_prompt_template: data.userPromptTemplate,
          max_sub_queries: data.maxSubQueries,
          max_depth: data.maxDepth,
          min_complexity_score: data.minComplexityScore,
          guardrails: data.guardrails,
        },
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: [queryKeys.rag.knowledgeBases.decomposition, knowledgeBaseId],
      })
    },
  })
}

export const useDeleteDecompositionConfig = (knowledgeBaseId: string) => {
  const queryClient = useQueryClient()
  return useMutation<void, ErrorResponse<AxiosError>, void>({
    mutationKey: [
      queryKeys.rag.knowledgeBases.decomposition,
      knowledgeBaseId,
      "delete",
    ],
    mutationFn: () =>
      axios<void>({
        method: "DELETE",
        url: pathVariable(apiRouters.rag.knowledgeBases.decomposition, {
          id: knowledgeBaseId,
        }),
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: [queryKeys.rag.knowledgeBases.decomposition, knowledgeBaseId],
      })
    },
  })
}

export const useDecompositionDefaults = (knowledgeBaseId: string | null) => {
  return useQuery<DecompositionDefaultsResponse, ErrorResponse<AxiosError>>({
    queryKey: [
      queryKeys.rag.knowledgeBases.decompositionDefaults,
      knowledgeBaseId,
    ],
    queryFn: () =>
      axios<DecompositionDefaultsResponse>({
        method: "GET",
        url: pathVariable(apiRouters.rag.knowledgeBases.decompositionDefaults, {
          id: knowledgeBaseId as string,
        }),
      }),
    enabled: !!knowledgeBaseId,
  })
}
