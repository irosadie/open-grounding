import { PanelCard } from "$/components/panel-card"
import { consoleNavItems } from "$/configs/console"

export default function ConsolePage() {
  return (
    <div className="flex flex-col gap-6">
      <PanelCard
        title="RAG Console"
        description="Upload documents, ask grounded questions, and review platform health."
        noPadding
      >
        <div className="p-6">
          <p className="text-sm text-gray-600">
            Welcome to the RAG console. Use the navigation on the left to manage
            ingestion, retrieve grounded answers, and review platform
            configuration.
          </p>
        </div>
      </PanelCard>

      <section className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {consoleNavItems.map((item) => {
          const Icon = item.icon
          return (
            <a
              key={item.href}
              href={item.href}
              className="group rounded-xl border border-gray-200 bg-white p-5 shadow-xs transition-colors hover:border-primary-200 hover:bg-primary-50"
            >
              <Icon className="h-6 w-6 text-primary-500" />
              <h3 className="mt-3 text-sm font-semibold text-gray-900">
                {item.label}
              </h3>
              <p className="mt-1 text-xs text-gray-500">{item.description}</p>
            </a>
          )
        })}
      </section>
    </div>
  )
}
