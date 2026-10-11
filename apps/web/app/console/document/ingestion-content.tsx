"use client"

import { Button } from "$/components/button"
import { EmptyState } from "$/components/empty-state"
import { KnowledgeBaseSelect } from "$/components/knowledge-base-select"
import { PanelCard } from "$/components/panel-card"
import { useRagIngestionComplete } from "$/hooks/transactions/use-rag-ingestion"
import { useRagIngestionDelete } from "$/hooks/transactions/use-rag-ingestion"
import { useRagIngestionIntake } from "$/hooks/transactions/use-rag-ingestion"
import { useRagDocuments } from "$/hooks/transactions/use-rag-ingestion"
import type { DocumentVersionItem } from "$/hooks/transactions/use-rag-ingestion"
import { useIngestionStatuses } from "$/hooks/transactions/use-rag-ingestion/use-ingestion-statuses"
import { ingestionMimeTypes } from "@open-grounding/schemas"
import type { KnowledgeBaseResponseProps } from "@open-grounding/types"
import {
  ClipboardCheck,
  FileUp,
  RefreshCw,
  Trash2,
  Upload,
  X,
} from "lucide-react"
import Link from "next/link"
import {
  type ChangeEvent,
  type DragEvent,
  useId,
  useRef,
  useState,
} from "react"
import IngestionVersionCard from "./version-card"

type UploadedVersion = {
  documentVersionId: string
  filename: string
}

const computeChecksum = async (file: File): Promise<string> => {
  const buffer = await file.arrayBuffer()
  const digest = await crypto.subtle.digest("SHA-256", buffer)
  return Array.from(new Uint8Array(digest))
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("")
}

const isSupportedFile = (file: File) => {
  return ingestionMimeTypes.includes(
    file.type as (typeof ingestionMimeTypes)[number],
  )
}

const lifecycleLabel: Record<string, string> = {
  PENDING: "Pending",
  RECEIVED: "Received",
  STORED: "Stored",
  QUEUED: "Queued",
  PARSING: "Parsing",
  NORMALIZING: "Normalizing",
  CHUNKING: "Chunking",
  EMBEDDING: "Embedding",
  INDEXING: "Indexing",
  READY: "Ready",
  FAILED: "Failed",
  DELETING: "Deleting",
  DELETED: "Deleted",
  NEEDS_REVIEW: "Needs Review",
  SUPERSEDED: "Superseded",
}

const lifecycleBadgeClass: Record<string, string> = {
  READY: "bg-green-100 text-green-700",
  FAILED: "bg-red-100 text-red-700",
  DELETING: "bg-gray-100 text-gray-500",
  DELETED: "bg-gray-100 text-gray-400",
  NEEDS_REVIEW: "bg-amber-100 text-amber-700",
  SUPERSEDED: "bg-gray-100 text-gray-500",
}

const deletableLifecycleStates = new Set(["READY", "FAILED", "NEEDS_REVIEW"])

// Windowing client-side: render batch awal, tambah progresif via tombol.
const INITIAL_VISIBLE_DOCUMENTS = 50

