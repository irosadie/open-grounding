import { Suspense } from "react"
import IngestionContent from "./ingestion-content"

type Props = {
  params: Promise<{ id: string }>
}

export default async function IngestionSettingsPage({ params }: Props) {
  const { id } = await params
  return (
    <Suspense
      fallback={
        <div className="py-8 text-center text-sm text-gray-400">Loading...</div>
      }
    >
      <IngestionContent knowledgeBaseId={id} />
    </Suspense>
  )
}
