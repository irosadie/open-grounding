import { PanelCard } from "$/components/panel-card"
import { consoleNavItems } from "$/configs/console"

export default function ConsolePage() {
  const navItems = consoleNavItems.filter((item) => item.href !== "/console")

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold text-gray-900">Overview</h1>
        <p className="mt-1 text-sm text-gray-500">
          Manage documents, ask grounded questions, and monitor platform status
          from here.
        </p>
      </div>

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {navItems.map((item) => {
          const Icon = item.icon
          return (
            <a
              key={item.href}
              href={item.href}
              className="group flex flex-col gap-3 rounded-xl border border-gray-200 bg-white p-5 shadow-xs transition-colors hover:border-primary-200 hover:bg-primary-50"
            >
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary-50 group-hover:bg-primary-100">
                <Icon className="h-5 w-5 text-primary-600" />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-gray-900">
                  {item.label}
                </h3>
                <p className="mt-0.5 text-xs text-gray-500">
                  {item.description}
                </p>
              </div>
              <span className="mt-auto text-xs font-medium text-primary-600 group-hover:underline">
                Open →
              </span>
            </a>
          )
        })}
      </section>

      <PanelCard title="How to Use" noPadding>
        <ol className="flex flex-col divide-y divide-gray-100">
          <li className="flex gap-4 px-6 py-4">
            <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary-100 text-xs font-semibold text-primary-700">
              1
            </span>
            <div>
              <p className="text-sm font-medium text-gray-900">
                Upload documents in Ingestion
              </p>
              <p className="mt-0.5 text-xs text-gray-500">
                Go to <strong>Ingestion</strong>, select a Knowledge Base,
                choose a PDF/Markdown/TXT file, then click{" "}
                <em>Upload &amp; Ingest</em>. Wait until the status changes to{" "}
                <em>Ready</em>.
              </p>
            </div>
          </li>
          <li className="flex gap-4 px-6 py-4">
            <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary-100 text-xs font-semibold text-primary-700">
              2
            </span>
            <div>
              <p className="text-sm font-medium text-gray-900">
                Ask questions in Retrieval
              </p>
              <p className="mt-0.5 text-xs text-gray-500">
                Go to <strong>Retrieval</strong>, select the same Knowledge
                Base, type your question, then click <em>Ask</em>. The answer
                will appear with source citations.
              </p>
            </div>
          </li>
          <li className="flex gap-4 px-6 py-4">
            <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary-100 text-xs font-semibold text-primary-700">
              3
            </span>
            <div>
              <p className="text-sm font-medium text-gray-900">
                Check platform status in Settings
              </p>
              <p className="mt-0.5 text-xs text-gray-500">
                Open <strong>Settings</strong> to verify all components
                (PostgreSQL, Redis, Qdrant, object storage) are{" "}
                <em>available</em> before starting ingestion.
              </p>
            </div>
          </li>
        </ol>
      </PanelCard>
    </div>
  )
}
