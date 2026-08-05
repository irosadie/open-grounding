import { z } from "zod"

export const ragQueryRoutes = ["grounded", "clarify", "abstain"] as const

export const ragQueryRouteLabels = [
  { label: "Grounded", value: "grounded" },
  { label: "Clarify", value: "clarify" },
  { label: "Abstain", value: "abstain" },
]

export const getRagQueryRouteLabel = (
  value: (typeof ragQueryRoutes)[number],
) => {
  return (
    ragQueryRouteLabels.find((item) => item.value === value)?.label ?? value
  )
}

export const ragEvidenceLevels = ["high", "medium", "low", "none"] as const

export const ragEvidenceLevelLabels = [
  { label: "High", value: "high" },
  { label: "Medium", value: "medium" },
  { label: "Low", value: "low" },
  { label: "None", value: "none" },
]

export const getRagEvidenceLevelLabel = (
  value: (typeof ragEvidenceLevels)[number],
) => {
  return (
    ragEvidenceLevelLabels.find((item) => item.value === value)?.label ?? value
  )
}

export const ragQuerySchema = z.object({
  message: z
    .string()
    .min(1, "Question is required")
    .max(8000, "Question must be 8000 characters or less"),
  knowledgeBaseIds: z
    .array(z.string().min(1))
    .min(1, "Select at least one knowledge base")
    .max(20, "Select at most 20 knowledge bases"),
  conversationId: z
    .string()
    .max(120, "Conversation id must be 120 characters or less")
    .optional(),
  mode: z.literal("grounded").default("grounded"),
  stream: z.boolean().default(false),
})

export type RagQueryProps = z.infer<typeof ragQuerySchema>

export const ragAnswerFeedbackSchema = z.object({
  rating: z
    .number()
    .int()
    .min(1, "Rating must be between 1 and 5")
    .max(5, "Rating must be between 1 and 5")
    .optional(),
  comment: z
    .string()
    .max(2000, "Comment must be 2000 characters or less")
    .optional(),
})

export type RagAnswerFeedbackProps = z.infer<typeof ragAnswerFeedbackSchema>
