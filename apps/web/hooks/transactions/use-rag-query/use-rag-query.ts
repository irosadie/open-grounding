"use client"

import { apiRouters, queryKeys } from "$/constants"
import { axios } from "$/services/axios"
import type { ErrorResponse } from "$/types/generals"
import { useMutation } from "@tanstack/react-query"
import { type RagQueryProps, ragQuerySchema } from "@vibecoding-starter/schemas"
import type { RagQueryResponse } from "@vibecoding-starter/types"
import type { AxiosError } from "axios"

const askRag = async (payload: RagQueryProps) => {
  const validated = ragQuerySchema.parse(payload)
  const result = await axios<RagQueryResponse>({
    method: "POST",
    url: apiRouters.rag.query.ask,
    data: { ...validated, stream: false },
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
