"use client"

import { Button } from "$/components/button"
import { Input } from "$/components/input"
import { PanelCard } from "$/components/panel-card"
import { Textarea } from "$/components/textarea"
import {
  useCreateMcpServer,
  useDeleteMcpServer,
  useMcpServerDiscover,
  useMcpServerTest,
  useMcpServers,
  useMcpToolInvoke,
  useMcpTools,
  useUpdateMcpServer,
  useUpdateMcpTool,
} from "$/hooks/transactions/use-mcp"
import {
  type McpServerSchemaProps,
  getMcpTransportLabel,
  invokeToolSchema,
  mcpAuthTypeLabels,
  mcpServerSchema,
  mcpTransportLabels,
} from "@open-grounding/schemas"
import type { McpServerResponse, McpToolResponse } from "@open-grounding/types"
import { ChevronRight, Plus, RefreshCw, Trash2, Wrench } from "lucide-react"
import { useState } from "react"

const emptyForm: McpServerSchemaProps = {
  name: "",
  transport: "stdio",
  command: "",
  args: [],
  url: "",
  authType: "none",
  credential: "",
  headers: {},
  timeoutSeconds: 30,
  maxPayloadBytes: 1048576,
  allowInsecure: false,
  enabled: true,
}

const statusClasses: Record<McpServerResponse["status"], string> = {
  connected: "bg-success-100 text-success-700",
  error: "bg-danger-100 text-danger-700",
  unknown: "bg-gray-100 text-gray-600",
}

const errorMessage = (error: unknown) =>
  typeof error === "object" && error !== null && "message" in error
    ? String(error.message)
    : "Request failed"

