"use client"

import { LoadingSpinner } from "$/components/loading-spinner"
import { PanelCard } from "$/components/panel-card"
import { useReadiness } from "$/hooks/transactions/use-system"
import { useTenantContext } from "$/hooks/transactions/use-system"
import { cn } from "$/utils/cn"
import { Activity, Check, Copy, ShieldCheck } from "lucide-react"
import { useState } from "react"

function CopyableId({ label, value }: { label: string; value: string }) {
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    await navigator.clipboard.writeText(value)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div>
      <dt className="text-xs font-medium text-gray-500">{label}</dt>
      <dd className="mt-0.5 flex items-center gap-1.5">
        <span className="break-all text-sm text-gray-900">{value}</span>
        <button
          type="button"
          onClick={handleCopy}
          className="shrink-0 rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
          aria-label={`Copy ${label}`}
        >
          {copied ? (
            <Check className="h-3.5 w-3.5 text-success-600" />
          ) : (
            <Copy className="h-3.5 w-3.5" />
          )}
        </button>
      </dd>
    </div>
  )
}

export function SettingsContent() {
  const readiness = useReadiness()
  const tenant = useTenantContext()

  const isReady = readiness.data?.status === "ready"

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold text-gray-900">Settings</h1>
        <p className="mt-1 text-sm text-gray-500">
          Platform status and tenant information for diagnostics.
        </p>
      </div>

      <PanelCard
        title="Platform Status"
        description="Dependency health: PostgreSQL, Redis, Qdrant, object storage, and tenant."
      >
        {readiness.isLoading ? (
          <LoadingSpinner />
        ) : readiness.data ? (
          <div className="flex flex-col gap-4">
            <div className="flex items-center gap-2">
              <Activity
                className={cn(
                  "h-5 w-5",
                  isReady ? "text-success-600" : "text-warning-600",
                )}
              />
              <span
                className={cn(
                  "rounded-full px-2.5 py-0.5 text-xs font-medium",
                  isReady
                    ? "bg-success-100 text-success-700"
                    : "bg-warning-100 text-warning-700",
                )}
              >
                {isReady ? "Ready" : "Degraded"}
              </span>
              <span className="text-xs text-gray-500">
                RAG {readiness.data.ragEnabled ? "enabled" : "disabled"} ·{" "}
                {readiness.data.ragRuntimeMode}
              </span>
            </div>
            <ul className="flex flex-col gap-2">
              {readiness.data.components.map((component) => (
                <li
                  key={component.name}
                  className="flex items-center justify-between rounded-lg border border-gray-200 px-4 py-2.5"
                >
                  <span className="text-sm font-medium text-gray-900 capitalize">
                    {component.name}
                  </span>
                  <div className="flex items-center gap-2">
                    <span
                      className={cn(
                        "inline-flex h-2 w-2 rounded-full",
                        component.available
                          ? "bg-success-500"
                          : "bg-danger-500",
                      )}
                    />
                    <span
                      className={cn(
                        "text-xs",
                        component.available
                          ? "text-success-700"
                          : "text-danger-600",
                      )}
                    >
                      {component.available
                        ? "Available"
                        : (component.detail ?? "Unavailable")}
                    </span>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        ) : (
          <p className="text-sm text-gray-500">Unable to load status report.</p>
        )}
      </PanelCard>

      <PanelCard
        title="Tenant Information"
        description="Active tenant, membership, and user identity (read-only)."
      >
        {tenant.isLoading ? (
          <LoadingSpinner />
        ) : tenant.data ? (
          <div className="flex items-start gap-3">
            <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-primary-600" />
            <dl className="grid w-full grid-cols-1 gap-4 sm:grid-cols-3">
              <CopyableId label="Tenant ID" value={tenant.data.tenantId} />
              <CopyableId
                label="Membership ID"
                value={tenant.data.membershipId}
              />
              <CopyableId label="User ID" value={tenant.data.userId} />
            </dl>
          </div>
        ) : (
          <p className="text-sm text-gray-500">
            Unable to load tenant information.
          </p>
        )}
      </PanelCard>

      <PanelCard
        title="Knowledge Bases & Profiles"
        description="Tenant knowledge base and model/index profile metadata (read-only)."
      >
        <div className="rounded-lg bg-gray-50 p-4">
          <p className="text-sm text-gray-600">
            Knowledge base and profile management is pending catalog write
            endpoints. For now, use the <strong>Ingestion</strong> page to
            upload documents to an existing knowledge base.
          </p>
        </div>
      </PanelCard>
    </div>
  )
}

export default SettingsContent
