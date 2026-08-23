export type PlannerConfigResponse = {
  id: string
  knowledgeBaseId: string
  enabled: boolean
  modelProfileId: string
  systemPrompt: string
  userPromptTemplate: string
  maxTasks: number
  taskTimeoutSeconds: number
  taskTypes: Array<"RAG" | "MCP" | "GENERAL">
  mcpEnabled: boolean
  guardrails: Record<string, unknown>
  createdAt: string
  updatedAt: string
}

export type PlannerDefaultsResponse = {
  systemPrompt: string
  userPromptTemplate: string
  maxTasks: number
  taskTimeoutSeconds: number
  taskTypes: Array<"RAG" | "MCP" | "GENERAL">
  mcpEnabled: boolean
  guardrails: Record<string, unknown>
}
