"use client"

import { apiRouters, queryKeys } from "$/constants"
import { axios } from "$/services/axios"
import type { ErrorResponse } from "$/types/generals"
import { pathVariable } from "$/utils/path-variable"
import type { IngestionConfigInput } from "@open-grounding/schemas"
import type { IngestionConfigResponse } from "@open-grounding/types"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import type { AxiosError } from "axios"

export const useIngestionConfig = (knowledgeBaseId: string | null) =>
  useQuery<IngestionConfigResponse, ErrorResponse<AxiosError>>({
    queryKey: [queryKeys.rag.knowledgeBases.ingestionConfig, knowledgeBaseId],
    queryFn: () =>
      axios<IngestionConfigResponse>({
        method: "GET",
        url: pathVariable(apiRouters.rag.knowledgeBases.ingestionConfig, {
          id: knowledgeBaseId as string,
        }),
      }),
    enabled: !!knowledgeBaseId,
    retry: false,
  })

export const useUpsertIngestionConfig = (knowledgeBaseId: string) => {
  const queryClient = useQueryClient()
  return useMutation<
    IngestionConfigResponse,
    ErrorResponse<AxiosError>,
    IngestionConfigInput
  >({
    mutationKey: [
      queryKeys.rag.knowledgeBases.ingestionConfig,
      knowledgeBaseId,
    ],
    mutationFn: (data) =>
      axios<IngestionConfigResponse>({
        method: "PUT",
        url: pathVariable(apiRouters.rag.knowledgeBases.ingestionConfig, {
          id: knowledgeBaseId,
        }),
        data: {
          min_text_coverage: data.minTextCoverage,
          max_invalid_char_ratio: data.maxInvalidCharRatio,
          min_aggregate_confidence: data.minAggregateConfidence,
          min_page_coverage: data.minPageCoverage,
          auto_review: data.autoReview,
        },
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: [
          queryKeys.rag.knowledgeBases.ingestionConfig,
          knowledgeBaseId,
        ],
      })
    },
  })
}
