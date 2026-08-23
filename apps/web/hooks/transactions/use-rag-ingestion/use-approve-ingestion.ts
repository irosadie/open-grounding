"use client"

import { apiRouters, queryKeys } from "$/constants"
import { axios } from "$/services/axios"
import type { ErrorResponse } from "$/types/generals"
import type { ApproveIngestionResponse } from "@open-grounding/types"
import { useMutation } from "@tanstack/react-query"
import type { AxiosError } from "axios"

const approveIngestion = async (versionId: string) => {
  const url = apiRouters.rag.ingestion.approve.replace(":versionId", versionId)
  const result = await axios<ApproveIngestionResponse>({
    method: "POST",
    url,
  })
  return result
}

export const useApproveIngestion = (versionId: string) => {
  return useMutation<
    ApproveIngestionResponse,
    ErrorResponse<AxiosError>,
    void,
    unknown
  >({
    mutationKey: [queryKeys.rag.ingestion.approve, versionId],
    mutationFn: () => approveIngestion(versionId),
  })
}

export default useApproveIngestion
