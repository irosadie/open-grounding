"use client"

import { Button } from "$/components/button"
import { EmptyState } from "$/components/empty-state"
import { Input } from "$/components/input"
import { PanelCard } from "$/components/panel-card"
import {
  useCreateKnowledgeBase,
  useDeleteKnowledgeBase,
  useKnowledgeBases,
} from "$/hooks/transactions/use-knowledge-bases"
import { cn } from "$/utils/cn"
import { knowledgeBaseCreateSchema } from "@open-grounding/schemas"
import type { KnowledgeBaseResponseProps } from "@open-grounding/types"
import { Database, ExternalLink, Plus, Trash2 } from "lucide-react"
import Link from "next/link"
import { type ChangeEvent, useState } from "react"

export default function KnowledgeBasesContent() {
  const { data: kbs, isLoading } = useKnowledgeBases()
  const createMutation = useCreateKnowledgeBase()
  const deleteMutation = useDeleteKnowledgeBase()

  const [showForm, setShowForm] = useState(false)
  const [name, setName] = useState("")
  const [slug, setSlug] = useState("")
  const [formError, setFormError] = useState("")
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null)

  const autoSlug = (value: string) =>
    value
      .toLowerCase()
      .trim()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "")

  const handleNameChange = (value: string) => {
    setName(value)
    setSlug(autoSlug(value))
    setFormError("")
  }

  const handleCreate = async () => {
    setFormError("")
    const parsed = knowledgeBaseCreateSchema.safeParse({ name, slug })
    if (!parsed.success) {
      setFormError(parsed.error.issues[0]?.message ?? "Invalid input.")
      return
    }
    try {
      await createMutation.mutateAsync(parsed.data)
      setName("")
      setSlug("")
      setShowForm(false)
    } catch (error) {
      setFormError(
        (error as { message?: string })?.message ??
          "Failed to create knowledge base.",
      )
    }
  }

  const handleDelete = (id: string) => {
    deleteMutation.mutate(id, {
      onSuccess: () => setConfirmDeleteId(null),
    })
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">
            Knowledge Bases
          </h1>
          <p className="mt-1 text-sm text-gray-500">
            Manage knowledge bases for document ingestion and retrieval.
          </p>
        </div>
        <Button
          intent="primary"
          leftIcon={<Plus className="h-4 w-4" />}
          onClick={() => setShowForm((v) => !v)}
        >
          New Knowledge Base
        </Button>
      </div>

      {showForm ? (
        <PanelCard title="Create New Knowledge Base">
          <div className="flex flex-col gap-4">
            <Input
              label="Nama"
              name="name"
              placeholder="e.g. Product Documentation 2024"
              value={name}
              onChange={(e: ChangeEvent<HTMLInputElement>) =>
                handleNameChange(e.target.value)
              }
              required
            />
            <Input
              label="Slug"
              name="slug"
              placeholder="e.g. product-documentation-2024"
              value={slug}
              onChange={(e: ChangeEvent<HTMLInputElement>) => {
                setSlug(e.target.value)
                setFormError("")
              }}
              hint="Lowercase letters, numbers, and hyphens only. Auto-generated from name."
              required
            />
            {formError ? (
              <p className="text-sm text-danger-500">{formError}</p>
            ) : null}
            <div className="flex items-center gap-2">
              <Button
                intent="primary"
                onClick={handleCreate}
                loading={createMutation.isPending}
                disabled={
                  createMutation.isPending || !name.trim() || !slug.trim()
                }
              >
                Save
              </Button>
              <Button
                intent="secondary"
                bordered
                onClick={() => {
                  setShowForm(false)
                  setName("")
                  setSlug("")
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
        title="Knowledge Base List"
        description="Active knowledge bases available for ingestion and retrieval."
      >
        {isLoading ? (
          <div className="py-8 text-center text-sm text-gray-400">
            Loading...
          </div>
        ) : !kbs || kbs.length === 0 ? (
          <EmptyState
            icon={Database}
            title="No knowledge bases yet"
            description="Create your first knowledge base to start uploading documents."
          />
        ) : (
          <ul className="flex flex-col divide-y divide-gray-100">
            {kbs.map((kb: KnowledgeBaseResponseProps) => (
              <li
                key={kb.id}
                className="flex items-center justify-between py-4"
              >
                <div className="min-w-0">
                  <Link
                    href={`/console/knowledge-bases/${kb.id}/planner`}
                    className="hover:underline"
                  >
                    <p className="truncate text-sm font-semibold text-gray-900">
                      {kb.name}
                    </p>
                  </Link>
                  <p className="mt-0.5 text-xs text-gray-500">
                    <span className="font-mono">{kb.slug}</span>
                    {" · "}
                    <span className="font-mono text-gray-400">{kb.id}</span>
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-2 pl-4">
                  <span
                    className={cn(
                      "rounded-full px-2 py-0.5 text-xs font-medium",
                      kb.status === "ACTIVE"
                        ? "bg-success-100 text-success-700"
                        : "bg-gray-100 text-gray-500",
                    )}
                  >
                    {kb.status === "ACTIVE" ? "Active" : kb.status}
                  </span>
                  <Link href={`/console/knowledge-bases/${kb.id}/planner`}>
                    <Button
                      intent="secondary"
                      size="small"
                      bordered
                      leftIcon={<ExternalLink className="h-3.5 w-3.5" />}
                    >
                      Open
                    </Button>
                  </Link>
                  {confirmDeleteId === kb.id ? (
                    <div className="flex items-center gap-1">
                      <Button
                        intent="danger"
                        size="small"
                        onClick={() => handleDelete(kb.id)}
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
                      onClick={() => setConfirmDeleteId(kb.id)}
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
