export type RagCitationResponse = {
  citationId: string
  documentVersionId: string
  title: string
  locator: string | null
  snippet: string
  sourceKind: "DOCUMENT" | "MCP"
  sourceId?: string | null
  serverId?: string | null
  toolId?: string | null
  invocationId?: string | null
  traceId?: string | null
  producedAt?: string | null
  expiresAt?: string | null
}

export type RagQueryResponse = {
  // BUG-PKG-01: backend _render_answer() returns a string, not a Record.
  answer: string | null
  route: "grounded" | "answered" | "clarify" | "abstain" | "refused"
  evidenceLevel: "high" | "medium" | "low" | "none"
  citations: RagCitationResponse[]
  limitations: string[]
  traceId: string
  conversationId: string
}

export type RagAnswerFeedbackResponse = {
  success: boolean
}
