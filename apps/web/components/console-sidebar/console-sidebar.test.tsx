import { ConsoleSidebar } from "$/components/console-sidebar"
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
  it("renders all navigation items", () => {
    render(<ConsoleSidebar />)
    expect(screen.getByText("Overview")).toBeTruthy()
    expect(screen.getByText("Documents")).toBeTruthy()
    expect(screen.getByText("Query")).toBeTruthy()
    expect(screen.getByText("Configuration")).toBeTruthy()
  })

  it("marks the active route", () => {
    render(<ConsoleSidebar />)
    const activeLink = screen.getByText("Documents").closest("a")
    expect(activeLink?.getAttribute("aria-current")).toBe("page")
  })

  it("does not mark inactive routes as current", () => {
    render(<ConsoleSidebar />)
    const inactiveLink = screen.getByText("Query").closest("a")
    expect(inactiveLink?.getAttribute("aria-current")).toBeNull()
  })

  it("renders section group labels", () => {
    render(<ConsoleSidebar />)
    expect(screen.getByText("WORKSPACE")).toBeTruthy()
    expect(screen.getByText("SETTINGS")).toBeTruthy()
  })
})
