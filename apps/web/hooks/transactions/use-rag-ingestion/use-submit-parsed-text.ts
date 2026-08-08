"use client"

import { apiRouters, queryKeys } from "$/constants"
import { axios } from "$/services/axios"
import type { ErrorResponse } from "$/types/generals"
import {
  type SubmitParsedTextProps,
  submitParsedTextSchema,
} from "@open-grounding/schemas"
import type { ParsedTextResponse } from "@open-grounding/types"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import type { AxiosError } from "axios"

const submitParsedText = async (
  versionId: string,
  payload: SubmitParsedTextProps,
) => {
  const validated = submitParsedTextSchema.parse(payload)
  const url = apiRouters.rag.ingestion.parsedText.replace(
    ":versionId",
    versionId,
  )
  const result = await axios<ParsedTextResponse>({
    method: "PATCH",
    url,
    data: { text: validated.text },
  })
  return result
}

export const useSubmitParsedText = (versionId: string) => {
  const queryClient = useQueryClient()

  return useMutation<
    ParsedTextResponse,
    ErrorResponse<AxiosError>,
    SubmitParsedTextProps,
    unknown
  >({
    mutationKey: [queryKeys.rag.ingestion.parsedText, versionId],
    mutationFn: (payload) => submitParsedText(versionId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: [queryKeys.rag.ingestion.parsedText, versionId],
      })
    },
  })
}

export default useSubmitParsedText
