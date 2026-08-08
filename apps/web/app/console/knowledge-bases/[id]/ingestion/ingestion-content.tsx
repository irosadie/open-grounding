"use client"

import { Button } from "$/components/button"
import { PanelCard } from "$/components/panel-card"
import {
  useIngestionConfig,
  useUpsertIngestionConfig,
} from "$/hooks/transactions/use-ingestion-config"
import { ingestionConfigSchema } from "@open-grounding/schemas"
import type { IngestionConfigInput } from "@open-grounding/schemas"
import { AlertTriangle, Save } from "lucide-react"
import { useEffect, useState } from "react"

type Props = { knowledgeBaseId: string }

const DEFAULT_VALUES: IngestionConfigInput = {
  minTextCoverage: 0.3,
  maxInvalidCharRatio: 0.1,
  minAggregateConfidence: 0.5,
  minPageCoverage: 0.5,
  autoReview: false,
}

type ThresholdFieldProps = {
  id: string
  label: string
  description: string
  value: number
  onChange: (v: number) => void
}

function ThresholdField({
  id,
  label,
  description,
  value,
  onChange,
}: ThresholdFieldProps) {
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-sm font-medium text-gray-700">
        {label}
      </label>
      <p className="text-xs text-gray-500">{description}</p>
      <div className="flex items-center gap-3">
        <input
          id={id}
          type="range"
          min={0}
          max={1}
          step={0.01}
          value={value}
          onChange={(e) => onChange(Number(e.target.value))}
          className="h-2 w-full cursor-pointer accent-primary-600"
        />
        <span className="w-12 shrink-0 text-right text-sm font-mono text-gray-700">
          {value.toFixed(2)}
        </span>
      </div>
    </div>
  )
}

export default function IngestionContent({ knowledgeBaseId }: Props) {
  const { data: config, isLoading } = useIngestionConfig(knowledgeBaseId)
  const saveMutation = useUpsertIngestionConfig(knowledgeBaseId)

  const [form, setForm] = useState<IngestionConfigInput>(DEFAULT_VALUES)
  const [formError, setFormError] = useState("")
  const [saveSuccess, setSaveSuccess] = useState(false)

  useEffect(() => {
    if (config) {
      setForm({
        minTextCoverage: config.minTextCoverage,
        maxInvalidCharRatio: config.maxInvalidCharRatio,
        minAggregateConfidence: config.minAggregateConfidence,
        minPageCoverage: config.minPageCoverage,
        autoReview: config.autoReview,
      })
    }
  }, [config])

  const handleSave = async () => {
    setFormError("")
    setSaveSuccess(false)
    const parsed = ingestionConfigSchema.safeParse(form)
    if (!parsed.success) {
      setFormError(parsed.error.issues[0]?.message ?? "Invalid input.")
      return
    }
    try {
      await saveMutation.mutateAsync(parsed.data)
      setSaveSuccess(true)
      setTimeout(() => setSaveSuccess(false), 3000)
    } catch {
      setFormError("Failed to save configuration.")
    }
  }

  const setField = <K extends keyof IngestionConfigInput>(
    key: K,
    value: IngestionConfigInput[K],
  ) => {
    setForm((prev) => ({ ...prev, [key]: value }))
    setSaveSuccess(false)
  }

  if (isLoading) {
    return (
      <div className="py-8 text-center text-sm text-gray-400">Loading...</div>
    )
  }

  return (
    <div className="flex flex-col gap-6">
      {/* Auto Review Toggle */}
      <PanelCard
        title="Human Review"
        description="When enabled, all documents pause after parsing and require human approval before indexing continues — regardless of quality gate results."
      >
        <div className="flex flex-col gap-4">
          <label className="flex cursor-pointer items-center gap-3">
            <div className="relative">
              <input
                type="checkbox"
                className="sr-only"
                checked={form.autoReview}
                onChange={(e) => setField("autoReview", e.target.checked)}
              />
              <div
                className={`h-6 w-11 rounded-full transition-colors ${form.autoReview ? "bg-primary-600" : "bg-gray-300"}`}
              />
              <div
                className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform ${form.autoReview ? "translate-x-5" : "translate-x-0.5"}`}
              />
            </div>
            <span className="text-sm font-medium text-gray-700">
              {form.autoReview
                ? "Enabled — documents wait for approval before indexing"
                : "Disabled — quality gate decides automatically"}
            </span>
          </label>

          {form.autoReview ? (
            <div className="flex items-start gap-2 rounded-lg border border-warning-200 bg-warning-50 px-4 py-3">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warning-600" />
              <p className="text-sm text-warning-700">
                Human review is required. Every document will pause after
                parsing and wait for your approval before indexing continues.
                This may increase review workload on high-volume knowledge
                bases.
              </p>
            </div>
          ) : null}
        </div>
      </PanelCard>

      {/* Quality Gate Thresholds */}
      <PanelCard
        title="Quality Gate Thresholds"
        description="Documents that fail these thresholds are routed to human review instead of continuing automatically."
      >
        <div className="flex flex-col gap-6">
          <ThresholdField
            id="minTextCoverage"
            label="Min Text Coverage"
            description="Minimum ratio of elements with non-empty text. Documents below this threshold are flagged for review."
            value={form.minTextCoverage}
            onChange={(v) => setField("minTextCoverage", v)}
          />
          <ThresholdField
            id="maxInvalidCharRatio"
            label="Max Invalid Char Ratio"
            description="Maximum allowed ratio of invalid/control characters. High ratios indicate OCR corruption."
            value={form.maxInvalidCharRatio}
            onChange={(v) => setField("maxInvalidCharRatio", v)}
          />
          <ThresholdField
            id="minAggregateConfidence"
            label="Min Aggregate Confidence"
            description="Minimum average extraction confidence reported by the parser. Lower values indicate uncertain OCR output."
            value={form.minAggregateConfidence}
            onChange={(v) => setField("minAggregateConfidence", v)}
          />
          <ThresholdField
            id="minPageCoverage"
            label="Min Page Coverage (PDF only)"
            description="Minimum ratio of PDF pages that must contain extracted elements."
            value={form.minPageCoverage}
            onChange={(v) => setField("minPageCoverage", v)}
          />
        </div>
      </PanelCard>

      {/* Actions */}
      <div className="flex items-center gap-3">
        <Button
          intent="primary"
          leftIcon={<Save className="h-4 w-4" />}
          onClick={handleSave}
          loading={saveMutation.isPending}
          disabled={saveMutation.isPending}
        >
          Save Configuration
        </Button>
        {saveSuccess ? (
          <span className="text-sm text-success-600">Configuration saved.</span>
        ) : null}
        {formError ? (
          <span className="text-sm text-danger-600">{formError}</span>
        ) : null}
      </div>
    </div>
  )
}
