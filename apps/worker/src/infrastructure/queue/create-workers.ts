import type { Worker } from "bullmq"
import type Redis from "ioredis"
import { createToolExecutionWorker } from "./processors/tool-execution.processor.js"

export const createWorkers = (connection: Redis): Worker[] => [
  createToolExecutionWorker(connection),
]
