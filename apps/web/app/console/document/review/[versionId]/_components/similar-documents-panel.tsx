"use client"

import { PanelCard } from "$/components/panel-card"
import { useSimilarDocuments } from "$/hooks/transactions/use-rag-ingestion"
import { AlertTriangle, ArrowUpRight, FileText, Loader2 } from "lucide-react"
import Link from "next/link"

type Props = {
  versionId: string
}

const lifecycleLabel: Record<string, string> = {
  READY: "Ready",
  NEEDS_REVIEW: "Needs review",
  FAILED: "Rejected",
}

const formatScore = (score: number) =>
  `${Math.round(Math.max(0, Math.min(1, score)) * 100)}%`

export function SimilarDocumentsPanel({ versionId }: Props) {
  const { data, isLoading, isError } = useSimilarDocuments(versionId)

  return (
    <PanelCard
      title="Similar documents"
      description="Related indexed documents found in this knowledge base."
    >
      {isLoading && (
        <div className="flex items-center gap-2 py-3 text-sm text-gray-500">
          <Loader2 className="h-4 w-4 animate-spin" />
          Looking for related documents...
        </div>
      )}

      {isError && (
        <div className="flex items-start gap-2 rounded-lg border border-warning-200 bg-warning-50 px-3 py-2 text-sm text-warning-800">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          Similar documents are temporarily unavailable. You can continue
          reviewing this document.
        </div>
      )}

      {!isLoading && !isError && data?.documents.length === 0 && (
        <p className="py-3 text-sm text-gray-500">
          No similar indexed documents were found in this knowledge base.
        </p>
      )}

      {!isLoading &&
        !isError &&
        data?.documents &&
        data.documents.length > 0 && (
          <div className="space-y-3">
            {data.documents.map((document) => (
              <div
                key={document.documentVersionId}
                className="rounded-lg border border-gray-200 bg-gray-50 p-3"
              >
                <div className="flex items-start gap-3">
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-white">
                    <FileText className="h-4 w-4 text-gray-500" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <Link
                        href={`/console/document/review/${document.documentVersionId}`}
                        className="truncate text-sm font-medium text-gray-900 hover:text-primary-600"
                      >
                        {document.title}
                      </Link>
                      <span className="shrink-0 rounded-full bg-primary-50 px-2 py-0.5 text-xs font-medium text-primary-700">
                        {formatScore(document.score)} similar
                      </span>
                    </div>
                    <div className="mt-1 flex items-center gap-2 text-xs text-gray-500">
                      <span>
                        {lifecycleLabel[document.lifecycleState] ??
                          document.lifecycleState}
                      </span>
                      <span aria-hidden="true">·</span>
                      <span>{document.documentVersionId}</span>
                    </div>
                    <p className="mt-2 line-clamp-3 text-sm leading-5 text-gray-600">
                      {document.preview || "No preview available."}
                    </p>
                    <Link
                      href={`/console/document/review/${document.documentVersionId}`}
                      className="mt-2 inline-flex items-center gap-1 text-xs font-medium text-primary-600 hover:text-primary-700"
                    >
                      Open document
                      <ArrowUpRight className="h-3.5 w-3.5" />
                    </Link>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
    </PanelCard>
  )
}
