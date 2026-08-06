import { z } from "zod"

export const memoryConfigSchema = z.object({
  enabled: z.boolean().default(false),
  summarizationModelProfileId: z.string().min(1, "Summarization model profile is required"),
  embeddingProfileId: z.string().min(1, "Embedding profile is required"),
  retentionDays: z.number().int().min(1).max(365).default(90),
  retrievalTopK: z.number().int().min(1).max(20).default(5),
  minTurnsToSummarize: z.number().int().min(1).max(20).default(3),
  systemPrompt: z.string().min(1, "System prompt is required"),
})

export type MemoryConfigInput = z.infer<typeof memoryConfigSchema>
