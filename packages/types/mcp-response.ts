export type McpServerResponse = {
  id: string
  name: string
  transport: "stdio" | "http" | "sse"
  command: string | null
  args: string[]
  url: string | null
  authType: "none" | "bearer" | "header" | null
  hasCredential: boolean
  headers: Record<string, string>
  timeoutSeconds: number
  maxPayloadBytes: number
  allowInsecure: boolean
  enabled: boolean
  status: "unknown" | "connected" | "error"
  lastError: string | null
  createdAt: string
  updatedAt: string
}

export type McpToolResponse = {
  id: string
  serverId: string
  name: string
  description: string
  inputSchema: Record<string, unknown>
  allowed: boolean
  isStale: boolean
  lastDiscoveredAt: string
}

export type McpInvocationResponse = {
  id: string
  serverId: string
  toolId: string
  serverName?: string
  toolName?: string
  userId: string
  argsHash: string
  status: "success" | "error" | "timeout" | "denied"
  resultText: string | null
  durationMs: number
  createdAt: string
}

export type McpConnectionTestResponse = {
  status: "connected" | "error"
  latencyMs: number
  toolCount: number
  error?: string | null
}

export type McpInvocationListResponse = {
  items: McpInvocationResponse[]
  total: number
}

export type McpToolInvokeResponse = {
  result: unknown
}
