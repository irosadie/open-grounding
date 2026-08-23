"use client"

import { apiRouters, queryKeys } from "$/constants"
import { axios } from "$/services/axios"
import type { ErrorResponse } from "$/types/generals"
import {
  type CompleteIntakeProps,
  completeIntakeSchema,
} from "@open-grounding/schemas"
import type { IngestionCompleteResponse } from "@open-grounding/types"
import { useMutation } from "@tanstack/react-query"
import type { AxiosError } from "axios"

const completeIntake = async (payload: CompleteIntakeProps) => {
  const validated = completeIntakeSchema.parse(payload)
  const result = await axios<IngestionCompleteResponse>({
    method: "POST",
    url: apiRouters.rag.ingestion.complete,
    data: {
      document_version_id: validated.documentVersionId,
      content_checksum: validated.contentChecksum,
    },
  })
  return result
}

export const useRagIngestionComplete = () => {
  const mutation = useMutation<
    IngestionCompleteResponse,
    ErrorResponse<AxiosError>,
    CompleteIntakeProps,
    unknown
  >({
    mutationKey: [queryKeys.rag.ingestion.complete],
    mutationFn: completeIntake,
  })

  return {
    ...mutation,
  }
}

export default useRagIngestionComplete
