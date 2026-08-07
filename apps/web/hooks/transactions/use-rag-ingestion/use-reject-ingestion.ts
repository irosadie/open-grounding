"use client"

import { apiRouters, queryKeys } from "$/constants"
import { axios } from "$/services/axios"
import type { ErrorResponse } from "$/types/generals"
import type { RejectIngestionResponse } from "@open-grounding/types"
import { useMutation } from "@tanstack/react-query"
import type { AxiosError } from "axios"

const rejectIngestion = async (versionId: string) => {
  const url = apiRouters.rag.ingestion.reject.replace(":versionId", versionId)
  const result = await axios<RejectIngestionResponse>({
    method: "POST",
    url,
  })
  return result
}

export const useRejectIngestion = (versionId: string) => {
  return useMutation<
    RejectIngestionResponse,
    ErrorResponse<AxiosError>,
    void,
    unknown
  >({
    mutationKey: [queryKeys.rag.ingestion.reject, versionId],
    mutationFn: () => rejectIngestion(versionId),
  })
}

export default useRejectIngestion
