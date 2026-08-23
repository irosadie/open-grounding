import { describe, expect, it } from "vitest"
import {
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
