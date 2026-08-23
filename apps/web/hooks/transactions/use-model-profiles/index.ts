"use client"

import { apiRouters, queryKeys } from "$/constants"
import { axios } from "$/services/axios"
import type { ErrorResponse } from "$/types/generals"
import { pathVariable } from "$/utils/path-variable"
import {
  type ModelProfileCreateProps,
  modelProfileCreateSchema,
} from "@open-grounding/schemas"
import type {
  ModelProfileCreateResponse,
  ModelProfileListResponse,
} from "@open-grounding/types"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import type { AxiosError } from "axios"

export const useModelProfiles = () => {
  return useQuery<ModelProfileListResponse, ErrorResponse<AxiosError>>({
    queryKey: [queryKeys.rag.modelProfiles.list],
    queryFn: () =>
      axios<ModelProfileListResponse>({
        method: "GET",
        url: apiRouters.rag.modelProfiles.list,
      }),
  })
}

export const useCreateModelProfile = () => {
  const queryClient = useQueryClient()
  return useMutation<
    ModelProfileCreateResponse,
    ErrorResponse<AxiosError>,
    ModelProfileCreateProps
  >({
    mutationKey: [queryKeys.rag.modelProfiles.create],
    mutationFn: async (payload) => {
      const validated = modelProfileCreateSchema.parse(payload)
      return axios<ModelProfileCreateResponse>({
        method: "POST",
        url: apiRouters.rag.modelProfiles.create,
        data: {
          name: validated.name,
          profile_kind: validated.profileKind,
          provider: validated.provider,
          model: validated.model,
          modality: validated.modality,
          dimensions: validated.dimensions,
          config_json: validated.configJson,
        },
      })
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: [queryKeys.rag.modelProfiles.list],
      })
    },
  })
}

export const useDeleteModelProfile = () => {
  const queryClient = useQueryClient()
  return useMutation<unknown, ErrorResponse<AxiosError>, string>({
    mutationKey: [queryKeys.rag.modelProfiles.delete],
    mutationFn: (id) =>
      axios({
        method: "DELETE",
        url: pathVariable(apiRouters.rag.modelProfiles.delete, { id }),
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: [queryKeys.rag.modelProfiles.list],
      })
    },
  })
}
