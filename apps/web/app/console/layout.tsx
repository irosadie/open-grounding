import { ConsoleGuard } from "$/components/console-guard"

export default function ConsoleLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return <ConsoleGuard>{children}</ConsoleGuard>
}
