import { z } from "zod"

export const knowledgeBaseCreateSchema = z.object({
  name: z
    .string()
    .min(1, "Name is required")
    .max(255, "Name must be 255 characters or less"),
  slug: z
    .string()
    .min(1, "Slug is required")
    .max(120, "Slug must be 120 characters or less")
    .regex(
      /^[a-z0-9]+(?:-[a-z0-9]+)*$/,
      "Slug must be lowercase kebab-case (e.g. my-knowledge-base)",
    ),
})

export type KnowledgeBaseCreateProps = z.infer<typeof knowledgeBaseCreateSchema>
