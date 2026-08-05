"use client"

import { apiRouters, queryKeys } from "$/constants"
import { axios } from "$/services/axios"
import type { ErrorResponse } from "$/types/generals"
import { pathVariable } from "$/utils/path-variable"
import type { IngestionDeleteResponse } from "@open-grounding/types"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import type { AxiosError } from "axios"

const deleteVersion = async (documentVersionId: string) => {
  const result = await axios<IngestionDeleteResponse>({
    method: "DELETE",
    url: pathVariable(apiRouters.rag.ingestion.delete, { documentVersionId }),
  })
  return result
}

export const useRagIngestionDelete = () => {
  const queryClient = useQueryClient()
  const mutation = useMutation<
    IngestionDeleteResponse,
    ErrorResponse<AxiosError>,
    string,
    unknown
  >({
    mutationKey: [queryKeys.rag.ingestion.delete],
    mutationFn: deleteVersion,
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: [queryKeys.rag.ingestion.status],
      })
    },
  })

  return {
    ...mutation,
  }
}

export default useRagIngestionDelete
