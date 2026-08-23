import { describe, expect, it } from "vitest"
import {
  getCurrentStageIndex,
  getIngestionStage,
  getIngestionStageLabel,
  ingestionStages,
  isIngestionTerminal,
} from "./ingestion-pipeline"

describe("ingestion pipeline", () => {
  it("maps lifecycle states to the correct stage", () => {
    expect(getIngestionStage("PENDING")).toBe("intake")
    expect(getIngestionStage("STORED")).toBe("parse")
    expect(getIngestionStage("PARSING")).toBe("parse")
    expect(getIngestionStage("EMBEDDING")).toBe("embed")
    expect(getIngestionStage("INDEXING")).toBe("index")
    expect(getIngestionStage("READY")).toBe("complete")
    expect(getIngestionStage("FAILED")).toBe("complete")
  })

  it("returns the intake stage for unknown states", () => {
    expect(getIngestionStage("UNKNOWN")).toBe("intake")
  })

  it("computes a non-negative current stage index", () => {
    expect(getCurrentStageIndex("PENDING")).toBeGreaterThanOrEqual(0)
    expect(getCurrentStageIndex("INDEXING")).toBeGreaterThan(
      getCurrentStageIndex("PARSING"),
    )
    expect(getCurrentStageIndex("READY")).toBe(ingestionStages.length - 1)
  })

  it("labels lifecycle states", () => {
    expect(getIngestionStageLabel("READY")).toBe("Ready")
    expect(getIngestionStageLabel("PARSING")).toBe("Parsing")
  })

  it("identifies terminal states", () => {
    expect(isIngestionTerminal("READY")).toBe(true)
    expect(isIngestionTerminal("FAILED")).toBe(true)
    expect(isIngestionTerminal("PARSING")).toBe(false)
  })
})
