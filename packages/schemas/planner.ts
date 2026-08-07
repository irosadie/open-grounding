import { z } from "zod"

export const plannerTaskTypes = ["RAG", "MCP", "GENERAL"] as const

export const plannerConfigSchema = z.object({
  enabled: z.boolean().default(true),
  modelProfileId: z.string().min(1, "Model profile is required"),
  systemPrompt: z.string().min(1, "System prompt is required"),
  userPromptTemplate: z.string().min(1, "User prompt template is required"),
  maxTasks: z.number().int().min(1).max(8).default(4),
  taskTimeoutSeconds: z.number().int().min(1).max(60).default(15),
  taskTypes: z.array(z.enum(plannerTaskTypes)).min(1).default([...plannerTaskTypes]),
  mcpEnabled: z.boolean().default(false),
  guardrails: z.record(z.unknown()).default({}),
})

export const plannerOverrideSchema = z.object({
  enabled: z.boolean().optional(),
  maxTasks: z.number().int().min(1).max(8).optional(),
  taskTypes: z.array(z.enum(plannerTaskTypes)).min(1).optional(),
})

export type PlannerConfigInput = z.infer<typeof plannerConfigSchema>
export type PlannerOverrideInput = z.infer<typeof plannerOverrideSchema>
