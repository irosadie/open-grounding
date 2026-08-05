"use client"

import { Button } from "$/components/button"
import { useRagIngestionDelete } from "$/hooks/transactions/use-rag-ingestion"
import { useRagIngestionStatus } from "$/hooks/transactions/use-rag-ingestion"
import { cn } from "$/utils/cn"
import {
  getCurrentStageIndex,
  getIngestionStageLabel,
  ingestionStages,
  isIngestionTerminal,
} from "$/utils/ingestion-pipeline"
import { Check, CircleAlert, Loader2 } from "lucide-react"
import { useState } from "react"

type VersionCardProps = {
  documentVersionId: string
  filename: string
  onDeleted: (documentVersionId: string) => void
}

export function IngestionVersionCard({
  documentVersionId,
  filename,
  onDeleted,
}: VersionCardProps) {
  const { data, isLoading } = useRagIngestionStatus({
    documentVersionId,
    enabled: true,
  })
  const deleteVersion = useRagIngestionDelete()
  const [confirmingDelete, setConfirmingDelete] = useState(false)

  const lifecycleState = data?.lifecycleState ?? "PENDING"
  const currentIndex = getCurrentStageIndex(lifecycleState)
  const isFailed = lifecycleState === "FAILED"
  const isReady = lifecycleState === "READY"
  const isTerminal = isIngestionTerminal(lifecycleState)
  const stageLabel = getIngestionStageLabel(lifecycleState)

  const handleDelete = () => {
    deleteVersion.mutate(documentVersionId, {
      onSuccess: () => {
        onDeleted(documentVersionId)
      },
    })
  }

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-xs">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-gray-900">
            {filename}
          </p>
          <p className="mt-0.5 text-xs text-gray-500">
            {isLoading
              ? "Loading status..."
              : `Stage: ${stageLabel}${data ? ` · ${(data.sizeBytes / 1024).toFixed(1)} KB` : ""}`}
          </p>
        </div>
        {isTerminal ? (
          <div className="flex items-center gap-2">
            <span
              className={cn(
                "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium",
                isReady
                  ? "bg-success-100 text-success-700"
                  : "bg-danger-100 text-danger-700",
              )}
            >
              {isReady ? "Ready" : "Failed"}
            </span>
            {confirmingDelete ? (
              <div className="flex items-center gap-1">
                <Button
                  intent="danger"
                  size="small"
                  onClick={handleDelete}
                  loading={deleteVersion.isPending}
                >
                  Confirm
                </Button>
                <Button
                  intent="secondary"
                  size="small"
                  onClick={() => setConfirmingDelete(false)}
                >
                  Cancel
                </Button>
              </div>
            ) : (
              <Button
                intent="secondary"
                size="small"
                bordered
                onClick={() => setConfirmingDelete(true)}
              >
                Delete
              </Button>
            )}
          </div>
        ) : (
          <span className="inline-flex items-center gap-1 text-xs text-gray-500">
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
            Processing
          </span>
        )}
      </div>

      <ol className="mt-4 flex items-center">
        {ingestionStages.map((stage, index) => {
          const isCompleted = isReady || (!isFailed && index < currentIndex)
          const isCurrent = !isTerminal && index === currentIndex
          const isFailedStage = isFailed && index === currentIndex

          return (
            <li
              key={stage.id}
              className="flex flex-1 items-center last:flex-none"
            >
              <div className="flex flex-col items-center">
                <span
                  className={cn(
                    "flex h-7 w-7 items-center justify-center rounded-full border-2 text-xs font-medium",
                    isCompleted &&
                      "border-success-500 bg-success-500 text-white",
                    isCurrent &&
                      "border-primary-500 bg-primary-50 text-primary-700",
                    isFailedStage &&
                      "border-danger-500 bg-danger-50 text-danger-700",
                    !isCompleted &&
                      !isCurrent &&
                      !isFailedStage &&
                      "border-gray-300 bg-white text-gray-400",
                  )}
                >
                  {isCompleted ? (
                    <Check className="h-3.5 w-3.5" />
                  ) : isFailedStage ? (
                    <CircleAlert className="h-3.5 w-3.5" />
                  ) : isCurrent ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    index + 1
                  )}
                </span>
                <span
                  className={cn(
                    "mt-1.5 text-[10px] font-medium",
                    isCompleted || isCurrent
                      ? "text-gray-700"
                      : "text-gray-400",
                  )}
                >
                  {stage.label}
                </span>
              </div>
              {index < ingestionStages.length - 1 && (
                <div
                  className={cn(
                    "mx-1.5 h-0.5 flex-1",
                    isCompleted ? "bg-success-500" : "bg-gray-200",
                  )}
                />
              )}
            </li>
          )
        })}
      </ol>
    </div>
  )
}

export default IngestionVersionCard
