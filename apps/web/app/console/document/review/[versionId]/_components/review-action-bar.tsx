"use client"

import { Button } from "$/components/button"
import { CheckCircle, Save, XCircle } from "lucide-react"
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
  const isNeedsReview = lifecycleState === "NEEDS_REVIEW"

  return (
    <div className="sticky bottom-0 border-t border-gray-200 bg-white px-6 py-4 shadow-lg">
      <div className="mx-auto flex max-w-4xl items-center justify-between">
        <p className="text-sm text-gray-500">
          {isDirty
            ? "You have unsaved corrections."
            : "Review the parsed content above before taking action."}
        </p>

        <div className="flex items-center gap-2">
          <Button
            intent="clean"
            bordered
            size="small"
            leftIcon={<Save className="h-4 w-4" />}
            disabled={!isDirty || isPending || !isNeedsReview}
            loading={isPending && !confirmReject}
            onClick={onSave}
          >
            Save Corrections
          </Button>

          {confirmReject ? (
            <div className="flex items-center gap-2">
              <span className="text-sm text-danger-600">Reject this document?</span>
              <Button
                intent="danger"
                size="small"
                loading={isPending}
                onClick={() => {
                  setConfirmReject(false)
                  onReject()
                }}
              >
                Yes, Reject
              </Button>
              <Button
                intent="clean"
                bordered
                size="small"
                disabled={isPending}
                onClick={() => setConfirmReject(false)}
              >
                Cancel
              </Button>
            </div>
          ) : (
            <>
              <Button
                intent="danger"
                bordered
                size="small"
                leftIcon={<XCircle className="h-4 w-4" />}
                disabled={isPending || !isNeedsReview}
                onClick={() => setConfirmReject(true)}
              >
                Reject
              </Button>

              <Button
                intent="success"
                size="small"
                leftIcon={<CheckCircle className="h-4 w-4" />}
                disabled={isPending || !isNeedsReview}
                loading={isPending}
                onClick={onApprove}
              >
                Approve
              </Button>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
