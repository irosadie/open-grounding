"use client"

import { Button } from "$/components/button"
import { PanelCard } from "$/components/panel-card"
import { useKnowledgeBases } from "$/hooks/transactions/use-knowledge-bases"
import {
  useClearMemory,
  useDeleteMemoryChunk,
  useMemoryChunks,
} from "$/hooks/transactions/use-memory"
import type {
  KnowledgeBaseListResponse,
  MemoryChunkResponse,
} from "@open-grounding/types"
import { Brain, Trash2 } from "lucide-react"
import { useState } from "react"

export default function MemoryContent() {
  const { data: kbs } = useKnowledgeBases()
  const knowledgeBases = (kbs as KnowledgeBaseListResponse | undefined) ?? []
  const [selectedKbId, setSelectedKbId] = useState<string | null>(
    knowledgeBases[0]?.id ?? null,
  )

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold text-gray-900">My Memory</h1>
        <p className="mt-1 text-sm text-gray-500">
          View and manage your persistent conversation memory across knowledge
          bases. Memory is only stored when enabled by the knowledge base
          administrator.
        </p>
      </div>

      {knowledgeBases.length > 0 && (
        <div className="flex items-center gap-3">
          <label
            className="text-sm font-medium text-gray-700"
            htmlFor="kb-select"
          >
            Knowledge Base
          </label>
          <select
            id="kb-select"
            value={selectedKbId ?? ""}
            onChange={(e) => setSelectedKbId(e.target.value || null)}
            className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
          >
            <option value="">Select a knowledge base...</option>
            {knowledgeBases.map((kb) => (
              <option key={kb.id} value={kb.id}>
                {kb.name}
              </option>
            ))}
          </select>
        </div>
      )}

      {selectedKbId ? (
        <MemoryChunkList knowledgeBaseId={selectedKbId} />
      ) : (
        <div className="flex flex-col items-center gap-3 py-16 text-gray-400">
          <Brain className="h-10 w-10" />
          <p className="text-sm">
            Select a knowledge base to view your memory.
          </p>
        </div>
      )}
    </div>
  )
}

function MemoryChunkList({ knowledgeBaseId }: { knowledgeBaseId: string }) {
  const [page, setPage] = useState(1)
  const pageSize = 20
  const { data, isLoading } = useMemoryChunks(knowledgeBaseId, page, pageSize)
  const deleteChunk = useDeleteMemoryChunk(knowledgeBaseId)
  const clearMemory = useClearMemory(knowledgeBaseId)
  const [error, setError] = useState("")

  const chunks = data?.items ?? []
  const total = data?.total ?? 0
  const totalPages = Math.ceil(total / pageSize)

  const handleDelete = async (chunkId: string) => {
    if (!confirm("Delete this memory chunk?")) return
    try {
      await deleteChunk.mutateAsync(chunkId)
    } catch {
      setError("Failed to delete chunk.")
    }
  }

  const handleClear = async () => {
    if (
      !confirm(
        "Clear all memory for this knowledge base? This cannot be undone.",
      )
    )
      return
    try {
      await clearMemory.mutateAsync()
      setPage(1)
    } catch {
      setError("Failed to clear memory.")
    }
  }

  if (isLoading) {
    return <p className="text-sm text-gray-400">Loading memory...</p>
  }

  if (chunks.length === 0) {
    return (
      <div className="flex flex-col items-center gap-3 py-16 text-gray-400">
        <Brain className="h-10 w-10" />
        <p className="text-sm">
          No memory chunks found for this knowledge base.
        </p>
        <p className="text-xs">
          Memory is created after completed conversations when memory is
          enabled.
        </p>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-gray-500">
          {total} memory chunk{total !== 1 ? "s" : ""}
        </p>
        <Button
          intent="danger"
          onClick={handleClear}
          loading={clearMemory.isPending}
          leftIcon={<Trash2 className="h-4 w-4" />}
        >
          Clear All
        </Button>
      </div>

      {error && <p className="text-sm text-red-500">{error}</p>}

      <div className="flex flex-col gap-3">
        {chunks.map((chunk: MemoryChunkResponse) => (
          <MemoryChunkCard
            key={chunk.id}
            chunk={chunk}
            onDelete={() => handleDelete(chunk.id)}
            isDeleting={deleteChunk.isPending}
          />
        ))}
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-3 pt-2">
          <Button
            intent="secondary"
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
          >
            Previous
          </Button>
          <span className="text-sm text-gray-500">
            Page {page} of {totalPages}
          </span>
          <Button
            intent="secondary"
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
          >
            Next
          </Button>
        </div>
      )}
    </div>
  )
}

function MemoryChunkCard({
  chunk,
  onDelete,
  isDeleting,
}: {
  chunk: MemoryChunkResponse
  onDelete: () => void
  isDeleting: boolean
}) {
  const createdAt = new Date(chunk.createdAt).toLocaleDateString()
  const expiresAt = new Date(chunk.expiresAt).toLocaleDateString()

  return (
    <PanelCard title="" description="">
      <div className="flex flex-col gap-2">
        <div className="flex items-start justify-between gap-4">
          <p className="flex-1 text-sm leading-relaxed text-gray-700">
            {chunk.summary}
          </p>
          <button
            type="button"
            onClick={onDelete}
            disabled={isDeleting}
            aria-label="Delete memory chunk"
            className="shrink-0 rounded-md p-1.5 text-gray-400 hover:bg-red-50 hover:text-red-500 disabled:cursor-not-allowed"
          >
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
        <div className="flex items-center gap-4 text-xs text-gray-400">
          <span>
            {chunk.turnCount} turn{chunk.turnCount !== 1 ? "s" : ""}
          </span>
          <span>Created {createdAt}</span>
          <span>Expires {expiresAt}</span>
        </div>
      </div>
    </PanelCard>
  )
}
