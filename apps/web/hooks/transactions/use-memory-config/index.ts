"use client"

import { apiRouters, queryKeys } from "$/constants"
import { axios } from "$/services/axios"
import type { ErrorResponse } from "$/types/generals"
import { pathVariable } from "$/utils/path-variable"
import type { MemoryConfigInput } from "@open-grounding/schemas"
import type {
  MemoryConfigDefaultsResponse,
  MemoryConfigResponse,
} from "@open-grounding/types"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import type { AxiosError } from "axios"

export const useMemoryConfig = (knowledgeBaseId: string | null) => {
  return useQuery<MemoryConfigResponse, ErrorResponse<AxiosError>>({
    queryKey: [queryKeys.rag.knowledgeBases.memoryConfig, knowledgeBaseId],
    queryFn: () =>
      axios<MemoryConfigResponse>({
        method: "GET",
        url: pathVariable(apiRouters.rag.knowledgeBases.memoryConfig, {
          id: knowledgeBaseId as string,
        }),
      }),
    enabled: !!knowledgeBaseId,
    retry: false,
  })
}

export const useUpsertMemoryConfig = (knowledgeBaseId: string) => {
  const queryClient = useQueryClient()
  return useMutation<
    MemoryConfigResponse,
    ErrorResponse<AxiosError>,
    MemoryConfigInput
  >({
    mutationKey: [queryKeys.rag.knowledgeBases.memoryConfig, knowledgeBaseId],
    mutationFn: (data) =>
      axios<MemoryConfigResponse>({
        method: "POST",
        url: pathVariable(apiRouters.rag.knowledgeBases.memoryConfig, {
          id: knowledgeBaseId,
        }),
        data: {
          enabled: data.enabled,
          summarization_model_profile_id: data.summarizationModelProfileId,
          embedding_profile_id: data.embeddingProfileId,
          retention_days: data.retentionDays,
          retrieval_top_k: data.retrievalTopK,
          min_turns_to_summarize: data.minTurnsToSummarize,
          system_prompt: data.systemPrompt,
        },
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: [queryKeys.rag.knowledgeBases.memoryConfig, knowledgeBaseId],
      })
    },
  })
}

export const useDeleteMemoryConfig = (knowledgeBaseId: string) => {
  const queryClient = useQueryClient()
  return useMutation<void, ErrorResponse<AxiosError>, void>({
    mutationKey: [
      queryKeys.rag.knowledgeBases.memoryConfig,
      knowledgeBaseId,
      "delete",
    ],
    mutationFn: () =>
      axios<void>({
        method: "DELETE",
        url: pathVariable(apiRouters.rag.knowledgeBases.memoryConfig, {
          id: knowledgeBaseId,
        }),
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: [queryKeys.rag.knowledgeBases.memoryConfig, knowledgeBaseId],
      })
    },
  })
}

export const useMemoryConfigDefaults = (knowledgeBaseId: string | null) => {
  return useQuery<MemoryConfigDefaultsResponse, ErrorResponse<AxiosError>>({
    queryKey: [
      queryKeys.rag.knowledgeBases.memoryConfigDefaults,
      knowledgeBaseId,
    ],
    queryFn: () =>
      axios<MemoryConfigDefaultsResponse>({
        method: "GET",
        url: pathVariable(apiRouters.rag.knowledgeBases.memoryConfigDefaults, {
          id: knowledgeBaseId as string,
        }),
      }),
    enabled: !!knowledgeBaseId,
  })
}

export const useProjectMemoryConfig = (projectId: string | null) =>
  useQuery<MemoryConfigResponse, ErrorResponse<AxiosError>>({
    queryKey: [queryKeys.rag.projects.memoryConfig, projectId],
    queryFn: () =>
      axios({
        method: "GET",
        url: pathVariable(apiRouters.rag.projects.memoryConfig, {
          id: projectId as string,
        }),
      }),
    enabled: !!projectId,
    retry: false,
  })

export const useProjectMemoryConfigDefaults = (projectId: string | null) =>
  useQuery<MemoryConfigDefaultsResponse, ErrorResponse<AxiosError>>({
    queryKey: [queryKeys.rag.projects.memoryConfigDefaults, projectId],
    queryFn: () =>
      axios({
        method: "GET",
        url: pathVariable(apiRouters.rag.projects.memoryConfigDefaults, {
          id: projectId as string,
        }),
      }),
    enabled: !!projectId,
  })

export const useUpsertProjectMemoryConfig = (projectId: string) => {
  const queryClient = useQueryClient()
  return useMutation<
    MemoryConfigResponse,
    ErrorResponse<AxiosError>,
    MemoryConfigInput
  >({
    mutationKey: [queryKeys.rag.projects.memoryConfig, projectId],
    mutationFn: (data) =>
      axios({
        method: "POST",
        url: pathVariable(apiRouters.rag.projects.memoryConfig, {
          id: projectId,
        }),
        data: {
          enabled: data.enabled,
          summarization_model_profile_id: data.summarizationModelProfileId,
          embedding_profile_id: data.embeddingProfileId,
          retention_days: data.retentionDays,
          retrieval_top_k: data.retrievalTopK,
          min_turns_to_summarize: data.minTurnsToSummarize,
          system_prompt: data.systemPrompt,
        },
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: [queryKeys.rag.projects.memoryConfig, projectId],
      })
    },
  })
}

export const useDeleteProjectMemoryConfig = (projectId: string) => {
  const queryClient = useQueryClient()
  return useMutation<void, ErrorResponse<AxiosError>, void>({
    mutationKey: [queryKeys.rag.projects.memoryConfig, projectId, "delete"],
    mutationFn: () =>
      axios({
        method: "DELETE",
        url: pathVariable(apiRouters.rag.projects.memoryConfig, {
          id: projectId,
        }),
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: [queryKeys.rag.projects.memoryConfig, projectId],
      })
    },
  })
}
