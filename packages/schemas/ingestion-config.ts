import { z } from "zod"

export const PARSER_OPTIONS = ["auto", "docling_serve", "docling_inprocess", "pdfminer"] as const
export type ParserOption = (typeof PARSER_OPTIONS)[number]

export const ingestionConfigSchema = z.object({
  minTextCoverage: z.number().min(0).max(1).default(0.3),
  maxInvalidCharRatio: z.number().min(0).max(1).default(0.1),
  minAggregateConfidence: z.number().min(0).max(1).default(0.5),
  minPageCoverage: z.number().min(0).max(1).default(0.5),
  autoReview: z.boolean().default(false),
  parser: z.enum(PARSER_OPTIONS).default("auto"),
  doclingServeUrl: z.string().nullable().default(null),
  doclingServeApiKey: z.string().nullable().default(null),
})

export type IngestionConfigInput = z.infer<typeof ingestionConfigSchema>
