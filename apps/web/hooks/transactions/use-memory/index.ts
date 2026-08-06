"use client"

import { apiRouters, queryKeys } from "$/constants"
import { axios } from "$/services/axios"
import type { ErrorResponse } from "$/types/generals"
import { pathVariable } from "$/utils/path-variable"
import type { MemoryChunkListResponse } from "@open-grounding/types"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import type { AxiosError } from "axios"

export const useMemoryChunks = (
  knowledgeBaseId: string | null,
  page = 1,
  pageSize = 20,
) => {
  return useQuery<MemoryChunkListResponse, ErrorResponse<AxiosError>>({
    queryKey: [queryKeys.rag.memory.list, knowledgeBaseId, page, pageSize],
    queryFn: () =>
      axios<MemoryChunkListResponse>({
        method: "GET",
        url: apiRouters.rag.memory.list,
        params: {
          knowledge_base_id: knowledgeBaseId,
          page,
          page_size: pageSize,
        },
      }),
    enabled: !!knowledgeBaseId,
  })
}

export const useDeleteMemoryChunk = (knowledgeBaseId: string | null) => {
  const queryClient = useQueryClient()
  return useMutation<void, ErrorResponse<AxiosError>, string>({
    mutationKey: [queryKeys.rag.memory.deleteChunk],
    mutationFn: (chunkId) =>
      axios<void>({
        method: "DELETE",
        url: pathVariable(apiRouters.rag.memory.deleteChunk, {
          chunkId,
        }),
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: [queryKeys.rag.memory.list, knowledgeBaseId],
      })
    },
  })
}

export const useClearMemory = (knowledgeBaseId: string | null) => {
  const queryClient = useQueryClient()
  return useMutation<void, ErrorResponse<AxiosError>, void>({
    mutationKey: [queryKeys.rag.memory.clear, knowledgeBaseId],
    mutationFn: () =>
      axios<void>({
        method: "DELETE",
        url: apiRouters.rag.memory.clear,
        params: knowledgeBaseId
          ? { knowledge_base_id: knowledgeBaseId }
          : undefined,
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: [queryKeys.rag.memory.list, knowledgeBaseId],
      })
    },
  })
}
