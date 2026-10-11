export type AnswerBehaviorProfileResponse = {
  id?: string
  knowledgeBaseId?: string | null
  projectId?: string | null
  version: string
  scope: "DEPLOYMENT" | "TENANT" | "PROJECT" | "KNOWLEDGE_BASE"
  persona: string
  responseStyle: "CONCISE" | "BALANCED" | "DETAILED"
  maxOutputTokens: number
  sourcePolicy: "DOCUMENT_ONLY" | "DOCUMENT_OR_MCP" | "DOCUMENT_MCP_GENERAL"
  greetingPolicy: "ALLOW_UNGROUNDED" | "REQUIRE_ALLOWED_SOURCE" | "REFUSE"
  noEvidenceAction: "ABSTAIN" | "REFUSE" | "ANSWER_UNGROUNDED"
  requireCitations: boolean
  allowMcpSources: boolean
  isActive: boolean
  createdAt?: string
  updatedAt?: string
}

export type GuardrailProfileResponse = {
  id?: string
  knowledgeBaseId?: string | null
  projectId?: string | null
  version: string
  scope: "DEPLOYMENT" | "TENANT" | "PROJECT" | "KNOWLEDGE_BASE"
  inputRules: string[]
  toolRules: string[]
  outputRules: string[]
  maxToolCalls: number
  maxToolTimeoutSeconds: number
  maxToolPayloadBytes: number
  maxMcpFreshnessSeconds: number
  requireToolConfirmation: boolean
  isActive: boolean
  createdAt?: string
  updatedAt?: string
}

export type AnswerPolicyDefaultsResponse = {
  answerBehavior: AnswerBehaviorProfileResponse
  guardrails: GuardrailProfileResponse
  deploymentMaxOutputTokens: number
}

export type EffectiveAnswerPolicyResponse = {
  knowledgeBaseId?: string | null
  projectId?: string | null
  answerBehaviorVersion: string
  guardrailVersion: string
  answerBehavior: AnswerBehaviorProfileResponse
  guardrails: GuardrailProfileResponse
}
