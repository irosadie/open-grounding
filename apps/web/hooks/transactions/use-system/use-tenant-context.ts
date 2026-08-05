"use client"

import { apiRouters, queryKeys } from "$/constants"
import { axios } from "$/services/axios"
import type { ErrorResponse } from "$/types/generals"
import { useQuery } from "@tanstack/react-query"
import type { TenantContextResponse } from "@vibecoding-starter/types"
import type { AxiosError } from "axios"

const fetchTenantContext = async () => {
  const result = await axios<TenantContextResponse>({
    method: "GET",
    url: apiRouters.auth.tenantContext,
  })
  return result
}

type UseTenantContextArgs = {
  enabled?: boolean
}

export const useTenantContext = (args?: UseTenantContextArgs) => {
  const { enabled = true } = args || {}

  const query = useQuery<
    TenantContextResponse,
    ErrorResponse<AxiosError>,
    TenantContextResponse,
    [string]
  >({
    queryKey: [queryKeys.auth.tenantContext],
    queryFn: fetchTenantContext,
    enabled,
  })

  return {
    ...query,
  }
}

export default useTenantContext
