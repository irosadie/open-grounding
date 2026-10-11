import { act, renderHook, waitFor } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import { parseSseChunk, useRagQueryStream } from "./use-rag-query-stream"

const sseBlock = (event: string, data: object) =>
  `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`

const sseTextBlock = (event: string, data: string) =>
  `event: ${event}\n${data
    .split("\n")
    .map((line) => `data: ${line}`)
    .join("\n")}\n\n`

describe("parseSseChunk", () => {
  it("parses a single SSE block", () => {
    const chunk = sseBlock("response.started", {
      traceId: "t-1",
      conversationId: "conversation-1",
    })
    const events = parseSseChunk(chunk)
    expect(events).toHaveLength(1)
    expect(events[0]?.event).toBe("response.started")
    expect(events[0]?.data).toEqual({
      traceId: "t-1",
      conversationId: "conversation-1",
    })
  })

  it("parses events in emitted order", () => {
    const chunk =
      sseBlock("response.started", { traceId: "t-1" }) +
      sseBlock("response.progress", {
        stage: "retrieving",
        message: "Mengambil referensi...",
      }) +
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
      "response.progress",
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

  it("parses a non-grounded answer route like any other response route", () => {
    const events = parseSseChunk(
      sseBlock("response.route", { route: "answered" }) +
        sseTextBlock("response.delta", "Hello from the LLM."),
    )

    expect(events.map((event) => event.data)).toEqual([
      { route: "answered" },
      "Hello from the LLM.",
    ])
  })

  it("parses multiline Markdown answer data without trimming its content", () => {
    const events = parseSseChunk(
      sseTextBlock(
        "response.delta",
        "- Main fact.\n\n### Inferences\n- Derived conclusion.",
      ),
    )

    expect(events[0]?.data).toBe(
      "- Main fact.\n\n### Inferences\n- Derived conclusion.",
    )
  })

  it("ignores incomplete blocks", () => {
    const events = parseSseChunk("event: response.started\ndata: {")
    expect(events).toHaveLength(0)
  })

  it("reuses the server conversation ID for follow-up requests", async () => {
    const responseBody = (conversationId: string) =>
      new ReadableStream<Uint8Array>({
        start(controller) {
          controller.enqueue(
            new TextEncoder().encode(
              sseBlock("response.started", {
                traceId: "trace-1",
                conversationId,
              }) +
                sseBlock("response.completed", {
                  traceId: "trace-1",
                  evidenceLevel: "none",
                  limitations: [],
                }),
            ),
          )
          controller.close()
        },
      })
    const fetchMock = vi.fn()
    fetchMock
      .mockResolvedValueOnce({ ok: true, body: responseBody("conversation-1") })
      .mockResolvedValueOnce({ ok: true, body: responseBody("conversation-1") })
    vi.stubGlobal("fetch", fetchMock)

    const { result } = renderHook(() => useRagQueryStream())
    await act(async () => {
      await result.current.stream({
        message: "first question",
        knowledgeBaseIds: ["kb-1"],
      })
    })
    await act(async () => {
      await result.current.stream({
        message: "follow-up question",
        knowledgeBaseIds: ["kb-1"],
      })
    })

    const firstPayload = JSON.parse(
      fetchMock.mock.calls[0]?.[1].body as string,
    ) as Record<string, unknown>
    const secondPayload = JSON.parse(
      fetchMock.mock.calls[1]?.[1].body as string,
    ) as Record<string, unknown>
    expect(firstPayload).not.toHaveProperty("conversation_id")
    expect(secondPayload.conversation_id).toBe("conversation-1")
    expect(result.current.conversationId).toBe("conversation-1")

    vi.unstubAllGlobals()
  })

  it("appends multiple validated answer deltas in order", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      body: new ReadableStream<Uint8Array>({
        start(controller) {
          controller.enqueue(
            new TextEncoder().encode(
              sseBlock("response.started", {
                traceId: "trace-1",
                conversationId: "conversation-1",
              }) +
                sseBlock("response.delta", { answer: "Hello " }) +
                sseBlock("response.delta", { answer: "world." }) +
                sseBlock("response.completed", {
                  traceId: "trace-1",
                  evidenceLevel: "none",
                  limitations: [],
                }),
            ),
          )
          controller.close()
        },
      }),
    })
    vi.stubGlobal("fetch", fetchMock)

    const { result } = renderHook(() => useRagQueryStream())
    const onCompleted = vi.fn()
    await act(async () => {
      await result.current.stream({
        message: "question",
        knowledgeBaseIds: ["kb-1"],
        onCompleted,
      })
    })

    expect(onCompleted).not.toHaveBeenCalled()
    await waitFor(() => {
      expect(result.current.answer).toBe("Hello world.")
      expect(result.current.state).toBe("completed")
    })
    expect(onCompleted).toHaveBeenCalledOnce()
    vi.unstubAllGlobals()
  })

  it("discards queued answer text when a newer query replaces the stream", async () => {
    const responseBody = (answer: string, traceId: string) =>
      new ReadableStream<Uint8Array>({
        start(controller) {
          controller.enqueue(
            new TextEncoder().encode(
              sseBlock("response.delta", { answer }) +
                sseBlock("response.completed", {
                  traceId,
                  evidenceLevel: "none",
                  limitations: [],
                }),
            ),
          )
          controller.close()
        },
      })
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        body: responseBody("stale answer", "trace-1"),
      })
      .mockResolvedValueOnce({
        ok: true,
        body: responseBody("fresh answer", "trace-2"),
      })
    vi.stubGlobal("fetch", fetchMock)

    const { result } = renderHook(() => useRagQueryStream())
    await act(async () => {
      await result.current.stream({
        message: "first question",
        knowledgeBaseIds: ["kb-1"],
      })
    })
    await act(async () => {
      await result.current.stream({
        message: "second question",
        knowledgeBaseIds: ["kb-1"],
      })
    })

    await waitFor(() => {
      expect(result.current.answer).toBe("fresh answer")
      expect(result.current.state).toBe("completed")
    })
    vi.unstubAllGlobals()
  })

  it("updates progress without adding it to the answer", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      body: new ReadableStream<Uint8Array>({
        start(controller) {
          controller.enqueue(
            new TextEncoder().encode(
              sseBlock("response.progress", {
                stage: "retrieving",
                message: "Mengambil referensi...",
                conversationId: "conversation-1",
              }) +
                sseBlock("response.delta", { answer: "Final answer." }) +
                sseBlock("response.completed", {
                  traceId: "trace-1",
                  evidenceLevel: "high",
                  limitations: [],
                }),
            ),
          )
          controller.close()
        },
      }),
    })
    vi.stubGlobal("fetch", fetchMock)

    const { result } = renderHook(() => useRagQueryStream())
    await act(async () => {
      await result.current.stream({
        message: "question",
        knowledgeBaseIds: ["kb-1"],
      })
    })

    expect(result.current.progress).toBe("Mengambil referensi...")
    await waitFor(() => expect(result.current.answer).toBe("Final answer."))
    expect(result.current.conversationId).toBe("conversation-1")
    vi.unstubAllGlobals()
  })

  it("renders raw Markdown deltas through the same answer state", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      body: new ReadableStream<Uint8Array>({
        start(controller) {
          controller.enqueue(
            new TextEncoder().encode(
              sseTextBlock(
                "response.delta",
                "- Main fact.\n\n### Limitations",
              ) +
                sseTextBlock("response.delta", "\n- Missing context.") +
                sseBlock("response.completed", {
                  traceId: "trace-markdown",
                  evidenceLevel: "none",
                  limitations: ["Missing context."],
                }),
            ),
          )
          controller.close()
        },
      }),
    })
    vi.stubGlobal("fetch", fetchMock)

    const { result } = renderHook(() => useRagQueryStream())
    await act(async () => {
      await result.current.stream({
        message: "question",
        knowledgeBaseIds: ["kb-1"],
      })
    })

    await waitFor(() => {
      expect(result.current.answer).toBe(
        "- Main fact.\n\n### Limitations\n- Missing context.",
      )
      expect(result.current.state).toBe("completed")
    })
    vi.unstubAllGlobals()
  })

  it("hydrates the same state from a blocking JSON response", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        success: true,
        data: {
          answer: "Blocking answer.",
          route: "grounded",
          evidenceLevel: "high",
          citations: [],
          limitations: [],
          traceId: "trace-2",
          conversationId: "conversation-2",
        },
      }),
    })
    vi.stubGlobal("fetch", fetchMock)

    const { result } = renderHook(() => useRagQueryStream())
    await act(async () => {
      await result.current.stream({
        message: "question",
        knowledgeBaseIds: ["kb-1"],
        stream: false,
      })
    })

    const payload = JSON.parse(
      fetchMock.mock.calls[0]?.[1].body as string,
    ) as Record<string, unknown>
    expect(payload.stream).toBe(false)
    expect(result.current.answer).toBe("Blocking answer.")
    expect(result.current.state).toBe("completed")
    expect(result.current.conversationId).toBe("conversation-2")
    expect(result.current.traceId).toBe("trace-2")
    vi.unstubAllGlobals()
  })
})
