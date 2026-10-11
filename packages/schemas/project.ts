import { z } from "zod"

export const projectCreateSchema = z.object({
  name: z.string().min(1).max(255),
  slug: z
    .string()
    .min(1)
    .max(120)
    .regex(/^[a-z0-9]+(?:-[a-z0-9]+)*$/),
  knowledgeBaseIds: z.array(z.string()).default([]),
})

export type ProjectCreateInput = z.infer<typeof projectCreateSchema>
