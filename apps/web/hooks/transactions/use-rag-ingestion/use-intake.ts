"use client"

import { apiRouters, queryKeys } from "$/constants"
import { axios } from "$/services/axios"
import type { ErrorResponse } from "$/types/generals"
import { useMutation } from "@tanstack/react-query"
import {
  type CreateIntakeProps,
  createIntakeSchema,
} from "@vibecoding-starter/schemas"
import type { IngestionIntakeResponse } from "@vibecoding-starter/types"
import type { AxiosError } from "axios"

const createIntake = async (payload: CreateIntakeProps) => {
  const validated = createIntakeSchema.parse(payload)
  const result = await axios<IngestionIntakeResponse>({
    method: "POST",
    url: apiRouters.rag.ingestion.intake,
    data: validated,
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
