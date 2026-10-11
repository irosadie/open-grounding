"use client"

import { Button } from "$/components/button"
import { EmptyState } from "$/components/empty-state"
import { Input } from "$/components/input"
import { KnowledgeBaseMultiSelect } from "$/components/knowledge-base-multi-select"
import { PanelCard } from "$/components/panel-card"
import { useProjects } from "$/hooks/transactions/use-projects"
import {
  useRagFeedback,
  useRagQueryStream,
} from "$/hooks/transactions/use-rag-query"
import { cn } from "$/utils/cn"
import {
  type RagQueryRoute,
  getRagEvidenceLevelLabel,
  getRagQueryRouteLabel,
} from "@open-grounding/schemas"
import type { KnowledgeBaseResponseProps } from "@open-grounding/types"
import { AlertTriangle, MessageSquareText, Send, Star } from "lucide-react"
import { type ChangeEvent, useId, useState } from "react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"

const EVIDENCE_VARIANT: Record<string, string> = {
  high: "bg-success-100 text-success-700",
  medium: "bg-info-100 text-info-700",
  low: "bg-warning-100 text-warning-700",
  none: "bg-gray-100 text-gray-600",
}
export function RetrievalContent() {
  const stream = useRagQueryStream()
  const { data: projects } = useProjects()
  const [message, setMessage] = useState("")
  const [selectedKbs, setSelectedKbs] = useState<KnowledgeBaseResponseProps[]>(
    [],
  )
  const [projectId, setProjectId] = useState<string>("")
  const [formError, setFormError] = useState("")
  const [streamEnabled, setStreamEnabled] = useState(true)
  const [feedbackRating, setFeedbackRating] = useState<number | null>(null)
  const [feedbackHover, setFeedbackHover] = useState<number | null>(null)
  const [feedbackComment, setFeedbackComment] = useState("")
  const questionInputId = useId()

  const feedback = useRagFeedback({
    traceId: stream.traceId ?? "",
  })

  const handleSubmit = () => {
    setFormError("")
    const trimmedMessage = message.trim()
    const knowledgeBaseIds = selectedKbs.map((kb) => kb.id)

    if (!trimmedMessage) {
      setFormError("Question is required.")
      return
    }
    if (knowledgeBaseIds.length === 0) {
      setFormError("Select at least one Knowledge Base.")
      return
    }

    void stream.stream({
      message: trimmedMessage,
      knowledgeBaseIds,
      projectId: projectId || undefined,
      stream: streamEnabled,
      onCompleted: () => {
        setFeedbackRating(null)
        setFeedbackComment("")
      },
    })
  }

  const handleRatingSubmit = () => {
    if (!stream.traceId || feedbackRating === null) {
      return
    }
    feedback.mutate({
      rating: feedbackRating,
      comment: feedbackComment.trim() || undefined,
    })
  }

  const isStreaming = stream.state === "streaming"
  const showRefusal = stream.route === "refused"
  const showAbstain = stream.route === "abstain" || stream.route === "clarify"
  const showUngrounded =
    stream.route === "answered" &&
    stream.state === "completed" &&
    Boolean(stream.answer)

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold text-gray-900">Retrieval</h1>
        <p className="mt-1 text-sm text-gray-500">
          Ask questions against your knowledge bases. Answers use document
          evidence when available and can also respond generally.
        </p>
      </div>

      <PanelCard
        title="Ask a Question"
        description="Answers use ingested documents when matching evidence is available."
      >
        <div className="flex flex-col gap-4">
          <label className="flex flex-col gap-1.5 text-sm font-medium text-main-700">
            Project
            <select
              className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
              value={projectId}
              onChange={(event) => {
                setProjectId(event.target.value)
                setSelectedKbs([])
              }}
              disabled={isStreaming}
            >
              <option value="">Infer from selected Knowledge Bases</option>
              {projects
                ?.filter((project) => project.status === "ACTIVE")
                .map((project) => (
                  <option key={project.id} value={project.id}>
                    {project.name}
                  </option>
                ))}
            </select>
            <span className="text-xs font-normal text-gray-400">
              All selected Knowledge Bases must belong to one Project.
            </span>
          </label>
          <KnowledgeBaseMultiSelect
            value={selectedKbs}
            onChange={setSelectedKbs}
            label="Knowledge Bases"
            required
            disabled={isStreaming}
            hint="Select one or more knowledge bases to provide optional evidence."
            projectId={projectId || null}
          />

          <div className="flex flex-col gap-1.5">
            <label
              htmlFor={questionInputId}
              className="text-sm font-medium text-main-700"
            >
              Question <span className="text-danger-500">*</span>
            </label>
            <textarea
              id={questionInputId}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
              rows={3}
              placeholder="e.g. What is the current data retention policy?"
              value={message}
              onChange={(event) => setMessage(event.target.value)}
              disabled={isStreaming}
            />
          </div>

          <label className="flex items-center gap-2 text-sm text-gray-700">
            <input
              type="checkbox"
              checked={streamEnabled}
              onChange={(event) => setStreamEnabled(event.target.checked)}
              disabled={isStreaming}
              className="h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
            />
            <span>Stream answer</span>
            <span className="text-xs text-gray-500">
              Show the validated conclusion progressively
            </span>
          </label>

          {formError ? (
            <p className="text-sm text-danger-500">{formError}</p>
          ) : null}
          {stream.error ? (
            <p className="text-sm text-danger-500">{stream.error}</p>
          ) : null}

          <div className="flex items-center gap-2">
            <Button
              intent="primary"
              onClick={handleSubmit}
              loading={isStreaming}
              disabled={isStreaming}
              leftIcon={<Send className="h-4 w-4" />}
            >
              {isStreaming ? "Thinking..." : "Ask"}
            </Button>
            {isStreaming ? (
              <Button intent="secondary" bordered onClick={stream.abort}>
                Stop
              </Button>
            ) : null}
          </div>
        </div>
      </PanelCard>

      {stream.state === "idle" && !stream.answer ? (
        <PanelCard title="Answer">
          <EmptyState
            icon={MessageSquareText}
            title="No answer yet"
            description="Ask a question above to get a document-grounded answer with source citations."
          />
        </PanelCard>
      ) : (
        <PanelCard
          title="Answer"
          action={
            stream.route ? (
              <div className="flex items-center gap-2">
                <span className="text-xs text-gray-500">Route</span>
                <span className="rounded-full bg-primary-50 px-2.5 py-0.5 text-xs font-medium text-primary-700">
                  {getRagQueryRouteLabel(stream.route as RagQueryRoute)}
                </span>
              </div>
            ) : null
          }
        >
          {isStreaming ? (
            <output
              className="mb-4 flex items-center gap-2 rounded-lg bg-gray-50 px-3 py-2 text-sm text-gray-600"
              aria-live="polite"
            >
              <span className="h-2 w-2 animate-pulse rounded-full bg-primary-500" />
              {stream.progress}
            </output>
          ) : null}

          {showRefusal ? (
            <div className="flex items-start gap-3 rounded-lg bg-danger-50 p-4">
              <AlertTriangle className="mt-0.5 h-5 w-5 text-danger-600" />
              <div>
                <p className="text-sm font-medium text-danger-800">
                  Request refused by safety guardrails
                </p>
                {stream.limitations.length > 0 ? (
                  <ul className="mt-1 list-inside list-disc text-sm text-danger-700">
                    {stream.limitations.map((limitation) => (
                      <li key={limitation}>{limitation}</li>
                    ))}
                  </ul>
                ) : null}
              </div>
            </div>
          ) : null}

          {showAbstain ? (
            <div className="flex items-start gap-3 rounded-lg bg-warning-50 p-4">
              <AlertTriangle className="mt-0.5 h-5 w-5 text-warning-600" />
              <div>
                <p className="text-sm font-medium text-warning-800">
                  {stream.route === "clarify"
                    ? "Question needs clarification"
                    : "Cannot answer from available documents"}
                </p>
                {stream.limitations.length > 0 ? (
                  <ul className="mt-1 list-inside list-disc text-sm text-warning-700">
                    {stream.limitations.map((limitation) => (
                      <li key={limitation}>{limitation}</li>
                    ))}
                  </ul>
                ) : null}
              </div>
            </div>
          ) : null}

          {showUngrounded ? (
            <div className="mb-3 rounded-lg bg-info-50 p-3 text-sm text-info-800">
              This answer is not grounded in the selected knowledge bases.
            </div>
          ) : null}

          {stream.answer ? (
            <div className="prose prose-sm prose-headings:text-main-800 prose-h1:text-2xl prose-h2:text-xl prose-h3:text-lg prose-a:text-primary-600 prose-code:rounded prose-code:bg-gray-100 prose-code:px-1 prose-code:text-primary-700 prose-pre:bg-main-800 prose-pre:text-gray-100 max-w-none text-gray-800">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {stream.answer}
              </ReactMarkdown>
            </div>
          ) : null}

          {stream.evidenceLevel ? (
            <div className="mt-4 flex items-center gap-2">
              <span className="text-xs text-gray-500">Evidence level</span>
              <span
                className={cn(
                  "rounded-full px-2.5 py-0.5 text-xs font-medium",
                  EVIDENCE_VARIANT[stream.evidenceLevel] ??
                    "bg-gray-100 text-gray-600",
                )}
              >
                {getRagEvidenceLevelLabel(
                  stream.evidenceLevel as "high" | "medium" | "low" | "none",
                )}
              </span>
            </div>
          ) : null}

          {stream.tasks.length > 0 ? (
            <div className="mt-4 rounded-lg border border-gray-200 p-4">
              <h4 className="text-sm font-semibold text-gray-900">Task Run</h4>
              <div className="mt-2 flex flex-col gap-2">
                {stream.tasks.map((task) => (
                  <div
                    key={String(task.id)}
                    className="flex items-center justify-between rounded border border-gray-100 px-3 py-2 text-xs"
                  >
                    <span className="font-medium text-gray-700">
                      {String(task.id)} · {String(task.type)}
                    </span>
                    <span className="text-gray-500">
                      {String(task.status)}
                      {task.reason ? ` · ${String(task.reason)}` : ""}
                    </span>
                  </div>
                ))}
              </div>
              {stream.resume ? (
                <p className="mt-3 text-xs text-gray-500">
                  Resume: {String(stream.resume.rerank_route ?? "unknown")} ·{" "}
                  {String(stream.resume.merged_evidence_count ?? 0)} evidence ·{" "}
                  {String(stream.resume.supplementary_blocks ?? 0)}{" "}
                  supplementary blocks
                </p>
              ) : null}
              {stream.planner ? (
                <p className="mt-1 text-xs text-gray-500">
                  Planner:{" "}
                  {stream.planner.planner_fallback ? "fallback" : "active"} ·{" "}
                  {String(stream.planner.task_count ?? stream.tasks.length)}{" "}
                  tasks
                </p>
              ) : null}
            </div>
          ) : null}

          {stream.citations.length > 0 ? (
            <div className="mt-4">
              <h4 className="text-sm font-semibold text-gray-900">
                Source Citations
              </h4>
              <ul className="mt-2 flex flex-col gap-2">
                {stream.citations.map((citation) => (
                  <li
                    key={citation.citationId}
                    className="rounded-lg border border-gray-200 p-3"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-gray-900">
                          {citation.title}
                        </span>
                        <span
                          className={cn(
                            "rounded-full px-2 py-0.5 text-[10px] font-medium",
                            citation.sourceKind === "MCP"
                              ? "bg-info-100 text-info-700"
                              : "bg-success-100 text-success-700",
                          )}
                        >
                          {citation.sourceKind === "MCP" ? "MCP" : "DOCUMENT"}
                        </span>
                      </div>
                      {citation.sourceKind === "MCP" ? (
                        <span className="text-xs text-gray-500">
                          {citation.toolId ?? citation.invocationId}
                        </span>
                      ) : (
                        <a
                          href={`/console/document/${citation.documentVersionId}`}
                          className="text-xs text-primary-600 hover:underline"
                        >
                          {citation.locator ?? citation.documentVersionId}
                        </a>
                      )}
                    </div>
                    <p className="mt-1 text-xs text-gray-600">
                      {citation.snippet}
                    </p>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          {stream.state === "completed" && stream.traceId ? (
            <div className="mt-4 rounded-lg border border-gray-200 p-4">
              <h4 className="text-sm font-semibold text-gray-900">
                Rate this Answer
              </h4>
              <p className="mt-0.5 text-xs text-gray-500">
                How helpful was this answer?
              </p>
              <div className="mt-3 flex flex-col gap-3">
                {/* Star rating */}
                <div className="flex items-center gap-1">
                  {[1, 2, 3, 4, 5].map((star) => (
                    <button
                      key={`rating-${star}`}
                      type="button"
                      onClick={() => setFeedbackRating(star)}
                      onMouseEnter={() => setFeedbackHover(star)}
                      onMouseLeave={() => setFeedbackHover(null)}
                      className="rounded p-0.5 transition-transform hover:scale-110"
                      aria-label={`Rate ${star} star${star === 1 ? "" : "s"}`}
                    >
                      <Star
                        className={cn(
                          "h-6 w-6 transition-colors",
                          (feedbackHover ?? feedbackRating ?? 0) >= star
                            ? "fill-warning-400 text-warning-400"
                            : "fill-gray-200 text-gray-200",
                        )}
                      />
                    </button>
                  ))}
                  {feedbackRating ? (
                    <span className="ml-2 text-xs text-gray-500">
                      {feedbackRating === 5
                        ? "Very helpful"
                        : feedbackRating === 4
                          ? "Helpful"
                          : feedbackRating === 3
                            ? "Neutral"
                            : feedbackRating === 2
                              ? "Not very helpful"
                              : "Not helpful"}
                    </span>
                  ) : null}
                </div>

                <div className="flex items-center gap-2">
                  <Input
                    className="flex-1"
                    placeholder="Comment (optional)"
                    value={feedbackComment}
                    onChange={(event: ChangeEvent<HTMLInputElement>) =>
                      setFeedbackComment(event.target.value)
                    }
                  />
                  <Button
                    intent="primary"
                    size="small"
                    onClick={handleRatingSubmit}
                    disabled={feedbackRating === null || feedback.isPending}
                    loading={feedback.isPending}
                  >
                    Submit
                  </Button>
                </div>
              </div>
              {feedback.isSuccess ? (
                <p className="mt-2 text-xs text-success-600">
                  Feedback submitted successfully.
                </p>
              ) : null}
            </div>
          ) : null}
        </PanelCard>
      )}
    </div>
  )
}

export default RetrievalContent
