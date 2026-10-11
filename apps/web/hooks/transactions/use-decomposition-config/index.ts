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

export const useProjectDecompositionConfig = (projectId: string | null) =>
  useQuery<DecompositionConfigResponse, ErrorResponse<AxiosError>>({
    queryKey: [queryKeys.rag.projects.decomposition, projectId],
    queryFn: () =>
      axios({
        method: "GET",
        url: pathVariable(apiRouters.rag.projects.decomposition, {
          id: projectId as string,
        }),
      }),
    enabled: !!projectId,
    retry: false,
  })

export const useProjectDecompositionDefaults = (projectId: string | null) =>
  useQuery<DecompositionDefaultsResponse, ErrorResponse<AxiosError>>({
    queryKey: [queryKeys.rag.projects.decompositionDefaults, projectId],
    queryFn: () =>
      axios({
        method: "GET",
        url: pathVariable(apiRouters.rag.projects.decompositionDefaults, {
          id: projectId as string,
        }),
      }),
    enabled: !!projectId,
  })

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

export const useUpsertProjectDecompositionConfig = (projectId: string) => {
  const queryClient = useQueryClient()
  return useMutation<
    DecompositionConfigResponse,
    ErrorResponse<AxiosError>,
    DecompositionConfigInput
  >({
    mutationKey: [queryKeys.rag.projects.decomposition, projectId],
    mutationFn: (data) =>
      axios({
        method: "POST",
        url: pathVariable(apiRouters.rag.projects.decomposition, {
          id: projectId,
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
        queryKey: [queryKeys.rag.projects.decomposition, projectId],
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

export const useDeleteProjectDecompositionConfig = (projectId: string) => {
  const queryClient = useQueryClient()
  return useMutation<void, ErrorResponse<AxiosError>, void>({
    mutationKey: [queryKeys.rag.projects.decomposition, projectId, "delete"],
    mutationFn: () =>
      axios({
        method: "DELETE",
        url: pathVariable(apiRouters.rag.projects.decomposition, {
          id: projectId,
        }),
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: [queryKeys.rag.projects.decomposition, projectId],
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
