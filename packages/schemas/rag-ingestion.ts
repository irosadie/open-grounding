import { z } from "zod"

export const ingestionMimeTypes = [
  "application/pdf",
  "text/markdown",
  "text/plain",
] as const

export const ingestionMimeLabels = [
  { label: "PDF", value: "application/pdf" },
  { label: "Markdown", value: "text/markdown" },
  { label: "Plain Text", value: "text/plain" },
]

export const getIngestionMimeLabel = (
  value: (typeof ingestionMimeTypes)[number],
) => {
  return (
    ingestionMimeLabels.find((item) => item.value === value)?.label ?? value
  )
}

export const documentVersionLifecycleStates = [
  "PENDING",
  "STORED",
  "PARSING",
  "NORMALIZING",
  "NEEDS_REVIEW",
  "CHUNKING",
  "EMBEDDING",
  "INDEXING",
  "READY",
  "FAILED",
  "DELETING",
] as const

export const documentVersionLifecycleLabels = [
  { label: "Pending", value: "PENDING" },
  { label: "Stored", value: "STORED" },
  { label: "Parsing", value: "PARSING" },
  { label: "Normalizing", value: "NORMALIZING" },
  { label: "Perlu Ditinjau", value: "NEEDS_REVIEW" },
  { label: "Chunking", value: "CHUNKING" },
  { label: "Embedding", value: "EMBEDDING" },
  { label: "Indexing", value: "INDEXING" },
  { label: "Ready", value: "READY" },
  { label: "Failed", value: "FAILED" },
  { label: "Deleting", value: "DELETING" },
]

export const getDocumentVersionLifecycleLabel = (
  value: (typeof documentVersionLifecycleStates)[number],
) => {
  return (
    documentVersionLifecycleLabels.find((item) => item.value === value)
      ?.label ?? value
  )
}

export const isTerminalLifecycleState = (
  value: string,
): value is (typeof documentVersionLifecycleStates)[number] => {
  return value === "READY" || value === "FAILED"
}

export const createIntakeSchema = z.object({
  knowledgeBaseId: z
    .string()
    .min(1, "Knowledge base is required")
    .max(120, "Knowledge base id must be 120 characters or less"),
  filename: z
    .string()
    .min(1, "Filename is required")
    .max(512, "Filename must be 512 characters or less"),
  mimeType: z.enum(ingestionMimeTypes, {
    errorMap: () => ({ message: "Unsupported file type" }),
  }),
  sizeBytes: z.number().int().positive("File size must be greater than zero"),
  sourceRevision: z
    .string()
    .max(512, "Source revision must be 512 characters or less")
    .optional(),
  title: z.string().max(512, "Title must be 512 characters or less").optional(),
})

export type CreateIntakeProps = z.infer<typeof createIntakeSchema>

export const completeIntakeSchema = z.object({
  documentVersionId: z
    .string()
    .min(1, "Document version is required")
    .max(120, "Document version id must be 120 characters or less"),
  contentChecksum: z
    .string()
    .min(1, "Content checksum is required")
    .max(128, "Content checksum must be 128 characters or less"),
})

export type CompleteIntakeProps = z.infer<typeof completeIntakeSchema>

export const submitParsedTextSchema = z.object({
  text: z.string().min(1, "Teks tidak boleh kosong"),
})

export type SubmitParsedTextProps = z.infer<typeof submitParsedTextSchema>
