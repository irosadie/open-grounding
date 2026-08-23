"use client"

import { Button } from "$/components/button"
import { PanelCard } from "$/components/panel-card"
import {
  useApproveIngestion,
  useIngestionParsedText,
  useRejectIngestion,
  useSubmitParsedText,
} from "$/hooks/transactions/use-rag-ingestion"
import { AlertTriangle, ArrowLeft, CheckCircle, FileText, XCircle } from "lucide-react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { useEffect, useState } from "react"
import { DocumentMetaCard } from "./_components/document-meta-card"
import { ParsedTextEditor } from "./_components/parsed-text-editor"
import { ReviewActionBar } from "./_components/review-action-bar"

type Props = {
  versionId: string
}

export function ReviewContent({ versionId }: Props) {
  const router = useRouter()
  const { data, isLoading, isError } = useIngestionParsedText(versionId)
  const submitMutation = useSubmitParsedText(versionId)
  const approveMutation = useApproveIngestion(versionId)
  const rejectMutation = useRejectIngestion(versionId)

  const [editedText, setEditedText] = useState("")
  const [isDirty, setIsDirty] = useState(false)

  useEffect(() => {
    if (data?.parsedText) {
      setEditedText(data.parsedText)
    }
  }, [data?.parsedText])

  const isPending =
    submitMutation.isPending ||
    approveMutation.isPending ||
    rejectMutation.isPending

  const handleChange = (text: string) => {
    setEditedText(text)
    setIsDirty(text !== (data?.parsedText ?? ""))
  }

  const handleSave = async () => {
    await submitMutation.mutateAsync({ text: editedText })
    setIsDirty(false)
  }

  const handleApprove = async () => {
    await approveMutation.mutateAsync()
    router.push("/console/document")
  }

  const handleReject = async () => {
    await rejectMutation.mutateAsync()
    router.push("/console/document")
  }

  if (isLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="h-6 w-6 animate-spin rounded-full border-2 border-gray-300 border-t-primary-500" />
          <p className="text-sm text-gray-500">Loading document...</p>
        </div>
      </div>
    )
  }

  if (isError || !data) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="flex flex-col items-center gap-3 text-center">
          <XCircle className="h-8 w-8 text-danger-400" />
          <p className="text-sm text-gray-500">
            Failed to load document. Check your connection or try again.
          </p>
          <Link href="/console/document">
            <Button intent="clean" bordered size="small">
              Back to Documents
            </Button>
          </Link>
        </div>
      </div>
    )
  }

  const isEditable = data.lifecycleState === "NEEDS_REVIEW" && !isPending
  const isTerminal = data.lifecycleState === "READY" || data.lifecycleState === "FAILED"

  return (
    <div className="flex min-h-screen flex-col bg-gray-50">
      {/* Header */}
      <div className="border-b border-gray-200 bg-white px-6 py-4">
        <div className="mx-auto max-w-4xl">
          <Link
            href="/console/document"
            className="mb-3 inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to Documents
          </Link>
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary-50">
              <FileText className="h-5 w-5 text-primary-600" />
            </div>
            <div>
              <h1 className="text-lg font-semibold text-gray-900">Document Review</h1>
              <p className="text-sm text-gray-500">Review parsed content before indexing</p>
            </div>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 px-6 py-6 pb-32">
        <div className="mx-auto max-w-4xl space-y-4">

          {/* Status banner */}
          {data.lifecycleState === "NEEDS_REVIEW" && (
            <div className="flex items-start gap-3 rounded-xl border border-warning-200 bg-warning-50 px-4 py-3">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warning-600" />
              <p className="text-sm text-warning-800">
                This document is waiting for your review. Correct any parsing errors in the text below, then <strong>Approve</strong> to index or <strong>Reject</strong> to discard.
              </p>
            </div>
          )}

          {data.lifecycleState === "READY" && (
            <div className="flex items-start gap-3 rounded-xl border border-success-200 bg-success-50 px-4 py-3">
              <CheckCircle className="mt-0.5 h-4 w-4 shrink-0 text-success-600" />
              <p className="text-sm text-success-800">
                This document has been approved and indexed successfully.
              </p>
            </div>
          )}

          {data.lifecycleState === "FAILED" && (
            <div className="flex items-start gap-3 rounded-xl border border-danger-200 bg-danger-50 px-4 py-3">
              <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-danger-600" />
              <p className="text-sm text-danger-800">
                This document was rejected and will not be indexed.
              </p>
            </div>
          )}

          {/* Document meta */}
          <DocumentMetaCard
            filename={versionId}
            lifecycleState={data.lifecycleState}
          />

          {/* Parsed text editor */}
          <PanelCard
            title="Parsed Content"
            description={isEditable ? "Review and correct the extracted text before approving." : "Extracted text content from this document."}
          >
            <ParsedTextEditor
              content={editedText}
              editable={isEditable}
              onChange={handleChange}
            />
          </PanelCard>

        </div>
      </div>

      {/* Action bar */}
      {!isTerminal && (
        <ReviewActionBar
          isDirty={isDirty}
          isPending={isPending}
          lifecycleState={data.lifecycleState}
          onSave={handleSave}
          onApprove={handleApprove}
          onReject={handleReject}
        />
      )}
    </div>
  )
}

export default ReviewContent
