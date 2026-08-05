"use client"

import { apiRouters, queryKeys } from "$/constants"
import { axios } from "$/services/axios"
import type { ErrorResponse } from "$/types/generals"
import { pathVariable } from "$/utils/path-variable"
import type {
  ProviderCredentialListResponse,
  ProviderCredentialRevokeResponse,
  ProviderCredentialSetResponse,
} from "@open-grounding/types"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import type { AxiosError } from "axios"

export const useProviderCredentials = () => {
  return useQuery<ProviderCredentialListResponse, ErrorResponse<AxiosError>>({
    queryKey: [queryKeys.rag.providerCredentials.list],
    queryFn: () =>
      axios<ProviderCredentialListResponse>({
        method: "GET",
        url: apiRouters.rag.providerCredentials.list,
      }),
  })
}

export const useSetProviderCredential = () => {
  const queryClient = useQueryClient()
  return useMutation<
    ProviderCredentialSetResponse,
    ErrorResponse<AxiosError>,
    { provider: string; keyName: string; value: string }
  >({
    mutationKey: [queryKeys.rag.providerCredentials.set],
    mutationFn: ({ provider, keyName, value }) =>
      axios<ProviderCredentialSetResponse>({
        method: "POST",
        url: apiRouters.rag.providerCredentials.set,
        data: { provider, key_name: keyName, value },
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: [queryKeys.rag.providerCredentials.list],
      })
    },
  })
}

export const useRevokeProviderCredential = () => {
  const queryClient = useQueryClient()
  return useMutation<
    ProviderCredentialRevokeResponse,
    ErrorResponse<AxiosError>,
    { provider: string; keyName: string }
  >({
    mutationKey: [queryKeys.rag.providerCredentials.revoke],
    mutationFn: ({ provider, keyName }) =>
      axios<ProviderCredentialRevokeResponse>({
        method: "DELETE",
        url: pathVariable(apiRouters.rag.providerCredentials.revoke, {
          provider,
          keyName,
        }),
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: [queryKeys.rag.providerCredentials.list],
      })
    },
  })
}
