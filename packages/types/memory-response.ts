export type MemoryConfigResponse = {
  id: string
  knowledgeBaseId: string
  enabled: boolean
  summarizationModelProfileId: string
  embeddingProfileId: string
  retentionDays: number
  retrievalTopK: number
  minTurnsToSummarize: number
  systemPrompt: string
  createdAt: string
  updatedAt: string
}

export type MemoryConfigDefaultsResponse = {
  systemPrompt: string
  enabled: boolean
  retentionDays: number
  retrievalTopK: number
  minTurnsToSummarize: number
}

export type MemoryChunkResponse = {
  id: string
  knowledgeBaseId: string
  userId: string
  conversationId: string | null
  summary: string
  turnCount: number
  expiresAt: string
  createdAt: string
}

export type MemoryChunkListResponse = {
  items: MemoryChunkResponse[]
  total: number
  page: number
  pageSize: number
}
