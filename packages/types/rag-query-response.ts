export type RagCitationResponse = {
  citationId: string
  documentVersionId: string
  title: string
  locator: string | null
  snippet: string
}

export type RagQueryResponse = {
  answer: Record<string, unknown> | null
  route: "grounded" | "clarify" | "abstain"
  evidenceLevel: "high" | "medium" | "low" | "none"
  citations: RagCitationResponse[]
  limitations: string[]
  traceId: string
}

export type RagAnswerFeedbackResponse = {
  success: boolean
}
