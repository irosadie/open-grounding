import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import HomePage from "./page"

describe("HomePage smoke", () => {
  it("renders the starter landing page", () => {
    render(<HomePage />)

    expect(
      screen.getByText("Blank starter for vibe coding from scratch"),
    ).toBeTruthy()
    expect(screen.getByText("Homepage starter ready to use")).toBeTruthy()
    expect(
      screen.getByText("No demo routes locked in this starter."),
    ).toBeTruthy()
  })
})
