import { describe, expect, it } from "vitest"
import { pathVariable } from "./path-variable"

describe("pathVariable", () => {
  it("replaces a single path variable", () => {
    expect(pathVariable("/rag/ingestion/:id", { id: "abc" })).toBe(
      "/rag/ingestion/abc",
    )
  })

  it("replaces named variables", () => {
    expect(
      pathVariable("/rag/ingestion/status/:documentVersionId", {
        documentVersionId: "v-123",
      }),
    ).toBe("/rag/ingestion/status/v-123")
  })

  it("encodes the variable value", () => {
    expect(pathVariable("/rag/:id", { id: "a b/c" })).toBe("/rag/a%20b%2Fc")
  })

  it("leaves the template untouched when a variable is missing", () => {
    expect(pathVariable("/rag/:id", {})).toBe("/rag/:id")
  })
})
