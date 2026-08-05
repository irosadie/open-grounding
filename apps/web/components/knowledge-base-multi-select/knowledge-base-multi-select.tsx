"use client"

import { useKnowledgeBases } from "$/hooks/transactions/use-knowledge-bases"
import { cn } from "$/utils/cn"
import type { KnowledgeBaseResponseProps } from "@open-grounding/types"
import { X } from "lucide-react"

type KnowledgeBaseMultiSelectProps = {
  value: KnowledgeBaseResponseProps[]
  onChange: (kbs: KnowledgeBaseResponseProps[]) => void
  disabled?: boolean
  required?: boolean
  label?: string
  hint?: string
  error?: string
}

export function KnowledgeBaseMultiSelect({
  value,
  onChange,
  disabled = false,
  required = false,
  label = "Knowledge Bases",
  hint,
  error,
}: KnowledgeBaseMultiSelectProps) {
  const { data, isLoading } = useKnowledgeBases()
  const kbs = data ?? []
  const selectedIds = new Set(value.map((kb) => kb.id))
  const available = kbs.filter((kb) => !selectedIds.has(kb.id))

  const handleAdd = (id: string) => {
    const kb = kbs.find((k) => k.id === id)
    if (kb) onChange([...value, kb])
  }

  const handleRemove = (id: string) => {
    onChange(value.filter((kb) => kb.id !== id))
  }

  return (
    <div className="flex flex-col gap-1.5">
      {label ? (
        <label
          htmlFor="kb-multi-select"
          className="text-sm font-medium text-main-700"
        >
          {label}
          {required ? <span className="text-danger-500"> *</span> : null}
        </label>
      ) : null}

      {/* Selected badges */}
      {value.length > 0 ? (
        <div className="flex flex-wrap gap-1.5">
          {value.map((kb) => (
            <span
              key={kb.id}
              className="inline-flex items-center gap-1 rounded-md bg-primary-50 px-2 py-1 text-xs font-medium text-primary-700"
            >
              {kb.name}
              <button
                type="button"
                onClick={() => handleRemove(kb.id)}
                disabled={disabled}
                className="rounded hover:text-primary-900 disabled:opacity-50"
                aria-label={`Remove ${kb.name}`}
              >
                <X className="h-3 w-3" />
              </button>
            </span>
          ))}
        </div>
      ) : null}

      {/* Dropdown to add */}
      <select
        id="kb-multi-select"
        value=""
        onChange={(e) => {
          if (e.target.value) handleAdd(e.target.value)
        }}
        disabled={disabled || isLoading || available.length === 0}
        className={cn(
          "w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 disabled:cursor-not-allowed disabled:bg-gray-50 disabled:text-gray-400",
          error ? "border-danger-500" : "",
        )}
      >
        <option value="">
          {isLoading
            ? "Loading..."
            : available.length === 0 && kbs.length === 0
              ? "No knowledge bases — create one first"
              : available.length === 0
                ? "All knowledge bases selected"
                : "Add a knowledge base..."}
        </option>
        {available.map((kb) => (
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

export default KnowledgeBaseMultiSelect
