import { FileText } from "lucide-react"

const lifecycleBadgeClass: Record<string, string> = {
  READY: "bg-success-100 text-success-700",
  FAILED: "bg-danger-100 text-danger-700",
  DELETING: "bg-gray-100 text-gray-500",
  NEEDS_REVIEW: "bg-warning-100 text-warning-700",
  PARSING: "bg-info-100 text-info-700",
  NORMALIZING: "bg-info-100 text-info-700",
  CHUNKING: "bg-info-100 text-info-700",
  EMBEDDING: "bg-info-100 text-info-700",
  INDEXING: "bg-info-100 text-info-700",
}

const lifecycleLabel: Record<string, string> = {
  READY: "Ready",
  FAILED: "Rejected",
  DELETING: "Deleting",
  NEEDS_REVIEW: "Needs Review",
  PARSING: "Parsing",
  NORMALIZING: "Normalizing",
  CHUNKING: "Chunking",
  EMBEDDING: "Embedding",
  INDEXING: "Indexing",
}

type Props = {
  filename: string
  lifecycleState: string
  uploadedAt?: string
}

export function DocumentMetaCard({ filename, lifecycleState, uploadedAt }: Props) {
  const badgeClass = lifecycleBadgeClass[lifecycleState] ?? "bg-gray-100 text-gray-700"
  const label = lifecycleLabel[lifecycleState] ?? lifecycleState
  const formattedDate = uploadedAt
    ? new Intl.DateTimeFormat("en-US", {
        dateStyle: "medium",
        timeStyle: "short",
      }).format(new Date(uploadedAt))
    : "—"

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-xs">
      <div className="flex items-start gap-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-gray-100">
          <FileText className="h-4 w-4 text-gray-500" />
        </div>
        <div className="flex-1 min-w-0 space-y-2">
          <div className="flex items-center justify-between gap-2">
            <p className="truncate text-sm font-medium text-gray-900">{filename}</p>
            <span className={`shrink-0 rounded-full px-2.5 py-0.5 text-xs font-medium ${badgeClass}`}>
              {label}
            </span>
          </div>
          <div className="flex items-center gap-4">
            <span className="text-xs text-gray-500">
              Uploaded: <span className="text-gray-700">{formattedDate}</span>
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}