export function IngestionContent() {
  const intake = useRagIngestionIntake()
  const complete = useRagIngestionComplete()
  const deleteVersion = useRagIngestionDelete()
  const sourceFileInputId = useId()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [selectedKb, setSelectedKb] =
    useState<KnowledgeBaseResponseProps | null>(null)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [formError, setFormError] = useState("")
  const [versions, setVersions] = useState<UploadedVersion[]>([])
  const [isDragging, setIsDragging] = useState(false)
  const [confirmingDelete, setConfirmingDelete] = useState<string | null>(null)
  const [visibleDocCount, setVisibleDocCount] = useState(
    INITIAL_VISIBLE_DOCUMENTS,
  )

  const {
    data: kbDocuments,
    isLoading: isLoadingDocs,
    refetch: refetchDocs,
  } = useRagDocuments(selectedKb?.id ?? null)

  // Agregasi polling N -> 1: satu query untuk semua kartu status.
  const versionIds = versions.map((version) => version.documentVersionId)
  const { data: ingestionStatuses, isLoading: isLoadingStatuses } =
    useIngestionStatuses({ versionIds })

  const totalDocs = kbDocuments?.length ?? 0
  const visibleDocs = (kbDocuments ?? []).slice(0, visibleDocCount)
  const remainingDocs = totalDocs - visibleDocs.length

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0] ?? null
    setFormError("")
    if (file && !isSupportedFile(file)) {
      setFormError("Only PDF, Markdown, and plain-text files are supported.")
      setSelectedFile(null)
      return
    }
    setSelectedFile(file)
  }

  const handleDrop = (event: DragEvent<HTMLButtonElement>) => {
    event.preventDefault()
    setIsDragging(false)
    const file = event.dataTransfer.files?.[0] ?? null
    setFormError("")
    if (!file) return
    if (!isSupportedFile(file)) {
      setFormError("Only PDF, Markdown, and plain-text files are supported.")
      return
    }
    setSelectedFile(file)
  }

  const handleDragOver = (event: DragEvent<HTMLButtonElement>) => {
    event.preventDefault()
    setIsDragging(true)
  }

  const handleDragLeave = () => {
    setIsDragging(false)
  }

  const handleUpload = async () => {
    setFormError("")
    if (!selectedKb) {
      setFormError("Please select a knowledge base first.")
      return
    }
    if (!selectedFile) {
      setFormError("Please select a file to upload.")
      return
    }

    try {
      const intakeResult = await intake.mutateAsync({
        knowledgeBaseId: selectedKb.id,
        filename: selectedFile.name,
        mimeType: selectedFile.type as (typeof ingestionMimeTypes)[number],
        sizeBytes: selectedFile.size,
        title: selectedFile.name,
      })

      // Upload file to API which stores it in MinIO
      const formData = new FormData()
      formData.append("file", selectedFile)
      const uploadRes = await fetch(
        `/api/proxy/rag/ingestion/upload/${intakeResult.documentVersionId}`,
        { method: "PUT", body: formData },
      )
      if (!uploadRes.ok) {
        throw new Error("File upload to server failed.")
      }

      const checksum = await computeChecksum(selectedFile)

      await complete.mutateAsync({
        documentVersionId: intakeResult.documentVersionId,
        contentChecksum: checksum,
      })

      setVersions((current) => [
        ...current,
        {
          documentVersionId: intakeResult.documentVersionId,
          filename: selectedFile.name,
        },
      ])
      setSelectedFile(null)
      if (fileInputRef.current) fileInputRef.current.value = ""
      refetchDocs()
    } catch (error) {
      const message =
        (error as { message?: string })?.message ?? "Upload failed."
      setFormError(message)
    }
  }

  const handleDeleted = (documentVersionId: string) => {
    setVersions((current) =>
      current.filter(
        (version) => version.documentVersionId !== documentVersionId,
      ),
    )
    refetchDocs()
  }

  const handleDocumentDelete = (documentVersionId: string) => {
    deleteVersion.mutate(documentVersionId, {
      onSuccess: () => {
        setConfirmingDelete(null)
        void refetchDocs()
      },
    })
  }

  const isBusy = intake.isPending || complete.isPending

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold text-gray-900">Ingestion</h1>
        <p className="mt-1 text-sm text-gray-500">
          Upload documents to a knowledge base to be processed and indexed by
          the RAG pipeline.
        </p>
      </div>

      <PanelCard
        title="Upload Document"
        description="Supports PDF, Markdown (.md), and plain-text (.txt) formats."
      >
        <div className="flex flex-col gap-4">
          <KnowledgeBaseSelect
            value={selectedKb}
            onChange={(kb) => {
              setSelectedKb(kb)
              setVisibleDocCount(INITIAL_VISIBLE_DOCUMENTS)
            }}
            label="Knowledge Base"
            hint="Select the destination knowledge base for this document."
            required
            disabled={isBusy}
          />

          {/* Drop zone */}
          <div className="flex flex-col gap-1.5">
            <label
              htmlFor={sourceFileInputId}
              className="text-sm font-medium text-main-700"
            >
              File <span className="text-danger-500">*</span>
            </label>
            <button
              type="button"
              aria-label="File upload area"
              onClick={() => fileInputRef.current?.click()}
              onDrop={handleDrop}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              className={`flex w-full cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed px-6 py-8 text-center transition-colors ${
                isDragging
                  ? "border-primary-400 bg-primary-50"
                  : "border-gray-200 bg-gray-50 hover:border-primary-300 hover:bg-primary-50/50"
              }`}
            >
              <Upload className="h-8 w-8 text-gray-400" />
              <div>
                <p className="text-sm font-medium text-gray-700">
                  Click to select a file, or drag &amp; drop here
                </p>
                <p className="mt-0.5 text-xs text-gray-400">
                  PDF, Markdown, TXT — max size per server configuration
                </p>
              </div>
            </button>
            <input
              ref={fileInputRef}
              id={sourceFileInputId}
              type="file"
              accept=".pdf,.md,.markdown,.txt,application/pdf,text/markdown,text/plain"
              onChange={handleFileChange}
              className="sr-only"
            />
          </div>

          {/* Selected file chip */}
          {selectedFile ? (
            <div className="flex items-center gap-2 rounded-lg border border-gray-200 bg-white px-3 py-2">
              <FileUp className="h-4 w-4 shrink-0 text-primary-500" />
              <span className="min-w-0 flex-1 truncate text-sm text-gray-700">
                {selectedFile.name}
              </span>
              <span className="shrink-0 text-xs text-gray-400">
                {(selectedFile.size / 1024).toFixed(1)} KB
              </span>
              <button
                type="button"
                onClick={() => {
                  setSelectedFile(null)
                  if (fileInputRef.current) fileInputRef.current.value = ""
                }}
                className="shrink-0 rounded p-0.5 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
                aria-label="Remove file"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          ) : null}

          {formError ? (
            <p className="text-sm text-danger-500">{formError}</p>
          ) : null}

          <Button
            intent="primary"
            onClick={handleUpload}
            loading={isBusy}
            disabled={isBusy || !selectedFile || !selectedKb}
            leftIcon={<Upload className="h-4 w-4" />}
          >
            {isBusy ? "Uploading..." : "Upload & Ingest"}
          </Button>
        </div>
      </PanelCard>

      {/* Documents in selected KB */}
      {selectedKb ? (
        <PanelCard
          title={`Documents in "${selectedKb.name}"`}
          description="Documents uploaded to this knowledge base."
        >
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs text-gray-400">
              {isLoadingDocs
                ? "Loading..."
                : `${kbDocuments?.length ?? 0} document${(kbDocuments?.length ?? 0) === 1 ? "" : "s"}`}
            </span>
            <button
              type="button"
              onClick={() => refetchDocs()}
              className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
              aria-label="Refresh"
            >
              <RefreshCw className="h-3.5 w-3.5" />
            </button>
          </div>
          {isLoadingDocs ? (
            <p className="text-sm text-gray-400">Loading documents...</p>
          ) : !kbDocuments || kbDocuments.length === 0 ? (
            <EmptyState
              icon={FileUp}
              title="No documents yet"
              description="Upload a document above to start the ingestion pipeline."
            />
          ) : (
            <>
              <div className="flex flex-col divide-y divide-gray-100">
                {visibleDocs.map((doc: DocumentVersionItem) => (
                  <div
                    key={doc.documentVersionId}
                    className={`flex items-center gap-3 py-2.5 ${doc.lifecycleState === "DELETED" ? "opacity-50" : ""}`}
                  >
                    <FileUp className="h-4 w-4 shrink-0 text-gray-400" />
                    <span className="min-w-0 flex-1 truncate text-sm text-gray-700">
                      {doc.title}
                    </span>
                    <span className="shrink-0 text-xs text-gray-400">
                      {doc.sizeBytes
                        ? `${(doc.sizeBytes / 1024).toFixed(1)} KB`
                        : "—"}
                    </span>
                    {doc.lifecycleState === "NEEDS_REVIEW" ? (
                      <Link
                        href={`/console/document/review/${doc.documentVersionId}`}
                        className="inline-flex shrink-0 items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700 hover:bg-amber-200"
                      >
                        <ClipboardCheck className="h-3 w-3" />
                        Needs Review
                      </Link>
                    ) : (
                      <span
                        className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${lifecycleBadgeClass[doc.lifecycleState] ?? "bg-blue-100 text-blue-700"}`}
                      >
                        {lifecycleLabel[doc.lifecycleState] ??
                          doc.lifecycleState}
                      </span>
                    )}
                    {deletableLifecycleStates.has(doc.lifecycleState) ? (
                      confirmingDelete === doc.documentVersionId ? (
                        <div
                          className="flex shrink-0 items-center gap-1 rounded-lg border border-danger-100 bg-danger-50 px-2 py-1"
                          role="alertdialog"
                          aria-label={`Confirm deletion of ${doc.title}`}
                        >
                          <span className="mr-1 text-xs text-danger-700">
                            Delete?
                          </span>
                          <Button
                            intent="danger"
                            size="small"
                            onClick={() =>
                              handleDocumentDelete(doc.documentVersionId)
                            }
                            loading={
                              deleteVersion.isPending &&
                              deleteVersion.variables === doc.documentVersionId
                            }
                          >
                            Confirm
                          </Button>
                          <Button
                            intent="secondary"
                            size="small"
                            onClick={() => setConfirmingDelete(null)}
                          >
                            Cancel
                          </Button>
                        </div>
                      ) : (
                        <Button
                          intent="secondary"
                          size="small"
                          bordered
                          onClick={() =>
                            setConfirmingDelete(doc.documentVersionId)
                          }
                          leftIcon={<Trash2 className="h-3.5 w-3.5" />}
                        >
                          Delete
                        </Button>
                      )
                    ) : null}
                  </div>
                ))}
              </div>
              {remainingDocs > 0 ? (
                <button
                  type="button"
                  onClick={() =>
                    setVisibleDocCount(
                      (count) => count + INITIAL_VISIBLE_DOCUMENTS,
                    )
                  }
                  className="mt-2 w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm font-medium text-gray-600 hover:bg-gray-50"
                >
                  Muat lebih banyak ({remainingDocs} lagi)
                </button>
              ) : null}
            </>
          )}
        </PanelCard>
      ) : null}

      <PanelCard
        title="Ingestion Status"
        description="Monitor documents being processed through the pipeline."
      >
        {versions.length === 0 ? (
          <EmptyState
            icon={FileUp}
            title="No documents yet"
            description="Upload a document above to start the ingestion pipeline."
          />
        ) : (
          <div className="flex flex-col gap-4">
            {versions.map((version) => (
              <IngestionVersionCard
                key={version.documentVersionId}
                documentVersionId={version.documentVersionId}
                filename={version.filename}
                onDeleted={handleDeleted}
                status={ingestionStatuses?.[version.documentVersionId]}
                isLoadingStatus={isLoadingStatuses}
              />
            ))}
          </div>
        )}
      </PanelCard>
    </div>
  )
}

export default IngestionContent
