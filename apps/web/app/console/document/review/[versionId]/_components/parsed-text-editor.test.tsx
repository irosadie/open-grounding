import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import {
  ParsedTextEditor,
  normalizeMarkdown,
  updateMarkdownIndentation,
} from "./parsed-text-editor"

describe("normalizeMarkdown", () => {
  it("repairs OCR headings without changing fenced code", () => {
    const markdown = "##SURAT PERNYATAAN\n\n```md\n##keep-raw\n```"

    expect(normalizeMarkdown(markdown)).toBe(
      "## SURAT PERNYATAAN\n\n```md\n##keep-raw\n```",
    )
  })

  it("indents selected markdown lines with Tab", () => {
    expect(updateMarkdownIndentation("one\ntwo", 0, 7)).toEqual({
      value: "  one\n  two",
      selectionStart: 2,
      selectionEnd: 11,
    })
  })

  it("unindents selected markdown lines with Shift+Tab", () => {
    expect(updateMarkdownIndentation("  one\n    two", 0, 13, true)).toEqual({
      value: "one\n  two",
      selectionStart: 0,
      selectionEnd: 9,
    })
  })
})

describe("ParsedTextEditor", () => {
  it("toggles split view and updates the read-only preview from markdown edits", async () => {
    const onChange = vi.fn()

    render(
      <ParsedTextEditor content="# Initial" editable onChange={onChange} />,
    )

    fireEvent.click(screen.getByRole("button", { name: "Enable split view" }))

    const textarea = document.querySelector("textarea") as HTMLTextAreaElement
    expect(textarea.value).toBe("# Initial")
    expect(textarea.hasAttribute("readonly")).toBe(false)

    fireEvent.change(textarea, { target: { value: "# Updated" } })

    expect(onChange).toHaveBeenCalledWith("# Updated")
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Updated" })).toBeTruthy()
    })

    fireEvent.click(screen.getByRole("button", { name: "Exit split view" }))
    expect(document.querySelector("textarea")).toBeNull()
  })

  it("keeps the raw markdown pane read-only when editing is disabled", () => {
    render(
      <ParsedTextEditor
        content="Read-only"
        editable={false}
        onChange={vi.fn()}
      />,
    )

    fireEvent.click(screen.getByRole("button", { name: "Enable split view" }))

    const textarea = document.querySelector("textarea") as HTMLTextAreaElement
    expect(textarea.hasAttribute("readonly")).toBe(true)
  })

  it("exits fullscreen with Escape and restores page scrolling", () => {
    const { container } = render(
      <ParsedTextEditor content="Fullscreen" editable onChange={vi.fn()} />,
    )

    fireEvent.click(screen.getByRole("button", { name: "Enable fullscreen" }))

    expect(container.firstElementChild?.classList.contains("fixed")).toBe(true)
    expect(container.firstElementChild?.classList.contains("inset-0")).toBe(
      true,
    )
    expect(document.body.style.overflow).toBe("hidden")

    fireEvent.keyDown(document, { key: "Escape" })

    expect(container.firstElementChild?.classList.contains("fixed")).toBe(false)
    expect(document.body.style.overflow).toBe("")
  })

  it("preserves split view while entering and leaving fullscreen", () => {
    const { container } = render(
      <ParsedTextEditor content="# Split" editable onChange={vi.fn()} />,
    )

    fireEvent.click(screen.getByRole("button", { name: "Enable split view" }))
    fireEvent.click(screen.getByRole("button", { name: "Enable fullscreen" }))

    expect(container.firstElementChild?.classList.contains("fixed")).toBe(true)
    expect(document.querySelector("textarea")).not.toBeNull()

    fireEvent.keyDown(document, { key: "Escape" })

    expect(container.firstElementChild?.classList.contains("fixed")).toBe(false)
    expect(document.querySelector("textarea")).not.toBeNull()
  })
})
