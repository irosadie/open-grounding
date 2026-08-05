"use client"

import { apiRouters, queryKeys } from "$/constants"
import { axios } from "$/services/axios"
import type { ErrorResponse } from "$/types/generals"
import { type RagQueryProps, ragQuerySchema } from "@open-grounding/schemas"
import type { RagQueryResponse } from "@open-grounding/types"
import { useMutation } from "@tanstack/react-query"
import type { AxiosError } from "axios"

const askRag = async (payload: RagQueryProps) => {
  const validated = ragQuerySchema.parse(payload)
  const result = await axios<RagQueryResponse>({
    method: "POST",
    url: apiRouters.rag.query.ask,
    data: {
      message: validated.message,
      knowledge_base_ids: validated.knowledgeBaseIds,
      conversation_id: validated.conversationId,
      mode: validated.mode,
      stream: false,
    },
  })
  return result
}

export const useRagQuery = () => {
  const mutation = useMutation<
    RagQueryResponse,
    ErrorResponse<AxiosError>,
    RagQueryProps,
    unknown
  >({
    mutationKey: [queryKeys.rag.query.ask],
    mutationFn: askRag,
  })

  return {
    ...mutation,
  }
}

export default useRagQuery
