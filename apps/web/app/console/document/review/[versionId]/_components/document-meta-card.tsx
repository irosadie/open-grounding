const lifecycleBadgeClass: Record<string, string> = {
  READY: "bg-green-100 text-green-700",
  FAILED: "bg-red-100 text-red-700",
  DELETING: "bg-gray-100 text-gray-500",
  NEEDS_REVIEW: "bg-amber-100 text-amber-700",
  PARSING: "bg-blue-100 text-blue-700",
  NORMALIZING: "bg-blue-100 text-blue-700",
  CHUNKING: "bg-blue-100 text-blue-700",
  EMBEDDING: "bg-blue-100 text-blue-700",
  INDEXING: "bg-blue-100 text-blue-700",
}

type Props = {
  filename: string
  lifecycleState: string
  uploadedAt?: string
}

export function DocumentMetaCard({ filename, lifecycleState, uploadedAt }: Props) {
  const badgeClass = lifecycleBadgeClass[lifecycleState] ?? "bg-gray-100 text-gray-700"
  const formattedDate = uploadedAt
    ? new Intl.DateTimeFormat("id-ID", {
        dateStyle: "medium",
        timeStyle: "short",
      }).format(new Date(uploadedAt))
    : "-"

  return (
    <div className="rounded-lg border bg-white p-4 shadow-sm">
      <h2 className="text-sm font-semibold text-gray-500 mb-3">Informasi Dokumen</h2>
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <span className="text-sm text-gray-500 w-28 shrink-0">Nama File</span>
          <span className="text-sm font-medium text-gray-900 truncate">{filename}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-sm text-gray-500 w-28 shrink-0">Status</span>
          <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${badgeClass}`}>
            {lifecycleState}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-sm text-gray-500 w-28 shrink-0">Diunggah</span>
          <span className="text-sm text-gray-700">{formattedDate}</span>
        </div>
      </div>
    </div>
  )
}
