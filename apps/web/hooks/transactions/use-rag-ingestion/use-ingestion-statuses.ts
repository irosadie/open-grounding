"use client"

import { apiRouters, queryKeys } from "$/constants"
import { axios } from "$/services/axios"
import type { ErrorResponse } from "$/types/generals"
import { pathVariable } from "$/utils/path-variable"
import { isTerminalLifecycleState } from "@open-grounding/schemas"
import type { IngestionStatusResponse } from "@open-grounding/types"
import { useQuery } from "@tanstack/react-query"
import type { AxiosError } from "axios"

const BASE_POLL_INTERVAL_MS = 3000
const MAX_POLL_INTERVAL_MS = 12000

const fetchIngestionStatus = async (documentVersionId: string) => {
  const result = await axios<IngestionStatusResponse>({
    method: "GET",
    url: pathVariable(apiRouters.rag.ingestion.status, { documentVersionId }),
  })
  return result
}

const fetchIngestionStatuses = async (
  versionIds: string[],
): Promise<Record<string, IngestionStatusResponse>> => {
  const entries = await Promise.all(
    versionIds.map(async (documentVersionId) => {
      const status = await fetchIngestionStatus(documentVersionId)
      return [documentVersionId, status] as const
    }),
  )
  return Object.fromEntries(entries)
}

type UseIngestionStatusesArgs = {
  versionIds: string[]
  enabled?: boolean
}

export const useIngestionStatuses = (args: UseIngestionStatusesArgs) => {
  const { versionIds, enabled = true } = args
  // Key material yang stabil: deduplikasi + urutkan agar urutan render
  // tidak mengubah queryKey dan cache tetap hit.
  const keyMaterial = [...new Set(versionIds)].sort().join(",")

  const query = useQuery<
    Record<string, IngestionStatusResponse>,
    ErrorResponse<AxiosError>
  >({
    queryKey: [queryKeys.rag.ingestion.status, "batch", keyMaterial],
    queryFn: () =>
      fetchIngestionStatuses(keyMaterial ? keyMaterial.split(",") : []),
    enabled: enabled && keyMaterial.length > 0,
    // Tab hidden: polling berhenti otomatis karena
    // refetchIntervalInBackground: false + visibility bawaan react-query
    // (tidak ada interval manual / dep tambahan).
    refetchIntervalInBackground: false,
    refetchInterval: (query) => {
      // Backoff saat error berurutan: 3s -> 6s -> 12s (max),
      // reset otomatis ke 3s saat fetch sukses (fetchFailureCount -> 0).
      const failures = query.state.fetchFailureCount ?? 0
      if (failures > 0) {
        return Math.min(
          BASE_POLL_INTERVAL_MS * 2 ** failures,
          MAX_POLL_INTERVAL_MS,
        )
      }
      const data = query.state.data
      if (!data) {
        return BASE_POLL_INTERVAL_MS
      }
      const statuses = Object.values(data)
      if (
        statuses.length > 0 &&
        statuses.every((status) =>
          isTerminalLifecycleState(status.lifecycleState),
        )
      ) {
        return false
      }
      return BASE_POLL_INTERVAL_MS
    },
  })

  return {
    ...query,
  }
}

export default useIngestionStatuses
