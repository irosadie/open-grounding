"use client"

import { Button } from "$/components/button"
import { PanelCard } from "$/components/panel-card"
import {
  useDeleteMemoryConfig,
  useMemoryConfig,
  useMemoryConfigDefaults,
  useUpsertMemoryConfig,
} from "$/hooks/transactions/use-memory-config"
import { useModelProfiles } from "$/hooks/transactions/use-model-profiles"
import { memoryConfigSchema } from "@open-grounding/schemas"
import type { ModelProfileListResponse } from "@open-grounding/types"
import { Save, Trash2 } from "lucide-react"
import { useEffect, useId, useState } from "react"

const JINJA_VARS_HINT =
  "Available variables: {{ conversation_messages }}, {{ knowledge_base_name }}, {{ turn_count }}"

type Props = {
  knowledgeBaseId: string
}

export default function MemoryConfigContent({ knowledgeBaseId }: Props) {
  const { data: config, isLoading } = useMemoryConfig(knowledgeBaseId)
  const { data: defaults } = useMemoryConfigDefaults(knowledgeBaseId)
  const { data: modelProfiles } = useModelProfiles()
  const upsertMutation = useUpsertMemoryConfig(knowledgeBaseId)
  const deleteMutation = useDeleteMemoryConfig(knowledgeBaseId)

  const enabledId = useId()
  const summModelId = useId()
  const embModelId = useId()
  const retentionId = useId()
  const topKId = useId()
  const minTurnsId = useId()
  const systemPromptId = useId()

  const profiles = (modelProfiles as ModelProfileListResponse | undefined) ?? []
  const generationProfiles = profiles.filter(
    (p) => p.profileKind === "GENERATION",
  )
  const embeddingProfiles = profiles.filter(
    (p) => p.profileKind === "DENSE_EMBEDDING" || p.profileKind === "EMBEDDING",
  )

  const [enabled, setEnabled] = useState(false)
  const [summarizationModelProfileId, setSummarizationModelProfileId] =
    useState("")
  const [embeddingProfileId, setEmbeddingProfileId] = useState("")
  const [retentionDays, setRetentionDays] = useState(90)
  const [retrievalTopK, setRetrievalTopK] = useState(5)
  const [minTurnsToSummarize, setMinTurnsToSummarize] = useState(3)
  const [systemPrompt, setSystemPrompt] = useState("")
  const [formError, setFormError] = useState("")
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    if (config) {
      setEnabled(config.enabled)
      setSummarizationModelProfileId(config.summarizationModelProfileId)
      setEmbeddingProfileId(config.embeddingProfileId)
      setRetentionDays(config.retentionDays)
      setRetrievalTopK(config.retrievalTopK)
      setMinTurnsToSummarize(config.minTurnsToSummarize)
      setSystemPrompt(config.systemPrompt)
    } else if (defaults && !config) {
      setEnabled(defaults.enabled)
      setRetentionDays(defaults.retentionDays)
      setRetrievalTopK(defaults.retrievalTopK)
      setMinTurnsToSummarize(defaults.minTurnsToSummarize)
      setSystemPrompt(defaults.systemPrompt)
    }
  }, [config, defaults])

  const handleSave = async () => {
    setFormError("")
    const parsed = memoryConfigSchema.safeParse({
      enabled,
      summarizationModelProfileId,
      embeddingProfileId,
      retentionDays,
      retrievalTopK,
      minTurnsToSummarize,
      systemPrompt,
    })
    if (!parsed.success) {
      setFormError(parsed.error.issues[0]?.message ?? "Invalid input.")
      return
    }
    try {
      await upsertMutation.mutateAsync(parsed.data)
      setSaved(true)
      setTimeout(() => setSaved(false), 3000)
    } catch (e) {
      setFormError((e as { message?: string })?.message ?? "Failed to save.")
    }
  }

  const handleDelete = async () => {
    if (
      !confirm(
        "Remove memory config? This will delete all memory chunks for this KB.",
      )
    )
      return
    try {
      await deleteMutation.mutateAsync()
    } catch (e) {
      setFormError((e as { message?: string })?.message ?? "Failed to delete.")
    }
  }

  const isBusy = upsertMutation.isPending || deleteMutation.isPending

  if (isLoading) {
    return <p className="text-sm text-gray-400 p-6">Loading...</p>
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold text-gray-900">
          Conversation Memory
        </h1>
        <p className="mt-1 text-sm text-gray-500">
          Enable persistent memory for this knowledge base. Completed
          conversations are summarized and retrieved at query time to provide
          context from prior sessions.
        </p>
      </div>

      <PanelCard
        title="Configuration"
        description="Memory settings for this knowledge base."
      >
        <div className="flex flex-col gap-5">
          {/* Enable toggle */}
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-700">Enable memory</p>
              <p className="text-xs text-gray-400">
                When enabled, completed sessions are summarized and used as
                context in future queries.
              </p>
            </div>
            <button
              id={enabledId}
              type="button"
              onClick={() => setEnabled(!enabled)}
              disabled={isBusy}
              aria-pressed={enabled}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${enabled ? "bg-primary-500" : "bg-gray-200"}`}
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${enabled ? "translate-x-6" : "translate-x-1"}`}
              />
            </button>
          </div>

          {/* Summarization model */}
          <div className="flex flex-col gap-1.5">
            <label
              htmlFor={summModelId}
              className="text-sm font-medium text-gray-700"
            >
              Summarization Model <span className="text-red-500">*</span>
            </label>
            <select
              id={summModelId}
              value={summarizationModelProfileId}
              onChange={(e) => setSummarizationModelProfileId(e.target.value)}
              disabled={isBusy}
              className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 disabled:bg-gray-50"
            >
              <option value="">Select a generation model...</option>
              {generationProfiles.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} ({p.provider} / {p.model})
                </option>
              ))}
            </select>
            {generationProfiles.length === 0 && (
              <p className="text-xs text-amber-600">
                No GENERATION model profiles found. Create one in Settings →
                Models first.
              </p>
            )}
          </div>

          {/* Embedding model */}
          <div className="flex flex-col gap-1.5">
            <label
              htmlFor={embModelId}
              className="text-sm font-medium text-gray-700"
            >
              Embedding Model <span className="text-red-500">*</span>
            </label>
            <select
              id={embModelId}
              value={embeddingProfileId}
              onChange={(e) => setEmbeddingProfileId(e.target.value)}
              disabled={isBusy}
              className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 disabled:bg-gray-50"
            >
              <option value="">Select an embedding model...</option>
              {embeddingProfiles.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} ({p.provider} / {p.model})
                </option>
              ))}
            </select>
            {embeddingProfiles.length === 0 && (
              <p className="text-xs text-amber-600">
                No embedding model profiles found. Create one in Settings →
                Models first.
              </p>
            )}
          </div>

          {/* Numeric settings */}
          <div className="grid grid-cols-3 gap-4">
            <div className="flex flex-col gap-1.5">
              <label
                htmlFor={retentionId}
                className="text-sm font-medium text-gray-700"
              >
                Retention Days
              </label>
              <p className="text-xs text-gray-400">1–365</p>
              <input
                id={retentionId}
                type="number"
                min={1}
                max={365}
                value={retentionDays}
                onChange={(e) => setRetentionDays(Number(e.target.value))}
                disabled={isBusy}
                className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 disabled:bg-gray-50"
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <label
                htmlFor={topKId}
                className="text-sm font-medium text-gray-700"
              >
                Retrieval Top-K
              </label>
              <p className="text-xs text-gray-400">1–20</p>
              <input
                id={topKId}
                type="number"
                min={1}
                max={20}
                value={retrievalTopK}
                onChange={(e) => setRetrievalTopK(Number(e.target.value))}
                disabled={isBusy}
                className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 disabled:bg-gray-50"
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <label
                htmlFor={minTurnsId}
                className="text-sm font-medium text-gray-700"
              >
                Min Turns to Summarize
              </label>
              <p className="text-xs text-gray-400">1–20</p>
              <input
                id={minTurnsId}
                type="number"
                min={1}
                max={20}
                value={minTurnsToSummarize}
                onChange={(e) => setMinTurnsToSummarize(Number(e.target.value))}
                disabled={isBusy}
                className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 disabled:bg-gray-50"
              />
            </div>
          </div>

          {/* System prompt */}
          <div className="flex flex-col gap-1.5">
            <label
              htmlFor={systemPromptId}
              className="text-sm font-medium text-gray-700"
            >
              Summarization System Prompt
            </label>
            <p className="text-xs text-gray-400">{JINJA_VARS_HINT}</p>
            <textarea
              id={systemPromptId}
              value={systemPrompt}
              onChange={(e) => setSystemPrompt(e.target.value)}
              disabled={isBusy}
              rows={6}
              className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm font-mono text-gray-900 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 disabled:bg-gray-50"
            />
          </div>

          {formError && <p className="text-sm text-red-500">{formError}</p>}
          {saved && (
            <p className="text-sm text-green-600">Saved successfully.</p>
          )}

          <div className="flex items-center gap-3">
            <Button
              intent="primary"
              onClick={handleSave}
              loading={upsertMutation.isPending}
              disabled={
                isBusy || !summarizationModelProfileId || !embeddingProfileId
              }
              leftIcon={<Save className="h-4 w-4" />}
            >
              Save Configuration
            </Button>
            {config && (
              <Button
                intent="danger"
                onClick={handleDelete}
                loading={deleteMutation.isPending}
                disabled={isBusy}
                leftIcon={<Trash2 className="h-4 w-4" />}
              >
                Remove Config
              </Button>
            )}
          </div>
        </div>
      </PanelCard>
    </div>
  )
}
