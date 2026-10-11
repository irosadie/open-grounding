import { z } from "zod"

export const policyScopes = ["DEPLOYMENT", "TENANT", "KNOWLEDGE_BASE"] as const
export const answerSourcePolicies = [
  "DOCUMENT_ONLY",
  "DOCUMENT_OR_MCP",
  "DOCUMENT_MCP_GENERAL",
] as const
export const greetingPolicies = [
  "ALLOW_UNGROUNDED",
  "REQUIRE_ALLOWED_SOURCE",
  "REFUSE",
] as const
export const noEvidenceActions = [
  "ABSTAIN",
  "REFUSE",
  "ANSWER_UNGROUNDED",
] as const
export const responseStyles = ["CONCISE", "BALANCED", "DETAILED"] as const
export const provenanceKinds = ["DOCUMENT", "MCP"] as const
export const guardrailStages = ["INPUT", "TOOL", "OUTPUT"] as const
export const guardrailDecisions = [
  "ALLOW",
  "DENY",
  "REDACT",
  "REQUIRE_CONFIRMATION",
  "FAIL_CLOSED",
] as const

export const answerBehaviorProfileSchema = z
  .object({
    version: z.string().min(1).max(120),
    scope: z.enum(policyScopes),
    persona: z.string().max(2000).default(""),
    responseStyle: z.enum(responseStyles).default("BALANCED"),
    maxOutputTokens: z.number().int().min(128).max(8192).default(1024),
    sourcePolicy: z.enum(answerSourcePolicies).default("DOCUMENT_MCP_GENERAL"),
    greetingPolicy: z.enum(greetingPolicies).default("ALLOW_UNGROUNDED"),
    noEvidenceAction: z.enum(noEvidenceActions).default("ANSWER_UNGROUNDED"),
    requireCitations: z.boolean().default(true),
    allowMcpSources: z.boolean().default(true),
    isActive: z.boolean().default(true),
  })
  .superRefine((value, context) => {
    if (
      value.noEvidenceAction === "ANSWER_UNGROUNDED" &&
      value.sourcePolicy !== "DOCUMENT_MCP_GENERAL"
    ) {
      context.addIssue({
        code: "custom",
        path: ["noEvidenceAction"],
        message: "ANSWER_UNGROUNDED requires DOCUMENT_MCP_GENERAL",
      })
    }
    if (value.sourcePolicy === "DOCUMENT_ONLY" && value.allowMcpSources) {
      context.addIssue({
        code: "custom",
        path: ["allowMcpSources"],
        message: "DOCUMENT_ONLY cannot enable MCP sources",
      })
    }
    const persona = value.persona.toLocaleLowerCase()
    if (
      persona.includes("ignore previous instructions") ||
      persona.includes("reveal the system prompt")
    ) {
      context.addIssue({
        code: "custom",
        path: ["persona"],
        message: "Persona conflicts with platform policy",
      })
    }
  })

export const guardrailProfileSchema = z.object({
  version: z.string().min(1).max(120),
  scope: z.enum(policyScopes),
  inputRules: z.array(z.string().min(1).max(80)).default([]),
  toolRules: z.array(z.string().min(1).max(80)).default([]),
  outputRules: z.array(z.string().min(1).max(80)).default([]),
  maxToolCalls: z.number().int().min(1).max(32).default(4),
  maxToolTimeoutSeconds: z.number().int().min(1).max(120).default(30),
  maxToolPayloadBytes: z
    .number()
    .int()
    .min(65536)
    .max(10485760)
    .default(1048576),
  maxMcpFreshnessSeconds: z.number().int().min(0).max(86400).default(900),
  requireToolConfirmation: z.boolean().default(false),
  isActive: z.boolean().default(true),
})

export const effectiveAnswerPolicySchema = z.object({
  answerBehavior: answerBehaviorProfileSchema,
  guardrails: guardrailProfileSchema,
})

export const answerBehaviorConfigSchema = z
  .object({
    version: z.string().min(1).max(120),
    persona: z.string().max(2000).default(""),
    responseStyle: z.enum(responseStyles).default("BALANCED"),
    maxOutputTokens: z.number().int().min(128).max(8192).default(1024),
    sourcePolicy: z.enum(answerSourcePolicies).default("DOCUMENT_MCP_GENERAL"),
    greetingPolicy: z.enum(greetingPolicies).default("ALLOW_UNGROUNDED"),
    noEvidenceAction: z.enum(noEvidenceActions).default("ANSWER_UNGROUNDED"),
    requireCitations: z.boolean().default(true),
    allowMcpSources: z.boolean().default(true),
  })
  .superRefine((value, context) => {
    if (
      value.noEvidenceAction === "ANSWER_UNGROUNDED" &&
      value.sourcePolicy !== "DOCUMENT_MCP_GENERAL"
    ) {
      context.addIssue({
        code: "custom",
        path: ["noEvidenceAction"],
        message: "ANSWER_UNGROUNDED requires DOCUMENT_MCP_GENERAL",
      })
    }
    if (value.sourcePolicy === "DOCUMENT_ONLY" && value.allowMcpSources) {
      context.addIssue({
        code: "custom",
        path: ["allowMcpSources"],
        message: "DOCUMENT_ONLY cannot enable MCP sources",
      })
    }
    const persona = value.persona.toLocaleLowerCase()
    if (
      persona.includes("ignore previous instructions") ||
      persona.includes("reveal the system prompt")
    ) {
      context.addIssue({
        code: "custom",
        path: ["persona"],
        message: "Persona conflicts with platform policy",
      })
    }
  })

export const guardrailConfigSchema = guardrailProfileSchema.omit({
  scope: true,
  isActive: true,
})

export type AnswerBehaviorProfileSchemaProps = z.infer<
  typeof answerBehaviorProfileSchema
>
export type GuardrailProfileSchemaProps = z.infer<typeof guardrailProfileSchema>
export type EffectiveAnswerPolicySchemaProps = z.infer<
  typeof effectiveAnswerPolicySchema
>
export type AnswerBehaviorConfigSchemaProps = z.infer<
  typeof answerBehaviorConfigSchema
>
export type GuardrailConfigSchemaProps = z.infer<typeof guardrailConfigSchema>
