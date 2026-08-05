"use client"

import { Button } from "$/components/button"
import { EmptyState } from "$/components/empty-state"
import { Input } from "$/components/input"
import { PanelCard } from "$/components/panel-card"
import {
  useCreateModelProfile,
  useDeleteModelProfile,
  useModelProfiles,
} from "$/hooks/transactions/use-model-profiles"
import { cn } from "$/utils/cn"
import {
  modelProfileCreateSchema,
  modelProfileKinds,
  modelProfileProviders,
} from "@open-grounding/schemas"
import type { ModelProfileResponseProps } from "@open-grounding/types"
import { Cpu, Plus, Trash2 } from "lucide-react"
import { type ChangeEvent, useState } from "react"

const KIND_LABELS: Record<string, string> = {
  DENSE_EMBEDDING: "Dense Embedding",
  SPARSE_EMBEDDING: "Sparse Embedding",
  RERANKER: "Reranker",
  GENERATION: "Generation LLM",
}

const PROVIDER_DEFAULTS: Record<
  string,
  { model: string; dimensions: number | undefined }
> = {
  fastembed: { model: "BAAI/bge-small-en-v1.5", dimensions: 384 },
  openai: { model: "text-embedding-3-small", dimensions: 1536 },
  ollama: { model: "nomic-embed-text", dimensions: 768 },
}

export default function ModelProfilesContent() {
  const { data: profiles, isLoading } = useModelProfiles()
  const createMutation = useCreateModelProfile()
  const deleteMutation = useDeleteModelProfile()

  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({
    name: "",
    profileKind: "DENSE_EMBEDDING" as (typeof modelProfileKinds)[number],
    provider: "fastembed" as (typeof modelProfileProviders)[number],
    model: "BAAI/bge-small-en-v1.5",
    dimensions: 384 as number | undefined,
  })
  const [formError, setFormError] = useState("")
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null)

  const handleProviderChange = (provider: string) => {
    const defaults = PROVIDER_DEFAULTS[provider] ?? {
      model: "",
      dimensions: undefined,
    }
    setForm((f) => ({
      ...f,
      provider: provider as (typeof modelProfileProviders)[number],
      model: defaults.model,
      dimensions: defaults.dimensions,
    }))
    setFormError("")
  }

  const handleCreate = async () => {
    setFormError("")
    const parsed = modelProfileCreateSchema.safeParse({
      ...form,
      modality: "TEXT",
    })
    if (!parsed.success) {
      setFormError(parsed.error.issues[0]?.message ?? "Invalid input.")
      return
    }
    try {
      await createMutation.mutateAsync(parsed.data)
      setShowForm(false)
      setForm({
        name: "",
        profileKind: "DENSE_EMBEDDING",
        provider: "fastembed",
        model: "BAAI/bge-small-en-v1.5",
        dimensions: 384,
      })
    } catch (error) {
      setFormError(
        (error as { message?: string })?.message ?? "Failed to create profile.",
      )
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">
            Model Profiles
          </h1>
          <p className="mt-1 text-sm text-gray-500">
            Configure embedding, sparse encoder, reranker, and generation
            models.
          </p>
        </div>
        <Button
          intent="primary"
          leftIcon={<Plus className="h-4 w-4" />}
          onClick={() => setShowForm((v) => !v)}
        >
          Add Profile
        </Button>
      </div>

      {showForm ? (
        <PanelCard title="New Model Profile">
          <div className="flex flex-col gap-4">
            <Input
              label="Name"
              name="name"
              placeholder="e.g. OpenAI Ada 002"
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
                  htmlFor="profile-kind"
                  className="text-sm font-medium text-main-700"
                >
                  Kind <span className="text-danger-500">*</span>
                </label>
                <select
                  id="profile-kind"
                  value={form.profileKind}
                  onChange={(e) =>
                    setForm((f) => ({
                      ...f,
                      profileKind: e.target
                        .value as (typeof modelProfileKinds)[number],
                    }))
                  }
                  className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
                >
                  {modelProfileKinds.map((k) => (
                    <option key={k} value={k}>
                      {KIND_LABELS[k] ?? k}
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex flex-col gap-1.5">
                <label
                  htmlFor="profile-provider"
                  className="text-sm font-medium text-main-700"
                >
                  Provider <span className="text-danger-500">*</span>
                </label>
                <select
                  id="profile-provider"
                  value={form.provider}
                  onChange={(e) => handleProviderChange(e.target.value)}
                  className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
                >
                  {modelProfileProviders.map((p) => (
                    <option key={p} value={p}>
                      {p}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Input
                label="Model"
                name="model"
                placeholder="e.g. BAAI/bge-small-en-v1.5"
                value={form.model}
                onChange={(e: ChangeEvent<HTMLInputElement>) =>
                  setForm((f) => ({ ...f, model: e.target.value }))
                }
                required
              />
              <Input
                label="Dimensions"
                name="dimensions"
                type="number"
                placeholder="e.g. 384"
                value={form.dimensions?.toString() ?? ""}
                onChange={(e: ChangeEvent<HTMLInputElement>) =>
                  setForm((f) => ({
                    ...f,
                    dimensions: e.target.value
                      ? Number(e.target.value)
                      : undefined,
                  }))
                }
                hint="Vector dimensions output by this model"
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
                disabled={!form.name || !form.model}
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
        title="Model Profiles"
        description="Active models available for index profiles."
      >
        {isLoading ? (
          <div className="py-8 text-center text-sm text-gray-400">
            Loading...
          </div>
        ) : !profiles || profiles.length === 0 ? (
          <EmptyState
            icon={Cpu}
            title="No model profiles"
            description="Add a model profile to start configuring your index."
          />
        ) : (
          <ul className="flex flex-col divide-y divide-gray-100">
            {profiles.map((p: ModelProfileResponseProps) => (
              <li key={p.id} className="flex items-center justify-between py-4">
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold text-gray-900">
                    {p.name}
                  </p>
                  <p className="mt-0.5 text-xs text-gray-500">
                    <span
                      className={cn(
                        "rounded px-1.5 py-0.5 text-[10px] font-medium",
                        "bg-primary-50 text-primary-700",
                      )}
                    >
                      {KIND_LABELS[p.profileKind] ?? p.profileKind}
                    </span>
                    {" · "}
                    <span className="font-mono">{p.provider}</span>
                    {" / "}
                    <span className="font-mono">{p.model}</span>
                    {p.dimensions ? ` · ${p.dimensions}d` : ""}
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-2 pl-4">
                  {confirmDeleteId === p.id ? (
                    <div className="flex gap-1">
                      <Button
                        intent="danger"
                        size="small"
                        onClick={() =>
                          deleteMutation.mutate(p.id, {
                            onSuccess: () => setConfirmDeleteId(null),
                          })
                        }
                        loading={deleteMutation.isPending}
                      >
                        Delete
                      </Button>
                      <Button
                        intent="secondary"
                        size="small"
                        onClick={() => setConfirmDeleteId(null)}
                      >
                        Cancel
                      </Button>
                    </div>
                  ) : (
                    <Button
                      intent="secondary"
                      size="small"
                      bordered
                      leftIcon={<Trash2 className="h-3.5 w-3.5" />}
                      onClick={() => setConfirmDeleteId(p.id)}
                    >
                      Delete
                    </Button>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </PanelCard>
    </div>
  )
}
