"use client"

import type { PlannerOverrideInput } from "@open-grounding/schemas"
import type { RagCitationResponse } from "@open-grounding/types"
import { useCallback, useEffect, useRef, useState } from "react"

const STREAM_BASE = "/api/stream"

export type StreamState = "idle" | "streaming" | "completed" | "failed"

export type StreamCallbacks = {
  onStarted?: (traceId: string) => void
  onRoute?: (route: string) => void
  onProgress?: (progress: { stage: string; message: string }) => void
  onRetrievalSummary?: (evidenceLevel: string) => void
  onDelta?: (answer: string) => void
  onCitations?: (citations: RagCitationResponse[]) => void
  onCompleted?: (result: StreamCompletion) => void
  onFailed?: (code: string) => void
}

export type StreamCompletion = {
  traceId: string
  projectId?: string | null
  evidenceLevel: string
  limitations: string[]
  answerBehaviorVersion?: string
  guardrailVersion?: string
  sourcePolicy?: string
  effectiveOutputTokens?: number
  planner?: Record<string, unknown>
  tasks?: Array<Record<string, unknown>>
  resume?: Record<string, unknown>
}

type StreamArgs = {
  message: string
  knowledgeBaseIds: string[]
  projectId?: string
  conversationId?: string
  stream?: boolean
  planner?: PlannerOverrideInput
} & StreamCallbacks

type ParsedEventData = Record<string, unknown> | string

type ParsedEvent = {
  event: string
  data: ParsedEventData
}

const TYPEWRITER_INTERVAL_MS = 16
const TYPEWRITER_CHARS_PER_TICK = 3

export const parseSseChunk = (chunk: string): ParsedEvent[] => {
  const events: ParsedEvent[] = []
  const blocks = chunk.split("\n\n")

  for (const block of blocks) {
    const lines = block.split("\n")
    let eventName = ""
    const dataLines: string[] = []

    for (const line of lines) {
      if (line.startsWith("event:")) {
        eventName = line.slice("event:".length).trim()
      } else if (line.startsWith("data:")) {
        const dataLine = line.slice("data:".length)
        dataLines.push(dataLine.startsWith(" ") ? dataLine.slice(1) : dataLine)
      }
    }

    if (eventName && dataLines.length > 0) {
      const dataText = dataLines.join("\n")
      try {
        const data = JSON.parse(dataText) as Record<string, unknown>
        events.push({ event: eventName, data })
      } catch {
        if (eventName === "response.delta") {
          events.push({ event: eventName, data: dataText })
        }
      }
    }
  }

  return events
}

