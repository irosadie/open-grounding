"use client"

import { apiRouters, queryKeys } from "$/constants"
import { axios } from "$/services/axios"
import type { ErrorResponse } from "$/types/generals"
import { pathVariable } from "$/utils/path-variable"
import { useQuery } from "@tanstack/react-query"
import { isTerminalLifecycleState } from "@vibecoding-starter/schemas"
import type { IngestionStatusResponse } from "@vibecoding-starter/types"
import type { AxiosError } from "axios"

const POLL_INTERVAL_MS = 3000

const fetchIngestionStatus = async (documentVersionId: string) => {
  const result = await axios<IngestionStatusResponse>({
    method: "GET",
    url: pathVariable(apiRouters.rag.ingestion.status, { documentVersionId }),
  })
  return result
}

type UseIngestionStatusArgs = {
  documentVersionId: string | null
  enabled?: boolean
}

export const useRagIngestionStatus = (args: UseIngestionStatusArgs) => {
  const { documentVersionId, enabled = true } = args

  const query = useQuery<
    IngestionStatusResponse,
    ErrorResponse<AxiosError>,
    IngestionStatusResponse,
    [string, string | null]
  >({
    queryKey: [queryKeys.rag.ingestion.status, documentVersionId],
    queryFn: () => fetchIngestionStatus(documentVersionId as string),
    enabled: enabled && !!documentVersionId,
    refetchInterval: (query) => {
      const data = query.state.data
      if (data && isTerminalLifecycleState(data.lifecycleState)) {
        return false
      }
      return POLL_INTERVAL_MS
    },
  })

  return {
    ...query,
  }
}

export default useRagIngestionStatus
