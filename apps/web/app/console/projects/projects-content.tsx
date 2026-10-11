"use client"

import { Button } from "$/components/button"
import { Input } from "$/components/input"
import { PanelCard } from "$/components/panel-card"
import {
  useCreateProject,
  useProjects,
} from "$/hooks/transactions/use-projects"
import { projectCreateSchema } from "@open-grounding/schemas"
import { Boxes, ExternalLink, Plus } from "lucide-react"
import Link from "next/link"
import { useState } from "react"

export default function ProjectsContent() {
  const { data: projects, isLoading, isError } = useProjects()
  const createMutation = useCreateProject()
  const [showForm, setShowForm] = useState(false)
  const [name, setName] = useState("")
  const [slug, setSlug] = useState("")
  const [error, setError] = useState("")

  const submit = async () => {
    const parsed = projectCreateSchema.safeParse({
      name,
      slug,
      knowledgeBaseIds: [],
    })
    if (!parsed.success) {
      setError(parsed.error.issues[0]?.message ?? "Project tidak valid.")
      return
    }
    try {
      await createMutation.mutateAsync(parsed.data)
      setName("")
      setSlug("")
      setShowForm(false)
      setError("")
    } catch (cause) {
      setError(
        (cause as { message?: string }).message ??
          "Project tidak dapat dibuat.",
      )
    }
  }

  const autoSlug = (value: string) =>
    value
      .toLowerCase()
      .trim()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "")

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Projects</h1>
          <p className="mt-1 text-sm text-gray-500">
            Satu Project dapat memakai banyak Knowledge Base dengan satu policy
            runtime.
          </p>
        </div>
        <Button
          intent="primary"
          leftIcon={<Plus className="h-4 w-4" />}
          onClick={() => setShowForm((value) => !value)}
        >
          New Project
        </Button>
      </div>

      {showForm ? (
        <PanelCard
          title="Create Project"
          description="Project menjadi pemilik Planner, Memory, Answer Policy, dan Guardrails."
        >
          <div className="grid gap-4 sm:grid-cols-2">
            <Input
              label="Name"
              value={name}
              onChange={(event) => {
                setName(event.target.value)
                setSlug(autoSlug(event.target.value))
              }}
            />
            <Input
              label="Slug"
              value={slug}
              onChange={(event) => setSlug(event.target.value)}
              hint="Lowercase kebab-case."
            />
          </div>
          {error ? (
            <p className="mt-3 text-sm text-danger-600">{error}</p>
          ) : null}
          <div className="mt-4 flex gap-2">
            <Button
              intent="primary"
              onClick={() => void submit()}
              loading={createMutation.isPending}
            >
              Create
            </Button>
            <Button
              intent="secondary"
              bordered
              onClick={() => setShowForm(false)}
            >
              Cancel
            </Button>
          </div>
        </PanelCard>
      ) : null}

      {isLoading ? (
        <p className="text-sm text-gray-400">Loading Projects...</p>
      ) : null}
      {isError ? (
        <p className="rounded-lg bg-danger-50 p-4 text-sm text-danger-700">
          Projects tidak dapat dimuat.
        </p>
      ) : null}
      {!isLoading && !isError && !projects?.length ? (
        <PanelCard>
          <div className="py-10 text-center">
            <Boxes className="mx-auto h-10 w-10 text-gray-300" />
            <p className="mt-3 text-sm text-gray-500">Belum ada Project.</p>
          </div>
        </PanelCard>
      ) : null}
      <div className="grid gap-4 md:grid-cols-2">
        {projects?.map((project) => (
          <PanelCard
            key={project.id}
            title={project.name}
            description={project.slug}
            action={
              <Link
                className="text-primary-600"
                href={`/console/projects/${project.id}`}
              >
                <ExternalLink className="h-4 w-4" />
              </Link>
            }
          >
            <div className="flex items-center justify-between text-sm">
              <span className="text-gray-500">Knowledge Bases</span>
              <strong>{project.knowledgeBases.length}</strong>
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              {project.knowledgeBases.slice(0, 4).map((kb) => (
                <span
                  key={kb.id}
                  className="rounded-full bg-gray-100 px-2.5 py-1 text-xs text-gray-600"
                >
                  {kb.name}
                </span>
              ))}
              {project.knowledgeBases.length > 4 ? (
                <span className="text-xs text-gray-400">
                  +{project.knowledgeBases.length - 4} more
                </span>
              ) : null}
            </div>
          </PanelCard>
        ))}
      </div>
    </div>
  )
}