function ServerForm({
  initial,
  isPending,
  onCancel,
  onSubmit,
}: {
  initial: McpServerSchemaProps
  isPending: boolean
  onCancel: () => void
  onSubmit: (payload: McpServerSchemaProps) => Promise<void>
}) {
  const [form, setForm] = useState(initial)
  const [error, setError] = useState("")
  const update = <K extends keyof McpServerSchemaProps>(
    key: K,
    value: McpServerSchemaProps[K],
  ) => setForm((current) => ({ ...current, [key]: value }))

  const submit = async () => {
    const parsed = mcpServerSchema.safeParse(form)
    if (!parsed.success) {
      setError(
        parsed.error.issues[0]?.message ?? "Invalid server configuration",
      )
      return
    }
    try {
      await onSubmit(parsed.data)
    } catch (submitError) {
      setError(errorMessage(submitError))
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <Input
          label="Name"
          value={form.name}
          onChange={(event) => update("name", event.target.value)}
          required
        />
        <div className="flex flex-col gap-1.5">
          <label
            htmlFor="mcp-transport"
            className="text-sm font-medium text-main-700"
          >
            Transport
          </label>
          <select
            id="mcp-transport"
            value={form.transport}
            onChange={(event) =>
              update(
                "transport",
                event.target.value as McpServerSchemaProps["transport"],
              )
            }
            className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm"
          >
            {mcpTransportLabels.map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </select>
        </div>
      </div>
      {form.transport === "stdio" ? (
        <>
          <Input
            label="Command"
            placeholder="/usr/local/bin/my-mcp"
            value={form.command}
            onChange={(event) => update("command", event.target.value)}
            required
          />
          <Input
            label="Arguments"
            hint="Space-separated command arguments"
            value={form.args.join(" ")}
            onChange={(event) =>
              update("args", event.target.value.split(" ").filter(Boolean))
            }
          />
        </>
      ) : (
        <>
          <Input
            label="URL"
            type="url"
            placeholder="https://mcp.example.com/mcp"
            value={form.url}
            onChange={(event) => update("url", event.target.value)}
            required
          />
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="flex flex-col gap-1.5">
              <label
                htmlFor="mcp-auth"
                className="text-sm font-medium text-main-700"
              >
                Authentication
              </label>
              <select
                id="mcp-auth"
                value={form.authType}
                onChange={(event) =>
                  update(
                    "authType",
                    event.target.value as McpServerSchemaProps["authType"],
                  )
                }
                className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm"
              >
                {mcpAuthTypeLabels.map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </select>
            </div>
            {form.authType !== "none" ? (
              <Input
                label="Credential"
                type="password"
                placeholder="Enter a new credential"
                value={form.credential}
                onChange={(event) => update("credential", event.target.value)}
                hint="Never prefilled or returned by the API"
              />
            ) : null}
          </div>
          <label className="flex items-center gap-2 text-sm text-gray-600">
            <input
              type="checkbox"
              checked={form.allowInsecure}
              onChange={(event) =>
                update("allowInsecure", event.target.checked)
              }
            />{" "}
            Allow insecure HTTP
          </label>
        </>
      )}
      <div className="grid gap-4 sm:grid-cols-2">
        <Input
          label="Timeout (seconds)"
          type="number"
          min={1}
          max={120}
          value={String(form.timeoutSeconds)}
          onChange={(event) =>
            update("timeoutSeconds", Number(event.target.value))
          }
        />
        <Input
          label="Max payload (bytes)"
          type="number"
          value={String(form.maxPayloadBytes)}
          onChange={(event) =>
            update("maxPayloadBytes", Number(event.target.value))
          }
        />
      </div>
      <label className="flex items-center gap-2 text-sm text-gray-600">
        <input
          type="checkbox"
          checked={form.enabled}
          onChange={(event) => update("enabled", event.target.checked)}
        />{" "}
        Server enabled
      </label>
      {error ? <p className="text-sm text-danger-500">{error}</p> : null}
      <div className="flex gap-2">
        <Button onClick={submit} loading={isPending}>
          Save server
        </Button>
        <Button intent="secondary" bordered onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </div>
  )
}

function ToolsBrowser({ serverId }: { serverId: string }) {
  const { data: tools, isLoading } = useMcpTools(serverId)
  const updateTool = useUpdateMcpTool()
  const invoke = useMcpToolInvoke()
  const [selected, setSelected] = useState<string | null>(null)
  const [argumentsText, setArgumentsText] = useState("{}")
  const [result, setResult] = useState("")
  const selectedTool = tools?.find((tool) => tool.id === selected)

  const tryTool = async (tool: McpToolResponse) => {
    setSelected(tool.id)
    setArgumentsText(
      JSON.stringify(tool.inputSchema.properties ?? {}, null, 2).replace(
        /: \{[^\n]*/g,
        ": null",
      ),
    )
    setResult("")
  }

  const invokeTool = async () => {
    if (!selectedTool) return
    try {
      const parsed = invokeToolSchema.parse({
        arguments: JSON.parse(argumentsText) as Record<string, unknown>,
      })
      const response = await invoke.mutateAsync({
        id: selectedTool.id,
        payload: parsed,
      })
      setResult(JSON.stringify(response.result, null, 2))
    } catch (error) {
      setResult(errorMessage(error))
    }
  }

  return (
    <PanelCard
      title="Tool browser"
      description="Discovered tools are denied by default until explicitly allowed."
    >
      {isLoading ? (
        <p className="text-sm text-gray-400">Loading tools...</p>
      ) : !tools?.length ? (
        <p className="text-sm text-gray-500">
          No cached tools. Discover tools from the server card.
        </p>
      ) : (
        <div className="flex flex-col gap-3">
          {tools.map((tool) => (
            <div
              key={tool.id}
              className="rounded-lg border border-gray-200 p-4"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <p className="font-mono text-sm font-semibold text-gray-900">
                    {tool.name}
                  </p>
                  <p className="mt-1 text-sm text-gray-500">
                    {tool.description || "No description"}
                  </p>
                  <p className="mt-2 text-xs text-gray-400">
                    {Object.keys(tool.inputSchema.properties ?? {}).length}{" "}
                    argument(s) {tool.isStale ? "· stale" : ""}
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-3">
                  <label className="flex items-center gap-2 text-xs text-gray-600">
                    <input
                      type="checkbox"
                      checked={tool.allowed}
                      onChange={(event) =>
                        updateTool.mutate({
                          id: tool.id,
                          allowed: event.target.checked,
                        })
                      }
                    />{" "}
                    Allowed
                  </label>
                  <Button
                    size="small"
                    intent="secondary"
                    bordered
                    onClick={() => tryTool(tool)}
                    disabled={!tool.allowed}
                  >
                    Try it
                  </Button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
      {selectedTool ? (
        <div className="mt-5 border-t border-gray-100 pt-5">
          <h3 className="text-sm font-semibold text-gray-900">
            Invoke {selectedTool.name}
          </h3>
          <Textarea
            className="mt-3 font-mono text-xs"
            rows={8}
            value={argumentsText}
            onChange={(event) => setArgumentsText(event.target.value)}
            label="Arguments (JSON)"
            hint="Arguments are validated against the tool input schema."
          />
          <Button
            className="mt-3"
            onClick={invokeTool}
            loading={invoke.isPending}
            leftIcon={<Wrench className="h-4 w-4" />}
          >
            Invoke tool
          </Button>
          {result ? (
            <pre className="mt-4 max-h-72 overflow-auto rounded-lg bg-gray-950 p-4 text-xs text-gray-100">
              {result}
            </pre>
          ) : null}
        </div>
      ) : null}
    </PanelCard>
  )
}

export default function McpServersContent() {
  const { data: servers, isLoading } = useMcpServers()
  const create = useCreateMcpServer()
  const update = useUpdateMcpServer()
  const remove = useDeleteMcpServer()
  const test = useMcpServerTest()
  const discover = useMcpServerDiscover()
  const [editing, setEditing] = useState<McpServerResponse | "new" | null>(null)
  const [selectedId, setSelectedId] = useState("")
  const [feedback, setFeedback] = useState<Record<string, string>>({})
  const selectedServer = servers?.find((server) => server.id === selectedId)

  const formFromServer = (server: McpServerResponse): McpServerSchemaProps => ({
    name: server.name,
    transport: server.transport,
    command: server.command ?? "",
    args: server.args,
    url: server.url ?? "",
    authType: server.authType ?? "none",
    credential: "",
    headers: server.headers,
    timeoutSeconds: server.timeoutSeconds,
    maxPayloadBytes: server.maxPayloadBytes,
    allowInsecure: server.allowInsecure,
    enabled: server.enabled,
  })

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">MCP Servers</h1>
          <p className="mt-1 text-sm text-gray-500">
            Connect external tools to your grounded runtime with explicit
            per-tool permissions.
          </p>
        </div>
        <div className="flex gap-2">
          <a
            href="/console/settings/mcp/audit"
            className="rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-700"
          >
            Audit log
          </a>
          <Button
            leftIcon={<Plus className="h-4 w-4" />}
            onClick={() => setEditing("new")}
          >
            Add server
          </Button>
        </div>
      </div>
      {editing ? (
        <PanelCard
          title={
            editing === "new" ? "Register MCP server" : `Edit ${editing.name}`
          }
        >
          <ServerForm
            initial={editing === "new" ? emptyForm : formFromServer(editing)}
            isPending={create.isPending || update.isPending}
            onCancel={() => setEditing(null)}
            onSubmit={async (payload) => {
              if (editing === "new") await create.mutateAsync(payload)
              else await update.mutateAsync({ id: editing.id, payload })
              setEditing(null)
            }}
          />
        </PanelCard>
      ) : null}
      <PanelCard title="Registered servers">
        <div className="flex flex-col divide-y divide-gray-100">
          {isLoading ? (
            <p className="py-6 text-sm text-gray-400">Loading servers...</p>
          ) : !servers?.length ? (
            <p className="py-6 text-sm text-gray-500">
              No MCP servers registered.
            </p>
          ) : (
            servers.map((server) => (
              <div
                key={server.id}
                className="flex flex-wrap items-center justify-between gap-4 py-4"
              >
                <button
                  type="button"
                  className="flex min-w-0 items-center gap-3 text-left"
                  onClick={() => setSelectedId(server.id)}
                >
                  <div className="rounded-lg bg-primary-50 p-2 text-primary-600">
                    <Wrench className="h-5 w-5" />
                  </div>
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-gray-900">
                      {server.name}
                    </p>
                    <p className="text-xs text-gray-500">
                      {getMcpTransportLabel(server.transport)} ·{" "}
                      {server.transport === "stdio"
                        ? server.command
                        : server.url}
                    </p>
                  </div>
                  <span
                    className={`rounded-full px-2 py-1 text-xs font-medium ${statusClasses[server.status]}`}
                  >
                    {server.status}
                  </span>
                </button>
                <div className="flex items-center gap-2">
                  <Button
                    size="small"
                    intent="secondary"
                    bordered
                    onClick={async () => {
                      try {
                        const response = await test.mutateAsync(server.id)
                        setFeedback((current) => ({
                          ...current,
                          [server.id]: `${response.latencyMs}ms · ${response.toolCount} tools`,
                        }))
                      } catch (error) {
                        setFeedback((current) => ({
                          ...current,
                          [server.id]: errorMessage(error),
                        }))
                      }
                    }}
                    loading={test.isPending}
                  >
                    Test
                  </Button>
                  <Button
                    size="small"
                    intent="secondary"
                    bordered
                    onClick={async () => {
                      await discover.mutateAsync(server.id)
                      setSelectedId(server.id)
                    }}
                    loading={discover.isPending}
                    leftIcon={<RefreshCw className="h-3.5 w-3.5" />}
                  >
                    Discover
                  </Button>
                  <Button
                    size="small"
                    intent="secondary"
                    bordered
                    onClick={() => setEditing(server)}
                  >
                    Edit
                  </Button>
                  <Button
                    size="small"
                    intent="danger"
                    bordered
                    onClick={() => remove.mutate(server.id)}
                    leftIcon={<Trash2 className="h-3.5 w-3.5" />}
                  >
                    Delete
                  </Button>
                </div>
                {feedback[server.id] ? (
                  <p className="basis-full text-xs text-gray-500">
                    {feedback[server.id]}
                  </p>
                ) : null}
                {server.lastError ? (
                  <p
                    className="basis-full text-xs text-danger-600"
                    title={server.lastError}
                  >
                    {server.lastError}
                  </p>
                ) : null}
              </div>
            ))
          )}
        </div>
      </PanelCard>
      {selectedServer ? (
        <ToolsBrowser serverId={selectedServer.id} />
      ) : (
        <PanelCard>
          <div className="flex items-center gap-3 text-sm text-gray-500">
            <ChevronRight className="h-4 w-4" /> Select a server to browse its
            cached tools.
          </div>
        </PanelCard>
      )}
    </div>
  )
}
