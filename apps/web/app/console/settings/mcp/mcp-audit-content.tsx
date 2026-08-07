"use client"

import { Button } from "$/components/button"
import { Input } from "$/components/input"
import { PanelCard } from "$/components/panel-card"
import { useMcpInvocations, useMcpServers } from "$/hooks/transactions/use-mcp"
import type { McpInvocationResponse } from "@open-grounding/types"
import { ArrowLeft, Shield } from "lucide-react"
import { useState } from "react"

const statusClasses: Record<McpInvocationResponse["status"], string> = {
  success: "text-success-700 bg-success-100",
  error: "text-danger-700 bg-danger-100",
  timeout: "text-warning-700 bg-warning-100",
  denied: "text-gray-700 bg-gray-100",
}

export default function McpAuditContent() {
  const { data: servers } = useMcpServers()
  const [filters, setFilters] = useState({
    serverId: "",
    status: "",
    userId: "",
  })
  const { data, isLoading } = useMcpInvocations(filters)
  const [selected, setSelected] = useState<McpInvocationResponse | null>(null)
  const update = (key: keyof typeof filters, value: string) =>
    setFilters((current) => ({ ...current, [key]: value }))

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <a
            href="/console/settings/mcp"
            className="mb-3 inline-flex items-center gap-1 text-sm text-primary-600"
          >
            <ArrowLeft className="h-4 w-4" /> MCP servers
          </a>
          <h1 className="text-xl font-semibold text-gray-900">
            Invocation audit
          </h1>
          <p className="mt-1 text-sm text-gray-500">
            Review tool calls without exposing raw arguments. Only the canonical
            argument hash is retained here.
          </p>
        </div>
        <Shield className="h-8 w-8 text-gray-300" />
      </div>
      <PanelCard title="Filters">
        <div className="grid gap-4 sm:grid-cols-3">
          <div className="flex flex-col gap-1.5">
            <label
              htmlFor="audit-server"
              className="text-sm font-medium text-main-700"
            >
              Server
            </label>
            <select
              id="audit-server"
              value={filters.serverId}
              onChange={(event) => update("serverId", event.target.value)}
              className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm"
            >
              <option value="">All servers</option>
              {servers?.map((server) => (
                <option key={server.id} value={server.id}>
                  {server.name}
                </option>
              ))}
            </select>
          </div>
          <div className="flex flex-col gap-1.5">
            <label
              htmlFor="audit-status"
              className="text-sm font-medium text-main-700"
            >
              Status
            </label>
            <select
              id="audit-status"
              value={filters.status}
              onChange={(event) => update("status", event.target.value)}
              className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm"
            >
              <option value="">All statuses</option>
              {["success", "error", "timeout", "denied"].map((status) => (
                <option key={status} value={status}>
                  {status}
                </option>
              ))}
            </select>
          </div>
          <Input
            label="User ID"
            value={filters.userId}
            onChange={(event) => update("userId", event.target.value)}
            placeholder="Filter by user"
          />
        </div>
        <Button
          className="mt-4"
          intent="secondary"
          bordered
          onClick={() => setFilters({ serverId: "", status: "", userId: "" })}
        >
          Clear filters
        </Button>
      </PanelCard>
      <PanelCard title="Recent invocations">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-gray-200 text-xs uppercase text-gray-500">
              <tr>
                <th className="px-3 py-3">Server / tool</th>
                <th className="px-3 py-3">Status</th>
                <th className="px-3 py-3">User</th>
                <th className="px-3 py-3">Duration</th>
                <th className="px-3 py-3">Time</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {isLoading ? (
                <tr>
                  <td className="px-3 py-6 text-gray-400" colSpan={5}>
                    Loading audit entries...
                  </td>
                </tr>
              ) : (
                data?.items.map((invocation) => (
                  <tr
                    key={invocation.id}
                    className="cursor-pointer hover:bg-gray-50"
                    tabIndex={0}
                    onClick={() => setSelected(invocation)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" || event.key === " ")
                        setSelected(invocation)
                    }}
                  >
                    <td className="px-3 py-3">
                      <div className="font-medium text-gray-900">
                        {invocation.serverName ?? invocation.serverId}
                      </div>
                      <div className="font-mono text-xs text-gray-500">
                        {invocation.toolName ?? invocation.toolId}
                      </div>
                    </td>
                    <td className="px-3 py-3">
                      <span
                        className={`rounded-full px-2 py-1 text-xs font-medium ${statusClasses[invocation.status]}`}
                      >
                        {invocation.status}
                      </span>
                    </td>
                    <td className="px-3 py-3 text-gray-600">
                      {invocation.userId}
                    </td>
                    <td className="px-3 py-3 text-gray-600">
                      {invocation.durationMs}ms
                    </td>
                    <td className="px-3 py-3 text-gray-600">
                      {new Date(invocation.createdAt).toLocaleString()}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
          {!isLoading && !data?.items.length ? (
            <p className="py-8 text-center text-sm text-gray-500">
              No invocations match these filters.
            </p>
          ) : null}
        </div>
      </PanelCard>
      {selected ? (
        <PanelCard
          title="Invocation detail"
          action={
            <Button
              size="small"
              intent="secondary"
              bordered
              onClick={() => setSelected(null)}
            >
              Close
            </Button>
          }
        >
          <dl className="grid gap-4 text-sm sm:grid-cols-2">
            <div>
              <dt className="text-gray-500">Argument hash</dt>
              <dd className="mt-1 break-all font-mono text-gray-900">
                {selected.argsHash}
              </dd>
            </div>
            <div>
              <dt className="text-gray-500">Status</dt>
              <dd className="mt-1 text-gray-900">{selected.status}</dd>
            </div>
            <div className="sm:col-span-2">
              <dt className="text-gray-500">Truncated result</dt>
              <dd className="mt-1 whitespace-pre-wrap rounded-lg bg-gray-950 p-4 font-mono text-xs text-gray-100">
                {selected.resultText ?? "No result recorded"}
              </dd>
            </div>
          </dl>
        </PanelCard>
      ) : null}
    </div>
  )
}
