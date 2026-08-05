"use client"

import { apiRouters, queryKeys } from "$/constants"
import { axios } from "$/services/axios"
import type { ErrorResponse } from "$/types/generals"
import {
  type CreateIntakeProps,
  createIntakeSchema,
} from "@open-grounding/schemas"
import type { IngestionIntakeResponse } from "@open-grounding/types"
import { useMutation } from "@tanstack/react-query"
import type { AxiosError } from "axios"

const createIntake = async (payload: CreateIntakeProps) => {
  const validated = createIntakeSchema.parse(payload)
  const result = await axios<IngestionIntakeResponse>({
    method: "POST",
    url: apiRouters.rag.ingestion.intake,
    data: {
      knowledge_base_id: validated.knowledgeBaseId,
      filename: validated.filename,
      mime_type: validated.mimeType,
      size_bytes: validated.sizeBytes,
      source_revision: validated.sourceRevision,
      title: validated.title,
    },
  })
  return result
}

export const useRagIngestionIntake = () => {
  const mutation = useMutation<
    IngestionIntakeResponse,
    ErrorResponse<AxiosError>,
    CreateIntakeProps,
    unknown
  >({
    mutationKey: [queryKeys.rag.ingestion.intake],
    mutationFn: createIntake,
  })

  return {
    ...mutation,
  }
}

export default useRagIngestionIntake
