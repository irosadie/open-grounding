import { describe, expect, it } from "vitest"
import { parseSseChunk } from "./use-rag-query-stream"

const sseBlock = (event: string, data: object) =>
  `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`

describe("parseSseChunk", () => {
  it("parses a single SSE block", () => {
    const chunk = sseBlock("response.started", { traceId: "t-1" })
    const events = parseSseChunk(chunk)
    expect(events).toHaveLength(1)
    expect(events[0]?.event).toBe("response.started")
    expect(events[0]?.data).toEqual({ traceId: "t-1" })
  })

  it("parses events in emitted order", () => {
    const chunk =
      sseBlock("response.started", { traceId: "t-1" }) +
      sseBlock("response.route", { route: "grounded" }) +
      sseBlock("response.delta", { answer: "Hello" }) +
      sseBlock("response.citations", { citations: [] }) +
      sseBlock("response.completed", {
        traceId: "t-1",
        evidenceLevel: "high",
        limitations: [],
      })
    const events = parseSseChunk(chunk)
    expect(events.map((e) => e.event)).toEqual([
      "response.started",
      "response.route",
      "response.delta",
      "response.citations",
      "response.completed",
    ])
  })

  it("parses the failed event", () => {
    const events = parseSseChunk(
      sseBlock("response.failed", { code: "QUERY_FAILED" }),
    )
    expect(events[0]?.event).toBe("response.failed")
    expect(events[0]?.data).toEqual({ code: "QUERY_FAILED" })
  })

  it("ignores incomplete blocks", () => {
    const events = parseSseChunk("event: response.started\ndata: {")
    expect(events).toHaveLength(0)
  })
})
