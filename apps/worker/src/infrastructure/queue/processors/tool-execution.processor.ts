import { Worker, type Job } from "bullmq"
import type Redis from "ioredis"
import { env } from "../../config/env.js"

interface ToolExecutionJobData {
  tenant_id: string
  profile_id: string
  tool_slug: string
  tool_definition_id: string
  input_data: Record<string, unknown>
  trace_id: string
  query_id: string
}

const callInternalApi = async (path: string, body: unknown): Promise<unknown> => {
  const response = await fetch(`${env.INTERNAL_API_URL}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Internal-Secret": env.INTERNAL_API_SECRET,
    },
    body: JSON.stringify(body),
  })
  if (!response.ok) {
    const text = await response.text()
    throw new Error(`Internal API error ${response.status}: ${text}`)
  }
  return response.json()
}

const processToolExecution = async (job: Job<ToolExecutionJobData>): Promise<unknown> => {
  const { tenant_id, tool_slug, tool_definition_id, input_data, trace_id, query_id } = job.data

  return callInternalApi("/internal/tools/execute", {
    tenant_id,
    tool_slug,
    tool_definition_id,
    input_data,
    trace_id,
    query_id,
  })
}

export const createToolExecutionWorker = (connection: Redis): Worker => {
  const worker = new Worker<ToolExecutionJobData>(
    "tool-execution",
    async (job) => {
      try {
        return await processToolExecution(job)
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error)
        process.stderr.write(`[tool-execution] job=${job.id} error: ${message}\n`)
        throw error
      }
    },
    { connection, concurrency: 5 }
  )

  worker.on("completed", (job) => {
    process.stdout.write(`[tool-execution] job=${job.id} completed\n`)
  })

  worker.on("failed", (job, error) => {
    process.stderr.write(`[tool-execution] job=${job?.id} failed: ${error.message}\n`)
  })

  return worker
}
