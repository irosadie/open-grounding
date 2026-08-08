import { z } from "zod"

export const ingestionConfigSchema = z.object({
  minTextCoverage: z.number().min(0).max(1).default(0.3),
  maxInvalidCharRatio: z.number().min(0).max(1).default(0.1),
  minAggregateConfidence: z.number().min(0).max(1).default(0.5),
  minPageCoverage: z.number().min(0).max(1).default(0.5),
  autoReview: z.boolean().default(false),
})

export type IngestionConfigInput = z.infer<typeof ingestionConfigSchema>
