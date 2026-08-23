import { z } from "zod"

export const retrievalConfigSchema = z.object({
  denseWeight: z.number().min(0, "Must be at least 0").max(5, "Must be at most 5"),
  sparseWeight: z.number().min(0, "Must be at least 0").max(5, "Must be at most 5"),
  fusionK: z.number().int("Must be a whole number").min(1, "Must be at least 1").max(200, "Must be at most 200"),
  denseCandidates: z.number().int("Must be a whole number").min(1, "Must be at least 1").max(200, "Must be at most 200"),
  sparseCandidates: z.number().int("Must be a whole number").min(1, "Must be at least 1").max(200, "Must be at most 200"),
  fusedCandidates: z.number().int("Must be a whole number").min(1, "Must be at least 1").max(200, "Must be at most 200"),
  enabled: z.boolean(),
})

export type RetrievalConfigInput = z.infer<typeof retrievalConfigSchema>
