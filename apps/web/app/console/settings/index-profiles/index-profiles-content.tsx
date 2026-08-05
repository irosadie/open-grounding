"use client"

import { Button } from "$/components/button"
import { EmptyState } from "$/components/empty-state"
import { Input } from "$/components/input"
import { PanelCard } from "$/components/panel-card"
import {
  useActivateIndexProfile,
  useCreateIndexProfile,
  useIndexProfiles,
} from "$/hooks/transactions/use-index-profiles"
import { useModelProfiles } from "$/hooks/transactions/use-model-profiles"
import { cn } from "$/utils/cn"
import {
  indexProfileChunkingStrategies,
  indexProfileCreateSchema,
  indexProfileDistanceMetrics,
} from "@open-grounding/schemas"
import type { IndexProfileResponseProps } from "@open-grounding/types"
import { LayoutList, Plus, Zap } from "lucide-react"
import { type ChangeEvent, useState } from "react"

export default function IndexProfilesContent() {
  const { data: profiles, isLoading } = useIndexProfiles()
  const { data: modelProfiles } = useModelProfiles()
  const createMutation = useCreateIndexProfile()
  const activateMutation = useActivateIndexProfile()

  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({
    name: "",
    embeddingProfileId: "",
    sparseProfileId: "",
    collection: "rag",
    dimensions: 384,
    distanceMetric: "cosine" as (typeof indexProfileDistanceMetrics)[number],
    chunkingStrategy:
      "RECURSIVE" as (typeof indexProfileChunkingStrategies)[number],
    chunkSizeTokens: 400,
    chunkOverlapTokens: 50,
    parentChunkSize: 1500,
  })
  const [formError, setFormError] = useState("")

  const denseProfiles =
    modelProfiles?.filter((p) => p.profileKind === "DENSE_EMBEDDING") ?? []
  const sparseProfiles =
    modelProfiles?.filter((p) => p.profileKind === "SPARSE_EMBEDDING") ?? []

  const handleCreate = async () => {
    setFormError("")
    const parsed = indexProfileCreateSchema.safeParse({
      ...form,
      sparseProfileId: form.sparseProfileId || undefined,
    })
    if (!parsed.success) {
      setFormError(parsed.error.issues[0]?.message ?? "Invalid input.")
      return
    }
    try {
      await createMutation.mutateAsync(parsed.data)
      setShowForm(false)
    } catch (error) {
      setFormError(
        (error as { message?: string })?.message ??
          "Failed to create index profile.",
      )
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">
            Index Profiles
          </h1>
          <p className="mt-1 text-sm text-gray-500">
            Configure vector index settings. The active profile is used for all
            new ingestion jobs.
          </p>
        </div>
        <Button
          intent="primary"
          leftIcon={<Plus className="h-4 w-4" />}
          onClick={() => setShowForm((v) => !v)}
        >
          New Profile
        </Button>
      </div>

      {showForm ? (
        <PanelCard title="New Index Profile">
          <div className="flex flex-col gap-4">
            <Input
              label="Name"
              name="name"
              placeholder="e.g. Production v1"
              value={form.name}
              onChange={(e: ChangeEvent<HTMLInputElement>) => {
                setForm((f) => ({ ...f, name: e.target.value }))
                setFormError("")
              }}
              required
            />

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="flex flex-col gap-1.5">
                <label
                  htmlFor="idx-embedding"
                  className="text-sm font-medium text-main-700"
                >
                  Embedding Model <span className="text-danger-500">*</span>
                </label>
                <select
                  id="idx-embedding"
                  value={form.embeddingProfileId}
                  onChange={(e) => {
                    const p = denseProfiles.find((p) => p.id === e.target.value)
                    setForm((f) => ({
                      ...f,
                      embeddingProfileId: e.target.value,
                      dimensions: p?.dimensions ?? f.dimensions,
                    }))
                  }}
                  className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
                >
                  <option value="">Select dense embedding model...</option>
                  {denseProfiles.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name} ({p.model})
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex flex-col gap-1.5">
                <label
                  htmlFor="idx-sparse"
                  className="text-sm font-medium text-main-700"
                >
                  Sparse Model (optional)
                </label>
                <select
                  id="idx-sparse"
                  value={form.sparseProfileId}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, sparseProfileId: e.target.value }))
                  }
                  className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
                >
                  <option value="">None</option>
                  {sparseProfiles.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name} ({p.model})
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <Input
                label="Collection"
                name="collection"
                value={form.collection}
                onChange={(e: ChangeEvent<HTMLInputElement>) =>
                  setForm((f) => ({ ...f, collection: e.target.value }))
                }
                required
              />
              <Input
                label="Dimensions"
                name="dimensions"
                type="number"
                value={form.dimensions.toString()}
                onChange={(e: ChangeEvent<HTMLInputElement>) =>
                  setForm((f) => ({ ...f, dimensions: Number(e.target.value) }))
                }
                required
              />
              <div className="flex flex-col gap-1.5">
                <label
                  htmlFor="idx-distance"
                  className="text-sm font-medium text-main-700"
                >
                  Distance Metric
                </label>
                <select
                  id="idx-distance"
                  value={form.distanceMetric}
                  onChange={(e) =>
                    setForm((f) => ({
                      ...f,
                      distanceMetric: e.target
                        .value as (typeof indexProfileDistanceMetrics)[number],
                    }))
                  }
                  className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm"
                >
                  {indexProfileDistanceMetrics.map((m) => (
                    <option key={m} value={m}>
                      {m}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-4">
              <div className="flex flex-col gap-1.5">
                <label
                  htmlFor="idx-chunking"
                  className="text-sm font-medium text-main-700"
                >
                  Chunking Strategy
                </label>
                <select
                  id="idx-chunking"
                  value={form.chunkingStrategy}
                  onChange={(e) =>
                    setForm((f) => ({
                      ...f,
                      chunkingStrategy: e.target
                        .value as (typeof indexProfileChunkingStrategies)[number],
                    }))
                  }
                  className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm"
                >
                  {indexProfileChunkingStrategies.map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </select>
              </div>
              <Input
                label="Chunk Size (tokens)"
                name="chunkSize"
                type="number"
                value={form.chunkSizeTokens.toString()}
                onChange={(e: ChangeEvent<HTMLInputElement>) =>
                  setForm((f) => ({
                    ...f,
                    chunkSizeTokens: Number(e.target.value),
                  }))
                }
              />
              <Input
                label="Overlap (tokens)"
                name="overlap"
                type="number"
                value={form.chunkOverlapTokens.toString()}
                onChange={(e: ChangeEvent<HTMLInputElement>) =>
                  setForm((f) => ({
                    ...f,
                    chunkOverlapTokens: Number(e.target.value),
                  }))
                }
              />
              <Input
                label="Parent Chunk Size"
                name="parentChunk"
                type="number"
                value={form.parentChunkSize.toString()}
                onChange={(e: ChangeEvent<HTMLInputElement>) =>
                  setForm((f) => ({
                    ...f,
                    parentChunkSize: Number(e.target.value),
                  }))
                }
              />
            </div>

            {formError ? (
              <p className="text-sm text-danger-500">{formError}</p>
            ) : null}
            <div className="flex gap-2">
              <Button
                intent="primary"
                onClick={handleCreate}
                loading={createMutation.isPending}
                disabled={!form.name || !form.embeddingProfileId}
              >
                Save
              </Button>
              <Button
                intent="secondary"
                bordered
                onClick={() => {
                  setShowForm(false)
                  setFormError("")
                }}
              >
                Cancel
              </Button>
            </div>
          </div>
        </PanelCard>
      ) : null}

      <PanelCard
        title="Index Profiles"
        description="One active profile is used for all ingestion jobs."
      >
        {isLoading ? (
          <div className="py-8 text-center text-sm text-gray-400">
            Loading...
          </div>
        ) : !profiles || profiles.length === 0 ? (
          <EmptyState
            icon={LayoutList}
            title="No index profiles"
            description="Create an index profile to configure how documents are indexed."
          />
        ) : (
          <ul className="flex flex-col divide-y divide-gray-100">
            {profiles.map((p: IndexProfileResponseProps) => (
              <li key={p.id} className="flex items-center justify-between py-4">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="truncate text-sm font-semibold text-gray-900">
                      {p.name}
                    </p>
                    {p.isActive ? (
                      <span className="rounded-full bg-success-100 px-2 py-0.5 text-[10px] font-medium text-success-700">
                        Active
                      </span>
                    ) : null}
                  </div>
                  <p className="mt-0.5 text-xs text-gray-500">
                    <span className="font-mono">{p.collection}</span>
                    {" · "}
                    {p.dimensions}d{" · "}
                    {p.distanceMetric}
                    {" · "}
                    {p.chunkingStrategy} ({p.chunkSizeTokens}t)
                  </p>
                </div>
                {!p.isActive ? (
                  <Button
                    intent="primary"
                    size="small"
                    leftIcon={<Zap className="h-3.5 w-3.5" />}
                    onClick={() => activateMutation.mutate(p.id)}
                    loading={activateMutation.isPending}
                    className={cn("shrink-0")}
                  >
                    Set Active
                  </Button>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </PanelCard>
    </div>
  )
}
