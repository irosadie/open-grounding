export type IngestionConfigResponse = {
  id: string | null
  knowledgeBaseId: string
  minTextCoverage: number
  maxInvalidCharRatio: number
  minAggregateConfidence: number
  minPageCoverage: number
  autoReview: boolean
  createdAt: string | null
  updatedAt: string | null
  isDefault: boolean
}
