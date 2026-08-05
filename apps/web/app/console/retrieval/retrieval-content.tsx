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
} from "@open-grounding/schemas"
import { AlertTriangle, MessageSquareText, Send, Star, X } from "lucide-react"
import { type ChangeEvent, type KeyboardEvent, useId, useState } from "react"

const EVIDENCE_VARIANT: Record<string, string> = {
  high: "bg-success-100 text-success-700",
  medium: "bg-info-100 text-info-700",
  low: "bg-warning-100 text-warning-700",
  none: "bg-gray-100 text-gray-600",
}

export function RetrievalContent() {
  const stream = useRagQueryStream()
  const [message, setMessage] = useState("")
  const [kbIdInput, setKbIdInput] = useState("")
  const [kbIds, setKbIds] = useState<string[]>([])
  const [formError, setFormError] = useState("")
  const [feedbackRating, setFeedbackRating] = useState<number | null>(null)
  const [feedbackHover, setFeedbackHover] = useState<number | null>(null)
  const [feedbackComment, setFeedbackComment] = useState("")
  const questionInputId = useId()

  const feedback = useRagFeedback({
    traceId: stream.traceId ?? "",
  })

  const addKbId = (value: string) => {
    const trimmed = value.trim()
    if (trimmed && !kbIds.includes(trimmed)) {
      setKbIds((prev) => [...prev, trimmed])
    }
    setKbIdInput("")
  }

  const handleKbIdKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter" || event.key === ",") {
      event.preventDefault()
      addKbId(kbIdInput)
    } else if (
      event.key === "Backspace" &&
      kbIdInput === "" &&
      kbIds.length > 0
    ) {
      setKbIds((prev) => prev.slice(0, -1))
    }
  }

  const removeKbId = (id: string) => {
    setKbIds((prev) => prev.filter((k) => k !== id))
  }

  const handleSubmit = () => {
    setFormError("")

    // Flush any pending input
    const pendingIds = kbIdInput.trim() ? [...kbIds, kbIdInput.trim()] : kbIds
    if (pendingIds.length === 0 && kbIdInput.trim()) {
      setKbIds([kbIdInput.trim()])
    }

    const trimmedMessage = message.trim()
    const knowledgeBaseIds = kbIdInput.trim()
      ? [...kbIds, kbIdInput.trim()]
      : kbIds

    if (!trimmedMessage) {
      setFormError("Pertanyaan wajib diisi.")
      return
    }
    if (knowledgeBaseIds.length === 0) {
      setFormError("Tambahkan minimal satu Knowledge Base ID.")
      return
    }

    if (kbIdInput.trim()) {
      setKbIds(knowledgeBaseIds)
      setKbIdInput("")
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
          {/* Tag input for KB IDs */}
          <div className="flex flex-col gap-1.5">
            <label
              htmlFor="kb-id-input"
              className="text-sm font-medium text-main-700"
            >
              Knowledge Base ID <span className="text-danger-500">*</span>
            </label>
            <div
              className={cn(
                "flex min-h-[42px] flex-wrap items-center gap-1.5 rounded-lg border bg-white px-3 py-2 text-sm transition-colors focus-within:border-primary-500 focus-within:ring-1 focus-within:ring-primary-500",
                kbIds.length > 0 || kbIdInput
                  ? "border-gray-300"
                  : "border-gray-300",
              )}
              onClick={() => {
                const input = document.getElementById("kb-id-input")
                input?.focus()
              }}
              onKeyDown={() => {
                const input = document.getElementById("kb-id-input")
                input?.focus()
              }}
            >
              {kbIds.map((id) => (
                <span
                  key={id}
                  className="inline-flex items-center gap-1 rounded-md bg-primary-50 px-2 py-0.5 text-xs font-medium text-primary-700"
                >
                  {id}
                  <button
                    type="button"
                    onClick={() => removeKbId(id)}
                    className="rounded hover:text-primary-900"
                    aria-label={`Hapus ${id}`}
                  >
                    <X className="h-3 w-3" />
                  </button>
                </span>
              ))}
              <input
                id="kb-id-input"
                type="text"
                value={kbIdInput}
                onChange={(e) => setKbIdInput(e.target.value)}
                onKeyDown={handleKbIdKeyDown}
                onBlur={() => {
                  if (kbIdInput.trim()) addKbId(kbIdInput)
                }}
                placeholder={
                  kbIds.length === 0
                    ? "Ketik ID lalu tekan Enter atau koma"
                    : "Tambah ID lagi..."
                }
                className="min-w-[180px] flex-1 bg-transparent text-sm text-gray-900 outline-none placeholder:text-gray-400"
                disabled={isStreaming}
              />
            </div>
            <p className="text-xs text-gray-400">
              Tekan{" "}
              <kbd className="rounded border border-gray-200 bg-gray-50 px-1 py-0.5 font-mono text-[10px]">
                Enter
              </kbd>{" "}
              atau{" "}
              <kbd className="rounded border border-gray-200 bg-gray-50 px-1 py-0.5 font-mono text-[10px]">
                ,
              </kbd>{" "}
              untuk menambah ID. Gunakan ID yang sama seperti saat upload di
              Ingestion.
            </p>
          </div>

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
