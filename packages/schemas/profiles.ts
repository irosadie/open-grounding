import { z } from "zod"

export const modelProfileKinds = [
  "DENSE_EMBEDDING",
  "SPARSE_EMBEDDING",
  "RERANKER",
  "GENERATION",
] as const

export const modelProfileModalities = ["TEXT", "IMAGE", "MULTIMODAL"] as const

export const modelProfileProviders = ["fastembed", "openai", "ollama"] as const

export const modelProfileCreateSchema = z.object({
  name: z.string().min(1, "Name is required").max(255),
  profileKind: z.enum(modelProfileKinds, {
    errorMap: () => ({ message: "Invalid profile kind" }),
  }),
  provider: z.enum(modelProfileProviders, {
    errorMap: () => ({ message: "Invalid provider" }),
  }),
  model: z.string().min(1, "Model is required").max(255),
  modality: z.enum(modelProfileModalities).default("TEXT"),
  dimensions: z.number().int().positive().optional(),
  configJson: z.string().optional(),
})

export type ModelProfileCreateProps = z.infer<typeof modelProfileCreateSchema>

export const indexProfileChunkingStrategies = [
  "RECURSIVE",
  "SENTENCE",
  "FIXED",
  "PARAGRAPH",
] as const

export const indexProfileDistanceMetrics = ["cosine", "dot", "euclid"] as const

export const indexProfileCreateSchema = z.object({
  name: z.string().min(1, "Name is required").max(255),
  embeddingProfileId: z.string().min(1, "Embedding profile is required"),
  sparseProfileId: z.string().optional(),
  rerankerProfileId: z.string().optional(),
  collection: z.string().min(1, "Collection is required").max(255),
  dimensions: z.number().int().positive("Dimensions must be positive"),
  distanceMetric: z.enum(indexProfileDistanceMetrics).default("cosine"),
  chunkingStrategy: z
    .enum(indexProfileChunkingStrategies)
    .default("RECURSIVE"),
  chunkSizeTokens: z.number().int().min(50).max(2000).default(400),
  chunkOverlapTokens: z.number().int().min(0).max(500).default(50),
  parentChunkSize: z.number().int().min(100).max(5000).default(1500),
})

export type IndexProfileCreateProps = z.infer<typeof indexProfileCreateSchema>
