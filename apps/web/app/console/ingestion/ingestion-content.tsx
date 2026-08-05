"use client"

import { Button } from "$/components/button"
import { EmptyState } from "$/components/empty-state"
import { KnowledgeBaseSelect } from "$/components/knowledge-base-select"
import { PanelCard } from "$/components/panel-card"
import { useRagIngestionComplete } from "$/hooks/transactions/use-rag-ingestion"
import { useRagIngestionIntake } from "$/hooks/transactions/use-rag-ingestion"
import { ingestionMimeTypes } from "@open-grounding/schemas"
import type { KnowledgeBaseResponseProps } from "@open-grounding/types"
import { FileUp, Upload, X } from "lucide-react"
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

export function IngestionContent() {
  const intake = useRagIngestionIntake()
  const complete = useRagIngestionComplete()
  const sourceFileInputId = useId()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [selectedKb, setSelectedKb] =
    useState<KnowledgeBaseResponseProps | null>(null)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [formError, setFormError] = useState("")
  const [versions, setVersions] = useState<UploadedVersion[]>([])
  const [isDragging, setIsDragging] = useState(false)

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0] ?? null
    setFormError("")
    if (file && !isSupportedFile(file)) {
      setFormError("Hanya file PDF, Markdown, dan plain-text yang didukung.")
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
      setFormError("Hanya file PDF, Markdown, dan plain-text yang didukung.")
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
      setFormError("Pilih knowledge base terlebih dahulu.")
      return
    }
    if (!selectedFile) {
      setFormError("Pilih file yang akan di-upload.")
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
    } catch (error) {
      const message =
        (error as { message?: string })?.message ?? "Upload gagal."
      setFormError(message)
    }
  }

  const handleDeleted = (documentVersionId: string) => {
    setVersions((current) =>
      current.filter(
        (version) => version.documentVersionId !== documentVersionId,
      ),
    )
  }

  const isBusy = intake.isPending || complete.isPending

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold text-gray-900">Ingestion</h1>
        <p className="mt-1 text-sm text-gray-500">
          Upload dokumen ke knowledge base untuk diproses dan diindeks oleh
          pipeline RAG.
        </p>
      </div>

      <PanelCard
        title="Upload Dokumen"
        description="Dukung format PDF, Markdown (.md), dan plain-text (.txt)."
      >
        <div className="flex flex-col gap-4">
          <KnowledgeBaseSelect
            value={selectedKb}
            onChange={setSelectedKb}
            label="Knowledge Base"
            hint="Pilih knowledge base tujuan dokumen ini."
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
              aria-label="Area upload file"
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
                  Klik untuk pilih file, atau drag &amp; drop ke sini
                </p>
                <p className="mt-0.5 text-xs text-gray-400">
                  PDF, Markdown, TXT — maks. ukuran sesuai konfigurasi server
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
                aria-label="Hapus file"
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
            {isBusy ? "Mengupload..." : "Upload & Ingest"}
          </Button>
        </div>
      </PanelCard>

      <PanelCard
        title="Status Ingestion"
        description="Pantau dokumen yang sedang diproses melalui pipeline."
      >
        {versions.length === 0 ? (
          <EmptyState
            icon={FileUp}
            title="Belum ada dokumen"
            description="Upload dokumen di atas untuk memulai pipeline ingestion."
          />
        ) : (
          <div className="flex flex-col gap-4">
            {versions.map((version) => (
              <IngestionVersionCard
                key={version.documentVersionId}
                documentVersionId={version.documentVersionId}
                filename={version.filename}
                onDeleted={handleDeleted}
              />
            ))}
          </div>
        )}
      </PanelCard>
    </div>
  )
}

export default IngestionContent
