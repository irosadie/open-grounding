import { z } from "zod"

export const decompositionConfigSchema = z.object({
  enabled: z.boolean().default(true),
  modelProfileId: z.string().min(1, "Model profile is required"),
  systemPrompt: z.string().min(1, "System prompt is required"),
  userPromptTemplate: z.string().min(1, "User prompt template is required"),
  maxSubQueries: z.number().int().min(1).max(5).default(3),
  maxDepth: z.number().int().min(1).max(3).default(2),
  minComplexityScore: z.number().min(0).max(1).default(0.6),
  guardrails: z.record(z.unknown()).default({}),
})

export type DecompositionConfigInput = z.infer<typeof decompositionConfigSchema>
