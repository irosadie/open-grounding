"use client"

import { Button } from "$/components/button"
import { EmptyState } from "$/components/empty-state"
import { PanelCard } from "$/components/panel-card"
import {
  useDecompositionConfig,
  useDecompositionDefaults,
  useDeleteDecompositionConfig,
  useUpsertDecompositionConfig,
} from "$/hooks/transactions/use-decomposition-config"
import { useModelProfiles } from "$/hooks/transactions/use-model-profiles"
import { decompositionConfigSchema } from "@open-grounding/schemas"
import type { ModelProfileListResponse } from "@open-grounding/types"
import { Brain, Save, Trash2 } from "lucide-react"
import { useEffect, useId, useState } from "react"

const JINJA_VARS_HINT =
  "Available variables: {{ query }}, {{ knowledge_base_name }}, {{ max_sub_queries }}"

type Props = {
  knowledgeBaseId: string
}

export default function DecompositionConfigContent({ knowledgeBaseId }: Props) {
  const { data: config, isLoading } = useDecompositionConfig(knowledgeBaseId)
  const { data: defaults } = useDecompositionDefaults(knowledgeBaseId)
  const { data: modelProfiles } = useModelProfiles()
  const upsertMutation = useUpsertDecompositionConfig(knowledgeBaseId)
  const deleteMutation = useDeleteDecompositionConfig(knowledgeBaseId)
  const systemPromptId = useId()
  const userPromptId = useId()
  const maxSubQueriesId = useId()
  const maxDepthId = useId()
  const minComplexityId = useId()
  const modelSelectId = useId()

  const generationProfiles =
    (modelProfiles as ModelProfileListResponse | undefined)?.filter(
      (p) => p.profileKind === "GENERATION",
    ) ?? []

  const [enabled, setEnabled] = useState(true)
  const [modelProfileId, setModelProfileId] = useState("")
  const [systemPrompt, setSystemPrompt] = useState("")
  const [userPromptTemplate, setUserPromptTemplate] = useState("")
  const [maxSubQueries, setMaxSubQueries] = useState(3)
  const [maxDepth, setMaxDepth] = useState(2)
  const [minComplexityScore, setMinComplexityScore] = useState(0.6)
  const [formError, setFormError] = useState("")
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    if (config) {
      setEnabled(config.enabled)
      setModelProfileId(config.modelProfileId)
      setSystemPrompt(config.systemPrompt)
      setUserPromptTemplate(config.userPromptTemplate)
      setMaxSubQueries(config.maxSubQueries)
      setMaxDepth(config.maxDepth)
      setMinComplexityScore(config.minComplexityScore)
    } else if (defaults && !config) {
      setSystemPrompt(defaults.systemPrompt)
      setUserPromptTemplate(defaults.userPromptTemplate)
      setMaxSubQueries(defaults.maxSubQueries)
      setMaxDepth(defaults.maxDepth)
      setMinComplexityScore(defaults.minComplexityScore)
    }
  }, [config, defaults])

  const handleSave = async () => {
    setFormError("")
    const parsed = decompositionConfigSchema.safeParse({
      enabled,
      modelProfileId,
      systemPrompt,
      userPromptTemplate,
      maxSubQueries,
      maxDepth,
      minComplexityScore,
      guardrails: {},
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
    if (!confirm("Remove decomposition config? This cannot be undone.")) return
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
          Query Decomposition
        </h1>
        <p className="mt-1 text-sm text-gray-500">
          Configure hybrid query decomposition for this knowledge base. Complex
          queries will be broken into sub-queries for better retrieval recall.
        </p>
      </div>

      <PanelCard
        title="Configuration"
        description="Decomposition settings for this knowledge base."
      >
        <div className="flex flex-col gap-5">
          {/* Enable toggle */}
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-700">
                Enable decomposition
              </p>
              <p className="text-xs text-gray-400">
                When enabled, complex queries will trigger the LLM decomposer.
              </p>
            </div>
            <button
              type="button"
              onClick={() => setEnabled(!enabled)}
              disabled={isBusy}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${enabled ? "bg-primary-500" : "bg-gray-200"}`}
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${enabled ? "translate-x-6" : "translate-x-1"}`}
              />
            </button>
          </div>

          {/* Model profile selector */}
          <div className="flex flex-col gap-1.5">
            <label
              htmlFor={modelSelectId}
              className="text-sm font-medium text-gray-700"
            >
              LLM Model Profile <span className="text-red-500">*</span>
            </label>
            <select
              id={modelSelectId}
              value={modelProfileId}
              onChange={(e) => setModelProfileId(e.target.value)}
              disabled={isBusy}
              className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 disabled:cursor-not-allowed disabled:bg-gray-50"
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

          {/* System prompt */}
          <div className="flex flex-col gap-1.5">
            <label
              htmlFor={systemPromptId}
              className="text-sm font-medium text-gray-700"
            >
              System Prompt
            </label>
            <p className="text-xs text-gray-400">{JINJA_VARS_HINT}</p>
            <textarea
              id={systemPromptId}
              value={systemPrompt}
              onChange={(e) => setSystemPrompt(e.target.value)}
              disabled={isBusy}
              rows={5}
              className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm font-mono text-gray-900 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 disabled:bg-gray-50"
            />
          </div>

          {/* User prompt template */}
          <div className="flex flex-col gap-1.5">
            <label
              htmlFor={userPromptId}
              className="text-sm font-medium text-gray-700"
            >
              User Prompt Template
            </label>
            <p className="text-xs text-gray-400">{JINJA_VARS_HINT}</p>
            <textarea
              id={userPromptId}
              value={userPromptTemplate}
              onChange={(e) => setUserPromptTemplate(e.target.value)}
              disabled={isBusy}
              rows={4}
              className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm font-mono text-gray-900 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 disabled:bg-gray-50"
            />
          </div>

          {/* Numeric settings */}
          <div className="grid grid-cols-3 gap-4">
            <div className="flex flex-col gap-1.5">
              <label
                htmlFor={maxSubQueriesId}
                className="text-sm font-medium text-gray-700"
              >
                Max Sub-queries
              </label>
              <p className="text-xs text-gray-400">1–5</p>
              <input
                id={maxSubQueriesId}
                type="number"
                min={1}
                max={5}
                value={maxSubQueries}
                onChange={(e) => setMaxSubQueries(Number(e.target.value))}
                disabled={isBusy}
                className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 disabled:bg-gray-50"
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <label
                htmlFor={maxDepthId}
                className="text-sm font-medium text-gray-700"
              >
                Max Depth
              </label>
              <p className="text-xs text-gray-400">1–3</p>
              <input
                id={maxDepthId}
                type="number"
                min={1}
                max={3}
                value={maxDepth}
                onChange={(e) => setMaxDepth(Number(e.target.value))}
                disabled={isBusy}
                className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 disabled:bg-gray-50"
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <label
                htmlFor={minComplexityId}
                className="text-sm font-medium text-gray-700"
              >
                Min Complexity Score
              </label>
              <p className="text-xs text-gray-400">0.0–1.0</p>
              <input
                id={minComplexityId}
                type="number"
                min={0}
                max={1}
                step={0.05}
                value={minComplexityScore}
                onChange={(e) => setMinComplexityScore(Number(e.target.value))}
                disabled={isBusy}
                className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 disabled:bg-gray-50"
              />
            </div>
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
              disabled={isBusy || !modelProfileId}
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

      {!config && !isLoading && (
        <EmptyState
          icon={Brain}
          title="No decomposition config"
          description="Fill the form above to enable query decomposition for this knowledge base."
        />
      )}
    </div>
  )
}
