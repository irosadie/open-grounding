import { ConsoleSidebar } from "$/components/console-sidebar"
import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

vi.mock("next/navigation", () => ({
  usePathname: () => "/console/ingestion",
  useRouter: () => ({
    replace: vi.fn(),
    push: vi.fn(),
    refresh: vi.fn(),
  }),
}))

describe("ConsoleSidebar", () => {
  it("renders all navigation items", () => {
    render(<ConsoleSidebar />)
    expect(screen.getByText("Overview")).toBeTruthy()
    expect(screen.getByText("Ingestion")).toBeTruthy()
    expect(screen.getByText("Retrieval")).toBeTruthy()
    expect(screen.getByText("Settings")).toBeTruthy()
  })

  it("marks the active route", () => {
    render(<ConsoleSidebar />)
    const activeLink = screen.getByText("Ingestion").closest("a")
    expect(activeLink?.getAttribute("aria-current")).toBe("page")
  })

  it("does not mark inactive routes as current", () => {
    render(<ConsoleSidebar />)
    const inactiveLink = screen.getByText("Retrieval").closest("a")
    expect(inactiveLink?.getAttribute("aria-current")).toBeNull()
  })
})
