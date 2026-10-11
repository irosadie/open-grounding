"use client"

import { apiRouters, queryKeys } from "$/constants"
import { axios } from "$/services/axios"
import type { ErrorResponse } from "$/types/generals"
import { pathVariable } from "$/utils/path-variable"
import type { ProjectCreateInput } from "@open-grounding/schemas"
import type {
  ProjectListResponse,
  ProjectResponse,
} from "@open-grounding/types"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import type { AxiosError } from "axios"

const projectUrl = (template: string, id: string) =>
  pathVariable(template, { id })

export const useProjects = () =>
  useQuery<ProjectListResponse, ErrorResponse<AxiosError>>({
    queryKey: [queryKeys.rag.projects.list],
    queryFn: () => axios({ method: "GET", url: apiRouters.rag.projects.list }),
  })

export const useProject = (projectId: string | null) =>
  useQuery<ProjectResponse, ErrorResponse<AxiosError>>({
    queryKey: [queryKeys.rag.projects.detail, projectId],
    queryFn: () =>
      axios({
        method: "GET",
        url: projectUrl(apiRouters.rag.projects.detail, projectId as string),
      }),
    enabled: !!projectId,
    retry: false,
  })

export const useCreateProject = () => {
  const queryClient = useQueryClient()
  return useMutation<
    ProjectResponse,
    ErrorResponse<AxiosError>,
    ProjectCreateInput
  >({
    mutationKey: [queryKeys.rag.projects.list, "create"],
    mutationFn: (data) =>
      axios({
        method: "POST",
        url: apiRouters.rag.projects.create,
        data: {
          name: data.name,
          slug: data.slug,
          knowledge_base_ids: data.knowledgeBaseIds,
        },
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: [queryKeys.rag.projects.list],
      })
    },
  })
}

export const useAssignProjectKnowledgeBase = (projectId: string) => {
  const queryClient = useQueryClient()
  return useMutation<ProjectResponse, ErrorResponse<AxiosError>, string>({
    mutationKey: [queryKeys.rag.projects.detail, projectId, "membership"],
    mutationFn: (knowledgeBaseId) =>
      axios({
        method: "POST",
        url: projectUrl(apiRouters.rag.projects.assignKnowledgeBase, projectId),
        data: { knowledge_base_id: knowledgeBaseId },
      }),
    onSuccess: (project) => {
      void queryClient.setQueryData(
        [queryKeys.rag.projects.detail, projectId],
        project,
      )
      void queryClient.invalidateQueries({
        queryKey: [queryKeys.rag.projects.list],
      })
      void queryClient.invalidateQueries({
        queryKey: [queryKeys.rag.knowledgeBases.list],
      })
    },
  })
}
