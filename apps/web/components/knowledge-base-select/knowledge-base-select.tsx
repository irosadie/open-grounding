"use client"

import { useKnowledgeBases } from "$/hooks/transactions/use-knowledge-bases"
import type { KnowledgeBaseResponseProps } from "@open-grounding/types"

type KnowledgeBaseSelectProps = {
  value: KnowledgeBaseResponseProps | null
  onChange: (kb: KnowledgeBaseResponseProps | null) => void
  disabled?: boolean
  required?: boolean
  label?: string
  hint?: string
  error?: string
}

export function KnowledgeBaseSelect({
  value,
  onChange,
  disabled = false,
  required = false,
  label = "Knowledge Base",
  hint,
  error,
}: KnowledgeBaseSelectProps) {
  const { data, isLoading } = useKnowledgeBases()
  const kbs = data ?? []

  return (
    <div className="flex flex-col gap-1.5">
      {label ? (
        <label
          htmlFor="kb-select"
          className="text-sm font-medium text-main-700"
        >
          {label}
          {required ? <span className="text-danger-500"> *</span> : null}
        </label>
      ) : null}
      <select
        id="kb-select"
        value={value?.id ?? ""}
        onChange={(e) => {
          const selected = kbs.find((kb) => kb.id === e.target.value) ?? null
          onChange(selected)
        }}
        disabled={disabled || isLoading}
        className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 disabled:cursor-not-allowed disabled:bg-gray-50 disabled:text-gray-400"
      >
        <option value="">
          {isLoading
            ? "Loading..."
            : kbs.length === 0
              ? "No knowledge bases — create one first"
              : "Select a knowledge base"}
        </option>
        {kbs.map((kb) => (
          <option key={kb.id} value={kb.id}>
            {kb.name} ({kb.slug})
          </option>
        ))}
      </select>
      {hint && !error ? <p className="text-xs text-gray-400">{hint}</p> : null}
      {error ? <p className="text-xs text-danger-500">{error}</p> : null}
    </div>
  )
}

export default KnowledgeBaseSelect
