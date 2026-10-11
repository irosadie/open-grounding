import { ConsoleSidebar } from "$/components/console-sidebar"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

vi.mock("next/navigation", () => ({
  usePathname: () => "/console/document",
  useRouter: () => ({
    replace: vi.fn(),
    push: vi.fn(),
    refresh: vi.fn(),
  }),
}))

describe("ConsoleSidebar", () => {
  const renderSidebar = () => {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
      },
    })

    return render(
      <QueryClientProvider client={queryClient}>
        <ConsoleSidebar />
      </QueryClientProvider>,
    )
  }

  it("renders all navigation items", () => {
    renderSidebar()
    expect(screen.getByText("Overview")).toBeTruthy()
    expect(screen.getByText("Documents")).toBeTruthy()
    expect(screen.getByText("Query")).toBeTruthy()
    expect(screen.getByText("Configuration")).toBeTruthy()
  })

  it("marks the active route", () => {
    renderSidebar()
    const activeLink = screen.getByText("Documents").closest("a")
    expect(activeLink?.getAttribute("aria-current")).toBe("page")
  })

  it("does not mark inactive routes as current", () => {
    renderSidebar()
    const inactiveLink = screen.getByText("Query").closest("a")
    expect(inactiveLink?.getAttribute("aria-current")).toBeNull()
  })

  it("renders section group labels", () => {
    renderSidebar()
    expect(screen.getByText("WORKSPACE")).toBeTruthy()
    expect(screen.getByText("SETTINGS")).toBeTruthy()
  })
})
