import { Suspense } from "react"
import ReviewContent from "./review-content"

type Props = {
  params: Promise<{ versionId: string }>
}

export default async function ReviewPage({ params }: Props) {
  const { versionId } = await params

  return (
    <Suspense
      fallback={
        <div className="flex h-64 items-center justify-center text-sm text-gray-500">
          Memuat...
        </div>
      }
    >
      <ReviewContent versionId={versionId} />
    </Suspense>
  )
}
