"use client"

import {
  useApproveIngestion,
  useIngestionParsedText,
  useRejectIngestion,
  useSubmitParsedText,
} from "$/hooks/transactions/use-rag-ingestion"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { useEffect, useState } from "react"
import { DocumentMetaCard } from "./_components/document-meta-card"
import { NeedsReviewBanner } from "./_components/needs-review-banner"
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
      <div className="flex h-64 items-center justify-center text-sm text-gray-500">
        Memuat data dokumen...
      </div>
    )
  }

  if (isError || !data) {
    return (
      <div className="flex h-64 items-center justify-center text-sm text-red-500">
        Gagal memuat data dokumen. Periksa koneksi atau coba lagi.
      </div>
    )
  }

  const isEditable = data.lifecycleState === "NEEDS_REVIEW" && !isPending

  return (
    <div className="flex min-h-screen flex-col">
      <div className="flex-1 space-y-4 px-6 py-6 pb-32">
        <div className="flex items-center gap-2">
          <Link
            href="/console/document"
            className="text-sm text-blue-600 hover:underline"
          >
            ← Kembali ke Ingestion
          </Link>
        </div>

        <h1 className="text-xl font-semibold text-gray-900">Tinjauan Dokumen</h1>

        <NeedsReviewBanner lifecycleState={data.lifecycleState} />

        <DocumentMetaCard
          filename={versionId}
          lifecycleState={data.lifecycleState}
        />

        <ParsedTextEditor
          content={editedText}
          editable={isEditable}
          onChange={handleChange}
        />
      </div>

      <ReviewActionBar
        isDirty={isDirty}
        isPending={isPending}
        lifecycleState={data.lifecycleState}
        onSave={handleSave}
        onApprove={handleApprove}
        onReject={handleReject}
      />
    </div>
  )
}

export default ReviewContent
