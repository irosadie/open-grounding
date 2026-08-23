import { z } from "zod"

export const mcpTransports = ["stdio", "http", "sse"] as const
export const mcpAuthTypes = ["none", "bearer", "header"] as const

export const mcpTransportLabels = [
  { label: "Stdio", value: "stdio" },
  { label: "Streamable HTTP", value: "http" },
  { label: "SSE", value: "sse" },
]

export const mcpAuthTypeLabels = [
  { label: "No authentication", value: "none" },
  { label: "Bearer token", value: "bearer" },
  { label: "Header", value: "header" },
]

export const getMcpTransportLabel = (value: (typeof mcpTransports)[number]) =>
  mcpTransportLabels.find((item) => item.value === value)?.label ?? value

export const mcpServerSchema = z
  .object({
    name: z.string().min(1, "Name is required").max(120),
    transport: z.enum(mcpTransports),
    command: z.string().optional(),
    args: z.array(z.string()).default([]),
    url: z.string().url("Enter a valid URL").optional().or(z.literal("")),
    authType: z.enum(mcpAuthTypes).default("none"),
    credential: z.string().optional(),
    headers: z.record(z.string()).default({}),
    timeoutSeconds: z.number().int().min(1).max(120).default(30),
    maxPayloadBytes: z.number().int().min(65536).max(10485760).default(1048576),
    allowInsecure: z.boolean().default(false),
    enabled: z.boolean().default(true),
  })
  .superRefine((value, context) => {
    if (value.transport === "stdio" && !value.command?.trim()) {
      context.addIssue({
        code: "custom",
        path: ["command"],
        message: "Command is required for stdio",
      })
    }
    if (value.transport !== "stdio" && !value.url) {
      context.addIssue({
        code: "custom",
        path: ["url"],
        message: "URL is required for remote transports",
      })
    }
    if (value.url?.startsWith("http://") && !value.allowInsecure) {
      context.addIssue({
        code: "custom",
        path: ["allowInsecure"],
        message: "Enable insecure HTTP explicitly",
      })
    }
  })

export type McpServerSchemaProps = z.infer<typeof mcpServerSchema>

export const invokeToolSchema = z.object({
  arguments: z.record(z.unknown()).default({}),
})

export type InvokeToolSchemaProps = z.infer<typeof invokeToolSchema>
