import { PanelCard } from "$/components/panel-card"
import { consoleNavItems } from "$/configs/console"

export default function ConsolePage() {
  const navItems = consoleNavItems.filter((item) => item.href !== "/console")

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold text-gray-900">Overview</h1>
        <p className="mt-1 text-sm text-gray-500">
          Kelola dokumen, tanya jawab berbasis dokumen, dan pantau status
          platform dari sini.
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
                Buka →
              </span>
            </a>
          )
        })}
      </section>

      <PanelCard title="Cara Pakai" noPadding>
        <ol className="flex flex-col divide-y divide-gray-100">
          <li className="flex gap-4 px-6 py-4">
            <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary-100 text-xs font-semibold text-primary-700">
              1
            </span>
            <div>
              <p className="text-sm font-medium text-gray-900">
                Upload dokumen ke Ingestion
              </p>
              <p className="mt-0.5 text-xs text-gray-500">
                Masuk ke menu <strong>Ingestion</strong>, isi Knowledge Base ID,
                pilih file PDF/Markdown/TXT, lalu klik{" "}
                <em>Upload &amp; Ingest</em>. Tunggu hingga status berubah ke{" "}
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
                Tanya jawab di Retrieval
              </p>
              <p className="mt-0.5 text-xs text-gray-500">
                Masuk ke menu <strong>Retrieval</strong>, masukkan Knowledge
                Base ID yang sama, tulis pertanyaan, lalu klik <em>Ask</em>.
                Jawaban akan muncul dengan kutipan sumber.
              </p>
            </div>
          </li>
          <li className="flex gap-4 px-6 py-4">
            <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary-100 text-xs font-semibold text-primary-700">
              3
            </span>
            <div>
              <p className="text-sm font-medium text-gray-900">
                Cek status platform di Settings
              </p>
              <p className="mt-0.5 text-xs text-gray-500">
                Buka <strong>Settings</strong> untuk memastikan semua komponen
                (PostgreSQL, Redis, Qdrant, object storage) berstatus{" "}
                <em>available</em> sebelum mulai ingestion.
              </p>
            </div>
          </li>
        </ol>
      </PanelCard>
    </div>
  )
}
