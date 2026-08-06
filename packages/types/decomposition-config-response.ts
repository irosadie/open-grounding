export type DecompositionConfigResponse = {
  id: string
  knowledgeBaseId: string
  enabled: boolean
  modelProfileId: string
  systemPrompt: string
  userPromptTemplate: string
  maxSubQueries: number
  maxDepth: number
  minComplexityScore: number
  guardrails: Record<string, unknown>
  createdAt: string
  updatedAt: string
}

export type DecompositionDefaultsResponse = {
  systemPrompt: string
  userPromptTemplate: string
  maxSubQueries: number
  maxDepth: number
  minComplexityScore: number
  guardrails: Record<string, unknown>
}
