"use client"

import { apiRouters, queryKeys } from "$/constants"
import { axios } from "$/services/axios"
import type { ErrorResponse } from "$/types/generals"
import { pathVariable } from "$/utils/path-variable"
import type { PlannerConfigInput } from "@open-grounding/schemas"
import type {
  PlannerConfigResponse,
  PlannerDefaultsResponse,
} from "@open-grounding/types"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import type { AxiosError } from "axios"

export const usePlannerConfig = (knowledgeBaseId: string | null) =>
  useQuery<PlannerConfigResponse, ErrorResponse<AxiosError>>({
    queryKey: [queryKeys.rag.knowledgeBases.planner, knowledgeBaseId],
    queryFn: () =>
      axios<PlannerConfigResponse>({
        method: "GET",
        url: pathVariable(apiRouters.rag.knowledgeBases.planner, {
          id: knowledgeBaseId as string,
        }),
      }),
    enabled: !!knowledgeBaseId,
    retry: false,
  })

export const usePlannerDefaults = (knowledgeBaseId: string | null) =>
  useQuery<PlannerDefaultsResponse, ErrorResponse<AxiosError>>({
    queryKey: [queryKeys.rag.knowledgeBases.plannerDefaults, knowledgeBaseId],
    queryFn: () =>
      axios<PlannerDefaultsResponse>({
        method: "GET",
        url: pathVariable(apiRouters.rag.knowledgeBases.plannerDefaults, {
          id: knowledgeBaseId as string,
        }),
      }),
    enabled: !!knowledgeBaseId,
  })

export const useUpsertPlannerConfig = (knowledgeBaseId: string) => {
  const queryClient = useQueryClient()
  return useMutation<
    PlannerConfigResponse,
    ErrorResponse<AxiosError>,
    PlannerConfigInput
  >({
    mutationKey: [queryKeys.rag.knowledgeBases.planner, knowledgeBaseId],
    mutationFn: (data) =>
      axios<PlannerConfigResponse>({
        method: "POST",
        url: pathVariable(apiRouters.rag.knowledgeBases.planner, {
          id: knowledgeBaseId,
        }),
        data: {
          enabled: data.enabled,
          model_profile_id: data.modelProfileId,
          system_prompt: data.systemPrompt,
          user_prompt_template: data.userPromptTemplate,
          max_tasks: data.maxTasks,
          task_timeout_seconds: data.taskTimeoutSeconds,
          task_types: data.taskTypes,
          mcp_enabled: data.mcpEnabled,
          guardrails: data.guardrails,
        },
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: [queryKeys.rag.knowledgeBases.planner, knowledgeBaseId],
      })
    },
  })
}

export const useDeletePlannerConfig = (knowledgeBaseId: string) => {
  const queryClient = useQueryClient()
  return useMutation<void, ErrorResponse<AxiosError>, void>({
    mutationKey: [
      queryKeys.rag.knowledgeBases.planner,
      knowledgeBaseId,
      "delete",
    ],
    mutationFn: () =>
      axios<void>({
        method: "DELETE",
        url: pathVariable(apiRouters.rag.knowledgeBases.planner, {
          id: knowledgeBaseId,
        }),
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: [queryKeys.rag.knowledgeBases.planner, knowledgeBaseId],
      })
    },
  })
}
