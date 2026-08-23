export type IngestionConfigResponse = {
  id: string | null
  knowledgeBaseId: string
  minTextCoverage: number
  maxInvalidCharRatio: number
  minAggregateConfidence: number
  minPageCoverage: number
  autoReview: boolean
  parser: string
  doclingServeUrl: string | null
  doclingServeApiKeySet: boolean
  createdAt: string | null
  updatedAt: string | null
  isDefault: boolean
}
