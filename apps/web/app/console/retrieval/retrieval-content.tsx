"use client"

import { Button } from "$/components/button"
import { EmptyState } from "$/components/empty-state"
import { Input } from "$/components/input"
import { PanelCard } from "$/components/panel-card"
import { useRagFeedback } from "$/hooks/transactions/use-rag-query"
import { useRagQueryStream } from "$/hooks/transactions/use-rag-query"
import { cn } from "$/utils/cn"
import {
  getRagEvidenceLevelLabel,
  getRagQueryRouteLabel,
} from "@vibecoding-starter/schemas"
import { AlertTriangle, MessageSquareText, Send } from "lucide-react"
import { type ChangeEvent, useId, useState } from "react"

const EVIDENCE_VARIANT: Record<string, string> = {
  high: "bg-success-100 text-success-700",
  medium: "bg-info-100 text-info-700",
  low: "bg-warning-100 text-warning-700",
  none: "bg-gray-100 text-gray-600",
}

export function RetrievalContent() {
  const stream = useRagQueryStream()
  const [message, setMessage] = useState("")
  const [knowledgeBaseInput, setKnowledgeBaseInput] = useState("")
  const [formError, setFormError] = useState("")
  const [feedbackRating, setFeedbackRating] = useState<number | null>(null)
  const [feedbackComment, setFeedbackComment] = useState("")
  const questionInputId = useId()

  const feedback = useRagFeedback({
    traceId: stream.traceId ?? "",
  })

  const handleSubmit = () => {
    setFormError("")
    const trimmedMessage = message.trim()
    const knowledgeBaseIds = knowledgeBaseInput
      .split(",")
      .map((id) => id.trim())
      .filter(Boolean)

    if (!trimmedMessage) {
      setFormError("Question is required.")
      return
    }
    if (knowledgeBaseIds.length === 0) {
      setFormError("At least one knowledge base id is required.")
      return
    }

    void stream.stream({
      message: trimmedMessage,
      knowledgeBaseIds,
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
  const showAbstain =
    stream.route === "abstain" ||
    stream.route === "clarify" ||
    (stream.evidenceLevel === "none" && stream.state === "completed")

  return (
    <div className="flex flex-col gap-6">
      <PanelCard
        title="Ask a Question"
        description="Ask a grounded question against your knowledge bases."
      >
        <div className="flex flex-col gap-4">
          <Input
            label="Knowledge Base Ids"
            name="knowledgeBaseIds"
            placeholder="kb-id-1, kb-id-2"
            value={knowledgeBaseInput}
            onChange={(event: ChangeEvent<HTMLInputElement>) =>
              setKnowledgeBaseInput(event.target.value)
            }
            hint="Comma-separated knowledge base ids"
            required
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
              placeholder="What is the retention policy?"
              value={message}
              onChange={(event) => setMessage(event.target.value)}
              disabled={isStreaming}
            />
          </div>

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
            description="Ask a question above to retrieve a grounded answer with citations."
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
                  {getRagQueryRouteLabel(
                    stream.route as "grounded" | "clarify" | "abstain",
                  )}
                </span>
              </div>
            ) : null
          }
        >
          {showAbstain ? (
            <div className="flex items-start gap-3 rounded-lg bg-warning-50 p-4">
              <AlertTriangle className="mt-0.5 h-5 w-5 text-warning-600" />
              <div>
                <p className="text-sm font-medium text-warning-800">
                  {stream.route === "clarify"
                    ? "Clarification needed"
                    : "Unable to answer from available evidence"}
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

          {stream.answer ? (
            <p className="whitespace-pre-wrap text-sm text-gray-800">
              {stream.answer}
            </p>
          ) : null}

          {stream.evidenceLevel ? (
            <div className="mt-4 flex items-center gap-2">
              <span className="text-xs text-gray-500">Evidence</span>
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

          {stream.citations.length > 0 ? (
            <div className="mt-4">
              <h4 className="text-sm font-semibold text-gray-900">Citations</h4>
              <ul className="mt-2 flex flex-col gap-2">
                {stream.citations.map((citation) => (
                  <li
                    key={citation.citationId}
                    className="rounded-lg border border-gray-200 p-3"
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium text-gray-900">
                        {citation.title}
                      </span>
                      <a
                        href="/console/ingestion"
                        className="text-xs text-primary-600 hover:underline"
                      >
                        {citation.locator ?? citation.documentVersionId}
                      </a>
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
                Answer Feedback
              </h4>
              <div className="mt-3 flex items-center gap-2">
                {[1, 2, 3, 4, 5].map((star) => (
                  <button
                    key={`rating-${star}`}
                    type="button"
                    onClick={() => setFeedbackRating(star)}
                    className={cn(
                      "h-8 w-8 rounded-md border text-sm font-medium",
                      feedbackRating === star
                        ? "border-primary-500 bg-primary-50 text-primary-700"
                        : "border-gray-300 text-gray-500 hover:bg-gray-50",
                    )}
                    aria-label={`Rate ${star}`}
                  >
                    {star}
                  </button>
                ))}
                <Input
                  className="ml-2 flex-1"
                  placeholder="Optional comment"
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
              {feedback.isSuccess ? (
                <p className="mt-2 text-xs text-success-600">
                  Feedback recorded.
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
