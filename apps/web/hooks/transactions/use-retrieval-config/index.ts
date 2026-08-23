"use client"

import { apiRouters, queryKeys } from "$/constants"
import { axios } from "$/services/axios"
import type { ErrorResponse } from "$/types/generals"
import { pathVariable } from "$/utils/path-variable"
import type { RetrievalConfigInput } from "@open-grounding/schemas"
import type { RetrievalConfigResponse } from "@open-grounding/types"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import type { AxiosError } from "axios"

export const useRetrievalConfig = (indexProfileId: string | null) =>
  useQuery<RetrievalConfigResponse, ErrorResponse<AxiosError>>({
    queryKey: [queryKeys.rag.indexProfiles.retrieval, indexProfileId],
    queryFn: () =>
      axios<RetrievalConfigResponse>({
        method: "GET",
        url: pathVariable(apiRouters.rag.indexProfiles.retrieval, {
          id: indexProfileId as string,
        }),
      }),
    enabled: !!indexProfileId,
    retry: false,
  })

export const useUpsertRetrievalConfig = (indexProfileId: string) => {
  const queryClient = useQueryClient()
  return useMutation<
    RetrievalConfigResponse,
    ErrorResponse<AxiosError>,
    RetrievalConfigInput
  >({
    mutationKey: [queryKeys.rag.indexProfiles.retrieval, indexProfileId],
    mutationFn: (data) =>
      axios<RetrievalConfigResponse>({
        method: "PUT",
        url: pathVariable(apiRouters.rag.indexProfiles.retrieval, {
          id: indexProfileId,
        }),
        data: {
          dense_weight: data.denseWeight,
          sparse_weight: data.sparseWeight,
          fusion_k: data.fusionK,
          dense_candidates: data.denseCandidates,
          sparse_candidates: data.sparseCandidates,
          fused_candidates: data.fusedCandidates,
          enabled: data.enabled,
        },
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: [queryKeys.rag.indexProfiles.retrieval, indexProfileId],
      })
    },
  })
}

export const useDeleteRetrievalConfig = (indexProfileId: string) => {
  const queryClient = useQueryClient()
  return useMutation<void, ErrorResponse<AxiosError>, void>({
    mutationKey: [
      queryKeys.rag.indexProfiles.retrieval,
      indexProfileId,
      "delete",
    ],
    mutationFn: () =>
      axios<void>({
        method: "DELETE",
        url: pathVariable(apiRouters.rag.indexProfiles.retrieval, {
          id: indexProfileId,
        }),
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: [queryKeys.rag.indexProfiles.retrieval, indexProfileId],
      })
    },
  })
}
