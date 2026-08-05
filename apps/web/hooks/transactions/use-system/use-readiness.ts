"use client"

import { apiRouters, queryKeys } from "$/constants"
import { axios } from "$/services/axios"
import type { ErrorResponse } from "$/types/generals"
import type { ReadinessResponse } from "@open-grounding/types"
import { useQuery } from "@tanstack/react-query"
import type { AxiosError } from "axios"

const fetchReadiness = async () => {
  const result = await axios<ReadinessResponse>({
    method: "GET",
    url: apiRouters.system.ready,
  })
  return result
}

type UseReadinessArgs = {
  enabled?: boolean
}

export const useReadiness = (args?: UseReadinessArgs) => {
  const { enabled = true } = args || {}

  const query = useQuery<
    ReadinessResponse,
    ErrorResponse<AxiosError>,
    ReadinessResponse,
    [string]
  >({
    queryKey: [queryKeys.system.ready],
    queryFn: fetchReadiness,
    enabled,
    refetchInterval: 30000,
  })

  return {
    ...query,
  }
}

export default useReadiness
