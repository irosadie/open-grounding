import { Worker, type Job } from "bullmq"
import type Redis from "ioredis"
import { env } from "../../config/env.js"

interface SyntheticFixtureJobData {
  tenant_id: string
  profile_id: string
  kb_id: string
  count: number
  trace_id: string
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

const processSyntheticFixture = async (job: Job<SyntheticFixtureJobData>): Promise<unknown> => {
  const { tenant_id, profile_id, kb_id, count, trace_id } = job.data
  return callInternalApi("/internal/confidence/fixtures/generate-synthetic", {
    tenant_id,
    profile_id,
    kb_id,
    count,
    trace_id,
  })
}

export const createSyntheticFixtureWorker = (connection: Redis): Worker => {
  const worker = new Worker<SyntheticFixtureJobData>(
    "synthetic-fixture",
    async (job) => {
      try {
        return await processSyntheticFixture(job)
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error)
        process.stderr.write(`[synthetic-fixture] job=${job.id} error: ${message}\n`)
        throw error
      }
    },
    { connection, concurrency: 2 }
  )

  worker.on("completed", (job) => {
    process.stdout.write(`[synthetic-fixture] job=${job.id} completed\n`)
  })

  worker.on("failed", (job, error) => {
    process.stderr.write(`[synthetic-fixture] job=${job?.id} failed: ${error.message}\n`)
  })

  return worker
}
