export type RagCitationResponse = {
  citationId: string
  documentVersionId: string
  title: string
  locator: string | null
  snippet: string
}

export type RagQueryResponse = {
  // BUG-PKG-01: backend _render_answer() returns a string, not a Record.
  answer: string | null
  route: "grounded" | "answered" | "clarify" | "abstain" | "refused"
  evidenceLevel: "high" | "medium" | "low" | "none"
  citations: RagCitationResponse[]
  limitations: string[]
  traceId: string
}

export type RagAnswerFeedbackResponse = {
  success: boolean
}
