"use client"

import { apiRouters, queryKeys } from "$/constants"
import { axios } from "$/services/axios"
import type { ErrorResponse } from "$/types/generals"
import { pathVariable } from "$/utils/path-variable"
import {
  type IndexProfileCreateProps,
  indexProfileCreateSchema,
} from "@open-grounding/schemas"
import type {
  IndexProfileActivateResponse,
  IndexProfileCreateResponse,
  IndexProfileListResponse,
} from "@open-grounding/types"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import type { AxiosError } from "axios"

export const useIndexProfiles = () => {
  return useQuery<IndexProfileListResponse, ErrorResponse<AxiosError>>({
    queryKey: [queryKeys.rag.indexProfiles.list],
    queryFn: () =>
      axios<IndexProfileListResponse>({
        method: "GET",
        url: apiRouters.rag.indexProfiles.list,
      }),
  })
}

export const useCreateIndexProfile = () => {
  const queryClient = useQueryClient()
  return useMutation<
    IndexProfileCreateResponse,
    ErrorResponse<AxiosError>,
    IndexProfileCreateProps
  >({
    mutationKey: [queryKeys.rag.indexProfiles.create],
    mutationFn: async (payload) => {
      const validated = indexProfileCreateSchema.parse(payload)
      return axios<IndexProfileCreateResponse>({
        method: "POST",
        url: apiRouters.rag.indexProfiles.create,
        data: {
          name: validated.name,
          embedding_profile_id: validated.embeddingProfileId,
          sparse_profile_id: validated.sparseProfileId,
          reranker_profile_id: validated.rerankerProfileId,
          collection: validated.collection,
          dimensions: validated.dimensions,
          distance_metric: validated.distanceMetric,
          chunking_strategy: validated.chunkingStrategy,
          chunk_size_tokens: validated.chunkSizeTokens,
          chunk_overlap_tokens: validated.chunkOverlapTokens,
          parent_chunk_size: validated.parentChunkSize,
        },
      })
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: [queryKeys.rag.indexProfiles.list],
      })
    },
  })
}

export const useActivateIndexProfile = () => {
  const queryClient = useQueryClient()
  return useMutation<
    IndexProfileActivateResponse,
    ErrorResponse<AxiosError>,
    string
  >({
    mutationKey: [queryKeys.rag.indexProfiles.activate],
    mutationFn: (id) =>
      axios<IndexProfileActivateResponse>({
        method: "POST",
        url: pathVariable(apiRouters.rag.indexProfiles.activate, { id }),
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: [queryKeys.rag.indexProfiles.list],
      })
    },
  })
}
