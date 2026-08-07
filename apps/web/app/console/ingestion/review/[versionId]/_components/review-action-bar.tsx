"use client"

import { useState } from "react"

type Props = {
  isDirty: boolean
  isPending: boolean
  lifecycleState: string
  onSave: () => void
  onApprove: () => void
  onReject: () => void
}

export function ReviewActionBar({
  isDirty,
  isPending,
  lifecycleState,
  onSave,
  onApprove,
  onReject,
}: Props) {
  const [confirmReject, setConfirmReject] = useState(false)
  const isTerminal = lifecycleState === "READY" || lifecycleState === "FAILED"
  const isNeedsReview = lifecycleState === "NEEDS_REVIEW"

  return (
    <div className="sticky bottom-0 border-t bg-white px-6 py-4 shadow-md">
      <div className="flex items-center justify-end gap-3">
        <button
          type="button"
          disabled={!isDirty || isPending || !isNeedsReview}
          onClick={onSave}
          className="rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-40"
        >
          Simpan Koreksi
        </button>

        <button
          type="button"
          disabled={isPending || isTerminal || !isNeedsReview}
          onClick={onApprove}
          className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-40"
        >
          Approve
        </button>

        {confirmReject ? (
          <div className="flex items-center gap-2">
            <span className="text-sm text-red-600">Yakin menolak dokumen ini?</span>
            <button
              type="button"
              onClick={() => {
                setConfirmReject(false)
                onReject()
              }}
              className="rounded-md bg-red-600 px-3 py-2 text-sm font-medium text-white hover:bg-red-700"
            >
              Ya, Tolak
            </button>
            <button
              type="button"
              onClick={() => setConfirmReject(false)}
              className="rounded-md border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
            >
              Batal
            </button>
          </div>
        ) : (
          <button
            type="button"
            disabled={isPending || isTerminal || !isNeedsReview}
            onClick={() => setConfirmReject(true)}
            className="rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:cursor-not-allowed disabled:opacity-40"
          >
            Tolak
          </button>
        )}
      </div>
    </div>
  )
}
