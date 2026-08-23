"use client"

import type { PlannerOverrideInput } from "@open-grounding/schemas"
import type { RagCitationResponse } from "@open-grounding/types"
import { useCallback, useEffect, useRef, useState } from "react"

const STREAM_BASE = "/api/stream"

export type StreamState = "idle" | "streaming" | "completed" | "failed"

export type StreamCallbacks = {
  onStarted?: (traceId: string) => void
  onRoute?: (route: string) => void
  onRetrievalSummary?: (evidenceLevel: string) => void
  onDelta?: (answer: string) => void
  onCitations?: (citations: RagCitationResponse[]) => void
  onCompleted?: (result: {
    traceId: string
    evidenceLevel: string
    limitations: string[]
    planner?: Record<string, unknown>
    tasks?: Array<Record<string, unknown>>
    resume?: Record<string, unknown>
  }) => void
  onFailed?: (code: string) => void
}

type StreamArgs = {
  message: string
  knowledgeBaseIds: string[]
  conversationId?: string
  planner?: PlannerOverrideInput
} & StreamCallbacks

type ParsedEvent = {
  event: string
  data: Record<string, unknown>
}

export const parseSseChunk = (chunk: string): ParsedEvent[] => {
  const events: ParsedEvent[] = []
  const blocks = chunk.split("\n\n")

  for (const block of blocks) {
    const lines = block.split("\n")
    let eventName = ""
    let dataLine = ""

    for (const line of lines) {
      if (line.startsWith("event:")) {
        eventName = line.slice("event:".length).trim()
      } else if (line.startsWith("data:")) {
        dataLine = line.slice("data:".length).trim()
      }
    }

    if (eventName && dataLine) {
      try {
        const data = JSON.parse(dataLine) as Record<string, unknown>
        events.push({ event: eventName, data })
      } catch {
        // BUG-WEB-03: skip only the malformed block, not the rest of the chunk
        continue
      }
    }
  }

  return events
}

const dispatchEvent = (parsed: ParsedEvent, callbacks: StreamCallbacks) => {
  const { event, data } = parsed

  switch (event) {
    case "response.started":
      callbacks.onStarted?.(String(data.traceId ?? ""))
      break
    case "response.route":
      callbacks.onRoute?.(String(data.route ?? ""))
      break
    case "response.retrieval_summary":
      callbacks.onRetrievalSummary?.(String(data.evidenceLevel ?? ""))
      break
    case "response.delta":
      callbacks.onDelta?.(String(data.answer ?? ""))
      break
    case "response.citations":
      callbacks.onCitations?.((data.citations as RagCitationResponse[]) ?? [])
      break
    case "response.completed":
      callbacks.onCompleted?.({
        traceId: String(data.traceId ?? ""),
        evidenceLevel: String(data.evidenceLevel ?? ""),
        limitations: (data.limitations as string[]) ?? [],
        planner: data.planner as Record<string, unknown> | undefined,
        tasks: data.tasks as Array<Record<string, unknown>> | undefined,
        resume: data.resume as Record<string, unknown> | undefined,
      })
      break
    case "response.failed":
      callbacks.onFailed?.(String(data.code ?? "QUERY_FAILED"))
      break
  }
}

export const useRagQueryStream = () => {
  const [state, setState] = useState<StreamState>("idle")
  const [answer, setAnswer] = useState("")
  const [route, setRoute] = useState<string | null>(null)
  const [evidenceLevel, setEvidenceLevel] = useState<string | null>(null)
  const [citations, setCitations] = useState<RagCitationResponse[]>([])
  const [limitations, setLimitations] = useState<string[]>([])
  const [traceId, setTraceId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [planner, setPlanner] = useState<Record<string, unknown> | null>(null)
  const [tasks, setTasks] = useState<Array<Record<string, unknown>>>([])
  const [resume, setResume] = useState<Record<string, unknown> | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  // BUG-WEB-02: abort any in-flight stream when the component unmounts to
  // prevent state updates on an unmounted component and avoid resource leaks.
  useEffect(() => {
    return () => {
      abortRef.current?.abort()
    }
  }, [])

  const reset = useCallback(() => {
    setState("idle")
    setAnswer("")
    setRoute(null)
    setEvidenceLevel(null)
    setCitations([])
    setLimitations([])
    setTraceId(null)
    setError(null)
    setPlanner(null)
    setTasks([])
    setResume(null)
  }, [])

  const stream = useCallback(async (args: StreamArgs) => {
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller

    setState("streaming")
    setAnswer("")
    setRoute(null)
    setEvidenceLevel(null)
    setCitations([])
    setLimitations([])
    setTraceId(null)
    setError(null)
    setPlanner(null)
    setTasks([])
    setResume(null)

    const payload = {
      message: args.message,
      knowledge_base_ids: args.knowledgeBaseIds,
      conversation_id: args.conversationId,
      mode: "grounded",
      stream: true,
      planner: args.planner
        ? {
            enabled: args.planner.enabled,
            max_tasks: args.planner.maxTasks,
            task_types: args.planner.taskTypes,
          }
        : undefined,
    }

    try {
      const response = await fetch(`${STREAM_BASE}/rag/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        signal: controller.signal,
      })

      if (!response.ok || !response.body) {
        setState("failed")
        setError("Stream request failed")
        args.onFailed?.("QUERY_FAILED")
        return
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ""

      const flush = () => {
        const events = parseSseChunk(buffer)
        for (const parsed of events) {
          dispatchEvent(parsed, args)
          if (parsed.event === "response.started") {
            setTraceId(String(parsed.data.traceId ?? ""))
          }
          if (parsed.event === "response.route") {
            setRoute(String(parsed.data.route ?? ""))
          }
          if (parsed.event === "response.retrieval_summary") {
            setEvidenceLevel(String(parsed.data.evidenceLevel ?? ""))
          }
          if (parsed.event === "response.delta") {
            setAnswer(String(parsed.data.answer ?? ""))
          }
          if (parsed.event === "response.citations") {
            setCitations((parsed.data.citations as RagCitationResponse[]) ?? [])
          }
          if (parsed.event === "response.completed") {
            setLimitations((parsed.data.limitations as string[]) ?? [])
            setPlanner(parsed.data.planner as Record<string, unknown> | null)
            setTasks(
              (parsed.data.tasks as Array<Record<string, unknown>>) ?? [],
            )
            setResume(parsed.data.resume as Record<string, unknown> | null)
            setState("completed")
          }
          if (parsed.event === "response.failed") {
            setState("failed")
            setError("Query failed")
          }
        }
        buffer = ""
      }

      while (true) {
        const { done, value } = await reader.read()
        if (done) {
          break
        }
        buffer += decoder.decode(value, { stream: true })
        if (buffer.includes("\n\n")) {
          flush()
        }
      }
      if (buffer.trim()) {
        flush()
      }
    } catch (err) {
      if ((err as Error).name === "AbortError") {
        return
      }
      setState("failed")
      setError("Stream interrupted")
      args.onFailed?.("QUERY_FAILED")
    }
  }, [])

  const abort = useCallback(() => {
    abortRef.current?.abort()
    setState("idle")
  }, [])

  return {
    state,
    answer,
    route,
    evidenceLevel,
    citations,
    limitations,
    traceId,
    error,
    planner,
    tasks,
    resume,
    stream,
    abort,
    reset,
  }
}

export type RagQueryStreamResult = ReturnType<typeof useRagQueryStream>

export default useRagQueryStream
