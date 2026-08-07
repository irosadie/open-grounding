"use client"

import { apiRouters, queryKeys } from "$/constants"
import { axios } from "$/services/axios"
import type { ErrorResponse } from "$/types/generals"
import { pathVariable } from "$/utils/path-variable"
import {
  type InvokeToolSchemaProps,
  type McpServerSchemaProps,
  invokeToolSchema,
  mcpServerSchema,
} from "@open-grounding/schemas"
import type {
  McpConnectionTestResponse,
  McpInvocationListResponse,
  McpServerResponse,
  McpToolInvokeResponse,
  McpToolResponse,
} from "@open-grounding/types"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import type { AxiosError } from "axios"

type ServerPayload = McpServerSchemaProps
type ServerResponse = McpServerResponse
type ApiError = ErrorResponse<AxiosError>

const toServerPayload = (payload: ServerPayload) => ({
  name: payload.name,
  transport: payload.transport,
  command: payload.transport === "stdio" ? payload.command : undefined,
  args: payload.transport === "stdio" ? payload.args : [],
  url: payload.transport === "stdio" ? undefined : payload.url,
  auth_type: payload.authType,
  credential: payload.credential || undefined,
  headers_json: payload.headers,
  timeout_seconds: payload.timeoutSeconds,
  max_payload_bytes: payload.maxPayloadBytes,
  allow_insecure: payload.allowInsecure,
  enabled: payload.enabled,
})

export const useMcpServers = () =>
  useQuery<ServerResponse[], ApiError>({
    queryKey: [queryKeys.rag.mcp.servers],
    queryFn: () =>
      axios<ServerResponse[]>({
        method: "GET",
        url: apiRouters.rag.mcp.servers,
      }),
  })

export const useCreateMcpServer = () => {
  const queryClient = useQueryClient()
  return useMutation<ServerResponse, ApiError, ServerPayload>({
    mutationKey: [queryKeys.rag.mcp.servers],
    mutationFn: (payload) =>
      axios<ServerResponse>({
        method: "POST",
        url: apiRouters.rag.mcp.servers,
        data: toServerPayload(mcpServerSchema.parse(payload)),
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: [queryKeys.rag.mcp.servers],
      })
    },
  })
}

export const useUpdateMcpServer = () => {
  const queryClient = useQueryClient()
  return useMutation<
    ServerResponse,
    ApiError,
    { id: string; payload: ServerPayload }
  >({
    mutationKey: [queryKeys.rag.mcp.servers],
    mutationFn: ({ id, payload }) =>
      axios<ServerResponse>({
        method: "PUT",
        url: pathVariable(apiRouters.rag.mcp.server, { id }),
        data: toServerPayload(mcpServerSchema.parse(payload)),
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: [queryKeys.rag.mcp.servers],
      })
    },
  })
}

export const useDeleteMcpServer = () => {
  const queryClient = useQueryClient()
  return useMutation<unknown, ApiError, string>({
    mutationKey: [queryKeys.rag.mcp.servers],
    mutationFn: (id) =>
      axios({
        method: "DELETE",
        url: pathVariable(apiRouters.rag.mcp.server, { id }),
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: [queryKeys.rag.mcp.servers],
      })
    },
  })
}

export const useMcpServerTest = () =>
  useMutation<McpConnectionTestResponse, ApiError, string>({
    mutationKey: [queryKeys.rag.mcp.test],
    mutationFn: (id) =>
      axios({
        method: "POST",
        url: pathVariable(apiRouters.rag.mcp.test, { id }),
      }),
  })

export const useMcpServerDiscover = () => {
  const queryClient = useQueryClient()
  return useMutation<McpToolResponse[], ApiError, string>({
    mutationKey: [queryKeys.rag.mcp.discover],
    mutationFn: (id) =>
      axios({
        method: "POST",
        url: pathVariable(apiRouters.rag.mcp.discover, { id }),
      }),
    onSuccess: (_, id) => {
      void queryClient.invalidateQueries({
        queryKey: [queryKeys.rag.mcp.tools, id],
      })
    },
  })
}

export const useMcpTools = (serverId: string) =>
  useQuery<McpToolResponse[], ApiError>({
    queryKey: [queryKeys.rag.mcp.tools, serverId],
    queryFn: () =>
      axios({
        method: "GET",
        url: pathVariable(apiRouters.rag.mcp.tools, { id: serverId }),
      }),
    enabled: Boolean(serverId),
  })

export const useUpdateMcpTool = () => {
  const queryClient = useQueryClient()
  return useMutation<
    McpToolResponse,
    ApiError,
    { id: string; allowed: boolean }
  >({
    mutationKey: [queryKeys.rag.mcp.updateTool],
    mutationFn: ({ id, allowed }) =>
      axios({
        method: "PUT",
        url: pathVariable(apiRouters.rag.mcp.tool, { id }),
        data: { allowed },
      }),
    onSuccess: (tool) => {
      void queryClient.invalidateQueries({
        queryKey: [queryKeys.rag.mcp.tools, tool.serverId],
      })
    },
  })
}

export const useMcpToolInvoke = () =>
  useMutation<
    McpToolInvokeResponse,
    ApiError,
    { id: string; payload: InvokeToolSchemaProps }
  >({
    mutationKey: [queryKeys.rag.mcp.invoke],
    mutationFn: ({ id, payload }) =>
      axios<McpToolInvokeResponse>({
        method: "POST",
        url: pathVariable(apiRouters.rag.mcp.invoke, { id }),
        data: invokeToolSchema.parse(payload),
      }),
  })

export const useMcpInvocations = (filters?: {
  serverId?: string
  status?: string
  userId?: string
  from?: string
  to?: string
}) =>
  useQuery<McpInvocationListResponse, ApiError>({
    queryKey: [queryKeys.rag.mcp.invocations, filters],
    queryFn: () =>
      axios({
        method: "GET",
        url: apiRouters.rag.mcp.invocations,
        params: {
          server_id: filters?.serverId,
          status: filters?.status,
          user_id: filters?.userId,
          created_after: filters?.from,
          created_before: filters?.to,
        },
      }),
  })