const dispatchEvent = (parsed: ParsedEvent, callbacks: StreamCallbacks) => {
  const { event, data } = parsed

  if (typeof data === "string") {
    if (event === "response.delta") {
      callbacks.onDelta?.(data)
    }
    return
  }

  switch (event) {
    case "response.started":
      callbacks.onStarted?.(String(data.traceId ?? ""))
      break
    case "response.route":
      callbacks.onRoute?.(String(data.route ?? ""))
      break
    case "response.progress":
      callbacks.onProgress?.({
        stage: String(data.stage ?? "processing"),
        message: String(data.message ?? "Processing..."),
      })
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
        projectId: data.projectId ? String(data.projectId) : null,
        evidenceLevel: String(data.evidenceLevel ?? ""),
        limitations: (data.limitations as string[]) ?? [],
        answerBehaviorVersion: data.answerBehaviorVersion
          ? String(data.answerBehaviorVersion)
          : undefined,
        guardrailVersion: data.guardrailVersion
          ? String(data.guardrailVersion)
          : undefined,
        sourcePolicy: data.sourcePolicy ? String(data.sourcePolicy) : undefined,
        effectiveOutputTokens:
          typeof data.effectiveOutputTokens === "number"
            ? data.effectiveOutputTokens
            : undefined,
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
  const [progress, setProgress] = useState("Idle")
  const [evidenceLevel, setEvidenceLevel] = useState<string | null>(null)
  const [citations, setCitations] = useState<RagCitationResponse[]>([])
  const [limitations, setLimitations] = useState<string[]>([])
  const [traceId, setTraceId] = useState<string | null>(null)
  const [conversationId, setConversationId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [planner, setPlanner] = useState<Record<string, unknown> | null>(null)
  const [tasks, setTasks] = useState<Array<Record<string, unknown>>>([])
  const [resume, setResume] = useState<Record<string, unknown> | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  const answerQueueRef = useRef<string[]>([])
  const typewriterTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const pendingCompletionRef = useRef<{
    generation: number
    result: StreamCompletion
    callback?: StreamCallbacks["onCompleted"]
  } | null>(null)
  const streamGenerationRef = useRef(0)

  const clearAnswerQueue = useCallback(() => {
    if (typewriterTimerRef.current !== null) {
      clearTimeout(typewriterTimerRef.current)
      typewriterTimerRef.current = null
    }
    answerQueueRef.current = []
    pendingCompletionRef.current = null
  }, [])

  const completeWhenAnswerIsVisible = useCallback((generation: number) => {
    if (
      generation !== streamGenerationRef.current ||
      answerQueueRef.current.length > 0 ||
      typewriterTimerRef.current !== null
    ) {
      return
    }

    const pending = pendingCompletionRef.current
    if (!pending || pending.generation !== generation) {
      return
    }

    pendingCompletionRef.current = null
    setState("completed")
    pending.callback?.(pending.result)
  }, [])

  const scheduleAnswerReveal = useCallback(
    (generation: number) => {
      if (
        generation !== streamGenerationRef.current ||
        typewriterTimerRef.current !== null
      ) {
        return
      }

      if (answerQueueRef.current.length === 0) {
        completeWhenAnswerIsVisible(generation)
        return
      }

      typewriterTimerRef.current = setTimeout(() => {
        typewriterTimerRef.current = null
        if (generation !== streamGenerationRef.current) {
          return
        }

        // Adaptive drain: smooth for small backlog, fast for large backlog
        // so `response.completed` does not wait 10+s behind the animation.
        // Final content is identical — only the completion signal is honest.
        const backlog = answerQueueRef.current.length
        const adaptiveChars =
          backlog > 300
            ? Math.min(120, Math.ceil(backlog / 8))
            : backlog > 100
              ? 24
              : backlog > 30
                ? 9
                : TYPEWRITER_CHARS_PER_TICK
        const nextChars = answerQueueRef.current.splice(0, adaptiveChars)
        if (nextChars.length > 0) {
          setAnswer((current) => current + nextChars.join(""))
        }

        if (answerQueueRef.current.length > 0) {
          scheduleAnswerReveal(generation)
        } else {
          completeWhenAnswerIsVisible(generation)
        }
      }, TYPEWRITER_INTERVAL_MS)
    },
    [completeWhenAnswerIsVisible],
  )

  const enqueueAnswerDelta = useCallback(
    (delta: string, generation: number) => {
      if (!delta || generation !== streamGenerationRef.current) {
        return
      }

      answerQueueRef.current.push(...Array.from(delta))
      scheduleAnswerReveal(generation)
    },
    [scheduleAnswerReveal],
  )

  // BUG-WEB-02: abort any in-flight stream when the component unmounts to
  // prevent state updates on an unmounted component and avoid resource leaks.
  useEffect(() => {
    return () => {
      streamGenerationRef.current += 1
      clearAnswerQueue()
      abortRef.current?.abort()
    }
  }, [clearAnswerQueue])

  const reset = useCallback(() => {
    streamGenerationRef.current += 1
    clearAnswerQueue()
    setState("idle")
    setAnswer("")
    setRoute(null)
    setProgress("Idle")
    setEvidenceLevel(null)
    setCitations([])
    setLimitations([])
    setTraceId(null)
    setConversationId(null)
    setError(null)
    setPlanner(null)
    setTasks([])
    setResume(null)
  }, [clearAnswerQueue])

  const stream = useCallback(
    async (args: StreamArgs) => {
      abortRef.current?.abort()
      const generation = streamGenerationRef.current + 1
      streamGenerationRef.current = generation
      clearAnswerQueue()
      const controller = new AbortController()
      abortRef.current = controller

      setState("streaming")
      setAnswer("")
      setRoute(null)
      setProgress("Memproses pertanyaan...")
      setEvidenceLevel(null)
      setCitations([])
      setLimitations([])
      setTraceId(null)
      setError(null)
      setPlanner(null)
      setTasks([])
      setResume(null)

      const activeConversationId = args.conversationId ?? conversationId
      const shouldStream = args.stream ?? true
      const payload = {
        message: args.message,
        knowledge_base_ids: args.knowledgeBaseIds,
        project_id: args.projectId,
        conversation_id: activeConversationId ?? undefined,
        mode: "grounded",
        stream: shouldStream,
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

        if (!response.ok) {
          setState("failed")
          setError("Stream request failed")
          args.onFailed?.("QUERY_FAILED")
          return
        }

        if (!shouldStream) {
          const envelope = (await response.json()) as Record<string, unknown>
          const data =
            typeof envelope.data === "object" && envelope.data !== null
              ? (envelope.data as Record<string, unknown>)
              : envelope
          const nextConversationId = data.conversationId
          if (typeof nextConversationId === "string" && nextConversationId) {
            setConversationId(nextConversationId)
          }
          const nextTraceId = String(data.traceId ?? "")
          const nextEvidenceLevel = String(data.evidenceLevel ?? "")
          const nextLimitations = (data.limitations as string[]) ?? []
          setTraceId(nextTraceId)
          setRoute(String(data.route ?? ""))
          setAnswer(typeof data.answer === "string" ? data.answer : "")
          setEvidenceLevel(nextEvidenceLevel)
          setCitations((data.citations as RagCitationResponse[]) ?? [])
          setLimitations(nextLimitations)
          setPlanner(data.planner as Record<string, unknown> | null)
          setTasks((data.tasks as Array<Record<string, unknown>>) ?? [])
          setResume(data.resume as Record<string, unknown> | null)
          setState("completed")
          args.onCompleted?.({
            traceId: nextTraceId,
            evidenceLevel: nextEvidenceLevel,
            limitations: nextLimitations,
            planner: data.planner as Record<string, unknown> | undefined,
            tasks: data.tasks as Array<Record<string, unknown>> | undefined,
            resume: data.resume as Record<string, unknown> | undefined,
          })
          return
        }

        if (!response.body) {
          setState("failed")
          setError("Stream request failed")
          args.onFailed?.("QUERY_FAILED")
          return
        }

        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ""

        const flush = (final = false) => {
          const separator = "\n\n"
          const boundary = buffer.lastIndexOf(separator)
          if (boundary === -1 && !final) {
            return
          }

          const complete =
            boundary === -1
              ? buffer
              : buffer.slice(0, boundary + separator.length)
          buffer =
            boundary === -1 ? "" : buffer.slice(boundary + separator.length)
          const events = parseSseChunk(complete)
          for (const parsed of events) {
            const data = parsed.data
            if (
              parsed.event === "response.completed" &&
              typeof data !== "string"
            ) {
              const completion: StreamCompletion = {
                traceId: String(data.traceId ?? ""),
                evidenceLevel: String(data.evidenceLevel ?? ""),
                limitations: (data.limitations as string[]) ?? [],
                planner: data.planner as Record<string, unknown> | undefined,
                tasks: data.tasks as Array<Record<string, unknown>> | undefined,
                resume: data.resume as Record<string, unknown> | undefined,
              }
              setLimitations(completion.limitations)
              setPlanner(completion.planner ?? null)
              setTasks(completion.tasks ?? [])
              setResume(completion.resume ?? null)
              pendingCompletionRef.current = {
                generation,
                result: completion,
                callback: args.onCompleted,
              }
              completeWhenAnswerIsVisible(generation)
              continue
            }

            dispatchEvent(parsed, args)
            if (parsed.event === "response.delta") {
              const delta =
                typeof data === "string" ? data : String(data.answer ?? "")
              enqueueAnswerDelta(delta, generation)
              continue
            }
            if (typeof data === "string") {
              continue
            }
            if (parsed.event === "response.started") {
              setTraceId(String(data.traceId ?? ""))
              const nextConversationId = data.conversationId
              if (
                typeof nextConversationId === "string" &&
                nextConversationId
              ) {
                setConversationId(nextConversationId)
              }
            }
            if (parsed.event === "response.route") {
              setRoute(String(data.route ?? ""))
            }
            if (parsed.event === "response.progress") {
              const nextConversationId = data.conversationId
              if (
                typeof nextConversationId === "string" &&
                nextConversationId
              ) {
                setConversationId(nextConversationId)
              }
              setProgress(String(data.message ?? "Memproses pertanyaan..."))
            }
            if (parsed.event === "response.retrieval_summary") {
              setEvidenceLevel(String(data.evidenceLevel ?? ""))
            }
            if (parsed.event === "response.citations") {
              setCitations((data.citations as RagCitationResponse[]) ?? [])
            }
            if (parsed.event === "response.failed") {
              clearAnswerQueue()
              setState("failed")
              setError("Query failed")
            }
          }
        }

        while (true) {
          const { done, value } = await reader.read()
          if (done) {
            break
          }
          buffer += decoder.decode(value, { stream: true })
          flush()
        }
        buffer += decoder.decode()
        if (buffer.trim()) {
          flush(true)
        }
      } catch (err) {
        if (generation !== streamGenerationRef.current) {
          return
        }
        if ((err as Error).name === "AbortError") {
          return
        }
        clearAnswerQueue()
        setState("failed")
        setError("Stream interrupted")
        args.onFailed?.("QUERY_FAILED")
      }
    },
    [
      clearAnswerQueue,
      completeWhenAnswerIsVisible,
      conversationId,
      enqueueAnswerDelta,
    ],
  )

  const abort = useCallback(() => {
    streamGenerationRef.current += 1
    clearAnswerQueue()
    abortRef.current?.abort()
    setState("idle")
  }, [clearAnswerQueue])

  return {
    state,
    answer,
    route,
    progress,
    evidenceLevel,
    citations,
    limitations,
    traceId,
    conversationId,
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
