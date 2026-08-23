type Props = {
  lifecycleState: string
}

export function NeedsReviewBanner({ lifecycleState }: Props) {
  if (lifecycleState !== "NEEDS_REVIEW") return null

  return (
    <div className="flex items-start gap-3 rounded-lg border border-amber-200 bg-amber-50 p-4">
      <span className="text-amber-500 text-lg leading-none">⚠</span>
      <p className="text-sm text-amber-800">
        This document requires manual review. Check the parsed text below,
        correct any OCR errors, then <strong>Approve</strong> or{" "}
        <strong>Reject</strong>.
      </p>
    </div>
  )
}
