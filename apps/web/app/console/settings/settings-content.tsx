"use client"

import { LoadingSpinner } from "$/components/loading-spinner"
import { PanelCard } from "$/components/panel-card"
import { useReadiness } from "$/hooks/transactions/use-system"
import { useTenantContext } from "$/hooks/transactions/use-system"
import { cn } from "$/utils/cn"
import { Activity, ShieldCheck } from "lucide-react"

export function SettingsContent() {
  const readiness = useReadiness()
  const tenant = useTenantContext()

  const isReady = readiness.data?.status === "ready"

  return (
    <div className="flex flex-col gap-6">
      <PanelCard
        title="Platform Readiness"
        description="Dependency health for PostgreSQL, Redis, Qdrant, object storage, and tenant."
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
                  className="flex items-center justify-between rounded-lg border border-gray-200 px-4 py-2"
                >
                  <span className="text-sm font-medium text-gray-900 capitalize">
                    {component.name}
                  </span>
                  <div className="flex items-center gap-2">
                    <span
                      className={cn(
                        "inline-flex h-2.5 w-2.5 rounded-full",
                        component.available
                          ? "bg-success-500"
                          : "bg-danger-500",
                      )}
                    />
                    <span className="text-xs text-gray-500">
                      {component.available
                        ? "available"
                        : (component.detail ?? "unavailable")}
                    </span>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        ) : (
          <p className="text-sm text-gray-500">
            Unable to load readiness report.
          </p>
        )}
      </PanelCard>

      <PanelCard
        title="Tenant Context"
        description="Server-derived tenant, membership, and user identity (read-only)."
      >
        {tenant.isLoading ? (
          <LoadingSpinner />
        ) : tenant.data ? (
          <div className="flex items-start gap-3">
            <ShieldCheck className="mt-0.5 h-5 w-5 text-primary-600" />
            <dl className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <div>
                <dt className="text-xs font-medium text-gray-500">Tenant Id</dt>
                <dd className="mt-0.5 break-all text-sm text-gray-900">
                  {tenant.data.tenantId}
                </dd>
              </div>
              <div>
                <dt className="text-xs font-medium text-gray-500">
                  Membership Id
                </dt>
                <dd className="mt-0.5 break-all text-sm text-gray-900">
                  {tenant.data.membershipId}
                </dd>
              </div>
              <div>
                <dt className="text-xs font-medium text-gray-500">User Id</dt>
                <dd className="mt-0.5 break-all text-sm text-gray-900">
                  {tenant.data.userId}
                </dd>
              </div>
            </dl>
          </div>
        ) : (
          <p className="text-sm text-gray-500">
            Unable to load tenant context.
          </p>
        )}
      </PanelCard>

      <PanelCard
        title="Knowledge Bases & Profiles"
        description="Tenant-scoped knowledge bases and model/index profile metadata (read-only)."
      >
        <div className="rounded-lg bg-gray-50 p-4">
          <p className="text-sm text-gray-600">
            Knowledge base and profile management surfaces depend on catalog
            write endpoints. They are shown read-only until those endpoints are
            available. Use the Ingestion workbench to upload documents into an
            existing knowledge base.
          </p>
        </div>
      </PanelCard>
    </div>
  )
}

export default SettingsContent
