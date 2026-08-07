import { Worker, type Job } from "bullmq"
import type Redis from "ioredis"
import { env } from "../../config/env.js"

interface CalibrationJobData {
  tenant_id: string
  profile_id: string
  fixture_id: string
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

const processCalibration = async (job: Job<CalibrationJobData>): Promise<unknown> => {
  const { tenant_id, profile_id, fixture_id, trace_id } = job.data
  return callInternalApi("/internal/confidence/calibrate", {
    tenant_id,
    profile_id,
    fixture_id,
    trace_id,
  })
}

export const createCalibrationWorker = (connection: Redis): Worker => {
  const worker = new Worker<CalibrationJobData>(
    "calibration",
    async (job) => {
      try {
        return await processCalibration(job)
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error)
        process.stderr.write(`[calibration] job=${job.id} error: ${message}\n`)
        throw error
      }
    },
    { connection, concurrency: 2 }
  )

  worker.on("completed", (job) => {
    process.stdout.write(`[calibration] job=${job.id} completed\n`)
  })

  worker.on("failed", (job, error) => {
    process.stderr.write(`[calibration] job=${job?.id} failed: ${error.message}\n`)
  })

  return worker
}
