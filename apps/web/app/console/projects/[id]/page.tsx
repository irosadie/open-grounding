"use client"

import { Button } from "$/components/button"
import { PanelCard } from "$/components/panel-card"
import { useKnowledgeBases } from "$/hooks/transactions/use-knowledge-bases"
import {
  useAssignProjectKnowledgeBase,
  useProject,
} from "$/hooks/transactions/use-projects"
import { AlertTriangle, Database, ExternalLink } from "lucide-react"
import Link from "next/link"
import { useState } from "react"

export default function ProjectOverviewPage({
  params,
}: { params: { id: string } }) {
  const { data: project, isLoading } = useProject(params.id)
  const { data: knowledgeBases } = useKnowledgeBases()
  const assign = useAssignProjectKnowledgeBase(params.id)
  const [selected, setSelected] = useState("")
  const memberIds = new Set(project?.knowledgeBases.map((kb) => kb.id))
  const available =
    knowledgeBases?.filter(
      (kb) => !memberIds.has(kb.id) && kb.status === "ACTIVE",
    ) ?? []

  if (isLoading)
    return <p className="text-sm text-gray-400">Loading Project...</p>
  if (!project)
    return (
      <p className="rounded-lg bg-danger-50 p-4 text-sm text-danger-700">
        Project tidak ditemukan.
      </p>
    )

  return (
    <div className="flex flex-col gap-6">
      {project.migrationReviews.length ? (
        <PanelCard
          title="Migration review required"
          description="Legacy configuration ditemukan saat Project dibuat. Simpan konfigurasi Project setelah meninjau dampaknya."
        >
          <div className="flex flex-col gap-2">
            {project.migrationReviews.map((review) => (
              <div
                key={review.id}
                className="flex items-center gap-3 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900"
              >
                <AlertTriangle className="h-4 w-4 shrink-0" />
                <span>
                  {review.configKind}: {review.legacyCount} legacy record(s),
                  status {review.status}.
                </span>
              </div>
            ))}
          </div>
        </PanelCard>
      ) : null}
      <PanelCard
        title="Knowledge Bases"
        description="Dokumen dan ingestion tetap dikelola di masing-masing Knowledge Base."
      >
        <div className="flex flex-col gap-3">
          {project.knowledgeBases.map((kb) => (
            <div
              key={kb.id}
              className="flex items-center justify-between rounded-lg border border-gray-200 p-3"
            >
              <div className="flex items-center gap-3">
                <Database className="h-4 w-4 text-gray-400" />
                <div>
                  <p className="text-sm font-medium text-gray-800">{kb.name}</p>
                  <p className="text-xs text-gray-500">{kb.slug}</p>
                </div>
              </div>
              <Link
                href={`/console/knowledge-bases/${kb.id}/ingestion`}
                className="text-primary-600"
              >
                <ExternalLink className="h-4 w-4" />
              </Link>
            </div>
          ))}
          {!project.knowledgeBases.length ? (
            <p className="text-sm text-gray-500">Belum ada Knowledge Base.</p>
          ) : null}
        </div>
      </PanelCard>
      <PanelCard
        title="Assign Knowledge Base"
        description="Memindahkan KB ke Project ini memengaruhi konfigurasi runtime berikutnya."
      >
        <div className="flex flex-col gap-3 sm:flex-row">
          <select
            className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
            value={selected}
            onChange={(event) => setSelected(event.target.value)}
          >
            <option value="">Select a Knowledge Base...</option>
            {available.map((kb) => (
              <option key={kb.id} value={kb.id}>
                {kb.name}
              </option>
            ))}
          </select>
          <Button
            intent="primary"
            disabled={!selected}
            loading={assign.isPending}
            onClick={() =>
              assign.mutate(selected, { onSuccess: () => setSelected("") })
            }
          >
            Assign
          </Button>
        </div>
        {assign.isError ? (
          <p className="mt-3 text-sm text-danger-600">
            Knowledge Base tidak dapat dipindahkan.
          </p>
        ) : null}
      </PanelCard>
    </div>
  )
}
