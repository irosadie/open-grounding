"use client"

import { Button } from "$/components/button"
import { EmptyState } from "$/components/empty-state"
import { Input } from "$/components/input"
import { KnowledgeBaseMultiSelect } from "$/components/knowledge-base-multi-select"
import { PanelCard } from "$/components/panel-card"
import { useRagFeedback } from "$/hooks/transactions/use-rag-query"
import { useRagQueryStream } from "$/hooks/transactions/use-rag-query"
import { cn } from "$/utils/cn"
import {
  getRagEvidenceLevelLabel,
  getRagQueryRouteLabel,
} from "@open-grounding/schemas"
import type { KnowledgeBaseResponseProps } from "@open-grounding/types"
import { AlertTriangle, MessageSquareText, Send, Star } from "lucide-react"
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
  const [selectedKbs, setSelectedKbs] = useState<KnowledgeBaseResponseProps[]>(
    [],
  )
  const [formError, setFormError] = useState("")
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
      setFormError("Pertanyaan wajib diisi.")
      return
    }
    if (knowledgeBaseIds.length === 0) {
      setFormError("Pilih minimal satu Knowledge Base.")
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
      <div>
        <h1 className="text-xl font-semibold text-gray-900">Retrieval</h1>
        <p className="mt-1 text-sm text-gray-500">
          Ajukan pertanyaan ke knowledge base dan dapatkan jawaban berbasis
          dokumen dengan kutipan sumber.
        </p>
      </div>

      <PanelCard
        title="Ajukan Pertanyaan"
        description="Jawaban akan dikutip langsung dari dokumen yang sudah diingestion."
      >
        <div className="flex flex-col gap-4">
          <KnowledgeBaseMultiSelect
            value={selectedKbs}
            onChange={setSelectedKbs}
            label="Knowledge Bases"
            required
            disabled={isStreaming}
            hint="Pilih satu atau lebih knowledge base sebagai sumber jawaban."
          />

          <div className="flex flex-col gap-1.5">
            <label
              htmlFor={questionInputId}
              className="text-sm font-medium text-main-700"
            >
              Pertanyaan <span className="text-danger-500">*</span>
            </label>
            <textarea
              id={questionInputId}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
              rows={3}
              placeholder="Contoh: Apa kebijakan retensi data yang berlaku?"
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
              {isStreaming ? "Sedang berpikir..." : "Tanya"}
            </Button>
            {isStreaming ? (
              <Button intent="secondary" bordered onClick={stream.abort}>
                Hentikan
              </Button>
            ) : null}
          </div>
        </div>
      </PanelCard>

      {stream.state === "idle" && !stream.answer ? (
        <PanelCard title="Jawaban">
          <EmptyState
            icon={MessageSquareText}
            title="Belum ada jawaban"
            description="Ajukan pertanyaan di atas untuk mendapatkan jawaban berbasis dokumen dengan kutipan sumber."
          />
        </PanelCard>
      ) : (
        <PanelCard
          title="Jawaban"
          action={
            stream.route ? (
              <div className="flex items-center gap-2">
                <span className="text-xs text-gray-500">Rute</span>
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
                    ? "Pertanyaan perlu diperjelas"
                    : "Tidak dapat menjawab dari dokumen yang tersedia"}
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
              <span className="text-xs text-gray-500">Tingkat bukti</span>
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
                Kutipan Sumber
              </h4>
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
                        href="/console/document"
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
                Beri Penilaian Jawaban
              </h4>
              <p className="mt-0.5 text-xs text-gray-500">
                Seberapa membantu jawaban ini?
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
                      aria-label={`Nilai ${star} bintang`}
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
                        ? "Sangat membantu"
                        : feedbackRating === 4
                          ? "Membantu"
                          : feedbackRating === 3
                            ? "Cukup"
                            : feedbackRating === 2
                              ? "Kurang membantu"
                              : "Tidak membantu"}
                    </span>
                  ) : null}
                </div>

                <div className="flex items-center gap-2">
                  <Input
                    className="flex-1"
                    placeholder="Komentar (opsional)"
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
                    Kirim
                  </Button>
                </div>
              </div>
              {feedback.isSuccess ? (
                <p className="mt-2 text-xs text-success-600">
                  Penilaian berhasil disimpan.
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
