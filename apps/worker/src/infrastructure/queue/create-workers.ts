import type { Worker } from "bullmq"
import type Redis from "ioredis"
import { createCalibrationWorker } from "./processors/calibration.processor.js"
import { createSyntheticFixtureWorker } from "./processors/synthetic-fixture.processor.js"
import { createToolExecutionWorker } from "./processors/tool-execution.processor.js"

export const createWorkers = (connection: Redis): Worker[] => [
  createToolExecutionWorker(connection),
  createCalibrationWorker(connection),
  createSyntheticFixtureWorker(connection),
]
