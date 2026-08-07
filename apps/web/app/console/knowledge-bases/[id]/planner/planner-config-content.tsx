"use client"

import { Button } from "$/components/button"
import { EmptyState } from "$/components/empty-state"
import { PanelCard } from "$/components/panel-card"
import { useModelProfiles } from "$/hooks/transactions/use-model-profiles"
import {
  useDeletePlannerConfig,
  usePlannerConfig,
  usePlannerDefaults,
  useUpsertPlannerConfig,
} from "$/hooks/transactions/use-planner-config"
import { plannerConfigSchema, plannerTaskTypes } from "@open-grounding/schemas"
import type { ModelProfileListResponse } from "@open-grounding/types"
import { Brain, Save, Trash2 } from "lucide-react"
import { useEffect, useId, useState } from "react"

type Props = { knowledgeBaseId: string }

const HINT =
  "Variables: {{ query }}, {{ max_tasks }}, {{ available_tools }}, {{ knowledge_base_name }}"

export default function PlannerConfigContent({ knowledgeBaseId }: Props) {
  const { data: config, isLoading } = usePlannerConfig(knowledgeBaseId)
  const { data: defaults } = usePlannerDefaults(knowledgeBaseId)
  const { data: modelProfiles } = useModelProfiles()
  const saveMutation = useUpsertPlannerConfig(knowledgeBaseId)
  const deleteMutation = useDeletePlannerConfig(knowledgeBaseId)
  const modelId = useId()
  const systemId = useId()
  const userId = useId()
  const [enabled, setEnabled] = useState(true)
  const [modelProfileId, setModelProfileId] = useState("")
  const [systemPrompt, setSystemPrompt] = useState("")
  const [userPromptTemplate, setUserPromptTemplate] = useState("")
  const [maxTasks, setMaxTasks] = useState(4)
  const [timeout, setTimeoutSeconds] = useState(15)
  const [taskTypes, setTaskTypes] = useState<string[]>([...plannerTaskTypes])
  const [mcpEnabled, setMcpEnabled] = useState(false)
  const [error, setError] = useState("")
  const [saved, setSaved] = useState(false)
  const profiles =
    (modelProfiles as ModelProfileListResponse | undefined)?.filter(
      (p) => p.profileKind === "GENERATION",
    ) ?? []

  useEffect(() => {
    const source = config ?? defaults
    if (!source) return
    setSystemPrompt(source.systemPrompt)
    setUserPromptTemplate(source.userPromptTemplate)
    setMaxTasks(source.maxTasks)
    setTimeoutSeconds(source.taskTimeoutSeconds)
    setTaskTypes(source.taskTypes)
    setMcpEnabled(source.mcpEnabled)
    if (config) {
      setEnabled(config.enabled)
      setModelProfileId(config.modelProfileId)
    }
  }, [config, defaults])

  const toggleType = (type: string) => {
    setTaskTypes((current) =>
      current.includes(type)
        ? current.filter((item) => item !== type)
        : [...current, type],
    )
  }

  const save = async () => {
    setError("")
    const parsed = plannerConfigSchema.safeParse({
      enabled,
      modelProfileId,
      systemPrompt,
      userPromptTemplate,
      maxTasks,
      taskTimeoutSeconds: timeout,
      taskTypes,
      mcpEnabled,
      guardrails: {},
    })
    if (!parsed.success) {
      setError(parsed.error.issues[0]?.message ?? "Invalid input")
      return
    }
    try {
      await saveMutation.mutateAsync(parsed.data)
      setSaved(true)
      window.setTimeout(() => setSaved(false), 3000)
    } catch {
      setError("Failed to save planner configuration")
    }
  }

  if (isLoading) return <p className="p-6 text-sm text-gray-400">Loading...</p>
  const busy = saveMutation.isPending || deleteMutation.isPending

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold text-gray-900">Query Planner</h1>
        <p className="mt-1 text-sm text-gray-500">
          Route complex questions into parallel RAG, MCP, and general tasks.
        </p>
      </div>
      <PanelCard
        title="Planner Configuration"
        description="Planner settings for this knowledge base."
      >
        <div className="flex flex-col gap-5">
          <label className="flex items-center justify-between text-sm font-medium text-gray-700">
            Enable planner
            <input
              type="checkbox"
              checked={enabled}
              onChange={(event) => setEnabled(event.target.checked)}
              disabled={busy}
            />
          </label>
          <div className="flex flex-col gap-1.5">
            <label
              htmlFor={modelId}
              className="text-sm font-medium text-gray-700"
            >
              Generation model
            </label>
            <select
              id={modelId}
              value={modelProfileId}
              onChange={(event) => setModelProfileId(event.target.value)}
              disabled={busy}
              className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
            >
              <option value="">Select a generation model...</option>
              {profiles.map((profile) => (
                <option key={profile.id} value={profile.id}>
                  {profile.name} ({profile.provider} / {profile.model})
                </option>
              ))}
            </select>
          </div>
          <div className="flex flex-col gap-1.5">
            <label
              htmlFor={systemId}
              className="text-sm font-medium text-gray-700"
            >
              System prompt
            </label>
            <p className="text-xs text-gray-400">{HINT}</p>
            <textarea
              id={systemId}
              rows={4}
              value={systemPrompt}
              onChange={(event) => setSystemPrompt(event.target.value)}
              disabled={busy}
              className="rounded-lg border border-gray-300 px-3 py-2 font-mono text-sm"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <label
              htmlFor={userId}
              className="text-sm font-medium text-gray-700"
            >
              User prompt template
            </label>
            <textarea
              id={userId}
              rows={4}
              value={userPromptTemplate}
              onChange={(event) => setUserPromptTemplate(event.target.value)}
              disabled={busy}
              className="rounded-lg border border-gray-300 px-3 py-2 font-mono text-sm"
            />
          </div>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <label className="flex flex-col gap-1.5 text-sm font-medium text-gray-700">
              Max tasks
              <input
                type="number"
                min={1}
                max={8}
                value={maxTasks}
                onChange={(event) => setMaxTasks(Number(event.target.value))}
                disabled={busy}
                className="rounded-lg border border-gray-300 px-3 py-2"
              />
            </label>
            <label className="flex flex-col gap-1.5 text-sm font-medium text-gray-700">
              Task timeout (seconds)
              <input
                type="number"
                min={1}
                max={60}
                value={timeout}
                onChange={(event) =>
                  setTimeoutSeconds(Number(event.target.value))
                }
                disabled={busy}
                className="rounded-lg border border-gray-300 px-3 py-2"
              />
            </label>
          </div>
          <div>
            <p className="mb-2 text-sm font-medium text-gray-700">
              Allowed task types
            </p>
            <div className="flex flex-wrap gap-3">
              {plannerTaskTypes.map((type) => (
                <label
                  key={type}
                  className="flex items-center gap-2 text-sm text-gray-600"
                >
                  <input
                    type="checkbox"
                    checked={taskTypes.includes(type)}
                    onChange={() => toggleType(type)}
                    disabled={busy}
                  />
                  {type}
                </label>
              ))}
            </div>
          </div>
          <label className="flex items-center gap-2 text-sm text-gray-700">
            <input
              type="checkbox"
              checked={mcpEnabled}
              onChange={(event) => setMcpEnabled(event.target.checked)}
              disabled={busy}
            />
            Enable MCP task dispatch
          </label>
          {error ? <p className="text-sm text-red-500">{error}</p> : null}
          {saved ? (
            <p className="text-sm text-green-600">Saved successfully.</p>
          ) : null}
          <div className="flex gap-3">
            <Button
              intent="primary"
              onClick={() => void save()}
              loading={saveMutation.isPending}
              disabled={busy || !modelProfileId}
              leftIcon={<Save className="h-4 w-4" />}
            >
              Save Planner
            </Button>
            {config ? (
              <Button
                intent="danger"
                onClick={() => void deleteMutation.mutateAsync()}
                loading={deleteMutation.isPending}
                disabled={busy}
                leftIcon={<Trash2 className="h-4 w-4" />}
              >
                Remove Config
              </Button>
            ) : null}
          </div>
        </div>
      </PanelCard>
      {!config ? (
        <EmptyState
          icon={Brain}
          title="No planner config"
          description="Save the configuration above to enable typed query planning."
        />
      ) : null}
    </div>
  )
}
