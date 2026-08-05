"use client"

import { Button } from "$/components/button"
import { EmptyState } from "$/components/empty-state"
import { Input } from "$/components/input"
import { PanelCard } from "$/components/panel-card"
import { useRagIngestionComplete } from "$/hooks/transactions/use-rag-ingestion"
import { useRagIngestionIntake } from "$/hooks/transactions/use-rag-ingestion"
import { ingestionMimeTypes } from "@vibecoding-starter/schemas"
import { FileUp, Upload } from "lucide-react"
import { type ChangeEvent, useId, useState } from "react"
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
  const [knowledgeBaseId, setKnowledgeBaseId] = useState("")
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [formError, setFormError] = useState("")
  const [versions, setVersions] = useState<UploadedVersion[]>([])

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

  const handleUpload = async () => {
    setFormError("")
    if (!knowledgeBaseId.trim()) {
      setFormError("Knowledge base id is required.")
      return
    }
    if (!selectedFile) {
      setFormError("Select a file to upload.")
      return
    }

    try {
      const intakeResult = await intake.mutateAsync({
        knowledgeBaseId: knowledgeBaseId.trim(),
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
  }

  const isBusy = intake.isPending || complete.isPending

  return (
    <div className="flex flex-col gap-6">
      <PanelCard
        title="Upload Document"
        description="Upload a PDF, Markdown, or plain-text file to ingest."
      >
        <div className="flex flex-col gap-4">
          <Input
            label="Knowledge Base Id"
            name="knowledgeBaseId"
            placeholder="knowledge-base-id"
            value={knowledgeBaseId}
            onChange={(event) => setKnowledgeBaseId(event.target.value)}
            required
          />
          <div className="flex flex-col gap-1.5">
            <label
              htmlFor={sourceFileInputId}
              className="text-sm font-medium text-main-700"
            >
              Source File <span className="text-danger-500">*</span>
            </label>
            <div className="flex items-center gap-3">
              <input
                id={sourceFileInputId}
                type="file"
                accept=".pdf,.md,.markdown,.txt,application/pdf,text/markdown,text/plain"
                onChange={handleFileChange}
                className="block w-full text-sm text-gray-500 file:mr-3 file:rounded-lg file:border-0 file:bg-primary-50 file:px-4 file:py-2 file:text-sm file:font-medium file:text-primary-700 hover:file:bg-primary-100"
              />
            </div>
            {selectedFile ? (
              <span className="text-xs text-gray-500">
                {selectedFile.name} · {(selectedFile.size / 1024).toFixed(1)} KB
              </span>
            ) : null}
          </div>

          {formError ? (
            <p className="text-sm text-danger-500">{formError}</p>
          ) : null}

          <Button
            intent="primary"
            onClick={handleUpload}
            loading={isBusy}
            disabled={isBusy}
            leftIcon={<Upload className="h-4 w-4" />}
          >
            {isBusy ? "Uploading..." : "Upload & Ingest"}
          </Button>
        </div>
      </PanelCard>

      <PanelCard
        title="Ingestion Status"
        description="Track documents through the worker pipeline to completion."
      >
        {versions.length === 0 ? (
          <EmptyState
            icon={FileUp}
            title="No documents ingested yet"
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
              />
            ))}
          </div>
        )}
      </PanelCard>
    </div>
  )
}

export default IngestionContent
